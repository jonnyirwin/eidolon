"""River-delta fan-out + power routing (design brief steps 11-14).

Everything that is not the switch matrix converges on the MCU / power parts in
the board's east region. The pretty, best-practice shape for that convergence
is the "river": parallel lanes at constant pitch, offset from the *board edge*
so they flow with the outline, with smooth rounded corners where each net
breaks out of a pad stack or peels off toward its destination.

Load-bearing discovery: the MCU (xiao_ble), power switch and battery pads are
all **through-hole**, so:

- the column fan-out runs entirely on **B.Cu** -- it leaves the MCU pads on the
  back, rides edge-offset lanes along the NE diagonal + north edge, and drops
  straight into each column's top switch pad (B.Cu). **Zero vias.**
- the boxed east-stack rows (R2/R3) leave their MCU pads directly on B.Cu and
  cross under the MCU region; one via each where they join their F.Cu row spine.
- GND / RAW_BATT run as a parallel B.Cu bundle along the *south* margin from
  the battery to the power switch / MCU; BATT crosses on F.Cu. No vias.

Lane geometry (offsets, peel order) is derived from the pad stack order, which
matches the column order -- so the nested-peel river needs no crossing logic.
The same construction re-runs on the mirrored right half: every x offset is
scaled by ``e`` (+1 = MCU east of the matrix), y offsets are mirror-invariant
(the Phantom mirror flips x only).
"""
from __future__ import annotations

import math

from . import kwrite
from .classify import nets_of
from .geometry import bezier_transition, catmull_rom, unit
from .model import Board, NetClass

Point = tuple[float, float]

SIG_W = 0.25       # signal trace width (matrix + fan-out)
PWR_W = 0.5        # power rail width (brief step 14)
VIA_SIZE = 0.6
VIA_DRILL = 0.3

LANE_BASE = 0.66   # outermost lane offset from the board edge (0.5 edge
                   # clearance + half trace + margin)
LANE_PITCH = 0.55  # signal lane pitch: 0.30 copper gap, so the 0.02 arc-fit
                   # tolerance cannot eat the 0.2 clearance rule
PINCH_PITCH = 0.5  # pitch between the two outermost lanes only: they ride the
                   # north pinch together (apex key's hotswap drill vs the top
                   # edge -- 1.58 mm for two traces needing 1.45), so the slack
                   # is split ~0.04 mm per rule. No outline relief needed.


def lane_offset(k: int) -> float:
    """Edge offset of lane ``k`` (0 = outermost)."""
    if k == 0:
        return LANE_BASE
    return LANE_BASE + PINCH_PITCH + LANE_PITCH * (k - 1)
PWR_BASE = 0.8     # 0.5 edge clearance + half a 0.5 rail + margin
PWR_PITCH = 0.8    # 0.30 copper gap between 0.5 rails

ARC_TOL = 0.02     # arc-fit tolerance for river paths (tight corridors)
CUT = 2.2          # corner-rounding reach (quadratic Bezier fillets)

# Riser windows for the column breakout (x offsets are mirror-scaled by ``e``).
# The obvious uniform stagger west of the MCU stack dies on PG1350 reality: the
# inner column's home-row switch puts its hotswap pad 2 (centre +8.275,-3.75)
# and drills right in the corridor. Two free windows remain:
#  - NEAR window, between that pad-2 box and the MCU pad boxes: 3 risers fit.
#  - FAR window, the gap in the same switch's pole/drill field (between the
#    3.429 centre pole and the 3.0 hotswap drill): 2 risers fit.
RISER_NEAR = (1.98, 2.53, 3.08)   # k = 0..2, west of the MCU pad column
RISER_FAR = (6.17, 5.61)          # k = 3, 4, east of the inner column top pad


# --- board outline helpers ------------------------------------------------------

