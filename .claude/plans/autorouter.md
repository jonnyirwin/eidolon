# Plan — ergogen-route autorouter

Domain-specific autorouter for Ergogen keyboard PCBs, living in `router/`. Full
design brief: `autorouter-prompt.md`. Status notes: `router/README.md`,
`router/RECOVERED_STATUS.md`.

## Done — matrix routing + vias (prompt steps 1–8)

Parses the board, classifies nets, routes the switch **matrix columns** on
**B.Cu** (73 segments) and the diode **rows** on **F.Cu** (81 segments) as
centripetal Catmull-Rom spines, then drops a **per-key transition via** (15) on
each `matrix_*` net with a B.Cu stub from the switch pad. 169 segments + 15 vias
total. Splices S-expressions into the normalised board and renders a PDF→PNG
checkpoint. Reloads cleanly in pcbnew.

**Step 7 done:** `route_columns` generalised into
`route_spine(board, klass, footprints)` in `cli.py`; columns =
`(COLUMN, SWITCH_FOOTPRINTS)`, rows = `(ROW, DIODE_FOOTPRINTS={"diode_sod123"})`.
Layer read per-net from the pads, nothing assumed. Each row net carries one
`xiao_ble` MCU pad, deferred to fan-out like the column GPIO pads.

**Step 8 done:** `kwrite.via(...)` emitter + `route_matrix_links(board)` in
`cli.py`. All 15 `matrix_*` nets are exactly 1 switch pad (B.Cu) + 1 diode pad
(F.Cu); the via is anchored on the diode pad (so it rotates with the footprint
for free, drill 0.3 / size 0.6 from the brief) with a B.Cu stub to the switch
pad. **Validated empirically:** routing with vs without the links closes exactly
15 ratsnest connections (31→16 unconnected), one per key. Remaining 16
unconnected = deferred MCU fan-out + power + USB.

Module map:

| Module | Role | Key symbols |
|---|---|---|
| `extract.py` | only pcbnew user: normalise 5.1.6→KiCad9 + dump pad facts JSON | `extract()`, `PadFact` |
| `model.py` | pure-data types | `Pad`, `Net`, `NetClass`, `Board.from_json` |
| `classify.py` | net → `NetClass`, layer read from pad copper stack | `classify_net`, `nets_of`, `_ROW_RE` (already matches `R\d+`) |
| `geometry.py` | PCA pad ordering + Catmull-Rom spline | `order_along_axis`, `catmull_rom` |
| `kwrite.py` | emit segments, splice into board text | `polyline(pts, width, layer, net_code)`, `splice` |
| `cli.py` | orchestration + render checkpoint | `route_columns`, `render_checkpoint`, `main` |

Run / validate:
```bash
cd router && python3 -m router.cli ../output/pcbs/phantom_left.kicad_pcb \
    -o /tmp/routed_left.kicad_pcb --render /tmp/out.png --verbose
```

## Load-bearing facts (do not relearn)

- **Layer convention is inverted from the prompt.** Switch (PG1350) pads on
  **B.Cu**, diode (SOD-123) pads on **F.Cu** ⇒ columns route B.Cu, **rows route
  F.Cu**. Never assume by convention — read `pad.layer` (from `CuStack()`).
- `pad.GetLayer()` lies for these SMD pads; `GetLayerSet().CuStack()` is
  authoritative (already handled in `extract.py`).
- Per-key via links switch pad 2 → diode pad 1 (the `matrix_*` net). That is a
  `MATRIX_LINK`, **not** a column→row transition.
- Column nets also carry the MCU GPIO pad; the slice excludes non-switch pads
  via `SWITCH_FOOTPRINTS` and defers the MCU pad to fan-out (step 11). Rows will
  have the same shape (a diode-chain net plus an MCU pad).
- No headless KiCad format-upgrade verb; the pcbnew load+save round-trip is the
  upgrade path. Render = `kicad-cli pcb export pdf` → `pdftoppm` → `convert -trim`.

## NEXT — Step 9: thumb-cluster Bézier transitions

The two thumb keys (S14/S15) are already threaded into C3/C4 column spines and
have working matrix-link vias (`thumb_left_thumb`, `thumb_right_thumb`). Step 9
is about the *transition geometry* where the thumb cluster splays away from the
main grid at an angle — the straight/Catmull spine segment into the thumbs may
want a smooth Bézier turn rather than the current sharp entry.

1. Check the thumb keys' rotation (`fp_rot` in the pad facts) and how the C3/C4
   spine currently enters them (it jumps from S6→S14 at y≈-36→+18, a long span).
2. Decide whether the prompt's "Bézier transition" means a smoother corner on
   that long spine segment, or a dedicated short curve. See `autorouter-prompt.md`
   §"Thumb cluster vias" and the bend/corner notes (lines ~47, ~161).
3. Likely implement as a corner-rounding pass in `geometry.py` applied to spine
   segments whose turn angle exceeds a threshold.

Watch-out: the via offset is already rotation-correct (anchored on the diode
pad), so thumb vias need no special handling — this step is purely the spine
curve aesthetics/clearance into the rotated keys.

## Roadmap (remaining prompt steps)

(Step 9 above is next.)
9. Thumb-cluster Bézier transitions
10. Split mirror (likely just re-run on `phantom_right.kicad_pcb`)
11. MCU fan-out (the deferred GPIO pads on column/row nets)
12. USB D+/D-  · 13. Interconnect  · 14. Power + GND pour  · 15. DRC pass
16. YAML config system (POWER_NETS, footprint sets, widths → config)
