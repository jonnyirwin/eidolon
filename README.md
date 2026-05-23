# Phantom — Ergogen recreation

An [Ergogen](https://ergogen.xyz) recreation of
[davidphilipbarr/Phantom](https://github.com/davidphilipbarr/Phantom), a small
column-staggered split using Kailh Choc switches.

This **baseline** reproduces the original hardware faithfully. Planned
modifications (BLE, diodes, etc.) are tracked below and live on later commits.

## Build

The board uses one custom footprint (`footprints/reset_button.js`, a compact SMD
reset), so build via the wrapper, which injects `footprints/*.js` before running
Ergogen (the npm CLI doesn't auto-load an external footprint folder):

```sh
npm install        # once
node build.js      # -> output/
```

On **ergogen.xyz**, paste `footprints/reset_button.js` into the web app's
Footprints section (name it `reset_button`); the rest of `config.yaml` works as-is.

Outputs land in `output/`:
- `outlines/board_left.svg|dxf`, `board_right.svg|dxf` — board / case perimeters
- `pcbs/phantom_left.kicad_pcb`, `phantom_right.kicad_pcb` — both halves, footprints
  + nets placed (route in KiCad)
- `points/` — key coordinates (with `--debug`)

Both halves come from one config: a `points.mirror` axis creates `mirror_*`
points, and `phantom_right` reuses the left footprint definitions filtered to the
mirrored points (Ergogen auto-flips footprint sides / x-offsets).

## How it was derived

- **Geometry** is reverse-engineered from `lephantom.kicad_pcb` switch
  coordinates, then idealised into clean Ergogen `stagger`/`spread`/`splay`
  parameters. Reconstructed key centres match the original to **< 0.15 mm**.
- **Wiring** matches the QMK firmware
  ([jonnyirwin/phantom_qmk_config](https://github.com/jonnyirwin/phantom_qmk_config)),
  which uses `DIRECT_PINS` — every switch wired straight to one Pro Micro GPIO
  plus GND, **no diode matrix**.

### Layout

```
 pinky  ring  middle index inner
   ·    top    top   top   ·       (pinky has no top; inner has no bottom)
 home  home   home  home  upper
 bot   bot    bot   bot   lower
                  thumbL thumbR    (-8°)
```

Pinky splayed 5°, ring splayed 3°; the other columns are straight. Choc
spacing: 18 mm columns, 17 mm rows.

### Pin map (QMK atmega → Arduino Pro Micro → Ergogen net)

| Key            | QMK | Ergogen net |
|----------------|-----|-------------|
| pinky upper    | E6  | P7  |
| pinky lower    | B1  | P15 |
| ring top       | F7  | P18 |
| ring home      | B3  | P14 |
| ring bottom    | D7  | P6  |
| middle top     | F6  | P19 |
| middle home    | B2  | P16 |
| middle bottom  | D4  | P4  |
| index top      | F5  | P20 |
| index home     | B6  | P10 |
| index bottom   | C6  | P5  |
| inner upper    | F4  | P21 |
| inner lower    | D3  | P3  |
| thumb left     | B4  | P8  |
| thumb right    | B5  | P9  |
| (split serial) | D2  | P2  |

## Deviations from the original

- **Mirrored L/R, not a single reversible board.** The original is one PCB
  flipped for both hands; this generates a left board and a mirrored right board.
  Functionally identical. **Firmware note:** because the original is reversible,
  QMK's `split.matrix_pins.right.direct` is the *reversed* row order of the left.
  With a true mirrored pair, the same physical-position→pin map holds on both
  halves, so the right-hand config should *mirror* the left, not reverse it.
- **Trackball omitted** (its footprint position is left empty).
- **Outline** is the original `Edge.Cuts` polygon traced exactly (corners
  rounded with a 1.5 mm fillet) — almost identical to the original board edge.

## Planned changes (each on its own commit)

1. ✅ baseline — Pro Micro, TRRS split, direct pins, hotswap Choc
2. hotswap sockets (already `hotswap: true`; verify socket clearance)
3. Seeed XIAO nRF52840 BLE + battery (Rufous-style) — **requires a diode matrix**
   (XIAO has too few GPIO for 15 direct pins)
4. power switch
5. Totem-style sandwich case (additional `outlines` layers → DXF/SVG)