class Outline:
    """The board boundary as an ordered closed loop, with inward offsetting.

    The river lanes are constant-distance offsets of this loop, so they follow
    the outline's lines *and* arcs by construction (brief: flow with the board).
    """

    def __init__(self, edge_segs):
        segs = [tuple(s) for s in edge_segs]
        loop = [segs[0][0], segs[0][1]]
        used = {0}
        while len(used) < len(segs):
            tail = loop[-1]
            for i, (a, b) in enumerate(segs):
                if i in used:
                    continue
                if _close(a, tail):
                    loop.append(b)
                    used.add(i)
                    break
                if _close(b, tail):
                    loop.append(a)
                    used.add(i)
                    break
            else:
                raise ValueError("board outline is not a closed chain")
        if _close(loop[0], loop[-1]):
            loop.pop()
        self.pts = loop

    def _inside(self, p: Point) -> bool:
        n, c = len(self.pts), False
        for i in range(n):
            a, b = self.pts[i], self.pts[(i + 1) % n]
            if (a[1] > p[1]) != (b[1] > p[1]):
                x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if p[0] < x:
                    c = not c
        return c

    def offset(self, d: float) -> list[Point]:
        """Closed loop offset ``d`` mm toward the board interior (miter joins)."""
        n = len(self.pts)
        # inward = the perpendicular that points into the polygon (probe once).
        a, b = self.pts[0], self.pts[1]
        t = unit((b[0] - a[0], b[1] - a[1]))
        nrm = (-t[1], t[0])
        mid = ((a[0] + b[0]) / 2 + nrm[0] * 0.05, (a[1] + b[1]) / 2 + nrm[1] * 0.05)
        sgn = 1.0 if self._inside(mid) else -1.0
        out = []
        for i in range(n):
            p0, p1, p2 = self.pts[i - 1], self.pts[i], self.pts[(i + 1) % n]
            t0 = unit((p1[0] - p0[0], p1[1] - p0[1]))
            t1 = unit((p2[0] - p1[0], p2[1] - p1[1]))
            n0 = (-t0[1] * sgn, t0[0] * sgn)
            n1 = (-t1[1] * sgn, t1[0] * sgn)
            mx, my = n0[0] + n1[0], n0[1] + n1[1]
            L = math.hypot(mx, my)
            if L < 1e-9:
                mx, my, L = n0[0], n0[1], 1.0
            # miter scale so the offset keeps distance d on both sides
            cos_half = L / 2.0
            k = d / max(0.2, cos_half)
            out.append((p1[0] + mx / L * k, p1[1] + my / L * k))
        return out

    @staticmethod
    def x_cross(loop: list[Point], x: float, north: bool):
        """Intersection of the vertical line at ``x`` with the closed loop.
        Returns ``(seg_index, t, point)`` for the northernmost (min y) or
        southernmost (max y) crossing."""
        hits = []
        n = len(loop)
        for i in range(n):
            a, b = loop[i], loop[(i + 1) % n]
            if (a[0] - x) * (b[0] - x) > 0 or a[0] == b[0]:
                continue
            t = (x - a[0]) / (b[0] - a[0])
            if 0.0 <= t <= 1.0:
                y = a[1] + t * (b[1] - a[1])
                hits.append((i, t, (x, y)))
        if not hits:
            raise ValueError(f"no outline crossing at x={x}")
        return min(hits, key=lambda h: h[2][1] if north else -h[2][1])

    @staticmethod
    def walk(loop: list[Point], a, b) -> list[Point]:
        """Loop samples from crossing ``a`` to crossing ``b`` (each from
        ``x_cross``), travelling the shorter way around. Includes both
        crossing points; interior samples are the loop vertices."""
        n = len(loop)
        ia, ta, pa = a
        ib, tb, pb = b

        def length(path):
            return sum(math.dist(p, q) for p, q in zip(path, path[1:]))

        fwd = [pa]
        i = (ia + 1) % n
        while i != (ib + 1) % n:
            fwd.append(loop[i])
            i = (i + 1) % n
        fwd.append(pb)
        bwd = [pa]
        i = ia
        while i != ib:
            bwd.append(loop[i])
            i = (i - 1) % n
        bwd.append(pb)
        return fwd if length(fwd) <= length(bwd) else bwd


def _close(a: Point, b: Point, tol: float = 1e-4) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


# --- corner rounding -------------------------------------------------------------

def round_corners(pts: list[Point], cut: float = CUT, samples: int = 12,
                  min_turn_deg: float = 12.0) -> list[Point]:
    """Round every sharp corner of a polyline with a quadratic Bezier whose
    legs reach ``cut`` mm back/forward along the path (clamped to the available
    run). Smooth sampled runs (lane arcs) turn a few degrees per vertex and are
    left untouched; the constructed 45-90 degree corners become fillets."""
    if len(pts) < 3:
        return list(pts)
    # cumulative arc length
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    sharp = []
    for j in range(1, len(pts) - 1):
        t0 = unit((pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1]))
        t1 = unit((pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1]))
        dot = max(-1.0, min(1.0, t0[0] * t1[0] + t0[1] * t1[1]))
        if math.degrees(math.acos(dot)) >= min_turn_deg:
            sharp.append(j)
    if not sharp:
        return list(pts)

    def at_arclen(s: float) -> Point:
        s = max(0.0, min(cum[-1], s))
        for i in range(len(cum) - 1):
            if cum[i + 1] >= s:
                seg = cum[i + 1] - cum[i]
                t = 0.0 if seg < 1e-12 else (s - cum[i]) / seg
                return (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]),
                        pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
        return pts[-1]

    out: list[Point] = []
    pos = 0.0                       # arclength consumed so far
    prev_idx = 0
    for k, j in enumerate(sharp):
        lo = cum[sharp[k - 1]] if k else 0.0
        hi = cum[sharp[k + 1]] if k + 1 < len(sharp) else cum[-1]
        c = min(cut, (cum[j] - lo) / 2.0, (hi - cum[j]) / 2.0)
        s0, s1 = cum[j] - c, cum[j] + c
        # straight/curved run up to the fillet start
        while prev_idx < len(pts) and cum[prev_idx] < s0 - 1e-9:
            if cum[prev_idx] >= pos - 1e-9:
                out.append(pts[prev_idx])
            prev_idx += 1
        a, b = at_arclen(s0), at_arclen(s1)
        ctrl = pts[j]
        for s in range(samples + 1):
            t = s / samples
            mt = 1 - t
            out.append((mt * mt * a[0] + 2 * mt * t * ctrl[0] + t * t * b[0],
                        mt * mt * a[1] + 2 * mt * t * ctrl[1] + t * t * b[1]))
        pos = s1
        while prev_idx < len(pts) and cum[prev_idx] <= s1 + 1e-9:
            prev_idx += 1
    out += pts[prev_idx:]
    if not _close(out[0], pts[0], 1e-9):
        out.insert(0, pts[0])
    return out


