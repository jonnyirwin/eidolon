"""``ergogen-route`` CLI -- vertical slice: column matrix routing.

Pipeline (slice scope = prompt steps 1-6):

    extract (pcbnew normalise + pad facts)
      -> classify nets
      -> column spines (PCA order + Catmull-Rom)
      -> write F/B copper segments as S-expressions
      -> (optional) render a PNG checkpoint

Rows, vias, thumb transitions, mirroring, MCU/USB/power and DRC are later
milestones with clear extension points already in the model.
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

# Switch footprint(s): the spine threads these pads. The MCU GPIO pad that also
# sits on each column net is a fan-out endpoint handled in a later milestone, so
# it is excluded here to keep the column spine clean.
SWITCH_FOOTPRINTS = {"PG1350"}


def route_columns(board: Board, verbose: bool = False) -> list[str]:
    """Generate column trace segments. Returns S-expression strings."""
    elements: list[str] = []
    for net in sorted(nets_of(board, NetClass.COLUMN), key=lambda n: n.name):
        switch_pads = [p for p in net.pads if p.footprint in SWITCH_FOOTPRINTS]
        deferred = len(net.pads) - len(switch_pads)
        pts = [p.xy for p in switch_pads]
        if len(pts) < 2:
            if verbose:
                print(f"  {net.name}: <2 switch pads, skipped")
            continue
        # Route on the net's dominant copper layer (B.Cu for this board).
        layer = collections.Counter(p.layer for p in switch_pads).most_common(1)[0][0]
        ordered = order_along_axis(pts)
        spine = catmull_rom(ordered, samples_per_segment=8)
        segs = kwrite.polyline(spine, SIGNAL_WIDTH, layer, net.code)
        elements += segs
        if verbose:
            note = f" (+{deferred} MCU pad deferred to fan-out)" if deferred else ""
            print(f"  {net.name}: {len(pts)} switch pads on {layer} -> "
                  f"{len(segs)} segments{note}")
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

        elements = route_columns(board, verbose=args.verbose)
        print(f"routed {len(elements)} column segments")

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
