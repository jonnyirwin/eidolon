"""Fact extraction + format normalisation via KiCad's ``pcbnew``.

This is the *only* module that touches the KiCad scripting API. Its job is to:

1. Load the (possibly ancient, KiCad 5.1.6) ``.kicad_pcb`` Ergogen emits.
2. Save a normalised copy in the modern (KiCad 9) file format -- the
   ``pcbnew`` round-trip is the only headless way to upgrade the format, since
   ``kicad-cli pcb`` has no ``upgrade`` verb.
3. Dump every pad's *absolute* position, net, layer and parent footprint to a
   plain JSON sidecar.

Everything downstream (classification, spines, trace writing) consumes the JSON
and the normalised text file -- never ``pcbnew``. That keeps the routing logic
pure Python and free of KiCad's coordinate-sign subtleties: we ask ``pcbnew``
for `GetPosition()` rather than re-deriving footprint rotation maths ourselves.

Run *with KiCad's python* (it bundles ``pcbnew``)::

    python3 -m router.extract input.kicad_pcb -o normalised.kicad_pcb -j pads.json
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict


# KiCad internal units are nanometres; board files are in millimetres.
NM_PER_MM = 1_000_000.0


@dataclass
class PadFact:
    ref: str          # parent footprint reference (e.g. "S1", "D1")
    footprint: str     # footprint library name (e.g. "PG1350", "diode_sod123")
    pad: str           # pad name/number within the footprint ("1", "2", ...)
    net: str           # net name ("C2", "matrix_middle_bottom", ...)
    net_code: int      # KiCad numeric net id
    layer: str         # primary copper layer ("F.Cu" / "B.Cu")
    cu_layers: list[str]  # all copper layers (>1 => through-hole)
    x: float           # absolute x in mm
    y: float           # absolute y in mm
    sx: float          # pad size x in mm
    sy: float          # pad size y in mm
    fp_x: float        # parent footprint origin x in mm
    fp_y: float        # parent footprint origin y in mm
    fp_rot: float      # parent footprint rotation in degrees


def extract(in_path: str, out_pcb: str, out_json: str) -> dict:
    import pcbnew  # imported lazily so the rest of the package needs no pcbnew

    board = pcbnew.LoadBoard(in_path)

    # 1+2: normalise the format by saving through the modern writer.
    pcbnew.SaveBoard(out_pcb, board)

    # 3: dump pad facts.
    pads: list[PadFact] = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        name = str(fp.GetFPID().GetLibItemName())
        fpos = fp.GetPosition()
        for pad in fp.Pads():
            net = pad.GetNet()
            netname = net.GetNetname() if net else ""
            # Skip pads with no net -- mounting holes, alignment pads, etc.
            if not netname:
                continue
            pos = pad.GetPosition()
            # GetLayer() is unreliable for SMD pads (returns F.Cu regardless);
            # the copper layer set is authoritative. This is what reveals the
            # board's real topology: switch pads on B.Cu, diode pads on F.Cu.
            cu_layers = [pcbnew.LayerName(l) for l in pad.GetLayerSet().CuStack()]
            layer = cu_layers[0] if cu_layers else "F.Cu"
            pads.append(PadFact(
                ref=ref,
                footprint=name,
                pad=pad.GetName(),
                net=netname,
                net_code=net.GetNetCode() if net else 0,
                layer=layer,
                cu_layers=cu_layers,
                x=pos.x / NM_PER_MM,
                y=pos.y / NM_PER_MM,
                sx=pad.GetSize().x / NM_PER_MM,
                sy=pad.GetSize().y / NM_PER_MM,
                fp_x=fpos.x / NM_PER_MM,
                fp_y=fpos.y / NM_PER_MM,
                fp_rot=fp.GetOrientationDegrees(),
            ))

    # No-net mechanical drills (choc poles + stabiliser holes, mounting holes).
    # These are skipped above (no net) but are hard obstacles for the fan-out
    # router -- a trace over a 3.4mm choc pole shorts nothing but fails DRC.
    holes = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                pos = pad.GetPosition()
                holes.append({
                    "x": pos.x / NM_PER_MM,
                    "y": pos.y / NM_PER_MM,
                    "d": pad.GetDrillSize().x / NM_PER_MM,
                })

    # Edge.Cuts geometry, arcs sampled to short chords, for the router's keep-out
    # band along the board outline.
    edge = []
    for d in board.GetDrawings():
        if d.GetLayerName() != "Edge.Cuts":
            continue
        if d.GetShape() == pcbnew.SHAPE_T_ARC:
            cx = d.GetCenter().x / NM_PER_MM
            cy = d.GetCenter().y / NM_PER_MM
            r = d.GetRadius() / NM_PER_MM
            import math
            a0 = math.atan2(d.GetStart().y / NM_PER_MM - cy,
                            d.GetStart().x / NM_PER_MM - cx)
            sweep = d.GetArcAngle().AsDegrees() * math.pi / 180.0
            steps = max(2, int(abs(sweep) / 0.2))
            pts = [(cx + r * math.cos(a0 + sweep * k / steps),
                    cy + r * math.sin(a0 + sweep * k / steps))
                   for k in range(steps + 1)]
            edge += list(zip(pts, pts[1:]))
        else:
            edge.append(((d.GetStart().x / NM_PER_MM, d.GetStart().y / NM_PER_MM),
                         (d.GetEnd().x / NM_PER_MM, d.GetEnd().y / NM_PER_MM)))

    bbox = board.GetBoardEdgesBoundingBox()
    data = {
        "source": in_path,
        "normalised_pcb": out_pcb,
        "board_bbox_mm": {
            "x": bbox.GetX() / NM_PER_MM,
            "y": bbox.GetY() / NM_PER_MM,
            "w": bbox.GetWidth() / NM_PER_MM,
            "h": bbox.GetHeight() / NM_PER_MM,
        },
        "pads": [asdict(p) for p in pads],
        "holes": holes,
        "edge": edge,
    }
    with open(out_json, "w") as fh:
        json.dump(data, fh, indent=1)
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract pad facts + normalise a .kicad_pcb")
    ap.add_argument("input")
    ap.add_argument("-o", "--out-pcb", required=True)
    ap.add_argument("-j", "--out-json", required=True)
    args = ap.parse_args()
    data = extract(args.input, args.out_pcb, args.out_json)
    print(f"extracted {len(data['pads'])} pads -> {args.out_json}")
    print(f"normalised pcb -> {args.out_pcb}")


if __name__ == "__main__":
    main()