# --- shared lookups --------------------------------------------------------------

def _mcu_pad(net):
    for p in net.pads:
        if p.footprint == "xiao_ble":
            return p
    return None


def _east_sign(board: Board) -> float:
    """+1 if the MCU sits east of the matrix (left half), -1 mirrored."""
    mcu = [p for p in board.pads if p.footprint == "xiao_ble"]
    sw = [p for p in board.pads if p.footprint == "PG1350"]
    mx = sum(p.x for p in mcu) / len(mcu)
    sx = sum(p.x for p in sw) / len(sw)
    return 1.0 if mx > sx else -1.0


def _spine_end(spine: list[Point], toward: Point):
    """(end_point, inward_tangent) of the spine end nearer ``toward``; the
    tangent points *into* the spine (the direction a joining trace continues)."""
    if math.dist(spine[-1], toward) <= math.dist(spine[0], toward):
        end, nxt = spine[-1], spine[-2]
    else:
        end, nxt = spine[0], spine[1]
    return end, unit((nxt[0] - end[0], nxt[1] - end[1]))


# --- column river (B.Cu, zero vias) ----------------------------------------------

# Per-column peel specials, derived from the PG1350 hotswap drill/pad pattern
# (relative to the top switch pad, mirror-safe via the east sign ``e``):
C0_DESCENT_DX = 1.06   # thread between the NW mounting hole and S13's hotswap
                       # drill: the free window's centre is 1.06 mm inboard of
                       # the pad
C0_TURN_DY = -3.4      # turn toward the pad once south of the NW hole band
C2_DESCENT_DX = 13.87  # peel inboard of the apex key's hotswap pad 2 box and
                       # west of the neighbour's 1.7 pole drill
C2_JOG_DY = 9.05       # tributary south of the choc poles and of the apex
                       # key's own matrix via; T-joins the column spine


