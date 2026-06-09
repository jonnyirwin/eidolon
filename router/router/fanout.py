"""Gridded A* router for the MCU fan-out (design brief step 11, part 2).

The matrix routes itself from regularity, but the GPIO pads break that
regularity: column/row nets converge on a stack of MCU pads and must thread a
dense, mirror-asymmetric obstacle field (choc poles, the power switch, existing
spines, the board edge) to reach their spines. The brief anticipates exactly
this -- "a small local fan-out router ... something closer to A* pathfinding ...
the search space is tiny". This is that router.

Approach: rasterise every obstacle into a two-layer occupancy grid (one cell per
``GRID`` mm, F.Cu + B.Cu), then route each fan-out net with A* from its MCU pad
to the nearest pad of its own spine, dropping vias to change layer. Nets are
routed hardest-first and each finished route becomes an obstacle for the rest.
The current net's own copper is never an obstacle -- it is the goal.
"""
from __future__ import annotations

import heapq
import math
import re

from . import kwrite

GRID = 0.25          # mm per cell
CLEAR = 0.2          # copper-to-copper clearance (Default net class)
HOLE_CLEAR = 0.25    # copper-to-hole clearance (board setup)
EDGE_CLEAR = 0.5     # copper-to-edge clearance
HALF = 0.125         # half the 0.25mm trace width
VIA_COST = 2.0       # mm-equivalent penalty per layer change (discourage vias)
VIA_R = 0.3          # via copper radius (0.6 size / 2)
MASK_MARGIN = 0.3    # trace-to-pad spacing: > copper clearance so the solder-mask
                     # web between trace and pad does not bridge

_LAYERS = ("F.Cu", "B.Cu")


# --- obstacle geometry parsed back from the emitted matrix S-expressions -------

def parse_tracks(elements):
    """Return (segments, vias) from emitted track strings.
    segments: list of (net_code, layer, (x0,y0), (x1,y1)); vias: (net_code, x, y)."""
    segs, vias = [], []
    for e in elements:
        m = re.search(r'\(start ([-\d.]+) ([-\d.]+)\) \(mid ([-\d.]+) ([-\d.]+)\) '
                      r'\(end ([-\d.]+) ([-\d.]+)\).*?\(layer "([\w.]+)"\) '
                      r'\(net (\d+)\)', e)
        if m:                                   # arc -> two chords (start-mid-end)
            sx, sy, mx, my, ex, ey, layer, nc = m.groups()
            nc = int(nc)
            segs.append((nc, layer, (float(sx), float(sy)), (float(mx), float(my))))
            segs.append((nc, layer, (float(mx), float(my)), (float(ex), float(ey))))
            continue
        m = re.search(r'\(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) '
                      r'\(width [\d.]+\) \(layer "([\w.]+)"\) \(net (\d+)\)', e)
        if m:
            sx, sy, ex, ey, layer, nc = m.groups()
            segs.append((int(nc), layer, (float(sx), float(sy)),
                         (float(ex), float(ey))))
            continue
        m = re.search(r'\(via \(at ([-\d.]+) ([-\d.]+)\).*?\(net (\d+)\)', e)
        if m:
            vias.append((int(m.group(3)), float(m.group(1)), float(m.group(2))))
    return segs, vias


# --- the occupancy grid --------------------------------------------------------

