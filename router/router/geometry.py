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