def route_column_river(board: Board, outline: Outline,
                       verbose: bool = False) -> list[str]:
    cols = []
    for net in nets_of(board, NetClass.COLUMN):
        mp = _mcu_pad(net)
        sw = [p for p in net.pads if p.footprint == "PG1350"]
        if mp is None or not sw:
            continue
        cols.append((net, mp, min(sw, key=lambda p: p.y)))   # top switch pad
    if not cols:
        return []
    cols.sort(key=lambda c: c[1].y)        # MCU pad stack, north -> south
    e = _east_sign(board)
    # the "apex" column owns the board's northernmost key: on the left half the
    # corridor pinches between that key's hotswap drill and the top edge, so the
    # apex column peels on the near side of its drills (tributary) instead of
    # riding through the pinch. Footprint internals do NOT mirror, so on the
    # right half the drills sit on the far side of pad 1 and the apex column
    # peels normally (its lane never reaches the pinch).
    apex = min(range(len(cols)), key=lambda i: cols[i][2].y) if e > 0 else -1
    inner_top = cols[-1][2]               # innermost column's top switch pad
    # riser x per column. Left half: two windows in the inner home key's
    # drill/pad field. Right half: the column pads face away from the matrix,
    # and the corridor between the stacks is broken up by the XIAO's BAT/GND
    # aux pads and SWD keepouts -- C0 fits between aux pads and keepouts, the
    # rest go through the window between the keepouts and the far stack.
    if e > 0:
        riser_x = [mp.x - e * RISER_NEAR[k] if k < len(RISER_NEAR)
                   else inner_top.x + e * RISER_FAR[k - len(RISER_NEAR)]
                   for k, (_, mp, _) in enumerate(cols)]
        esc_dy = [0.0] * len(cols)
    else:
        aux_x = max((p.x for p in board.pads
                     if p.footprint == "xiao_ble" and p.pad in ("BAT", "GND")),
                    default=cols[0][1].x + 3.18)
        kxs = [k["x"] for k in board.keepouts] or [aux_x + 3.2]
        # C0 rises between the BAT/GND aux pads and the SWD keepouts; the rest
        # go through the window between the keepouts and the matrix-side stack.
        c0_x = (aux_x + 1.025 + min(kxs) - 1.025) / 2.0
        far_w = max(kxs) + 0.6985 + 0.325 + 0.7
        riser_x = [c0_x] + [far_w + 0.55 * j for j in range(len(cols) - 1)]
        # escape tilts: thread the keepout rows / aux-pad bands at the pads' y
        esc_dy = [0.0, 0.55, -0.99, 0.97, 0.0][:len(cols)]
    elements = []
    for k, (net, mp, top) in enumerate(cols):
        off = lane_offset(k)
        lane = outline.offset(off)
        esc_x = riser_x[k]
        join = Outline.x_cross(lane, esc_x, north=True)
        # peel descent x: normally the pad's own x (hotswap drills sit inboard
        # of pad 1 on the spine side); C0/C2 dodge drills, see constants above.
        special = None
        if k == 0:
            dx = top.x + e * C0_DESCENT_DX
            special = "c0"
        elif k == apex:
            dx = top.x + e * C2_DESCENT_DX
            special = "c2"
        else:
            dx = top.x
        peel = Outline.x_cross(lane, dx, north=True)
        lane_pts = Outline.walk(lane, join, peel)
        if esc_dy[k]:
            ty = mp.y + esc_dy[k]
            path = [mp.xy, (mp.x - e * 1.9, ty), (esc_x, ty)] + lane_pts
        else:
            path = [mp.xy, (esc_x, mp.y)] + lane_pts
        if special == "c0":
            path += [(dx, top.y + C0_TURN_DY), top.xy]
        elif special == "c2":
            jog_y = top.y + C2_JOG_DY
            path += [(dx, jog_y), (top.x, jog_y)]   # T-join onto the own spine
        else:
            path += [top.xy]
        smooth = round_corners(path)
        elements += kwrite.curve(smooth, SIG_W, "B.Cu", net.code, tol=ARC_TOL)
        if verbose:
            print(f"  {net.name}: B.Cu lane @{off:.2f} esc x={esc_x:.2f} "
                  f"peel x={dx:.2f}{' (' + special + ')' if special else ''}")
    return elements


# --- near rows R0/R1 (F.Cu, no vias) ---------------------------------------------

def route_near_rows(board: Board, verbose: bool = False) -> list[str]:
    """Rows whose MCU pad shares the matrix-side stack: a single smooth F.Cu
    curve from the MCU pad into the easternmost diode's row pad (pad 2 is a
    natural junction -- the spine's stub already lands there)."""
    e = _east_sign(board)
    rows = []
    for net in nets_of(board, NetClass.ROW):
        mp = _mcu_pad(net)
        diodes = [p for p in net.pads if p.footprint == "diode_sod123"]
        if mp is None or not diodes:
            continue
        rows.append((net, mp, max(diodes, key=lambda p: e * p.x)))
    if not rows:
        return []
    sw = [p for p in board.pads if p.footprint == "PG1350"]
    matrix_x = sum(p.x for p in sw) / len(sw)
    stack_xs = sorted({round(mp.x, 1) for _, mp, _ in rows})
    near_x = min(stack_xs, key=lambda sx: abs(sx - matrix_x))
    near = [(n, m, a) for n, m, a in rows if round(m.x, 1) == near_x]
    near.sort(key=lambda r: r[1].y)        # north first
    elements = []
    for idx, (net, mp, att) in enumerate(near):
        if e < 0:
            # Right half: the near rows leave the matrix-side stack and drop
            # down the strip between the stack and the inner column's pole
            # field. The top-of-stack row peels off to the home-row diode
            # (entering from the *south* -- its pad 1 and the neighbouring
            # matrix-link leg bar the north side); the second row rides the
            # strip all the way down, around the thumb key's pole field, into
            # the thumb-row diode.
            strip_x = mp.x + 4.48 if idx == 0 else mp.x + 3.88
            if idx == 0:
                # home-row diode: pad 1 and the neighbouring matrix-link leg
                # bar the west and north -- swing under and enter from the south
                wps = [mp.xy, (strip_x, mp.y),
                       (strip_x, att.y - 2.2),
                       (att.x - 5.65, att.y + 1.05),
                       (att.x - 1.05, att.y + 2.15),
                       att.xy]
            else:
                # thumb-row diode: pad 1 sits west and the thumb key's
                # matrix-link leg sweeps over the pad from the north-east --
                # ride the strip past the thumb key's pole field, swing south
                # and enter the pad from below (alongside its own spine stub)
                wps = [mp.xy, (strip_x, mp.y),
                       (strip_x, att.y + 3.03),
                       (att.x - 0.14, att.y + 2.33),
                       att.xy]
            path = round_corners(wps, cut=1.5)
        elif idx == 0:
            # R0: escape west of the MCU pad boxes, rise north past the inner
            # home key's matrix via, run the channel north of that key's
            # hotswap field, dive south through the gap between its choc
            # poles, then west into its own diode pad. (R1 stays entirely
            # south-east of this, so the near rows never cross.) Waypoints are
            # anchored to the MCU / destination pads, mirror-scaled by ``e``.
            wps = [mp.xy,
                   (mp.x - e * 2.18, mp.y),
                   (mp.x - e * 2.18, mp.y - 13.41),
                   (mp.x - e * 4.88, mp.y - 13.41),
                   (mp.x - e * 9.68, mp.y - 13.56),
                   (mp.x - e * 10.48, mp.y - 14.26),
                   (att.x + e * 16.35, att.y + 1.35),
                   (att.x + e * 8.35, att.y + 1.30),
                   att.xy]
            path = round_corners(wps, cut=1.8)
        else:
            wps = [mp.xy, (mp.x - e * 2.58, mp.y),
                   (mp.x - e * 5.6, mp.y - 3.45), att.xy]
            path = catmull_rom(wps, samples_per_segment=10)
        elements += kwrite.curve(path, SIG_W, att.layer, net.code, tol=ARC_TOL)
        if verbose:
            print(f"  {net.name}: {att.layer} curve MCU -> {att.ref} pad2")
    return elements


