# Project state — phantom-ergogen

## In flight
**ergogen-route autorouter** (`router/`). Vertical slice (prompt steps 1–6) is
built and validated: routes the switch matrix **columns** as Catmull-Rom spines
on B.Cu (73 segments), splices S-expressions into the board, renders a PDF→PNG
checkpoint, reloads cleanly in pcbnew.

**Next step: Step 7 — row spines on F.Cu.** Detailed in the active plan.

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
