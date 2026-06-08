# ergogen-route

A domain-specific autorouter for Ergogen keyboard PCBs. It exploits keyboard
matrix regularity rather than solving general routing — see `../autorouter-prompt.md`
for the full design brief.

**Status: matrix routing (prompt steps 1–9).** Parses the board, classifies
nets, routes the switch **matrix columns** on B.Cu and the diode **rows** on
F.Cu as smooth spines, splays each **thumb key into its own spine group joined
by a Bézier** in the thumb's local frame, drops a **per-key transition via**
linking each switch pad to its diode, emits everything as **native KiCad arcs**
(not faceted segments), then renders a visual checkpoint. Mirroring, MCU/USB/power
and DRC are later milestones — the data model already has the extension points.

## Quick start

```bash
# system python3 here already has pcbnew 9 + numpy + pyyaml
python3 -m router.cli ../output/pcbs/phantom_left.kicad_pcb \
    -o /tmp/routed_left.kicad_pcb \
    --render /tmp/routed_left.png --verbose
```

`--render` produces a top-down PNG (B.Cu + F.Cu + Edge.Cuts) — this is the
visual validation step, since opening the GUI isn't always available.

## Architecture

```
extract.py   pcbnew: normalise format (5.1.6 -> KiCad 9) + dump pad facts -> JSON
   │            (the ONLY module touching pcbnew)
model.py     pure-data domain types (Pad, Net, NetClass, Board)
classify.py  net -> NetClass, layer read from actual pad copper, not assumed
geometry.py  PCA pad ordering + centripetal Catmull-Rom spines
kwrite.py    emit (segment ...) S-expressions, splice into the board text
cli.py       orchestration + render checkpoint
```

### Key findings (non-obvious, load-bearing)

- **The layer convention is inverted vs the prompt.** On this board the switch
  (PG1350) pads are on **B.Cu** and the diode (SOD-123) pads on **F.Cu**, so
  **columns route on B.Cu, rows on F.Cu**. The per-key via links the switch's
  pad 2 to the diode's pad 1 (the intermediate `matrix_*` net) — it is *not* a
  column→row transition. We classify layer from each pad's copper stack, never
  by convention.
- **`pad.GetLayer()` is unreliable** for these SMD pads (returns `F.Cu`
  regardless). `pad.GetLayerSet().CuStack()` is authoritative.
- **No headless format upgrade verb** — `kicad-cli pcb` only has
  `drc`/`export`/`render`. We upgrade 5.1.6 → modern by a `pcbnew`
  load+save round-trip. `pcbnew` is confined to `extract.py`; the routing logic
  writes S-expressions directly, per the design philosophy.
- **Visual checkpoint** = `kicad-cli pcb export pdf` → `pdftoppm` → `convert
  -trim`. SVG export can't be rasterised here; PDF can.
- **Column nets also include the MCU GPIO pad** and **thumb keys are part of
  C3/C4**. The slice threads switch pads only (MCU pad deferred to the fan-out
  milestone); thumb pads are included, so C3/C4 reach down to S14/S15.

## Roadmap (remaining prompt steps)

10. Split mirror (likely: just re-run on `phantom_right.kicad_pcb`, since Ergogen
emits both halves)  11. MCU fan-out **(river-style: parallel offsets at equal
spacing, curving together — this bundle is where the "river delta" visual lives,
brief lines 125–129)**  12. USB D+/D-  13. Interconnect  14. Power + GND pour
**(wider 0.5mm rails + river bundling)**  15. DRC pass  16. YAML config system.

### Trace-quality track (the brief's aesthetic best practices)

These are cross-cutting refinements, not net-type coverage, so they sit outside
the numbered net steps:

- **A. Native arc segments — DONE.** `geometry.fit_arcs` greedily collapses each
  dense spline sample polyline into native KiCad `(arc …)` + `(segment …)` tracks
  (≤0.05 mm fit tolerance): straight columns become one segment, staggered rows
  and thumb Béziers become smooth arcs. Emitted via `kwrite.curve`. Cut the
  matrix from ~185 straight chords to 26 arcs + 24 segments; connectivity
  unchanged, file↔pcbnew arc parity exact, no degenerate arcs.
- **B. Parallel-offset + stubs** — route each trace as an offset from its spine
  with short perpendicular stubs to the pads, rather than the spine straight
  through pad centres (brief line 125). Prerequisite for true river bundling;
  highest payoff combined with steps 11 & 14.

Without A and B the output is electrically correct but not yet the "flowing,
beautiful" board the brief targets.

Thumb handling (step 9): a switch is a thumb if its matrix-link net carries a
`_thumb` token; such keys are pulled out of the column spine into their own
group, joined back by a `bezier_transition` whose arrival tangent is the column
exit tangent rotated into the thumb's local frame (`fp_rot`). On the Phantom the
thumbs are mild (−8°, one per column) so the curve is gentle; the same path
handles aggressive 15–30° clusters (unit-tested) without change.

Columns and rows share one `route_spine(board, klass, footprints)` in `cli.py`;
`SWITCH_FOOTPRINTS`→B.Cu columns, `DIODE_FOOTPRINTS`→F.Cu rows. The layer is
read per-net from the pads, so the same code routes either with no convention
baked in.