# --- boxed rows R2/R3 (B.Cu under the MCU, one via each) -------------------------

def route_boxed_rows(board: Board, outline: Outline, spines: dict,
                     verbose: bool = False) -> list[str]:
    e = _east_sign(board)
    rows = []
    for net in nets_of(board, NetClass.ROW):
        mp = _mcu_pad(net)
        diodes = [p for p in net.pads if p.footprint == "diode_sod123"]
        if mp is None or not diodes or net.name not in spines:
            continue
        rows.append((net, mp))
    if not rows:
        return []
    # the boxed stack is the MCU pad column farther from the matrix
    far_x = max((m.x for _, m in rows), key=lambda x: e * x)
    far = sorted(((n, m) for n, m in rows if abs(m.x - far_x) < 1e-6),
                 key=lambda r: r[1].y)
    # the XIAO's no-net SWD pads sit between the stacks; thread their grid
    kxs = sorted({k["x"] for k in board.keepouts if k["ref"] == "MCU1"})
    kys = sorted({k["y"] for k in board.keepouts if k["ref"] == "MCU1"})
    if e < 0:
        return _route_boxed_rows_right(board, far, spines, verbose)
    elements = []
    for net, mp in far:
        _, spine = spines[net.name]
        end, tan = _spine_end(spine, mp.xy)
        if mp.y == min(m.y for _, m in far):
            # R2 (top of the stack): tilt into the gap between the SWD pad
            # rows, cross west of them, drop between the stacks, then swing
            # out to a via clear of the home key's matrix via, joining the
            # row spine tangentially.
            gap_y = sum(kys) / len(kys) if len(kys) == 2 else mp.y
            turn_x = min(kxs, key=lambda x: -e * x) - e * 1.37 if kxs \
                else mp.x - e * 9.6
            via_pt = (end[0] + e * 9.35, end[1] - 4.75)
            path = [mp.xy, (mp.x - e * 4.0, gap_y), (turn_x, gap_y),
                    (turn_x, via_pt[1] - 2.0), via_pt]
        else:
            # R3: escape past the SWD pads, run south inboard of the SE
            # mounting hole, thread between the thumb key's rotated hotswap
            # pad 2 / matrix via (inside) and the hole + margin lanes
            # (outside), then swing to a via on the inner margin line at the
            # spine end's x.
            lane = outline.offset(_r3_offset(board, outline))
            rx = (max(kxs, key=lambda x: e * x) + e * 1.43) if kxs \
                else mp.x - e * 5.6
            mh = _se_mount_hole(board, outline, e)
            via_x = end[0] + e * 1.4
            peel = Outline.x_cross(lane, via_x, north=False)
            via_pt = peel[2]
            path = [mp.xy, (rx, mp.y), (rx, 10.0)]
            if mh is not None:
                path += [(mh[0] - e * 2.8, mh[1] - 2.5),
                         (mh[0] - e * 3.4, mh[1] + 7.5)]
            # pass south of the thumb key's matrix-link via before the lane
            path += [(via_pt[0] + e * 5.85, via_pt[1] - 3.15), via_pt]
        smooth = round_corners(path)
        elements += kwrite.curve(smooth, SIG_W, "B.Cu", net.code, tol=ARC_TOL)
        elements.append(kwrite.via(via_pt, VIA_SIZE, VIA_DRILL, net.code))
        # F.Cu tail: leave the via along the B.Cu arrival heading, arrive
        # along the spine's own tangent (river confluence).
        t0 = unit((via_pt[0] - smooth[-2][0], via_pt[1] - smooth[-2][1]))
        tail = bezier_transition(via_pt, end, t0, tan, strength=0.4)
        elements += kwrite.curve(tail, SIG_W, "F.Cu", net.code, tol=ARC_TOL)
        if verbose:
            print(f"  {net.name}: B.Cu under MCU -> via "
                  f"({via_pt[0]:.1f},{via_pt[1]:.1f}) -> F.Cu join")
    return elements