class Grid:
    """Two occupancy layers (F.Cu/B.Cu) with two inflations each: ``block`` keeps a
    0.25mm trace its copper clearance from every obstacle; ``vblock`` keeps a 0.6mm
    via (and its annulus) clear -- a via cannot be dropped on a ``block``-free cell
    that a neighbouring obstacle would still foul."""

    def __init__(self, board):
        bb = board.bbox
        self.x0, self.y0 = bb["x"], bb["y"]
        self.w = int(bb["w"] / GRID) + 3
        self.h = int(bb["h"] / GRID) + 3
        self.block = {l: bytearray(self.w * self.h) for l in _LAYERS}
        self.vblock = {l: bytearray(self.w * self.h) for l in _LAYERS}

    def ij(self, x, y):
        return int(round((x - self.x0) / GRID)), int(round((y - self.y0) / GRID))

    def xy(self, i, j):
        return self.x0 + i * GRID, self.y0 + j * GRID

    def inb(self, i, j):
        return 0 <= i < self.w and 0 <= j < self.h

    def _disc(self, grids, layers, x, y, r):
        ci, cj = self.ij(x, y)
        rr = int(r / GRID) + 1
        for j in range(cj - rr, cj + rr + 1):
            for i in range(ci - rr, ci + rr + 1):
                if not self.inb(i, j):
                    continue
                gx, gy = self.xy(i, j)
                if (gx - x) ** 2 + (gy - y) ** 2 <= r * r:
                    for l in layers:
                        if l in grids:
                            grids[l][j * self.w + i] = 1

    def obstacle_disc(self, layers, x, y, clearance):
        """Block both grids around a disc obstacle: trace half-width for ``block``,
        via radius for ``vblock``."""
        self._disc(self.block, layers, x, y, HALF + clearance)
        self._disc(self.vblock, layers, x, y, VIA_R + clearance)

    def _rect(self, grids, layers, x, y, hx, hy):
        ci0, cj0 = self.ij(x - hx, y - hy)
        ci1, cj1 = self.ij(x + hx, y + hy)
        for j in range(cj0, cj1 + 1):
            for i in range(ci0, ci1 + 1):
                if self.inb(i, j):
                    for l in layers:
                        if l in grids:
                            grids[l][j * self.w + i] = 1

    def obstacle_rect(self, layers, x, y, hx, hy, clearance):
        """Block a rectangular pad (axis-aligned) -- a disc under-covers the
        corners of the wide MCU pads, letting traces slip through at <clearance."""
        self._rect(self.block, layers, x, y, hx + HALF + clearance,
                   hy + HALF + clearance)
        self._rect(self.vblock, layers, x, y, hx + VIA_R + clearance,
                   hy + VIA_R + clearance)

    def obstacle_seg(self, layers, a, b, clearance, half=HALF):
        n = max(1, int(math.dist(a, b) / (GRID * 0.5)))
        for k in range(n + 1):
            t = k / n
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            self._disc(self.block, layers, x, y, half + HALF + clearance)
            self._disc(self.vblock, layers, x, y, half + VIA_R + clearance)

    def carve(self, layers, x, y, r):
        """Force a small spot free so A* can start/end on a pad whose centre is
        buried in a neighbouring pad's clearance disc -- just enough to seat the
        first move (and a via)."""
        ci, cj = self.ij(x, y)
        rr = int(r / GRID) + 1
        for j in range(cj - rr, cj + rr + 1):
            for i in range(ci - rr, ci + rr + 1):
                if self.inb(i, j) and (self.xy(i, j)[0] - x) ** 2 + \
                        (self.xy(i, j)[1] - y) ** 2 <= r * r:
                    for l in layers:
                        self.block[l][j * self.w + i] = 0
                        self.vblock[l][j * self.w + i] = 0


def build_grid(board, segs, vias, skip_net):
    """Rasterise all obstacles except the copper of ``skip_net`` (start + goal)."""
    g = Grid(board)
    for p in board.pads:
        if p.net_code == skip_net:
            continue
        # pad as an (axis-aligned) rect + a mask margin -- keeps traces off the
        # pad's mask web, not just its copper, and (unlike a disc) covers corners.
        g.obstacle_rect(p.cu_layers, p.x, p.y, p.sx / 2.0, p.sy / 2.0, MASK_MARGIN)
    for h in board.holes:                       # mechanical drills: both layers
        g.obstacle_disc(_LAYERS, h["x"], h["y"], h["d"] / 2.0 + HOLE_CLEAR)
    for a, b in board.edge:                     # keep-out band along the outline
        g.obstacle_seg(_LAYERS, a, b, EDGE_CLEAR, half=0.0)
    for nc, layer, a, b in segs:
        if nc == skip_net:
            continue
        g.obstacle_seg([layer], a, b, CLEAR)
    for nc, x, y in vias:
        if nc == skip_net:
            continue
        g.obstacle_disc(_LAYERS, x, y, VIA_R + CLEAR)
    return g


# --- A* ------------------------------------------------------------------------

_STEPS = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
          (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]


def snap_free(grid, i, j, layer, limit=24):
    """Nearest cell to (i,j) that is unblocked on ``layer`` (ring search). A pad
    centre often sits inside a neighbouring pad's clearance disc; the trace must
    start/end at the first cell with real clearance and stub the rest."""
    if grid.inb(i, j) and not grid.block[layer][j * grid.w + i]:
        return i, j
    for rad in range(1, limit):
        best = None
        for dj in range(-rad, rad + 1):
            for di in range(-rad, rad + 1):
                if max(abs(di), abs(dj)) != rad:
                    continue
                ni, nj = i + di, j + dj
                if grid.inb(ni, nj) and not grid.block[layer][nj * grid.w + ni]:
                    d = di * di + dj * dj
                    if best is None or d < best[0]:
                        best = (d, ni, nj)
        if best:
            return best[1], best[2]
    return i, j


