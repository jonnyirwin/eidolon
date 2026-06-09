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

from . import fanout, kwrite
from .classify import classify, nets_of
from .extract import extract
from .geometry import (bezier_transition, catmull_rom, order_along_axis,
                       principal_axis, rotate, unit)
from .model import Board, NetClass

SIGNAL_WIDTH = 0.25  # mm, min signal trace width from the design rules
VIA_DRILL = 0.3      # mm, from the design brief (matrix_transition.drill)
VIA_SIZE = 0.6       # mm, drill + 2 * 0.15 annular ring
MATRIX_DETOUR = 6.0  # mm, south drop (switch local +y) so the matrix-link B.Cu
                     # run rounds the switch body instead of cutting its NPTHs

# Footprints whose pads a matrix spine threads. The MCU GPIO pad that also sits
# on each matrix net is a fan-out endpoint handled in a later milestone, so any
# non-matrix footprint (e.g. xiao_ble) is excluded here to keep the spine clean.
SWITCH_FOOTPRINTS = {"PG1350"}        # columns thread these switch pads (B.Cu)
DIODE_FOOTPRINTS = {"diode_sod123"}   # rows thread these diode pads    (F.Cu)
MCU_FOOTPRINTS = {"xiao_ble"}         # GPIO fan-out endpoints

# MCU fan-out (step 11). The MCU GPIO pads are stacked F.Cu; the columns they feed
# spread across the board on B.Cu, the rows on F.Cu. Columns can't cross the matrix
# body on either layer (both occupied by spines), so they run as parallel "river"
# lanes through the clear north margin -- the lane order matches the stacked-pad
# order, so they never cross -- then drop a via to B.Cu over each column's own x.
FANOUT_BASE_GAP = 2.0      # innermost lane's vertical gap north of the top-key line
                           # (clears the 3.4mm choc body NPTHs sitting at pad height)
FANOUT_LANE_PITCH = 0.5    # centre spacing between lanes (>0.45 = 0.25 trace + 0.2
                           # copper clearance)
FANOUT_TURN_GAP = 8.0      # how far past the MCU (toward the matrix) the diagonal
                           # breakout bundles the stacked pads into the lanes
FANOUT_ESCAPE_NEAR = 1.5   # first escape step west of the MCU pad column
FANOUT_ESCAPE_STEP = 0.6   # extra escape per lane so risers clear the pad stack
FANOUT_VIA_DROP = 0.5      # peel south of the trunk before the via, so the via sits
                           # clear of the outer lanes still passing overhead

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
            _, spine, segs = _offset_spine(pad_pts, layer, net.code, offset)
        else:
            _, spine, segs = _spine_through(pad_pts, layer, net.code)
        elements += segs
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


