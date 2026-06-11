"""``ergogen-route`` CLI -- matrix routing (prompt steps 1-7).

Pipeline:

    extract (pcbnew normalise + pad facts)
      -> classify nets
      -> column spines on B.Cu + row spines on F.Cu (PCA order + Catmull-Rom)
      -> write copper segments as S-expressions
      -> (optional) render a PNG checkpoint

Vias, thumb transitions, mirroring, MCU/USB/power and DRC are later milestones
with clear extension points already in the model.
"""
from __future__ import annotations

import argparse
import collections
import math
import os
import subprocess
import sys
import tempfile

from . import kwrite, river
from .classify import classify, nets_of
from .extract import extract
from .geometry import (bezier_transition, catmull_rom, order_along_axis,
                       principal_axis, rotate, unit)
from .model import Board, NetClass

SIGNAL_WIDTH = 0.25  # mm, min signal trace width from the design rules
VIA_DRILL = 0.3      # mm, from the design brief (matrix_transition.drill)
VIA_SIZE = 0.6       # mm, drill + 2 * 0.15 annular ring
MATRIX_DETOUR = 4.75  # mm, south drop (switch local +y) so the matrix-link B.Cu
                      # run rounds the switch body instead of cutting its NPTHs.
                      # Tracks the diode position (LED-cutout centre, +4.70 from
                      # the switch): the via->pad1 leg keeps its original angle
                      # past the diode's pad 2

# Footprints whose pads a matrix spine threads. The MCU GPIO pad that also sits
# on each matrix net is a fan-out endpoint handled in a later milestone, so any
# non-matrix footprint (e.g. xiao_ble) is excluded here to keep the spine clean.
SWITCH_FOOTPRINTS = {"PG1350"}        # columns thread these switch pads (B.Cu)
DIODE_FOOTPRINTS = {"diode_sod123"}   # rows thread these diode pads    (F.Cu)
MCU_FOOTPRINTS = {"xiao_ble"}         # GPIO fan-out endpoints

# The diode's two pads sit on the same row line (matrix pad1 left, row pad2
# right). Routing the row straight through pad2 also runs it over the adjacent
# matrix pad1 + its via -> short. Instead offset the row trace off the pad line
# and drop a perpendicular stub into each row pad, so it clears pad1 and the via.
ROW_OFFSET = 2.0  # mm, perpendicular offset of the row spine off its pad line
                  # (clears the matrix pads even where the row's diodes stagger)
THUMB_BEZIER_STRENGTH = 0.5  # control-point reach for the thumb transition; high
                             # enough that the curve hugs south out of the column
                             # before turning, clearing the bottom key's matrix link

# A switch belongs to the thumb cluster if its per-key matrix-link net carries
# one of these tokens (Ergogen's idiomatic thumb naming). Thumb keys break
# column regularity -- Ergogen splays them at a rotation -- so they are routed as
# a separate spine group joined back to the column by a Bezier (design brief
# step 9). A rotation threshold is the general fallback for boards that don't use
# the naming convention; on the Phantom the token is reliable.
THUMB_LINK_TOKENS = ("_thumb",)


def thumb_switch_refs(board: Board) -> frozenset[str]:
    """Footprint refs of switches whose matrix-link net names them a thumb key."""
    refs: set[str] = set()
    for net in board.nets.values():
        if net.klass is NetClass.MATRIX_LINK and \
                any(tok in net.name for tok in THUMB_LINK_TOKENS):
            refs.update(p.ref for p in net.pads if p.footprint in SWITCH_FOOTPRINTS)
    return frozenset(refs)


def _spine_through(pts, layer, net_code):
    """Order points along their principal axis, spline them, emit segments.
    Returns (ordered_pts, spine_samples, segment_strings)."""
    ordered = order_along_axis(pts)
    spine = catmull_rom(ordered, samples_per_segment=8)
    return ordered, spine, kwrite.curve(spine, SIGNAL_WIDTH, layer, net_code)


