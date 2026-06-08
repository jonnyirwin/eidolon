# Plan — ergogen-route autorouter

Domain-specific autorouter for Ergogen keyboard PCBs, living in `router/`. Full
design brief: `autorouter-prompt.md`. Status notes: `router/README.md`,
`router/RECOVERED_STATUS.md`.

## Done — matrix routing + vias + thumb Bézier (prompt steps 1–9)

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

**Step 9 done (general capability, per user choice):** `geometry.py` gained
`cubic_bezier`, `bezier_transition`, `rotate`, `unit`. `cli.py` detects thumb
switches via the `_thumb` matrix-link token (`thumb_switch_refs`), pulls them
out of the column spine, and `route_spine` joins each back with a
`bezier_transition` whose arrival tangent = column exit tangent rotated by the
thumb's relative `fp_rot` (local frame). **Validated:** geometry unit tests
incl. a synthetic 25° cluster; on the Phantom (S14/S15, −8°) connectivity stays
16 unconnected (thumbs still on C3/C4), the C3 join is tangent-continuous
(dot 0.9985) and lands exactly on the thumb pad with no overshoot. NOTE: the
separate-multi-key-thumb-spine branch (`len(thumb)≥2`) is exercised only by the
synthetic test, not this board.

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

## NEXT — Step 10: split mirror

Ergogen emits both halves; `output/pcbs/` has `phantom_right.kicad_pcb`. The
brief (line 177) wants the right half to be a **perfect mirror** of the left
under reflection across the split axis — "route in logical space, transform to
physical." But the cheap first cut is simply to run the existing pipeline on the
right-half board (its own pad facts), since each half is a self-contained PCB.

1. Run `python3 -m router.cli ../output/pcbs/phantom_right.kicad_pcb -o … --render`
   and check it routes/validates the same way (15 vias, rows/cols, thumb Bézier,
   connectivity).
2. Confirm the classifier/thumb-detection generalise (net names may differ on
   the right half — check `R\d+`/`C\d+`/`_thumb` still match).
3. Decide whether true mirror-identity (reflect left geometry) is needed for this
   project or whether per-half routing suffices. The brief wants identity; per-
   half routing is the pragmatic MVP. Likely raise with the user.

Watch-out: if the right half's nets are named identically to the left (both are
`C0..C4`/`R0..R3`), per-half routing is trivially correct. Mirror-identity only
matters for visual symmetry across the assembled board.

## Roadmap (remaining prompt steps)

(Step 10 above is next.)

11. MCU fan-out — **river-style**: parallel offsets at equal spacing curving
    together (brief 125–129); this convergent bundle is where the river-delta
    visual actually lives.
12. USB D+/D-   13. Interconnect
14. Power + GND pour — wider 0.5 mm rails + river bundling
15. DRC pass    16. YAML config system

### Trace-quality track (aesthetic best practices — NOT auto-covered by 10–16)

The numbered steps deliver electrical coverage; the brief's *visual* quality
needs these two cross-cutting passes, added explicitly so they aren't missed:

- **A. Native arc output — DONE.** `geometry.fit_arcs` greedily collapses each
  spline sample polyline into native `(arc …)` + `(segment …)` (≤0.05 mm fit
  tol, grows both a chord run and a circle and keeps whichever reaches further);
  emitted via `kwrite.curve`, repointed from `kwrite.polyline` in `_spine_through`
  and `_thumb_transition`. Result: matrix dropped from ~185 chords to 26 arcs +
  24 segments + 15 vias, connectivity still 16 unconnected, file↔pcbnew arc
  parity exact, no degenerate arcs. Validated by unit tests (circle→1 arc,
  line→1 seg, 0 mm deviation) + board reload.
- **B. Parallel-offset + perpendicular stubs** — route traces as offsets from
  the spine with stubs to pads (brief 125), the structural prerequisite for true
  **river bundling**. Highest payoff folded into steps 11 (fan-out) and 14
  (power), where multiple nets share a corridor. (In the bare matrix each
  column/row is a lone net, so offsetting a single spine is near-cosmetic — the
  river only appears once nets bundle.)

**Verdict for "does the plan reach the visual goals":** yes, *with* track A+B
added above. Steps 10–16 alone do not.
9. Thumb-cluster Bézier transitions
10. Split mirror (likely just re-run on `phantom_right.kicad_pcb`)
11. MCU fan-out (the deferred GPIO pads on column/row nets)
12. USB D+/D-  · 13. Interconnect  · 14. Power + GND pour  · 15. DRC pass
16. YAML config system (POWER_NETS, footprint sets, widths → config)
