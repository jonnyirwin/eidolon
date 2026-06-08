# Project state — phantom-ergogen

## In flight
**ergogen-route autorouter** (`router/`). Matrix routing (prompt steps 1–7)
built and validated: switch **columns** on B.Cu (73 segs) + diode **rows** on
F.Cu (81 segs) = 154 Catmull-Rom tracks, spliced as S-expressions, rendered to a
PDF→PNG checkpoint, reloads cleanly in pcbnew. Step 7 generalised
`route_columns` into `route_spine(board, klass, footprints)` in `cli.py`.

**Next step: Step 8 — per-key matrix-link vias.** Detailed in the active plan.

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