def astar(grid, start, goal):
    """start/goal are (i, j, layer). Returns a list of (i, j, layer) or None."""
    si, sj, sl = start
    gi, gj, gl = goal

    def h(i, j):
        return math.hypot(i - gi, j - gj) * GRID

    open_h = [(h(si, sj), 0.0, si, sj, sl)]
    came = {}
    best = {(si, sj, sl): 0.0}
    while open_h:
        f, cost, i, j, l = heapq.heappop(open_h)
        if (i, j, l) == (gi, gj, gl):
            path = [(i, j, l)]
            while (i, j, l) in came:
                i, j, l = came[(i, j, l)]
                path.append((i, j, l))
            return path[::-1]
        if cost > best.get((i, j, l), 1e18):
            continue
        # same-layer moves
        for di, dj, w in _STEPS:
            ni, nj = i + di, j + dj
            if not grid.inb(ni, nj) or grid.block[l][nj * grid.w + ni]:
                continue
            if di and dj:                        # no diagonal corner-cutting
                if grid.block[l][j * grid.w + ni] or grid.block[l][nj * grid.w + i]:
                    continue
            nc = cost + w * GRID
            if nc < best.get((ni, nj, l), 1e18):
                best[(ni, nj, l)] = nc
                came[(ni, nj, l)] = (i, j, l)
                heapq.heappush(open_h, (nc + h(ni, nj), nc, ni, nj, l))
        # via to the other layer: needs via-sized clearance on both layers
        other = _LAYERS[1] if l == _LAYERS[0] else _LAYERS[0]
        if (not grid.vblock[l][j * grid.w + i]
                and not grid.vblock[other][j * grid.w + i]):
            nc = cost + VIA_COST
            if nc < best.get((i, j, other), 1e18):
                best[(i, j, other)] = nc
                came[(i, j, other)] = (i, j, l)
                heapq.heappush(open_h, (nc + h(i, j), nc, i, j, other))
    return None


# --- path -> tracks ------------------------------------------------------------

def path_to_elements(grid, path, net_code, start_xy, goal_xy):
    """Turn an A* cell path into compressed segments + vias, snapping the ends to
    the real pad centres."""
    pts = [(grid.xy(i, j), l) for i, j, l in path]
    pts[0] = (start_xy, pts[0][1])
    pts[-1] = (goal_xy, pts[-1][1])
    out = []
    run = [pts[0][0]]
    layer = pts[0][1]
    for (xy, l), (pi, pj, _) in zip(pts[1:], path[1:]):
        if l != layer:                           # via: flush run, drop via
            run = _compress(run)
            out += kwrite.polyline(run, 0.25, layer, net_code)
            out.append(kwrite.via(run[-1], 0.6, 0.4, net_code))
            run = [run[-1]]
            layer = l
        run.append(xy)
    run = _compress(run)
    out += kwrite.polyline(run, 0.25, layer, net_code)
    return out


def route(board, matrix_elements, specs, verbose=False):
    """Route each fan-out net with A* over the obstacle grid.

    ``specs`` is a list of ``(name, net_code, start_xy, goal_xy, goal_layer)``.
    Routed hardest (longest) first; each finished route joins the obstacle set so
    later nets avoid it. Returns (elements, unrouted_names)."""
    segs, vias = parse_tracks(matrix_elements)
    specs = sorted(specs, key=lambda s: -math.dist(s[2], s[3]))
    elements, unrouted = [], []
    for name, code, start_xy, goal_xy, goal_layer in specs:
        grid = build_grid(board, segs, vias, code)
        # carve a small free spot at each pad centre (both layers at the start, so
        # a boxed pad can via straight down) so A* seats on the pad and is forced
        # to the real exit instead of grazing a neighbour.
        grid.carve(_LAYERS, *start_xy, 0.4)
        grid.carve([goal_layer], *goal_xy, 0.4)
        si, sj = grid.ij(*start_xy)
        gi, gj = grid.ij(*goal_xy)
        start = (si, sj, "F.Cu")
        goal = (gi, gj, goal_layer)
        path = astar(grid, start, goal)
        if path is None:
            unrouted.append(name)
            if verbose:
                print(f"  {name}: NO PATH ({start_xy} -> {goal_xy})")
            continue
        new = path_to_elements(grid, path, code, start_xy, goal_xy)
        elements += new
        ns, nv = parse_tracks(new)              # add this route to the obstacles
        segs += ns
        vias += nv
        if verbose:
            nvia = sum(1 for e in new if "(via " in e)
            print(f"  {name}: routed ({len(path)} cells, {nvia} via)")
    return elements, unrouted


def _compress(pts):
    """Drop collinear interior points so straight runs are single segments."""
    if len(pts) <= 2:
        return pts
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[k]
        cx, cy = pts[k + 1]
        if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1e-6:
            out.append(pts[k])
    out.append(pts[-1])
    return out