def _route_boxed_rows_right(board: Board, far, spines, verbose=False) -> list[str]:
    """Right half: the boxed rows sit on the outer (away-from-matrix) stack and
    their rows live deep in the matrix, behind the inner column's B.Cu spine
    and the bottom keys' drill fields. They go *west-about*: out the back of
    the stack, up the free margin inside the column lanes, then east over the
    top of everything along the row band.

    Planarity trick: the top row rises on **B.Cu** (one via at the top), the
    home row on F.Cu -- their west legs and risers interleave at the stack, so
    same-layer nesting is impossible. East of the rises both are F.Cu: the top
    row threads the slit between the inner home key's hotswap drill and its
    choc pole, then enters its diode pad from the north-east; the home row
    drops early, west of the bottom key's centre pole, and enters its pad from
    the north."""
    # Both rows leave the outer stack eastward on F.Cu along (or near) their
    # own pad rows, dip just enough to clear the GND branch hardware, and dive
    # north between the column risers (B.Cu, no conflict) and the matrix-side
    # stack. Nesting: the top row dives first (west) onto the NORTH lane over
    # the stack/keepouts; the home row dives east onto the SOUTH lane and
    # drops to its diode before the bottom key's pole field. Zero vias.
    gnd9 = max((p for p in board.pads
                if p.footprint == "xiao_ble" and p.net == "GND"),
               key=lambda p: p.x, default=None)
    g9x = gnd9.x if gnd9 else far[0][1].x + 15.24
    elements = []
    rows = sorted(far, key=lambda r: r[1].y)        # top row first
    for idx, (net, mp) in enumerate(rows):
        diodes = [p for p in net.pads if p.footprint == "diode_sod123"]
        att = min(diodes, key=lambda p: p.x)        # westmost = nearest
        if idx == 0:
            # top row: dip under BATT's via, north lane over everything, the
            # slit between the inner bottom key's second drill and its choc
            # pole, NE entry (pad 1 sits west)
            dive_x = g9x - 3.27
            wps = [mp.xy,
                   (mp.x + 4.52, mp.y),
                   (mp.x + 5.52, mp.y - 0.61),
                   (dive_x, mp.y - 0.61),
                   (dive_x, att.y + 0.70),
                   (att.x - 17.45, att.y + 0.70),
                   (att.x - 16.8, att.y + 2.50),
                   (att.x - 1.05, att.y + 2.50),
                   att.xy]
        else:
            # home row: ride its own row, hop north over the GND branch via,
            # dive onto the south lane, early drop west of the bottom key's
            # centre pole, south entry (pad 1 / matrix-link leg bar the north)
            dive_x = g9x - 2.67
            wps = [mp.xy,
                   (mp.x + 9.22, mp.y),
                   (mp.x + 9.92, mp.y - 1.65),
                   (dive_x, mp.y - 1.65),
                   (dive_x, att.y - 7.30),
                   (att.x - 4.65, att.y - 7.30),
                   (att.x - 4.65, att.y + 2.00),
                   (att.x, att.y + 2.00),
                   att.xy]
        elements += kwrite.curve(round_corners(wps, cut=1.4), SIG_W,
                                 "F.Cu", net.code, tol=ARC_TOL)
        if verbose:
            print(f"  {net.name}: F.Cu over the top (dive x={dive_x:.2f}) "
                  f"-> {att.ref}")
    return elements


def _se_mount_hole(board: Board, outline: Outline, e: float):
    """The mounting hole on the MCU-side south corner (the one R3 skirts)."""
    cands = [h for h in board.holes if 2.0 < h["d"] < 2.5 and h["y"] > 0]
    if not cands:
        return None
    h = max(cands, key=lambda h: e * h["x"])
    return (h["x"], h["y"])


def _r3_offset(board: Board, outline: Outline) -> float:
    """Lane offset for R3 along the south/SE margin: deep enough to clear the
    SE mounting hole on the inside (hole-to-edge distance + drill clearance +
    margin), shallow enough to stay a coherent part of the margin bundle."""
    best = None
    for h in board.holes:
        if h["d"] > 2.5 or h["d"] < 2.0:
            continue                      # mounting holes are the 2.2 mm drills
        d = _dist_to_loop((h["x"], h["y"]), outline.pts)
        if h["y"] > 0 and (best is None or d < best):
            # south-side mounting holes only
            if h["x"] > min(p[0] for p in outline.pts) + 30:
                best = d
    if best is None:
        return PWR_BASE + 2 * PWR_PITCH
    return best + (1.1 + 0.25 + SIG_W / 2) + 0.25