def _contour_y(contour, x):
    """Linear interpolation of the top-key contour ``[(x,y),...]`` (sorted by x) at
    ``x``, held constant (clamped) outside the key span."""
    if x <= contour[0][0]:
        return contour[0][1]
    if x >= contour[-1][0]:
        return contour[-1][1]
    for (x0, y0), (x1, y1) in zip(contour, contour[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return contour[-1][1]


def route_column_fanout(board: Board, verbose: bool = False) -> list[str]:
    """River-delta fan-out for the column nets. Each column's MCU GPIO pad (F.Cu)
    breaks out diagonally into a lane that follows the top-key contour (hugging just
    inside the rounded north edge, not a flat band), runs to the column's x, then
    drops a via to B.Cu and joins the column's north (top) switch pad.

    The lane offset converges: it starts outermost at the MCU (matching the stacked
    pad order, so the breakout is planar -- no crossings) and steps inward by one
    pitch each time an inner lane peels off, so the far columns ride low enough to
    clear the edge where the contour pinches against the rounded north corner. The
    lanes are straight chords between key samples (no arc fitting, which would bow
    the sparse samples into neighbours).
    """
    cols = []
    for net in nets_of(board, NetClass.COLUMN):
        mp = _mcu_pad(net)
        sw = [p for p in net.pads if p.footprint in SWITCH_FOOTPRINTS]
        if mp is None or not sw:
            continue
        cols.append((net, mp, min(sw, key=lambda p: p.y)))  # top = north open end
    if not cols:
        return []
    cols.sort(key=lambda c: c[1].y)            # MCU pads north -> south
    n = len(cols)
    contour = sorted((top.x, top.y) for _, _, top in cols)
    mcu_x = cols[0][1].x
    dir_x = 1.0 if cols[0][2].x > mcu_x else -1.0   # toward the matrix
    bundle_x = mcu_x + dir_x * FANOUT_TURN_GAP
    peel_dist = lambda x: abs(x - mcu_x)            # farther = peels later
    key_xs = [cx for cx, _ in contour]
    elements: list[str] = []
    for i, (net, mp, top) in enumerate(cols):
        # the lane keeps a fixed pitch from its neighbours but the whole bundle steps
        # inward by one pitch each time an inner lane peels: offset = base + pitch *
        # (lanes still overhead that peel before this one). So lanes stay parallel
        # (no pinching) yet the far columns ride low enough to clear the pinched
        # edge, and at the breakout every lane sits at its full outer offset (planar,
        # no crossings). Sampled only at key x's -> straight chords, no arc bowing.
        my_d = peel_dist(top.x)
        xs = [bundle_x] + [kx for kx in key_xs if min(bundle_x, top.x) < kx
                           < max(bundle_x, top.x)] + [top.x]
        xs.sort(key=peel_dist)                      # bundle (near) -> peel (far)
        lane = []
        for x in xs:
            rank = sum(1 for _, _, t in cols
                       if peel_dist(x) <= peel_dist(t.x) < my_d)
            off = FANOUT_BASE_GAP + FANOUT_LANE_PITCH * rank
            lane.append((x, _contour_y(contour, x) - off))
        # escape west of the stacked MCU pads (farther for the steeper, southern
        # pads) before diagonalling up to the lane, so no riser grazes a pad.
        escape = (mp.x + dir_x * (FANOUT_ESCAPE_NEAR + i * FANOUT_ESCAPE_STEP), mp.y)
        # peel south off the trunk to a via that clears the outer lanes overhead.
        via_pt = (top.x, top.y - FANOUT_VIA_DROP)
        elements += kwrite.polyline([mp.xy, escape] + lane + [via_pt],
                                    SIGNAL_WIDTH, "F.Cu", net.code)
        elements.append(kwrite.via(via_pt, VIA_SIZE, VIA_DRILL, net.code))
        elements += kwrite.polyline([via_pt, top.xy], SIGNAL_WIDTH, "B.Cu",
                                    net.code)
        if verbose:
            print(f"  {net.name}: MCU pad -> escape -> converging lane {i} "
                  f"-> via@({via_pt[0]:.1f},{via_pt[1]:.1f}) -> {top.ref}")
    return elements


def route_row_fanout(board: Board, verbose: bool = False) -> list[str]:
    """Fan the row nets out to the MCU GPIO pads. Rows and the MCU pads are both on
    F.Cu, so each is a single same-layer trace -- no via.

    The MCU pads sit in two stacks. The near stack (same side as the matrix) escapes
    horizontally clear of the pad column, rises/drops to the row's height, then runs
    in to the open (nearest) diode end. The far stack is boxed behind the MCU body,
    so it escapes to the board's east margin and runs down it to the row height --
    a longer detour that still avoids the body."""
    rows = []
    for net in nets_of(board, NetClass.ROW):
        mp = _mcu_pad(net)
        diodes = [p for p in net.pads if p.footprint in DIODE_FOOTPRINTS]
        if mp is None or not diodes:
            continue
        attach = min(diodes, key=lambda p: math.hypot(p.x - mp.x, p.y - mp.y))
        rows.append((net, mp, attach))
    if not rows:
        return []
    matrix_x = sorted(a.x for _, _, a in rows)[len(rows) // 2]
    stack_xs = sorted({round(mp.x, 1) for _, mp, _ in rows})
    near_x = min(stack_xs, key=lambda sx: abs(sx - matrix_x))
    # Only the near stack (same side as the matrix) has a clean exit. The far stack
    # is boxed behind the MCU body, and its east-margin detour runs straight into
    # the power switch -- that needs the MCU-region router (step 11 part 2), so we
    # skip it here rather than emit a colliding trace.
    near = [(net, mp, a) for net, mp, a in rows if round(mp.x, 1) == near_x]
    # stagger the escape so the risers don't collide: the row reaching farthest
    # turns nearest the pad column, the next one turns farther out, etc.
    near.sort(key=lambda r: -abs(r[2].x - r[1].x))
    elements: list[str] = []
    for k, (net, mp, attach) in enumerate(near):
        toward = 1.0 if attach.x > mp.x else -1.0          # matrix direction
        turn_x = mp.x + toward * (FANOUT_ESCAPE_NEAR + k * FANOUT_ESCAPE_STEP)
        path = [mp.xy, (turn_x, mp.y), (turn_x, attach.y), attach.xy]
        elements += kwrite.polyline(path, SIGNAL_WIDTH, "F.Cu", net.code)
        if verbose:
            print(f"  {net.name}: MCU pad (near) -> {attach.ref} "
                  f"({attach.x:.1f},{attach.y:.1f})")
    skipped = [net.name for net, mp, _ in rows if round(mp.x, 1) != near_x]
    if verbose and skipped:
        print(f"  deferred (boxed far stack, need MCU-region router): {skipped}")
    return elements


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
    with tempfile.TemporaryDirectory() as td:
        pdf = os.path.join(td, "board.pdf")
        subprocess.run(
            ["kicad-cli", "pcb", "export", "pdf", "--layers",
             "B.Cu,F.Cu,Edge.Cuts", "-o", pdf, pcb_path],
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
    ap.add_argument("--mcu-fanout", action="store_true",
                    help="(WIP, step 11) also fan the columns out to the MCU GPIO "
                         "pads; connects C0-C4 but not yet DRC-clean through the "
                         "hole-dense, edge-pinched north corridor")
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
        if args.verbose:
            print(f"columns (thumb keys: {sorted(thumbs) or 'none'}):")
        elements = route_spine(board, NetClass.COLUMN, SWITCH_FOOTPRINTS,
                               thumb_refs=thumbs, verbose=args.verbose)
        if args.verbose:
            print("rows:")
        elements += route_spine(board, NetClass.ROW, DIODE_FOOTPRINTS,
                                offset=ROW_OFFSET, verbose=args.verbose)
        if args.verbose:
            print("matrix links:")
        elements += route_matrix_links(board, verbose=args.verbose)
        if args.mcu_fanout:
            if args.verbose:
                print("MCU fan-out (grid A*):")
            specs = mcu_fanout_specs(board)
            fan, unrouted = fanout.route(board, elements, specs,
                                         verbose=args.verbose)
            elements += fan
            if unrouted:
                print(f"fan-out: {len(unrouted)} net(s) unrouted: {unrouted}")
        print(f"routed {len(elements)} matrix elements")

        if args.dry_run:
            return 0

        routed = kwrite.splice(open(norm).read(), elements)
        with open(args.output, "w") as fh:
            fh.write(routed)
        print(f"wrote {args.output}")

    if args.render:
        render_checkpoint(args.output, args.render)
        print(f"rendered {args.render}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
