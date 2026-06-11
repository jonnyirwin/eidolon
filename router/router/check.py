"""Exact clearance self-check for emitted track elements.

DRC (`kicad-cli pcb drc`) is the final authority, but its report positions are
item anchors, not violation points -- useless for tuning a 0.05 mm margin. This
module re-checks every emitted element against pads / holes / keepouts / the
board edge / other-net copper with exact geometry and reports the worst pairs
with true locations and distances, so constants can be tuned in one pass.
"""
from __future__ import annotations

import math
import re

from .geometry import circle_from_3

CLEAR = 0.2        # copper-copper (Default net class)
PAD_CLEAR = 0.3    # copper-pad: clearance + solder-mask web margin
HOLE_CLEAR = 0.25  # copper-hole
EDGE_CLEAR = 0.5   # copper-board edge

_ARC_RE = re.compile(
    r'\((arc|segment) \(start ([-\d.]+) ([-\d.]+)\)(?: \(mid ([-\d.]+) ([-\d.]+)\))?'
    r' \(end ([-\d.]+) ([-\d.]+)\) \(width ([\d.]+)\) \(layer "([\w.]+)"\)'
    r' \(net (\d+)\)')
_VIA_RE = re.compile(r'\(via \(at ([-\d.]+) ([-\d.]+)\) \(size ([\d.]+)\)')
_VIA_NET_RE = re.compile(r'\(via .*\(net (\d+)\)')


def _sample_arc(s, m, e, step=0.15):
    c = circle_from_3(s, m, e)
    if c is None:
        return [s, e]
    (cx, cy), r = c
    a0 = math.atan2(s[1] - cy, s[0] - cx)
    a1 = math.atan2(m[1] - cy, m[0] - cx)
    a2 = math.atan2(e[1] - cy, e[0] - cx)

    def sweep(f, t):
        d = t - f
        while d <= -math.pi:
            d += 2 * math.pi
        while d > math.pi:
            d -= 2 * math.pi
        return d
    d1, d2 = sweep(a0, a1), sweep(a1, a2)
    total = d1 + d2
    n = max(2, int(abs(total) * r / step))
    return [(cx + r * math.cos(a0 + total * k / n),
             cy + r * math.sin(a0 + total * k / n)) for k in range(n + 1)]


def parse_elements(elements):
    """-> tracks [(net, layer, halfwidth, [pts])], vias [(net, x, y, radius)]"""
    tracks, vias = [], []
    for el in elements:
        m = _ARC_RE.search(el)
        if m:
            kind, sx, sy, mx, my, ex, ey, w, layer, net = m.groups()
            s, e = (float(sx), float(sy)), (float(ex), float(ey))
            if kind == "arc" and mx is not None:
                pts = _sample_arc(s, (float(mx), float(my)), e)
            else:
                pts = [s, e]
            tracks.append((int(net), layer, float(w) / 2, pts))
            continue
        m = _VIA_RE.search(el)
        if m:
            nm = _VIA_NET_RE.search(el)
            vias.append((int(nm.group(1)), float(m.group(1)), float(m.group(2)),
                         float(m.group(3)) / 2))
    return tracks, vias


def _seg_seg(a, b, c, d):
    """min distance between segments ab and cd"""
    def ps(p, a, b):
        ax, ay = a; bx, by = b
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * dx +
                                                     (p[1] - ay) * dy) / L))
        return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))
    # crossing test
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    if (cross(a, b, c) * cross(a, b, d) < 0 and
            cross(c, d, a) * cross(c, d, b) < 0):
        return 0.0
    return min(ps(a, c, d), ps(b, c, d), ps(c, a, b), ps(d, a, b))


def _poly_min_dist(pts1, pts2):
    best, where = float("inf"), None
    for a, b in zip(pts1, pts1[1:]):
        for c, d in zip(pts2, pts2[1:]):
            v = _seg_seg(a, b, c, d)
            if v < best:
                best, where = v, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    return best, where


def _pt_poly_dist(p, pts):
    best = float("inf")
    for a, b in zip(pts, pts[1:]):
        ax, ay = a; bx, by = b
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * dx +
                                                     (p[1] - ay) * dy) / L))
        best = min(best, math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy)))
    return best