def _dist_to_loop(p: Point, loop: list[Point]) -> float:
    n = len(loop)
    best = float("inf")
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = dx * dx + dy * dy
        t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx +
                                                     (p[1] - a[1]) * dy) / L))
        best = min(best, math.hypot(p[0] - (a[0] + t * dx),
                                    p[1] - (a[1] + t * dy)))
    return best


# --- power (B.Cu margin bundle + F.Cu crossings, no vias) ------------------------

def route_power(board: Board, outline: Outline, verbose: bool = False) -> list[str]:
    e = _east_sign(board)
    nets = {n.name: n for n in board.nets.values()}

    def pad_of(net_name, footprint):
        net = nets.get(net_name)
        if not net:
            return None
        for p in net.pads:
            if p.footprint == footprint:
                return p
        return None

    elements = []
    raw_bt = pad_of("RAW_BATT", "battery_pads")
    raw_sw = pad_of("RAW_BATT", "power_switch_spdt")
    gnd_bt = pad_of("GND", "battery_pads")
    gnd_net = nets.get("GND")
    # pad 9 (the entry pad) is always the higher-x GND pad: the XIAO keeps its
    # orientation on both halves.
    gnd_mcu = sorted((p for p in gnd_net.pads if p.footprint == "xiao_ble"),
                     key=lambda p: -p.x) if gnd_net else []
    batt_mcu = pad_of("BATT", "xiao_ble")
    batt_sw = pad_of("BATT", "power_switch_spdt")
    sw_pads = [p for p in board.pads if p.footprint == "power_switch_spdt"]
    sw_x = sw_pads[0].x if sw_pads else None
    kxs = sorted({k["x"] for k in board.keepouts})
    kys = sorted({k["y"] for k in board.keepouts})

    # Lane assignment: the battery pad farther from the switch must take the
    # outer lane -- the nearer pad's riser drops *through* the farther pad's
    # lane span, so it has to stop short on the inner lane. (RAW is farther on
    # the left half, GND on the right.)
    raw_outer = True
    if raw_bt and gnd_bt and sw_x is not None:
        raw_outer = abs(raw_bt.x - sw_x) >= abs(gnd_bt.x - sw_x)

    # RAW_BATT: battery -> south-margin lane -> rise at the switch.
    if raw_bt and raw_sw:
        lane = outline.offset(PWR_BASE if raw_outer else PWR_BASE + PWR_PITCH)
        start = Outline.x_cross(lane, raw_bt.x, north=False)
        if e > 0:
            # left: the switch's RAW pad is northmost -- rise inboard of the
            # pad column, then a west-side entry at the pad's own y.
            rise_x = sw_x - e * 1.5
            tail = [(rise_x, raw_sw.y), raw_sw.xy]
        else:
            # right: the (flipped) switch puts RAW southmost -- rise straight
            # off the margin into the pad, nudged off the corner mounting hole.
            rise_x = sw_x - 0.15
            tail = [(rise_x, raw_sw.y + 1.5), raw_sw.xy]
        exit_ = Outline.x_cross(lane, rise_x, north=False)
        pts = Outline.walk(lane, start, exit_)
        path = [raw_bt.xy] + pts + tail
        elements += kwrite.curve(round_corners(path), PWR_W, "B.Cu",
                                 nets["RAW_BATT"].code, tol=ARC_TOL)
        if verbose:
            print("  RAW_BATT: B.Cu margin bundle -> switch")

    # GND: battery -> inner margin lane -> rise further inboard -> east-stack
    # GND pad; then an F.Cu jumper to the under-MCU GND pad (keeps the back
    # clear for the boxed-row crossings).
    if gnd_bt and gnd_mcu:
        outer = gnd_mcu[0]                     # pad 9, the entry pad
        inner = next((p for p in gnd_mcu[1:] if abs(p.x - outer.x) > 2.0), None)
        lane = outline.offset(PWR_BASE + PWR_PITCH if raw_outer else PWR_BASE)
        start = Outline.x_cross(lane, gnd_bt.x, north=False)
        if e > 0:
            # left: pad 9 faces the margin riser -- rise inboard of the switch,
            # clear of the stack's pad ovals (copper reaches 0.475 inboard of
            # the drills), west-side entry; then an F.Cu jumper around the
            # stack to the under-MCU GND pad.
            rise_x = sw_x - e * 3.3
            exit_ = Outline.x_cross(lane, rise_x, north=False)
            pts = Outline.walk(lane, start, exit_)
            path = [gnd_bt.xy] + pts + [(rise_x, outer.y), outer.xy]
            elements += kwrite.curve(round_corners(path), PWR_W, "B.Cu",
                                     nets["GND"].code, tol=ARC_TOL)
            if inner:
                jx = inner.x + 1.65
                jpath = [outer.xy, (jx, outer.y), (jx, inner.y), inner.xy]
                elements += kwrite.curve(round_corners(jpath, cut=1.6), PWR_W,
                                         "F.Cu", nets["GND"].code, tol=ARC_TOL)
        else:
            # right: pad 9 sits on the matrix-side stack, walled off on B.Cu
            # by the inner column's thumb sweep and the fan-out escapes -- and
            # a B.Cu->F.Cu via never clears RAW's neighbouring lane. So GND
            # runs entirely on F.Cu: battery riser, margin lane (the B.Cu RAW
            # rail and this make the bundle), then up the window between the
            # SWD keepouts and the stack into pad 9; the under-MCU pad joins
            # the rise with an F.Cu spur.
            # main: margin lane, rising between the SWD keepouts and the boxed
            # rows' dives, via south of every east-west run, finishing on
            # B.Cu into through-hole pad 9 (the F.Cu rows belong to the boxed
            # rows; B.Cu above the via belongs to the column escapes).
            rise_x = outer.x - 4.77
            via_pt = (rise_x, outer.y + 3.69)
            exit_ = Outline.x_cross(lane, rise_x, north=False)
            pts = Outline.walk(lane, start, exit_)
            fpath = [gnd_bt.xy] + pts + [via_pt]
            elements += kwrite.curve(round_corners(fpath), PWR_W,
                                     "F.Cu", nets["GND"].code, tol=ARC_TOL)
            elements.append(kwrite.via(via_pt, VIA_SIZE, VIA_DRILL,
                                       nets["GND"].code))
            stub = [via_pt, (outer.x - 2.32, outer.y), outer.xy]
            elements += kwrite.curve(round_corners(stub, cut=1.4), PWR_W,
                                     "B.Cu", nets["GND"].code, tol=ARC_TOL)
            if inner:
                # the under-MCU GND pad is fenced on every side at its own
                # latitude (aux pad south, stack west, SWD keepouts east, the
                # boxed rows' corridor in between). Escape NORTH on F.Cu,
                # thread the gap between the SWD pad rows, drop south just
                # east of the keepouts, and via onto a short B.Cu diagonal
                # into pad 9 (under the boxed rows' F.Cu, over the column
                # escapes' start band).
                gap_y = (sum(kys) / len(kys)) if len(kys) == 2 else inner.y - 5.1
                drop_x = max(kxs) + 1.73 if kxs else rise_x + 0.15
                via2 = (drop_x, outer.y - 1.76)
                jpath = [inner.xy, (inner.x, gap_y), (drop_x, gap_y), via2]
                elements += kwrite.curve(round_corners(jpath, cut=1.4),
                                         SIG_W, "F.Cu", nets["GND"].code,
                                         tol=ARC_TOL)
                elements.append(kwrite.via(via2, VIA_SIZE, VIA_DRILL,
                                           nets["GND"].code))
                j2 = [via2, (outer.x - 2.22, outer.y), outer.xy]
                elements += kwrite.curve(round_corners(j2, cut=1.4), SIG_W,
                                         "B.Cu", nets["GND"].code,
                                         tol=ARC_TOL)
        if verbose:
            print("  GND: B.Cu margin bundle -> MCU + F.Cu jumper")

    # BATT: under-MCU battery pad -> drop between the stacks -> side entry
    # into the switch. Left half: a single F.Cu drop (it crosses only B.Cu).
    # Right half: the drop must cross the column escapes (B.Cu) *and* the
    # boxed rows' corridor (F.Cu) -- so it crosses the first band on F.Cu,
    # vias in the slot between the two bands, and finishes on B.Cu.
    if batt_mcu and batt_sw:
        if e > 0:
            path = [batt_mcu.xy, (batt_mcu.x, batt_sw.y), batt_sw.xy]
            elements += kwrite.curve(round_corners(path, cut=3.0), PWR_W,
                                     "F.Cu", nets["BATT"].code, tol=ARC_TOL)
        else:
            via_pt = (batt_mcu.x + 1.74, batt_mcu.y + 3.99)
            elements += kwrite.curve(
                round_corners([batt_mcu.xy, (via_pt[0], batt_mcu.y + 1.79),
                               via_pt], cut=1.4),
                PWR_W, "F.Cu", nets["BATT"].code, tol=ARC_TOL)
            elements.append(kwrite.via(via_pt, VIA_SIZE, VIA_DRILL,
                                       nets["BATT"].code))
            bpath = [via_pt, (via_pt[0], batt_sw.y), batt_sw.xy]
            elements += kwrite.curve(round_corners(bpath, cut=3.0), PWR_W,
                                     "B.Cu", nets["BATT"].code, tol=ARC_TOL)
        if verbose:
            print("  BATT: between stacks -> switch")
    return elements