def _offset_spine(pts, layer, net_code, offset):
    """Like ``_spine_through`` but routes the spine offset perpendicular to its
    principal axis, with a short perpendicular stub from each pad to the offset
    trace. Keeps the run clear of pads sitting on the pad line (e.g. the row's
    matrix-pad neighbour). Offset is forced to the +y side for a stable result."""
    ordered = order_along_axis(pts)
    ax = principal_axis(ordered)
    perp = (-ax[1], ax[0])
    if perp[1] < 0:                       # force a consistent side (PCA sign is arbitrary)
        perp = (-perp[0], -perp[1])
    off = [(p[0] + perp[0] * offset, p[1] + perp[1] * offset) for p in ordered]
    spine = catmull_rom(off, samples_per_segment=8)
    segs = kwrite.curve(spine, SIGNAL_WIDTH, layer, net_code)
    for p, op in zip(ordered, off):       # perpendicular stub pad -> offset trace
        segs.append(kwrite.segment(p, op, SIGNAL_WIDTH, layer, net_code))
    return ordered, spine, segs


def _exit_tangent(spine, toward) -> tuple:
    """Unit tangent of ``spine`` at whichever end is nearer ``toward``, pointing
    away from the spine. Returns (point, tangent)."""
    head, tail = spine[0], spine[-1]
    if _dist(tail, toward) <= _dist(head, toward):
        return tail, unit((tail[0] - spine[-2][0], tail[1] - spine[-2][1]))
    return head, unit((head[0] - spine[1][0], head[1] - spine[1][1]))


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _thumb_transition(main_spine, thumb_pads, main_rot, layer, net_code):
    """Join a column spine to its thumb group with a Bezier in the thumb's local
    frame, plus the thumb group's own spine. Returns segment strings."""
    tpts = [p.xy for p in thumb_pads]
    centroid = (sum(x for x, _ in tpts) / len(tpts),
                sum(y for _, y in tpts) / len(tpts))
    p0, t0 = _exit_tangent(main_spine, centroid)
    # Arrive heading in the thumb's local frame: the column exit tangent rotated
    # by the thumb's rotation relative to the main keys.
    t1 = unit(rotate(t0, thumb_pads[0].fp_rot - main_rot))
    if len(tpts) >= 2:
        t_ordered, t_spine, t_segs = _spine_through(tpts, layer, net_code)
        p1 = t_ordered[0] if _dist(t_ordered[0], p0) <= _dist(t_ordered[-1], p0) \
            else t_ordered[-1]
    else:
        p1, t_segs = tpts[0], []
    bend = bezier_transition(p0, p1, t0, t1, strength=THUMB_BEZIER_STRENGTH)
    return kwrite.curve(bend, SIGNAL_WIDTH, layer, net_code) + t_segs


def route_spine(board: Board, klass: NetClass, footprints: set[str],
                thumb_refs: frozenset[str] = frozenset(),
                offset: float = 0.0,
                spines: dict | None = None,
                verbose: bool = False) -> list[str]:
    """Thread one smooth spine per net of ``klass`` through its ``footprints``
    pads. Columns and rows are the same problem on different layers; the routing
    layer is read from the pads, never assumed. Switches in ``thumb_refs`` are
    split off into a separate spine group joined back by a Bezier transition.
    ``offset`` (mm) routes the spine offset off the pad line with perpendicular
    stubs (rows, to clear the matrix pad/via). Returns S-expression strings."""
    elements: list[str] = []
    for net in sorted(nets_of(board, klass), key=lambda n: n.name):
        chain_pads = [p for p in net.pads if p.footprint in footprints]
        deferred = len(net.pads) - len(chain_pads)
        main_pads = [p for p in chain_pads if p.ref not in thumb_refs]
        thumb_pads = [p for p in chain_pads if p.ref in thumb_refs]
        if len(main_pads) < 2:
            if verbose:
                print(f"  {net.name}: <2 non-thumb pads, skipped")
            continue
        # Route on the net's dominant copper layer (B.Cu cols, F.Cu rows here).
        layer = collections.Counter(p.layer for p in main_pads).most_common(1)[0][0]
        pad_pts = [p.xy for p in main_pads]
        if offset:
            ordered, spine, segs = _offset_spine(pad_pts, layer, net.code, offset)
        else:
            ordered, spine, segs = _spine_through(pad_pts, layer, net.code)
        elements += segs
        if spines is not None:
            spines[net.name] = (ordered, spine)
        thumb_note = ""
        if thumb_pads:
            main_rot = collections.Counter(
                p.fp_rot for p in main_pads).most_common(1)[0][0]
            tseg = _thumb_transition(spine, thumb_pads, main_rot, layer, net.code)
            elements += tseg
            thumb_note = (f" +{len(thumb_pads)} thumb (Bezier, "
                          f"{thumb_pads[0].fp_rot:g} deg)")
        if verbose:
            note = f" (+{deferred} MCU pad deferred to fan-out)" if deferred else ""
            print(f"  {net.name}: {len(main_pads)} pads on {layer} -> "
                  f"{len(segs)} segments{note}{thumb_note}")
    return elements