def _rect_pts(cx, cy, sx, sy, rot_deg):
    r = math.radians(rot_deg)
    c, s = math.cos(r), math.sin(r)
    out = []
    for dx, dy in ((-sx / 2, -sy / 2), (sx / 2, -sy / 2), (sx / 2, sy / 2),
                   (-sx / 2, sy / 2), (-sx / 2, -sy / 2)):
        out.append((cx + dx * c - dy * s, cy + dx * s + dy * c))
    return out


def check(board, elements, verbose=True):
    """Return a list of (kind, name_a, name_b, need, actual, (x, y))."""
    tracks, vias = parse_elements(elements)
    issues = []

    pad_polys = []
    for p in board.pads:
        pad_polys.append((p.net_code, f"{p.ref}.{p.pad}", p.cu_layers,
                          _rect_pts(p.cx, p.cy, p.sx, p.sy, p.fp_rot)))
    keep_polys = [(f"{k['ref']}.{k['pad']}",
                   _rect_pts(k["x"], k["y"], k["sx"], k["sy"], 0.0))
                  for k in board.keepouts]

    for net, layer, hw, pts in tracks:
        nname = next((n.name for n in board.nets.values() if n.code == net), net)
        # pads of other nets (any shared copper layer)
        for pnet, pname, players, poly in pad_polys:
            if pnet == net or layer not in players:
                continue
            d, w = _poly_min_dist(pts, poly)
            if d < hw + PAD_CLEAR:
                issues.append(("pad", nname, pname, hw + PAD_CLEAR, d, w))
        for kname, poly in keep_polys:
            d, w = _poly_min_dist(pts, poly)
            if d < hw + PAD_CLEAR:
                issues.append(("keepout", nname, kname, hw + PAD_CLEAR, d, w))
        for h in board.holes:
            d = _pt_poly_dist((h["x"], h["y"]), pts) - h["d"] / 2
            if d < hw + HOLE_CLEAR:
                issues.append(("hole", nname, f"hole@{h['x']:.1f},{h['y']:.1f}",
                               hw + HOLE_CLEAR, d, (h["x"], h["y"])))
        for a, b in board.edge:
            d, w = _poly_min_dist(pts, [a, b])
            if d < hw + EDGE_CLEAR:
                issues.append(("edge", nname, "edge", hw + EDGE_CLEAR, d, w))
        for vnet, vx, vy, vr in vias:
            if vnet == net:
                continue
            d = _pt_poly_dist((vx, vy), pts) - vr
            if d < hw + CLEAR:
                issues.append(("via", nname, f"via[{vnet}]", hw + CLEAR, d,
                               (vx, vy)))
    # track vs track (different nets, same layer)
    for i in range(len(tracks)):
        ni, li, hi, pi = tracks[i]
        for j in range(i + 1, len(tracks)):
            nj, lj, hj, pj = tracks[j]
            if ni == nj or li != lj:
                continue
            d, w = _poly_min_dist(pi, pj)
            if d < hi + hj + CLEAR:
                a = next((n.name for n in board.nets.values() if n.code == ni), ni)
                b = next((n.name for n in board.nets.values() if n.code == nj), nj)
                issues.append(("track", a, b, hi + hj + CLEAR, d, w))
    # via vs pads/holes/edge/other vias
    for vnet, vx, vy, vr in vias:
        nname = next((n.name for n in board.nets.values() if n.code == vnet), vnet)
        for pnet, pname, players, poly in pad_polys:
            if pnet == vnet:
                continue
            d = _pt_poly_dist((vx, vy), poly) - vr
            if d < PAD_CLEAR:
                issues.append(("via-pad", nname, pname, PAD_CLEAR, d, (vx, vy)))
        for h in board.holes:
            d = math.hypot(vx - h["x"], vy - h["y"]) - h["d"] / 2 - vr
            if d < HOLE_CLEAR:
                issues.append(("via-hole", nname, "hole", HOLE_CLEAR, d, (vx, vy)))
        for a, b in board.edge:
            d = _pt_poly_dist((vx, vy), [a, b]) - vr
            if d < EDGE_CLEAR:
                issues.append(("via-edge", nname, "edge", EDGE_CLEAR, d, (vx, vy)))
    if verbose:
        for kind, a, b, need, got, w in sorted(issues, key=lambda x: x[4] - x[3]):
            print(f"  {kind:8} {a} <-> {b}: {got:.3f} < {need:.3f} "
                  f"@({w[0]:.2f},{w[1]:.2f})")
    return issues
