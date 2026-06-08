"""Write KiCad trace geometry as S-expressions, directly into the board text.

Per the project's design philosophy, routing output is emitted as raw
S-expressions -- no dependency on the ``pcbnew`` API (that is confined to
``extract.py`` for format normalisation + fact extraction). We append
``(segment ...)`` elements just before the board's final closing paren.
"""
from __future__ import annotations

import uuid as _uuid

from .geometry import Point


def segment(a: Point, b: Point, width: float, layer: str, net_code: int) -> str:
    return (
        f'\t(segment (start {a[0]:.4f} {a[1]:.4f}) '
        f'(end {b[0]:.4f} {b[1]:.4f}) '
        f'(width {width}) (layer "{layer}") (net {net_code}) '
        f'(uuid "{_uuid.uuid4()}"))'
    )


def polyline(points: list[Point], width: float, layer: str, net_code: int) -> list[str]:
    """One segment per consecutive pair of spine sample points."""
    out = []
    for a, b in zip(points, points[1:]):
        if a == b:
            continue
        out.append(segment(a, b, width, layer, net_code))
    return out


def splice(pcb_text: str, elements: list[str]) -> str:
    """Insert ``elements`` before the final top-level closing paren."""
    idx = pcb_text.rstrip().rfind(")")
    if idx < 0:
        raise ValueError("no closing paren found in board text")
    body = pcb_text[:idx].rstrip("\n")
    return body + "\n" + "\n".join(elements) + "\n)\n"
