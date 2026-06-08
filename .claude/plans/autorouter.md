# Plan — ergogen-route autorouter

Domain-specific autorouter for Ergogen keyboard PCBs, living in `router/`. Full
design brief: `autorouter-prompt.md`. Status notes: `router/README.md`,
`router/RECOVERED_STATUS.md`.

## Done — matrix routing (prompt steps 1–7)

Parses the board, classifies nets, routes the switch **matrix columns** on
**B.Cu** (73 segments) and the diode **rows** on **F.Cu** (81 segments) as
centripetal Catmull-Rom spines — 154 tracks total. Splices `(segment …)`
S-expressions into the normalised board and renders a PDF→PNG checkpoint.
Reloads cleanly in pcbnew (154 tracks).

**Step 7 done:** `route_columns` was generalised into
`route_spine(board, klass, footprints)` in `cli.py`; columns =
`(COLUMN, SWITCH_FOOTPRINTS)`, rows = `(ROW, DIODE_FOOTPRINTS={"diode_sod123"})`.
The routing layer is read per-net from the pads (B.Cu cols / F.Cu rows), nothing
assumed. Each row net also carries one `xiao_ble` MCU pad, deferred to fan-out
exactly like the column GPIO pads.

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

## NEXT — Step 8: per-key matrix-link vias

`classify.py` already tags the per-key intermediate nets as
`NetClass.MATRIX_LINK` (15 of them — switch pad 2 → diode pad 1). Each needs a
via placing the connection from the switch layer (B.Cu) to the diode layer
(F.Cu), plus short stubs from each pad to the via.

1. Add a `via(...)` emitter to `kwrite.py` alongside `segment` — KiCad
   `(via (at x y) (size …) (drill …) (layers "F.Cu" "B.Cu") (net code) (uuid …))`.
   Get default via size/drill from the design rules (check the board's
   `(setup …)` or the Ergogen footprint).
2. In `cli.py`, add `route_matrix_links(board)`: for each MATRIX_LINK net, find
   its switch pad (B.Cu) and diode pad (F.Cu), drop a via — placement choice:
   at the diode pad, at the switch pad, or midpoint — then a stub segment on
   each layer from pad to via if they aren't coincident.
3. Validate: 15 new vias, board reloads, render shows the links. DRC later.

Watch-outs: confirm via clears the row/column spines (these per-key nets are
short and local, so collisions are unlikely at this stage). The MCU pads on
column/row nets remain deferred to fan-out (step 11).

## Roadmap (remaining prompt steps)

(Step 8 above is next.)
9. Thumb-cluster Bézier transitions
10. Split mirror (likely just re-run on `phantom_right.kicad_pcb`)
11. MCU fan-out (the deferred GPIO pads on column/row nets)
12. USB D+/D-  · 13. Interconnect  · 14. Power + GND pour  · 15. DRC pass
16. YAML config system (POWER_NETS, footprint sets, widths → config)
