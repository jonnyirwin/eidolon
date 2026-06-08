"""Net classification.

The Ergogen YAML names nets semantically, which we exploit -- but we *verify*
the routing layer from the actual pad copper stack rather than assuming the
prompt's F.Cu/B.Cu convention (this board is inverted: columns on B.Cu, rows on
F.Cu). See ``extract.py`` for why the pad layer is authoritative.
"""
from __future__ import annotations

import re

from .model import Net, NetClass, Board

# Power rails on this board (XIAO BLE). Configurable later via the config system.
POWER_NETS = {"GND", "VCC", "P5V", "P3V3", "BATT", "RAW_BATT", "PWR_NC", "RST"}
USB_NETS = {"USB_DP", "USB_DM", "D+", "D-"}

_COL_RE = re.compile(r"^C\d+$")
_ROW_RE = re.compile(r"^R\d+$")


def classify_net(net: Net) -> NetClass:
    name = net.name
    if _COL_RE.match(name):
        return NetClass.COLUMN
    if _ROW_RE.match(name):
        return NetClass.ROW
    if name in POWER_NETS:
        return NetClass.POWER
    if name in USB_NETS:
        return NetClass.USB
    # Intermediate switch<->diode nets straddle both copper layers within a
    # single key; they are the per-key via links.
    if len(net.layers) > 1:
        return NetClass.MATRIX_LINK
    # Heuristic: semantic matrix-link names that happen to sit on one layer.
    if any(tok in name for tok in ("matrix_", "_thumb", "ring_ring", "pinky_pinky")):
        return NetClass.MATRIX_LINK
    return NetClass.MCU


def classify(board: Board) -> Board:
    for net in board.nets.values():
        net.klass = classify_net(net)
    return board


def nets_of(board: Board, klass: NetClass) -> list[Net]:
    return [n for n in board.nets.values() if n.klass is klass]
