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
- **Wiring** is a COL2ROW diode matrix to a Seeed XIAO nRF52840 (BLE). The
  original Pro Micro baseline instead matched the QMK firmware
  ([jonnyirwin/phantom_qmk_config](https://github.com/jonnyirwin/phantom_qmk_config))
  which used `DIRECT_PINS`; that's preserved in git history.

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

### Wiring — diode matrix (XIAO BLE)

Each half is an independent wireless unit (its own XIAO + battery, no TRRS).
COL2ROW diode matrix: the switch joins its column net to a per-key node, and the
diode joins that node to the row net.

| Matrix | Net | XIAO pin |
|--------|-----|----------|
| pinky col   | C0 | D0 |
| ring col    | C1 | D1 |
| middle col  | C2 | D2 |
| index col   | C3 | D3 |
| inner col   | C4 | D4 |
| top row     | R0 | D5 |
| home row    | R1 | D6 |
| bottom row  | R2 | D7 |
| thumb row   | R3 | D8 |

Power: battery + → `RAW_BATT` → slide switch → `BATT` → XIAO `B+`; battery − → GND.

> **Verify before fab:** the XIAO pad→pin mapping in `footprints/xiao_pogo.js`
> assumes the standard castellation mounted face-down; confirm against the XIAO
> datasheet. The earlier Pro Micro baseline used QMK `DIRECT_PINS` (see git history).

## Finishing in KiCad (routing + ground plane)

Ergogen places footprints and assigns nets only — it neither routes traces nor
pours copper. After `node build.js`, open the board in KiCad and:

1. **Route** the matrix — by hand, or export **Specctra DSN** → **Freerouting**
   → import the **`.ses`** session back.
2. **Add a GND copper pour** on both copper layers, matching the original
   Phantom's zone (`net 6 "GND"`, `F&B.Cu`):

   | Zone setting          | Value          |
   |-----------------------|----------------|
   | Net                   | `GND`          |
   | Layers                | `F.Cu` + `B.Cu` |
   | Clearance             | 0.508 mm       |
   | Minimum width         | 0.254 mm       |
   | Pad connection        | Thermal relief |
   | Thermal relief gap    | 0.508 mm       |
   | Thermal spoke width   | 0.508 mm       |
   | Remove islands        | Yes            |
   | Outline hatch (border)| Edge           |

   Draw the zone over the whole board outline on each layer, then **Fill All
   Zones** (`B`). The XIAO footprint carries a copper-pour **keepout**, so the
   fill automatically skips the nRF52840 antenna — leave that keepout in place.
3. **Run DRC** to confirm full connectivity and clearances.

## Case (Totem-style, OpenSCAD)

`case/case_left.scad` is a parametric case that **imports the Ergogen outline
DXFs** (so it tracks the board). It follows the **Phantom outline/key layout**
but takes its **proportions from the real Totem BLE STEP** (rim ≈ 14 mm tall,
sunken switchplate, ~2.4 mm walls — measured in FreeCAD):

- **Top body**: a chamfered shell with a **recessed switchplate** (14 mm Choc
  holes) set ~`recess` below a **raised rim**, so the key cluster is a sunken
  recess and the keycaps sit nearly flush with the rim (the Totem look). The
  controller wing is closed on top; USB cutout at the top edge, power-switch
  slot on the right.
- **Bottom**: a **deep tray** (Totem BLE-style, ~5.5 mm) — floor + perimeter
  walls with an open cavity for the **LiPo battery**; the hotswap sockets hang in
  the cavity. Chamfered bottom edge.
- **Join**: four **M2 screw bosses** (posts with pilot holes in the top; clearance
  + head counterbores on the tray's outer bottom).

Three Ergogen outlines feed it: `plate_left` (board − 14 mm switch holes),
`socketpockets_left` (socket cutouts), `keyfield_left` (merged key-cluster
recess). Key params at the top of the .scad: `recess`, `wall`, `chamf`,
`plate_gap`, `rim_t`.

```sh
node build.js                                              # regenerate DXFs first
openscad -o case_preview.png case/case_left.scad           # exploded preview
openscad -D 'part="bottom"' -o bottom_left.stl case/case_left.scad
openscad -D 'part="top"'    -o top_left.stl    case/case_left.scad
```

Key params (top of the .scad): `wall`, `floor_t`, `pcb_t`, `gap`, `plate_t`,
`sock_d`. Total height ≈ `floor_t + pcb_t + gap + plate_t` ≈ 8 mm.

**Still to do on the case:**
- **PCB mounting** — the screw posts sit just inside the edge; confirm they clear
  the PCB or add matching mounting holes in the Ergogen board.
- **Battery retention** — the cavity is open; add a shelf/retainer for the cell.
- **USB cutout Z** depends on the pogo/standoff height that lifts the XIAO.
- **Right half** — generate `*_right` outlines + a mirrored `case_right.scad`.
- Total height runs taller than the Totem's 12.7 mm because the halves stack
  (not nested) and assume a real ~3.5 mm cell; pick a thinner cell or nest to
  match. The real Totem top also has subtle freeform curvature; this matches the
  construction + proportions with chamfers rather than a full organic sculpt.
- **Battery** — a LiPo (~3–4 mm) won't fit the 2.2 mm gap under the plate; it
  needs a floor pocket or a bump-out. Decide cell size/location first.
- **USB cutout height** — the XIAO sits on pogo pins *above* the PCB, so the USB
  opening's Z depends on the chosen pogo/standoff height.
- **Right half** — generate `plate_right`/`socketpockets_right` and a mirrored
  `case_right.scad` once the left is dialled in.

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
2. ✅ Seeed XIAO nRF52840 BLE (pogo pins, footprint adapted from Rufous) +
   battery + 3-pin slide power switch, with a COL2ROW diode matrix. TRRS, Pro
   Micro and the dedicated reset are removed (XIAO uses double-tap reset).
3. Totem-style 3D-printed clamshell case (top bezel + bottom tray per half),
   modelled in CAD around `output/outlines/board_*.dxf`. Diodes are mounted
   **top-side in each Choc south LED gap** and the hotswap sockets are the only
   thing on the bottom — so the bottom tray needs just **socket pockets** (no
   diode reliefs), and the diodes stay clear of the switch-swap path.

### Still to refine on the BLE board
- Verify XIAO pad→pin mapping against the datasheet (`footprints/xiao_pogo.js`).
- Power-switch edge position — currently top of the controller wing; nudge to the
  exact case side and extend the outline if the actuator must clear the wall.
- Battery footprint marks solder pads only; confirm the physical cell fits / mounts.
- Route the matrix (hand or Freerouting) and add pours, then DRC.
