# Project state — phantom-ergogen

## In flight
**ergogen-route autorouter** (`router/`). Steps 1–9 built and validated:
columns on B.Cu + rows on F.Cu (Catmull-Rom) + 15 per-key transition vias +
**thumb keys split into their own spine joined by a Bézier** in the thumb's
local frame. 170 segs + 15 vias, 16 unconnected (all deferred MCU/power/USB),
reloads cleanly. Step 7 = `route_spine`; Step 8 = `route_matrix_links`; Step 9 =
`bezier_transition`/`cubic_bezier`/`rotate`/`unit` in geometry + thumb detection
(`thumb_switch_refs`, `_thumb` token) in `cli.py`. User chose the *general*
capability (unit-tested to 25°); on the Phantom it activates at −8° with
tangent-continuous joins (dot 0.9985).

**Next step: Step 10 — split mirror (route `phantom_right.kicad_pcb`).** In plan.

Active plan: `.claude/plans/autorouter.md`

## Quick validate
```bash
cd router && python3 -m router.cli ../output/pcbs/phantom_left.kicad_pcb \
    -o /tmp/routed_left.kicad_pcb --render /tmp/out.png --verbose
```

## Don't relearn
- Layer convention inverted from the prompt: switch pads B.Cu, diode pads F.Cu
  ⇒ columns route B.Cu, **rows route F.Cu**. Read `pad.layer` (`CuStack()`),
  never assume. `pad.GetLayer()` lies for these SMD pads.
- Per-key via = switch→diode `matrix_*` net (MATRIX_LINK), not a col→row hop.
- `pcbnew` confined to `extract.py`; routing emits raw S-expressions.
- Render: `kicad-cli pcb export pdf` → `pdftoppm` → `convert -trim`.

## Git
Branch `main`, ahead of origin by 3 commits. `router/` and
`autorouter-prompt.md` are untracked (not yet committed).

## Origin
Recovered from dead session 0bb58741 (2026-06-08) — see
`router/RECOVERED_STATUS.md`. That session is unrecoverable; do not `--resume`.
