"""Domain model for the keyboard router (pure data, no KiCad dependency)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class NetClass(str, Enum):
    COLUMN = "column"            # switch matrix column  (this board: B.Cu)
    ROW = "row"                  # diode matrix row      (this board: F.Cu)
    MATRIX_LINK = "matrix_link"  # switch<->diode intermediate net (needs a via)
    POWER = "power"              # VCC / GND / battery rails
    USB = "usb"                  # D+/D- to USB connector
    INTERCONNECT = "interconnect"  # split half-to-half signalling
    MCU = "mcu"                  # everything else terminating on the MCU
    SERIAL_CHAIN = "serial_chain"  # FUTURE: LED / OLED data (extension point)
    OTHER = "other"


@dataclass
class Pad:
    ref: str
    footprint: str
    pad: str
    net: str
    net_code: int
    layer: str
    cu_layers: list[str]
    x: float
    y: float
    fp_x: float
    fp_y: float
    fp_rot: float
    sx: float = 0.0
    sy: float = 0.0

    @property
    def xy(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Net:
    name: str
    code: int
    pads: list[Pad] = field(default_factory=list)
    klass: NetClass = NetClass.OTHER

    @property
    def layers(self) -> set[str]:
        return {p.layer for p in self.pads}


@dataclass
class Board:
    pads: list[Pad]
    nets: dict[str, Net]
    normalised_pcb: str
    bbox: dict
    holes: list[dict] = field(default_factory=list)   # no-net drills: {x,y,d}
    edge: list = field(default_factory=list)          # Edge.Cuts chords: ((x,y),(x,y))

    @classmethod
    def from_json(cls, path: str) -> "Board":
        data = json.load(open(path))
        pads = [Pad(**p) for p in data["pads"]]
        nets: dict[str, Net] = {}
        for p in pads:
            net = nets.get(p.net)
            if net is None:
                net = nets[p.net] = Net(name=p.net, code=p.net_code)
            net.pads.append(p)
        return cls(
            pads=pads,
            nets=nets,
            normalised_pcb=data["normalised_pcb"],
            bbox=data["board_bbox_mm"],
            holes=data.get("holes", []),
            edge=[tuple(map(tuple, seg)) for seg in data.get("edge", [])],
        )
