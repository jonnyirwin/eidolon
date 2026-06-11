# ergogen-route

A domain-specific autorouter for Ergogen keyboard PCBs. It exploits keyboard
matrix regularity rather than solving general routing — see `../autorouter-prompt.md`
for the full design brief.

**Status: BOTH HALVES FULLY ROUTED, 0 DRC violations, 0 unconnected items.**
Matrix (columns B.Cu / rows F.Cu as smooth arc spines, per-key transition vias,
thumb Béziers), the **river-delta MCU fan-out**, the boxed-row escapes and all
power rails. The committed `routed_left.kicad_pcb` / `routed_right.kicad_pcb`
and `checkpoint_*.png` are the current outputs.

## Quick start

```bash
# system python3 here already has pcbnew 9 + numpy + pyyaml
python3 -m router.cli ../output/pcbs/phantom_left.kicad_pcb \
    -o routed_left.kicad_pcb --render checkpoint_left.png --verbose
python3 -m router.cli ../output/pcbs/phantom_right.kicad_pcb \
    -o routed_right.kicad_pcb --render checkpoint_right.png

# validate
kicad-cli pcb drc --severity-error routed_left.kicad_pcb
```

`--render` produces a top-down PNG (B.Cu + F.Cu + Edge.Cuts); `--matrix-only`
skips the fan-out/power for the bare matrix.

## Architecture

```
extract.py   pcbnew: normalise format (5.1.6 -> KiCad 9), dump pad facts JSON
   │            (the ONLY module touching pcbnew; also page-shifts render copies)
model.py     pure-data domain types (Pad, Net, NetClass, Board)
classify.py  net -> NetClass, layer read from actual pad copper, not assumed
geometry.py  PCA ordering, Catmull-Rom/Bézier sampling, native-arc fitting
kwrite.py    emit (segment/arc/via ...) S-expressions, splice into board text
river.py     MCU fan-out + power: edge-offset river lanes, corner rounding
cli.py       matrix spines + matrix-link vias, orchestration, render checkpoint
check.py     exact-clearance self-check (true distances; DRC positions are vague)
fanout.py    gridded A* router (documented fallback; not used by the default run)
```

## The river (step 11+) — how the fan-out works

- **Columns ride B.Cu lanes offset from the board outline** (`Outline.offset`),
  base 0.66 mm, pitch 0.55 mm, nested in MCU-pad-stack order so peels never
  cross. Each column escapes the stack through a riser window, joins its lane,
  flows along the NE diagonal + top edge, and drops straight into its column's
  top switch pad. **Zero vias** — every MCU pad is a *through-hole* castellated
  pad, so the fan-out starts on B.Cu directly.
- The two outermost lanes squeeze the **north pinch** (apex key's hotswap drill
  vs the top edge) with a 0.5 mm local pitch; `board_right` got a +0.3 mm
  outline relief there (footprints don't mirror, so the right half's pinch was
  0.13 mm tighter — `config.yaml`, same precedent as the pinky relief).
- **Rows/power** are hand-shaped waypoint paths (mirror-aware where geometry
  allows, half-specific where it doesn't), rounded by `round_corners`
  (quadratic-Bézier fillets) and emitted as native arcs.
- The left half routes with **15 matrix vias only**; the right half adds 4
  (R0's lane change, BATT and GND×2 layer hops around the boxed MCU region).

### Key findings (non-obvious, load-bearing)

- **Every MCU/power/battery pad is through-hole** (`cu_layers` spans the full
  stack) and the XIAO's pads are **offset ovals** — copper centres sit 0.475 mm
  inboard of the drill (`pad.GetOffset()`); obstacle maths must use the copper
  centre (`Pad.cx/cy`), connections the drill.
- The XIAO has **no-net PTH pads** (RESET/SWCLK/SWDIO/DBG_GND) between its pad
  stacks — copper obstacles on every layer, exported as `keepouts`.
- **Footprint internals do not mirror** on the right half (only placements do):
  hotswap drills/pad 2 stay east of pad 1, the MCU keeps its orientation, the
  power switch flips. The right half is a different routing problem, not a
  reflection: columns face away from the matrix and the row/power roles of the
  two MCU stacks swap.
- **The arc fitter needs dense samples and a sagitta floor**: board files round
  coordinates to 4 decimals, and a huge-radius arc through three near-collinear
  rounded points reconstructs as a *different* circle (millimetres off). Fixed
  by densifying before `fit_arcs`, picking `mid` at the arc-length midpoint,
  and refusing arcs flatter than 0.12 mm sagitta.
- **The layer convention is inverted vs the prompt**: switch (PG1350) pads on
  **B.Cu**, diode (SOD-123) pads on **F.Cu**. `pad.GetLayer()` lies for SMD
  pads; `GetLayerSet().CuStack()` is authoritative.
- No headless format upgrade verb — `pcbnew` load+save round-trip upgrades
  5.1.6 → KiCad 9. Renders plot a **page-shifted copy** (Ergogen places the
  board at negative coordinates; the plotter silently clips off-page content).
- Validate with `kicad-cli pcb drc --severity-error` (the gate) plus
  `check.py` when tuning: DRC report positions are item anchors, useless for
  locating a 0.05 mm encroachment.

## Remaining ideas (not blocking)

- Step 12/13 (USB, interconnect) don't exist on this board (XIAO carries USB;
  halves are wireless). Step 14's GND pour was skipped — DRC is clean with
  routed rails; a pour can be layered on later.
- Step 16: promote the hand-tuned waypoint constants into the YAML config.