def route_matrix_links(board: Board, verbose: bool = False) -> list[str]:
    """Place the per-key transition between each switch pad (B.Cu) and its diode
    pad (F.Cu). Every ``matrix_*`` net spans exactly one pad per layer; we anchor
    a via on the diode (F.Cu) pad -- so it rotates with the footprint for free --
    and run a B.Cu stub from the switch pad to it. Returns S-expression strings.
    """
    elements: list[str] = []
    for net in sorted(nets_of(board, NetClass.MATRIX_LINK), key=lambda n: n.name):
        bcu = [p for p in net.pads if p.layer == "B.Cu"]
        fcu = [p for p in net.pads if p.layer == "F.Cu"]
        if len(bcu) != 1 or len(fcu) != 1:
            if verbose:
                print(f"  {net.name}: {len(bcu)}xB.Cu/{len(fcu)}xF.Cu, "
                      "not a simple 2-pad link, skipped")
            continue
        switch_pad, diode_pad = bcu[0], fcu[0]
        # The straight switch-pad -> diode-pad diagonal cuts through the switch's
        # alignment NPTH, and on the thumb columns the all-B.Cu run is crossed by
        # the column's thumb Bezier (topologically unavoidable on one layer).
        # So: drop south (clear side, switch local frame) to a waypoint, place the
        # via there in open space, and run the long west leg on F.Cu into the
        # diode pad -- leaving only a short B.Cu stub that conflicts with nothing.
        off = rotate((0.0, MATRIX_DETOUR), switch_pad.fp_rot)
        # The south drop has a small horizontal lean from fp_rot. On the mirrored
        # half fp_rot flips sign, so that lean points toward the *outer* board edge
        # -- and the pinky switch pad already sits on that edge, pushing the via
        # over it. The diode is interior on both halves, so steer the lean toward
        # the diode: keeps the left half (lean already diode-ward) untouched.
        if (off[0] > 0) != (diode_pad.x > switch_pad.x):
            off = (-off[0], off[1])
        waypoint = (switch_pad.x + off[0], switch_pad.y + off[1])
        elements.append(kwrite.via(waypoint, VIA_SIZE, VIA_DRILL, net.code))
        elements += kwrite.polyline([switch_pad.xy, waypoint],
                                    SIGNAL_WIDTH, "B.Cu", net.code)
        elements += kwrite.polyline([waypoint, diode_pad.xy],
                                    SIGNAL_WIDTH, "F.Cu", net.code)
        if verbose:
            print(f"  {net.name}: B.Cu stub {switch_pad.ref} -> via -> F.Cu to "
                  f"{diode_pad.ref}")
    return elements


def _mcu_pad(net):
    """The MCU GPIO pad on ``net`` (the fan-out endpoint), or None."""
    for p in net.pads:
        if p.footprint in MCU_FOOTPRINTS:
            return p
    return None


def mcu_fanout_specs(board: Board):
    """Build the grid router's work list: one (name, net_code, start, goal, layer)
    per matrix net, from its MCU GPIO pad to the nearest pad of its own spine."""
    specs = []
    for klass, fps in ((NetClass.COLUMN, SWITCH_FOOTPRINTS),
                       (NetClass.ROW, DIODE_FOOTPRINTS)):
        for net in nets_of(board, klass):
            mp = _mcu_pad(net)
            spine = [p for p in net.pads if p.footprint in fps]
            if mp is None or not spine:
                continue
            tgt = min(spine, key=lambda p: math.hypot(p.x - mp.x, p.y - mp.y))
            specs.append((net.name, net.code, mp.xy, tgt.xy, tgt.layer))
    return specs


