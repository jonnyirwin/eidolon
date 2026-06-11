"""Geometry: order pads along a column axis, fit a smooth spine, sample it.

A *spine* is a smooth curve threading through a net's pads. We order the pads
along the group's principal axis (PCA) so stagger/splay/rotation are handled
generically, then fit a centripetal Catmull-Rom spline (alpha=0.5 avoids the
cusps/overshoot plain Catmull-Rom produces on unevenly spaced points).

For a single near-collinear column the spline is essentially straight -- that is
the correct output. The flowing-"river" look is a cross-net offset effect that
arrives with multi-net corridors (later milestone), not from bending a lone
column.
"""
from __future__ import annotations

import math

Point = tuple[float, float]


def principal_axis(pts: list[Point]) -> Point:
    """Unit vector of the dominant spread direction (PCA, 2x2 covariance)."""
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts) / n
    syy = sum((p[1] - cy) ** 2 for p in pts) / n
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts) / n
    # Larger eigenvalue of [[sxx,sxy],[sxy,syy]].
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    lam = tr / 2 + math.sqrt(max(0.0, (tr / 2) ** 2 - det))
    # Eigenvector for lam.
    if abs(sxy) > 1e-12:
        vx, vy = lam - syy, sxy
    elif sxx >= syy:
        vx, vy = 1.0, 0.0
    else:
        vx, vy = 0.0, 1.0
    norm = math.hypot(vx, vy) or 1.0
    return (vx / norm, vy / norm)


def order_along_axis(pts: list[Point]) -> list[Point]:
    """Sort points by projection onto their principal axis."""
    if len(pts) < 3:
        return list(pts)
    ax = principal_axis(pts)
    return sorted(pts, key=lambda p: p[0] * ax[0] + p[1] * ax[1])


