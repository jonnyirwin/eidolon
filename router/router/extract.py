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
import math
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
    x: float           # absolute x in mm (pad origin = drill centre for PTH)
    y: float           # absolute y in mm
    cx: float          # copper centre x in mm (offset pads: oval shifted off
    cy: float          # the drill, e.g. the XIAO's castellated pads)
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
            # the copper shape can sit offset from the pad origin (the XIAO's
            # castellated ovals put the drill at one end) -- obstacle maths
            # must use the copper centre, connections the origin.
            import math as _math
            offv = pad.GetOffset()
            rot = _math.radians(pad.GetOrientationDegrees())
            ox = offv.x / NM_PER_MM
            oy = offv.y / NM_PER_MM
            cx = pos.x / NM_PER_MM + ox * _math.cos(rot) - oy * _math.sin(rot)
            cy = pos.y / NM_PER_MM + ox * _math.sin(rot) + oy * _math.cos(rot)
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
                cx=cx,
                cy=cy,
                sx=pad.GetSize().x / NM_PER_MM,
                sy=pad.GetSize().y / NM_PER_MM,
                fp_x=fpos.x / NM_PER_MM,
                fp_y=fpos.y / NM_PER_MM,
                fp_rot=fp.GetOrientationDegrees(),
            ))

    # No-net mechanical drills (choc poles + stabiliser holes, mounting holes).
    # These are skipped above (no net) but are hard obstacles for the fan-out
    # router -- a trace over a 3.4mm choc pole shorts nothing but fails DRC.
    # No-net *plated* pads (e.g. the XIAO's RESET/SWCLK bottom pads) are copper
    # obstacles on every layer; export them separately as keepouts.
    holes = []
    keepouts = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                pos = pad.GetPosition()
                holes.append({
                    "x": pos.x / NM_PER_MM,
                    "y": pos.y / NM_PER_MM,
                    "d": pad.GetDrillSize().x / NM_PER_MM,
                })
            elif not (pad.GetNet() and pad.GetNet().GetNetname()):
                pos = pad.GetPosition()
                keepouts.append({
                    "ref": fp.GetReference(),
                    "pad": pad.GetName(),
                    "x": pos.x / NM_PER_MM,
                    "y": pos.y / NM_PER_MM,
                    "sx": pad.GetSize().x / NM_PER_MM,
                    "sy": pad.GetSize().y / NM_PER_MM,
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
        "keepouts": keepouts,
        "edge": edge,
    }
    with open(out_json, "w") as fh:
        json.dump(data, fh, indent=1)
    return data


def add_gnd_pours(pcb_path: str) -> None:
    """Add filled GND pours (F.Cu + B.Cu) to a routed board, with a copper-pour
    keepout under the XIAO module (best practice: no fill under the MCU -- the
    nRF52840 antenna wants clear board; Seeed's guidance. Tracks stay allowed).

    Zone settings follow the project's manual-pour recipe: 0.508 clearance,
    0.254 min width, thermal reliefs 0.508/0.508, islands removed."""
    import pcbnew

    # JLCPCB wants >=0.3 mm copper-to-NPTH; the fill hugs holes at the board
    # hole-clearance rule (0.25 from ergogen), so raise it before filling.
    # The routed copper's tightest hole approach is 0.315, so DRC still passes.
    # The filler's DRC engine compiles rules at LOAD time, so the new value
    # must take a save/reload round-trip before filling.
    board = pcbnew.LoadBoard(pcb_path)
    board.GetDesignSettings().m_HoleClearance = int(0.3 * NM_PER_MM)
    pcbnew.SaveBoard(pcb_path, board)
    board = pcbnew.LoadBoard(pcb_path)
    gnd = board.GetNetcodeFromNetname("GND")
    if gnd <= 0:
        raise ValueError("no GND net on board")

    # keepout rule area under the MCU module (full body + 0.75 mm margin)
    mcu = next((fp for fp in board.GetFootprints()
                if str(fp.GetFPID().GetLibItemName()) == "xiao_ble"), None)
    if mcu is not None:
        pos = mcu.GetPosition()
        rot = math.radians(mcu.GetOrientationDegrees())
        hw, hl = 9.5, 11.25            # module 17.5 x 21 plus margin, halves
        ka = pcbnew.ZONE(board)
        ka.SetIsRuleArea(True)
        ka.SetDoNotAllowCopperPour(True)
        ka.SetDoNotAllowTracks(False)
        ka.SetDoNotAllowVias(False)
        ka.SetDoNotAllowPads(False)
        ka.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.B_Cu)
        ka.SetLayerSet(ls)
        # mutate the zone's own outline: SetOutline() stores the pointer and
        # Python's garbage collector frees the poly -> ZONE_FILLER segfault
        o = ka.Outline()
        o.NewOutline()
        for dx, dy in ((-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)):
            x = pos.x + int((dx * math.cos(rot) - dy * math.sin(rot)) * NM_PER_MM)
            y = pos.y + int((dx * math.sin(rot) + dy * math.cos(rot)) * NM_PER_MM)
            o.Append(pcbnew.VECTOR2I(x, y))
        board.Add(ka)

    # the battery GND pad sits in sparse palm-rest fill where its thermal
    # spokes land on slivers KiCad flags as starved/islands -- connect solid
    for fp in board.GetFootprints():
        if str(fp.GetFPID().GetLibItemName()) == "battery_pads":
            for pad in fp.Pads():
                if pad.GetNet() and pad.GetNet().GetNetname() == "GND":
                    pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)

    bb = board.GetBoardEdgesBoundingBox()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(gnd)
        z.SetLocalClearance(int(0.508 * NM_PER_MM))
        z.SetMinThickness(int(0.254 * NM_PER_MM))
        z.SetThermalReliefGap(int(0.508 * NM_PER_MM))
        z.SetThermalReliefSpokeWidth(int(0.508 * NM_PER_MM))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetHatchStyle(pcbnew.ZONE_BORDER_DISPLAY_STYLE_DIAGONAL_EDGE)
        o = z.Outline()
        o.NewOutline()
        for cx, cy in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()),
                       (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
            o.Append(pcbnew.VECTOR2I(cx, cy))
        board.Add(z)

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(pcb_path, board)


def shift_into_page(in_path: str, out_path: str, margin_mm: float = 25.0) -> None:
    """Save a copy of the board translated so its bbox starts at (margin, margin).

    Ergogen places the board around the origin, so much of it sits at *negative*
    coordinates -- KiCad's plotter silently clips anything off the page, which
    truncated every render checkpoint. The shifted copy is for rendering only;
    the routed output keeps Ergogen's coordinates."""
    import pcbnew

    board = pcbnew.LoadBoard(in_path)
    bbox = board.GetBoardEdgesBoundingBox()
    dx = int(margin_mm * NM_PER_MM) - bbox.GetX()
    dy = int(margin_mm * NM_PER_MM) - bbox.GetY()
    vec = pcbnew.VECTOR2I(dx, dy)
    for fp in board.GetFootprints():
        fp.Move(vec)
    for t in board.GetTracks():
        t.Move(vec)
    for d in board.GetDrawings():
        d.Move(vec)
    for z in board.Zones():
        z.Move(vec)
    pcbnew.SaveBoard(out_path, board)


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