def render_checkpoint(pcb_path: str, png_path: str) -> None:
    """Export copper+edge layers to a trimmed PNG for visual validation."""
    from .extract import shift_into_page
    with tempfile.TemporaryDirectory() as td:
        # plot a copy shifted to positive coordinates -- the plotter clips
        # anything off the page, which used to truncate the checkpoint.
        shifted = os.path.join(td, "shifted.kicad_pcb")
        shift_into_page(pcb_path, shifted)
        pdf = os.path.join(td, "board.pdf")
        subprocess.run(
            ["kicad-cli", "pcb", "export", "pdf", "--layers",
             "B.Cu,F.Cu,Edge.Cuts", "-o", pdf, shifted],
            check=True, capture_output=True,
        )
        raw = os.path.join(td, "raw.png")
        subprocess.run(["pdftoppm", "-png", "-r", "200", "-singlefile", pdf,
                        raw[:-4]], check=True, capture_output=True)
        subprocess.run(["convert", raw, "-trim", "+repage", "-bordercolor",
                        "white", "-border", "20", png_path], check=True,
                       capture_output=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ergogen-route")
    ap.add_argument("pcb", help="unrouted .kicad_pcb from Ergogen")
    ap.add_argument("-o", "--output", required=True, help="routed .kicad_pcb out")
    ap.add_argument("--render", metavar="PNG", help="also write a checkpoint PNG")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="parse, classify and plan but do not write output")
    ap.add_argument("--matrix-only", action="store_true",
                    help="route only the switch matrix (skip the MCU fan-out "
                         "river and power rails)")
    ap.add_argument("--no-pour", action="store_true",
                    help="skip the filled GND pours (F.Cu + B.Cu, with a "
                         "copper keepout under the XIAO module)")
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory() as td:
        norm = os.path.join(td, "norm.kicad_pcb")
        pads = os.path.join(td, "pads.json")
        extract(args.pcb, norm, pads)
        board = classify(Board.from_json(pads))

        if args.verbose:
            counts = collections.Counter(n.klass.value for n in board.nets.values())
            print("net classes:", dict(counts))

        thumbs = thumb_switch_refs(board)
        spines: dict = {}
        if args.verbose:
            print(f"columns (thumb keys: {sorted(thumbs) or 'none'}):")
        elements = route_spine(board, NetClass.COLUMN, SWITCH_FOOTPRINTS,
                               thumb_refs=thumbs, spines=spines,
                               verbose=args.verbose)
        if args.verbose:
            print("rows:")
        elements += route_spine(board, NetClass.ROW, DIODE_FOOTPRINTS,
                                offset=ROW_OFFSET, spines=spines,
                                verbose=args.verbose)
        if args.verbose:
            print("matrix links:")
        elements += route_matrix_links(board, verbose=args.verbose)
        if not args.matrix_only:
            outline = river.Outline(board.edge)
            if args.verbose:
                print("column river (B.Cu lanes along the north edge):")
            elements += river.route_column_river(board, outline,
                                                 verbose=args.verbose)
            if args.verbose:
                print("near rows:")
            elements += river.route_near_rows(board, verbose=args.verbose)
            if args.verbose:
                print("boxed rows (B.Cu under the MCU):")
            elements += river.route_boxed_rows(board, outline, spines,
                                               verbose=args.verbose)
            if args.verbose:
                print("power:")
            elements += river.route_power(board, outline, verbose=args.verbose)
        print(f"routed {len(elements)} elements")

        if args.dry_run:
            return 0

        routed = kwrite.splice(open(norm).read(), elements)
        with open(args.output, "w") as fh:
            fh.write(routed)
        print(f"wrote {args.output}")

    if not args.matrix_only and not args.no_pour:
        from .extract import add_gnd_pours
        add_gnd_pours(args.output)
        print("filled GND pours (F.Cu + B.Cu, MCU keepout)")

    if args.render:
        render_checkpoint(args.output, args.render)
        print(f"rendered {args.render}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