def catmull_rom(pts: list[Point], samples_per_segment: int = 8) -> list[Point]:
    """Centripetal Catmull-Rom spline through ``pts`` (passes through each)."""
    if len(pts) < 3:
        return list(pts)

    def tj(ti: float, a: Point, b: Point) -> float:
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        return ti + math.sqrt(d)  # alpha=0.5 (centripetal)

    # Phantom endpoints by reflection so the curve reaches the real end pads.
    p = [(2 * pts[0][0] - pts[1][0], 2 * pts[0][1] - pts[1][1]), *pts,
         (2 * pts[-1][0] - pts[-2][0], 2 * pts[-1][1] - pts[-2][1])]

    out: list[Point] = [pts[0]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        t0 = 0.0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        for s in range(1, samples_per_segment + 1):
            t = t1 + (t2 - t1) * s / samples_per_segment
            a1 = _lerp(p0, p1, t0, t1, t)
            a2 = _lerp(p1, p2, t1, t2, t)
            a3 = _lerp(p2, p3, t2, t3, t)
            b1 = _lerp(a1, a2, t0, t2, t)
            b2 = _lerp(a2, a3, t1, t3, t)
            out.append(_lerp(b1, b2, t1, t2, t))
    return out


def _lerp(a: Point, b: Point, ta: float, tb: float, t: float) -> Point:
    if tb == ta:
        return a
    w = (t - ta) / (tb - ta)
    return (a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w)


def unit(v: Point) -> Point:
    n = math.hypot(v[0], v[1]) or 1.0
    return (v[0] / n, v[1] / n)


def rotate(v: Point, deg: float) -> Point:
    """Rotate a vector by ``deg`` degrees (KiCad's y-down frame)."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def cubic_bezier(p0: Point, c0: Point, c1: Point, p1: Point,
                 samples: int = 12) -> list[Point]:
    """Sample a cubic Bézier; passes through ``p0`` and ``p1`` exactly."""
    out: list[Point] = []
    for s in range(samples + 1):
        t = s / samples
        mt = 1 - t
        a, b, c, d = mt * mt * mt, 3 * mt * mt * t, 3 * mt * t * t, t * t * t
        out.append((a * p0[0] + b * c0[0] + c * c1[0] + d * p1[0],
                    a * p0[1] + b * c0[1] + c * c1[1] + d * p1[1]))
    return out


def circle_from_3(a: Point, b: Point, c: Point):
    """Centre + radius of the circle through 3 points, or None if collinear."""
    ax, ay = a; bx, by = b; cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


def _point_seg_dist(p: Point, a: Point, b: Point) -> float:
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    if L < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


MIN_ARC_SAGITTA = 0.12  # arcs flatter than this are emitted as segments: the
                        # board file rounds coordinates to 4 decimals, and a
                        # huge-radius arc through three near-collinear rounded
                        # points reconstructs as a *different* circle that can
                        # bulge millimetres off the sampled path


def _arc_mid_index(pts: list[Point], i: int, j: int) -> int:
    """Sample index nearest the arc-length midpoint of ``pts[i..j]`` -- a
    numerically stable ``mid`` for the KiCad arc encoding (the index midpoint
    can sit next to one endpoint when sampling is uneven)."""
    total = 0.0
    cum = [0.0]
    for k in range(i, j):
        total += math.dist(pts[k], pts[k + 1])
        cum.append(total)
    half = total / 2.0
    best = min(range(1, len(cum) - 1), key=lambda k: abs(cum[k] - half),
               default=1)
    return i + best


def fit_arcs(pts: list[Point], tol: float = 0.05):
    """Greedily collapse a dense sample polyline into native circular arcs and
    straight segments. At each step it grows *both* a straight run (points within
    ``tol`` mm of the chord) and a circular arc (points within ``tol`` of the
    circle through start/mid/end), then keeps whichever reaches further -- so a
    dead-straight column becomes one segment and a curve becomes a few arcs.
    Near-straight arcs (sagitta < MIN_ARC_SAGITTA) are rejected in favour of
    segments. Endpoints are preserved exactly, so a fitted spine still begins
    and ends on its pads. Yields ``("arc", start, mid, end)`` or
    ``("seg", start, end)``."""
    out = []
    n = len(pts)
    i = 0
    while i < n - 1:
        # Grow a straight segment as far as the chord stays within tol.
        seg_j = i + 1
        while seg_j + 1 < n and all(
                _point_seg_dist(p, pts[i], pts[seg_j + 1]) <= tol
                for p in pts[i + 1:seg_j + 1]):
            seg_j += 1
        # Grow a circular arc as far as the circle stays within tol.
        arc_choice, arc_j = None, i + 1
        j = i + 2
        while j < n:
            mid = pts[_arc_mid_index(pts, i, j)]
            circ = circle_from_3(pts[i], mid, pts[j])
            if circ is None:
                break
            (cx, cy), r = circ
            if any(abs(math.hypot(p[0] - cx, p[1] - cy) - r) > tol
                   for p in pts[i + 1:j]):
                break
            sag = max(_point_seg_dist(p, pts[i], pts[j])
                      for p in pts[i + 1:j])
            arc_choice, arc_j = (("arc", pts[i], mid, pts[j]), j) \
                if sag >= MIN_ARC_SAGITTA else (arc_choice, arc_j)
            j += 1
        if arc_choice is not None and arc_j > seg_j:
            out.append(arc_choice)
            i = arc_j
        else:
            out.append(("seg", pts[i], pts[seg_j]))
            i = seg_j
    return out


def bezier_transition(p0: Point, p1: Point, t0: Point, t1: Point,
                      strength: float = 0.4, samples: int = 12) -> list[Point]:
    """Smooth cubic Bézier joining two spines: leaves ``p0`` along ``+t0`` and
    arrives at ``p1`` along ``+t1`` (t1 is the heading the curve continues *past*
    p1, so the control point is pulled back along ``-t1``). ``t0``/``t1`` are the
    two spines' local-frame tangents; this is the thumb-cluster transition."""
    d = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    k = strength * d
    c0 = (p0[0] + t0[0] * k, p0[1] + t0[1] * k)
    c1 = (p1[0] - t1[0] * k, p1[1] - t1[1] * k)
    return cubic_bezier(p0, c0, c1, p1, samples)
