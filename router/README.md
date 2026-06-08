# ergogen-route

A domain-specific autorouter for Ergogen keyboard PCBs. It exploits keyboard
matrix regularity rather than solving general routing — see `../autorouter-prompt.md`
for the full design brief.

**Status: matrix routing (prompt steps 1–7).** Parses the board, classifies
nets, and routes the switch **matrix columns** on B.Cu and the diode **rows** on
F.Cu as smooth spines, then renders a visual checkpoint. Vias, thumb
transitions, mirroring, MCU/USB/power and DRC are later milestones — the data
model already has the extension points.

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

8. Per-key matrix-link vias  9. Thumb-cluster Bézier transitions  10. Split
mirror (likely: just re-run on `phantom_right.kicad_pcb`, since Ergogen emits
both halves)  11. MCU fan-out  12. USB D+/D-  13. Interconnect  14. Power + GND
pour  15. DRC pass  16. YAML config system.

Columns and rows share one `route_spine(board, klass, footprints)` in `cli.py`;
`SWITCH_FOOTPRINTS`→B.Cu columns, `DIODE_FOOTPRINTS`→F.Cu rows. The layer is
read per-net from the pads, so the same code routes either with no convention
baked in.
