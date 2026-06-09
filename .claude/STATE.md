# phantom-ergogen — Work State
_Last updated: 2026-06-09 (session 2)_

## Done (this session)
- **Right-half routing DRC-clean**: fixed the matrix-link detour to steer toward
  the diode (mirror-safe), and added a **0.7mm outline relief** for the right
  pinky pads (S12/S13). Both halves now **0 DRC violations** by default
  (`b76b270`, `9f793f8`). Matrix routing complete + clean both halves.
- **Diode polarity verified** correct on both halves (silkscreen cathode bar on
  pad2/row; only column-splay tilt sign flips under mirror). Memory updated.
- **Step 11 MCU fan-out — substantial WIP, gated behind `--mcu-fanout`** (default
  output stays clean):
  - Heuristic river (`route_column_fanout`/`route_row_fanout`): connects nets,
    pretty-intent, but NOT DRC-clean at the north pinch / boxed rows.
  - **Gridded A\* router** (`router/router/fanout.py`, `7c2f865`): routes 9/9
    fan-out nets on the left (ratsnest 13→4 power-only) at **4 DRC violations**
    (boxed row R2). Extraction extended: NPTH holes, Edge.Cuts, pad sizes.
    Reliable + DRC-clean-ish but **grid-zigzag UGLY**.

## In flight — PRIORITY: make THIS board's fan-out PRETTY (river-delta)
User directives (see memory [[autorouter-subproject]]):
- **Pretty & best-practices is the goal**, not a deferrable follow-up. River-delta:
  parallel offset arc lanes, arcs/45° at turns, bundling, flow (brief 125–129).
- **Components cannot move** (MCU/pinout/switches fixed). Boxed right-stack rows
  R2/R3 must escape via **B.Cu under the MCU**.
- **Outline relief allowed** (not a component) — use it to open the ~2.2mm
  hole-dense north pinch (like the pinky relief).
- Generic tool secondary (may split to its own repo); A\* = fallback for boxed
  nets only; geometric river = primary.

## Next (pretty-river build — fresh, focused)
1. **Column river, left half, DRC-clean**: revive converging-lane river; switch
   vertical→**perpendicular** offset (vertical pinches <0.2 on steep flanks);
   apply north-edge outline relief to clear the pinch + choc poles; arc-fit for
   flow. Validate with `fanout.py`'s obstacle grid.
2. Easy rows (R0/R1) as smooth curves; **R2/R3 via B.Cu under the MCU** (A\*
   fallback acceptable for these boxed nets).
3. Mirror to right half (geometry-derived, verify DRC both halves).
4. Beautify (arc-fit/bundle) + render checkpoint; then steps 12–16.

## Validation gate
DRC (`kicad-cli pcb drc`) on routed vs bare to isolate ours. PLUS visual render
(`render_checkpoint`) — "pretty" is now an explicit acceptance criterion.

## References
- Active plan: .claude/plans/autorouter.md
- Memory: autorouter-subproject.md (priorities/constraints), phantom-right-half-mirror.md
- Router how-to: router/README.md ; fan-out: router/router/fanout.py
