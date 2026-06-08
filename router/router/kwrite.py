"""Write KiCad trace geometry as S-expressions, directly into the board text.

Per the project's design philosophy, routing output is emitted as raw
S-expressions -- no dependency on the ``pcbnew`` API (that is confined to
``extract.py`` for format normalisation + fact extraction). We append
``(segment ...)`` elements just before the board's final closing paren.
"""
from __future__ import annotations

import uuid as _uuid

from .geometry import Point, fit_arcs


def segment(a: Point, b: Point, width: float, layer: str, net_code: int) -> str:
    return (
        f'\t(segment (start {a[0]:.4f} {a[1]:.4f}) '
        f'(end {b[0]:.4f} {b[1]:.4f}) '
        f'(width {width}) (layer "{layer}") (net {net_code}) '
        f'(uuid "{_uuid.uuid4()}"))'
    )


def via(at: Point, size: float, drill: float, net_code: int,
        layers: tuple[str, str] = ("F.Cu", "B.Cu")) -> str:
    return (
        f'\t(via (at {at[0]:.4f} {at[1]:.4f}) '
        f'(size {size}) (drill {drill}) '
        f'(layers "{layers[0]}" "{layers[1]}") (net {net_code}) '
        f'(uuid "{_uuid.uuid4()}"))'
    )


def arc(start: Point, mid: Point, end: Point, width: float, layer: str,
        net_code: int) -> str:
    return (
        f'\t(arc (start {start[0]:.4f} {start[1]:.4f}) '
        f'(mid {mid[0]:.4f} {mid[1]:.4f}) '
        f'(end {end[0]:.4f} {end[1]:.4f}) '
        f'(width {width}) (layer "{layer}") (net {net_code}) '
        f'(uuid "{_uuid.uuid4()}"))'
    )


def polyline(points: list[Point], width: float, layer: str, net_code: int) -> list[str]:
    """One segment per consecutive pair of spine sample points (no arc fitting)."""
    out = []
    for a, b in zip(points, points[1:]):
        if a == b:
            continue
        out.append(segment(a, b, width, layer, net_code))
    return out


def curve(points: list[Point], width: float, layer: str, net_code: int) -> list[str]:
    """Emit a sample polyline as native ``(arc ...)`` + ``(segment ...)`` tracks,
    fitting circular arcs to curved runs (per the brief's arc-at-turns rule)."""
    out = []
    for prim in fit_arcs(points):
        if prim[0] == "arc":
            _, a, m, b = prim
            if a != b:
                out.append(arc(a, m, b, width, layer, net_code))
        else:
            _, a, b = prim
            if a != b:
                out.append(segment(a, b, width, layer, net_code))
    return out


def splice(pcb_text: str, elements: list[str]) -> str:
    """Insert ``elements`` before the final top-level closing paren."""
    idx = pcb_text.rstrip().rfind(")")
    if idx < 0:
        raise ValueError("no closing paren found in board text")
    body = pcb_text[:idx].rstrip("\n")
    return body + "\n" + "\n".join(elements) + "\n)\n"
