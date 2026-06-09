# phantom-ergogen — Work State
_Last updated: 2026-06-09_

## Done (this session)
- **Left half routes fully DRC-clean** (0 violations). Matrix cols (B.Cu) + rows
  (F.Cu) as arcs, per-key transition vias, thumb Béziers. Routing fixes: matrix
  link south-detour + via-drop-to-F.Cu, row offset 2.0, thumb strength (6d731b2);
  native arc output (9e574bc); silk footprint fixes (ec655b7).
- **Two hardware bugs the user caught, fixed:** BAT/RST pads swapped on xiao_ble
  footprint (ab26cde); mounting-hole + battery positions corrected to match the
  case — board↔case transform `case = board + (80, 58.97)` (a3b6876).
- **Right-half outline mirror bug fixed** (f967410): board_right shifts were
  pre-negated AND auto-flipped by Ergogen → ~18mm off, MCU off-board. Now correct.
- Router confirmed to **port structurally to the mirrored right half**.

## In flight
- **Right half**: footprint placement is now correct per the user's intent (see
  memory [[phantom-right-half-mirror]] — non-reversible split; sockets/MCU/battery
  KEEP orientation, only power switch flips; all already correct). Outline fixed.
  But the right half is **not yet DRC-clean** and routing wasn't re-evaluated on
  the corrected board.
- `main` is ~9 commits ahead of origin; nothing pushed (user hasn't asked).

## Next
1. Re-run right-half routing on the corrected board, re-check DRC. Each switch's
   *local* geometry now matches the left, so it should behave like the left — the
   earlier "~10 right-half routing violations" were measured pre-fix; re-verify.
2. Resolve 2 pinky matrix-pad outer-edge near-misses (sub-0.02mm) — small outline
   relief or accept. Inherent to sockets keeping orientation while position mirrors.
3. Continue roadmap: 11 MCU fan-out (river aesthetic), 12 USB, 13 interconnect,
   14 power+GND pour, 15 DRC, 16 YAML config (lifts the Phantom-tuned constants).

## Validation gate
DRC is the gate (`kicad-cli pcb drc`), not connectivity alone — connectivity
closure misses shorts. Compare routed vs bare-board DRC to isolate "ours".

## References
- Active plan: .claude/plans/autorouter.md
- Memory: phantom-right-half-mirror.md (right-half mirror intent)
- Router how-to + transform notes: router/README.md
