# phantom-ergogen — Work State
_Last updated: 2026-06-11 (session 3)_

## DONE — BOTH HALVES FULLY ROUTED, pretty, 0 DRC / 0 unconnected

The board is complete: matrix + **river-delta MCU fan-out** + boxed rows +
power, both halves. `kicad-cli pcb drc --severity-error` = **0 violations,
0 unconnected** on `router/routed_left.kicad_pcb` and `routed_right.kicad_pcb`
(committed, with `checkpoint_*.png` renders).

- **`router/router/river.py`** is the fan-out/power module: column lanes are
  constant offsets of the board outline (base 0.66, pitch 0.55, nested by MCU
  stack order → no crossings), corner rounding via quadratic-Bézier fillets,
  native-arc output. Columns are **all-B.Cu, zero vias** (the MCU pads are
  through-hole). Left half: 15 matrix vias only. Right: +4 (R0/BATT/GND×2).
- **Right half ≠ mirror**: footprint internals don't mirror (drills/pad2 stay
  east of pad1, MCU keeps orientation, switch flips). Column/row/power roles
  of the MCU stacks swap; right-specific waypoint branches in river.py.
- **board_right got +0.3mm top-edge outline relief** (config.yaml, ergogen
  rebuilt via `npm run build`) — the right pinch was 0.13mm too tight for two
  lanes. Same precedent as the 0.7mm pinky relief; no case dependency.
- A* `fanout.py` kept as documented fallback only; dead heuristic fan-out
  removed from cli.py. New `check.py` = exact clearance self-checker.
- Render checkpoint fixed (was silently clipping for the whole project):
  plots a page-shifted copy (`extract.shift_into_page`).

## Validation
`python3 -m router.cli ../output/pcbs/phantom_{left,right}.kicad_pcb -o … --render …`
then `kicad-cli pcb drc --severity-error …`. Renders + DRC both clean as of
the final commit this session.

## Possible follow-ups (none blocking)
- GND pour (brief step 14) — optional layering on top of clean routed rails.
- Step 16 YAML config: promote river waypoint constants.
- Steps 12/13 (USB/interconnect) don't exist on this board (XIAO + wireless).

## References
- Router how-to + load-bearing gotchas: `router/README.md` (rewritten)
- Memory: autorouter-subproject.md, phantom-right-half-mirror.md
- Plan archive: .claude/plans/autorouter.md (historic; superseded by README)
