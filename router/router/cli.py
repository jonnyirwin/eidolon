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
import os
import subprocess
import sys
import tempfile

from . import kwrite
from .classify import classify, nets_of
from .extract import extract
from .geometry import catmull_rom, order_along_axis
from .model import Board, NetClass

SIGNAL_WIDTH = 0.25  # mm, min signal trace width from the design rules
VIA_DRILL = 0.3      # mm, from the design brief (matrix_transition.drill)
VIA_SIZE = 0.6       # mm, drill + 2 * 0.15 annular ring

# Footprints whose pads a matrix spine threads. The MCU GPIO pad that also sits
# on each matrix net is a fan-out endpoint handled in a later milestone, so any
# non-matrix footprint (e.g. xiao_ble) is excluded here to keep the spine clean.
SWITCH_FOOTPRINTS = {"PG1350"}        # columns thread these switch pads (B.Cu)
DIODE_FOOTPRINTS = {"diode_sod123"}   # rows thread these diode pads    (F.Cu)


def route_spine(board: Board, klass: NetClass, footprints: set[str],
                verbose: bool = False) -> list[str]:
    """Thread one smooth spine per net of ``klass`` through its ``footprints``
    pads. Columns and rows are the same problem on different layers; the routing
    layer is read from the pads, never assumed. Returns S-expression strings."""
    elements: list[str] = []
    for net in sorted(nets_of(board, klass), key=lambda n: n.name):
        chain_pads = [p for p in net.pads if p.footprint in footprints]
        deferred = len(net.pads) - len(chain_pads)
        pts = [p.xy for p in chain_pads]
        if len(pts) < 2:
            if verbose:
                print(f"  {net.name}: <2 matrix pads, skipped")
            continue
        # Route on the net's dominant copper layer (B.Cu cols, F.Cu rows here).
        layer = collections.Counter(p.layer for p in chain_pads).most_common(1)[0][0]
        ordered = order_along_axis(pts)
        spine = catmull_rom(ordered, samples_per_segment=8)
        segs = kwrite.polyline(spine, SIGNAL_WIDTH, layer, net.code)
        elements += segs
        if verbose:
            note = f" (+{deferred} MCU pad deferred to fan-out)" if deferred else ""
            print(f"  {net.name}: {len(pts)} pads on {layer} -> "
                  f"{len(segs)} segments{note}")
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
        elements.append(kwrite.via(diode_pad.xy, VIA_SIZE, VIA_DRILL, net.code))
        if switch_pad.xy != diode_pad.xy:
            elements.append(kwrite.segment(switch_pad.xy, diode_pad.xy,
                                           SIGNAL_WIDTH, "B.Cu", net.code))
        if verbose:
            print(f"  {net.name}: via @ {diode_pad.ref} + B.Cu stub from "
                  f"{switch_pad.ref}")
    return elements


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
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory() as td:
        norm = os.path.join(td, "norm.kicad_pcb")
        pads = os.path.join(td, "pads.json")
        extract(args.pcb, norm, pads)
        board = classify(Board.from_json(pads))

        if args.verbose:
            counts = collections.Counter(n.klass.value for n in board.nets.values())
            print("net classes:", dict(counts))

        if args.verbose:
            print("columns:")
        elements = route_spine(board, NetClass.COLUMN, SWITCH_FOOTPRINTS,
                               verbose=args.verbose)
        if args.verbose:
            print("rows:")
        elements += route_spine(board, NetClass.ROW, DIODE_FOOTPRINTS,
                                verbose=args.verbose)
        if args.verbose:
            print("matrix links:")
        elements += route_matrix_links(board, verbose=args.verbose)
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
