# Plan — ergogen-route autorouter

Domain-specific autorouter for Ergogen keyboard PCBs, living in `router/`. Full
design brief: `autorouter-prompt.md`. Status notes: `router/README.md`,
`router/RECOVERED_STATUS.md`.

## Done — vertical slice (prompt steps 1–6)

Parses the board, classifies nets, routes the switch **matrix columns** as
centripetal Catmull-Rom spines on **B.Cu** (73 segments, all 5 columns + thumb
keys), splices `(segment …)` S-expressions into the normalised board, and
renders a PDF→PNG checkpoint. Reloads cleanly in pcbnew.

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

## NEXT — Step 7: row spines on F.Cu

`classify.py` already tags `R\d+` nets as `NetClass.ROW`, and `kwrite.polyline`
already takes a `layer` arg, so the geometry/write layers need **no change**.
The work is in `cli.py`.

1. **Confirm the diode footprint name.** Run the slice with `--dry-run --verbose`
   (or inspect the pads JSON) to read the actual `footprint` value for diode
   pads (README calls it `diode_sod123` / SOD-123). Define
   `DIODE_FOOTPRINTS = {…}` analogous to `SWITCH_FOOTPRINTS`.
2. **Generalise, don't copy.** Refactor `route_columns` into a shared
   `route_spine(board, klass, footprints, *, verbose)` that:
   - selects `nets_of(board, klass)`,
   - keeps only pads whose `footprint` is in `footprints` (deferring MCU/other
     pads, as columns already do),
   - picks the net's dominant `layer` via the existing `Counter` idiom (will be
     F.Cu for rows, B.Cu for columns),
   - orders (`order_along_axis`) + splines (`catmull_rom`) + writes
     (`kwrite.polyline`).
   Then `route_columns = route_spine(…, COLUMN, SWITCH_FOOTPRINTS)` and add
   `route_rows = route_spine(…, ROW, DIODE_FOOTPRINTS)`.
3. **Wire into `main`:** `elements = route_spine(COLUMN…) + route_spine(ROW…)`.
   Keep the per-class segment counts in the verbose summary.
4. **Validate:** re-render the checkpoint; expect ~4–5 horizontal row spines on
   F.Cu in addition to the column spines on B.Cu, reloading cleanly in pcbnew.
   Sanity-check row count against the matrix (Phantom row count from the Ergogen
   config).

Watch-outs: rows are near-horizontal so PCA should pick the X axis — verify the
spline doesn't fold back on a stagger; diode pad ordering must follow the
physical row, not net-name order. If a row net's diode pads aren't collinear
enough, the centripetal spline still passes through them (acceptable for now).

## Roadmap (remaining prompt steps)

8. Per-key matrix-link vias (switch pad2 → diode pad1)
9. Thumb-cluster Bézier transitions
10. Split mirror (likely just re-run on `phantom_right.kicad_pcb`)
11. MCU fan-out (the deferred GPIO pads on column/row nets)
12. USB D+/D-  · 13. Interconnect  · 14. Power + GND pour  · 15. DRC pass
16. YAML config system (POWER_NETS, footprint sets, widths → config)
