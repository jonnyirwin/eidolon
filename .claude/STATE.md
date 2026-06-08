# Project state — phantom-ergogen

## In flight
**ergogen-route autorouter** (`router/`). Matrix routing + vias (prompt steps
1–8) built and validated: switch **columns** on B.Cu (73 segs) + diode **rows**
on F.Cu (81 segs) + 15 B.Cu stubs + **15 per-key transition vias** = 169 segs +
15 vias. Reloads cleanly in pcbnew. Step 7 = `route_spine(board, klass,
footprints)`; Step 8 = `kwrite.via` + `route_matrix_links` (via on diode pad,
B.Cu stub to switch; validated by closing exactly 15 ratsnest links, 31→16).

**Next step: Step 9 — thumb-cluster Bézier transitions.** Detailed in the plan.

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
