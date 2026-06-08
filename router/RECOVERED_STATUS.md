# Autorouter — recovered status (from dead session 0bb58741, 2026-06-08 15:11)

Recovered after the original conversation got stuck on a `400 advisor_tool_result`
error at `messages.5` (unrecoverable — abandon that session, do not `--resume` it).

## Where the work stands

**Vertical slice (steps 1–6) is built and validated** in `router/`. It routes the
Phantom's matrix columns and renders a checkpoint image.

| Module | Role |
|---|---|
| `extract.py` | pcbnew: normalise 5.1.6→KiCad 9 + dump pad facts to JSON (only module touching pcbnew) |
| `model.py` | pure-data domain types (`Pad`, `Net`, `NetClass`, `Board`) |
| `classify.py` | net → class; layer read from actual pad copper, not assumed |
| `geometry.py` | PCA pad ordering + centripetal Catmull-Rom spines |
| `kwrite.py` | emit `(segment …)` S-expressions, splice into board text |
| `cli.py` | `ergogen-route` orchestration + PDF→PNG render checkpoint |

Run:
```bash
cd router && python3 -m router.cli ../output/pcbs/phantom_left.kicad_pcb \
    -o /tmp/routed_left.kicad_pcb --render /tmp/out.png --verbose
```
Result: 73 column tracks on B.Cu, threading all 5 columns + thumb keys, reloads
cleanly in pcbnew, mapped to the right nets.

## Load-bearing discovery
Board layer convention is **inverted from the prompt**: switch pads on **B.Cu**,
diode pads on **F.Cu** → columns route B.Cu, rows F.Cu. Per-key via links
switch→diode (the `matrix_*` net), not column→row. Classifier reads layers from
each pad's copper stack. Gotchas: `pad.GetLayer()` lies for these SMD pads (use
`CuStack()`); no headless KiCad format-upgrade verb (the pcbnew round-trip is the path).

## Deferred (steps 7–16)
MCU GPIO pad per column net → fan-out (step 11); plus rows, vias, thumb Béziers,
split mirror, USB/power/DRC, YAML config.

## NEXT STEP
**Step 7 — row spines on F.Cu.**
