"""Panelize the two routed Phantom halves into one mouse-bite panel.

Arrangement (chosen by exhaustive bbox search over side-by-side, stacked and
nested placements -- all land within 0.6% of each other, so join quality
decides): the right board sits west of the left board, pinky edges facing
across a 2 mm routed slot, both MCU edges facing OUTWARD. The mirrored pinky
edges diverge southward (the halves are reflections, so the sloped lines
aren't parallel); the gap is probed per tab so each tab spans it exactly.

Tabs are placed only where the facing edges carry no nearby copper (the GND
pour hugs every edge at 0.5 mm, so the mouse-bite holes are pushed 0.05 mm
OUTWARD: 0.5 + 0.05 - 0.25 hole radius = 0.30 mm pour-to-hole, JLCPCB's NPTH
guidance; the break then leaves <=0.2 mm nubs to sand). Tab positions also
dodge the right half's edge-hugging pinky pads (S12/S13 pad 2).

Run from router/:  python3 panelize_phantom.py
Writes phantom_panel.kicad_pcb.
"""
import sys

from kikit import panelize
from kikit.common import fromMm
from pcbnewTransition import pcbnew
from shapely.geometry import LineString

GAP_DX = -271.6040     # right-board translation in the boards' shared frame
TAB_YS_LEFT = (-33.0, -26.0, -17.5, -9.0, 4.0)  # tab centres, LEFT-board frame
TAB_W = 5.0            # tab width along the joint (y)
BITE_D = 0.5           # mouse-bite hole diameter
BITE_SPACING = 0.75    # hole pitch
BITE_OFFSET = -0.05    # negative = holes pushed outward (pour clearance)


def edge_center(path):
    b = pcbnew.LoadBoard(path)
    bb = b.GetBoardEdgesBoundingBox()
    return pcbnew.VECTOR2I(bb.GetCenter())


def main():
    cL = edge_center("routed_left.kicad_pcb")
    cR = edge_center("routed_right.kicad_pcb")

    panel = panelize.Panel("phantom_panel.kicad_pcb")
    net = lambda n, name: f"B{n}-{name}"
    ref = lambda n, r: f"B{n}-{r}"

    # Origin.Center: dest = where the board's bbox centre lands. Left centre
    # goes to (0,0); right keeps its original offset to left, plus GAP_DX.
    panel.appendBoard(
        "routed_left.kicad_pcb", pcbnew.VECTOR2I(0, 0),
        origin=panelize.Origin.Center, tolerance=fromMm(3),
        netRenamer=net, refRenamer=ref, inheritDrc=True)
    panel.appendBoard(
        "routed_right.kicad_pcb",
        pcbnew.VECTOR2I(cR.x - cL.x + fromMm(GAP_DX), cR.y - cL.y),
        origin=panelize.Origin.Center, tolerance=fromMm(3),
        netRenamer=net, refRenamer=ref, inheritDrc=False)

    subs = panel.substrates  # [0]=left (east board), [1]=right (west board)
    cuts = []
    for y_left in TAB_YS_LEFT:
        y = fromMm(y_left) - cL.y          # left frame -> panel frame
        probe = LineString([(fromMm(-200), y), (fromMm(-40), y)])
        xs_l = [p[0] for p in _crossings(subs[0], probe)]
        xs_r = [p[0] for p in _crossings(subs[1], probe)]
        if not xs_l or not xs_r:
            raise RuntimeError(f"tab at left-y={y_left} misses a board edge")
        xL, xR = min(xs_l), max(xs_r)   # facing edges: left board west, right board east
        # Cast each tab from just outside the OPPOSITE board so the two tab
        # polygons overlap across the whole gap -- a seam-free union (meeting
        # exactly at mid-gap leaves degenerate slivers in the outline).
        for sub, origin_x, direction in ((subs[0], xR + fromMm(0.4), (1, 0)),
                                         (subs[1], xL - fromMm(0.4), (-1, 0))):
            tab, cut = sub.tab((origin_x, y), direction, fromMm(TAB_W))
            # kikit's tab face coincides exactly with the board edge; on
            # sloped edges that leaves slivers in the union (kikit only
            # epsilon-penetrates when a partition line is given). Buffer 1 um.
            panel.appendSubstrate(tab.buffer(fromMm(0.001), join_style=2))
            cuts.append(cut)

    panel.makeMouseBites(cuts, fromMm(BITE_D), fromMm(BITE_SPACING),
                         fromMm(BITE_OFFSET), prolongation=fromMm(0.0))
    panel.save()
    print("wrote phantom_panel.kicad_pcb")


def _crossings(substrate, probe):
    inter = substrate.substrates.boundary.intersection(probe)
    if inter.is_empty:
        return []
    geoms = getattr(inter, "geoms", [inter])
    pts = []
    for g in geoms:
        pts.extend(g.coords)
    return pts


if __name__ == "__main__":
    sys.exit(main())
