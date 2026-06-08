# CLI KiCad Autorouter for Ergogen Keyboard Designs

## Project Overview

Build a CLI tool that takes an Ergogen keyboard design as input and produces a fully-routed `.kicad_pcb` file as output. This is a **domain-specific** autorouter — it exploits the regularity of keyboard matrix PCBs rather than solving the general routing problem. The primary goals are **correct routing** and **aesthetically pleasing trace geometry**.

This is not a wrapper around FreeRouting or any existing autorouter. It is a constraint-based scripted router that understands keyboard topology and uses that knowledge to produce clean, beautiful traces.

## Core Design Philosophy

- **Consume Ergogen YAML directly** (not just the KiCad output) to retain semantic knowledge: which keys are in which columns/rows, physical layout, rotation angles, stagger, and split-half membership. This semantic knowledge is the tool's biggest advantage over a generic router.
- **Spine-based routing**: compute smooth curves ("spines") through groups of related pads, then route traces as offsets from these spines. This produces flowing, organic-looking traces that follow the keyboard's geometry.
- **Deterministic via placement**: via positions are a function of the switch footprint, stamped uniformly at every switch position.
- **Mirror-based split keyboard support**: route one half, then mirror all geometry to produce the other half.

## Architecture — Processing Pipeline

```
Ergogen YAML + .kicad_pcb (unrouted)
    │
    ▼
┌─────────────────────┐
│  Layout Parser       │  Extract physical positions, rotations,
│                      │  column/row assignments, split halves
│                      │  from Ergogen YAML. Parse the .kicad_pcb
│                      │  for pad coordinates and netlist.
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Net Classifier      │  Categorise every net into:
│                      │  matrix-col, matrix-row, power, USB,
│                      │  interconnect. (LED/serial-data is a
│                      │  future extension — leave a clear
│                      │  extension point but don't implement.)
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Spine Generator     │  For each column and each row, compute
│                      │  a smooth spine curve (Catmull-Rom or
│                      │  cubic Bézier) through the relevant pads.
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Trace Router        │  Generate actual trace geometry:
│                      │  parallel offsets from spines, short
│                      │  perpendicular stubs to pads, arc
│                      │  segments at turns, via placement.
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Mirror Transform    │  For split keyboards: generate the
│                      │  second half by reflecting all geometry
│                      │  around the split axis.
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Special Nets Router │  USB D+/D-, power distribution, TRRS/
│                      │  USB-C interconnect between halves.
│                      │  MCU fan-out from GPIO pins to matrix
│                      │  spines.
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│  Pour & DRC          │  Add ground pour on back layer,
│                      │  run clearance checks, emit warnings.
└──────────┬──────────┘
           ▼
    .kicad_pcb output (routed)
```

## Net Classification

Every net in a keyboard falls into one of these categories. Each has a different routing strategy:

### Matrix Column Nets
- Connect switches in the same column
- Route on **front copper (F.Cu)**
- Spine follows the local axis of the column (not global vertical — it curves with the column stagger)
- Typical trace width: 0.25mm

### Matrix Row Nets
- Connect diodes in the same row
- Route on **back copper (B.Cu)**
- Spine runs roughly horizontally across the stagger
- Typical trace width: 0.25mm

### Power (VCC/GND)
- VCC routed as explicit wider traces (0.5mm+)
- GND handled primarily via ground pour on back layer with thermal relief on pads
- Power vias as needed to connect layers

### USB (D+/D-)
- From MCU to USB connector
- Must be short, matched length, controlled impedance
- Minimal vias (ideally zero)
- Typical trace width: depends on impedance target

### Interconnect (Split)
- TRRS or USB-C between halves
- Small number of nets (VCC, GND, data, clock, possibly extra matrix lines)
- Routes from MCU to connector at inner edge

### Serial Data (FUTURE — not yet implemented)
- WS2812 LED chains, I²C for OLEDs
- Fixed sequential order, short hops between components
- Leave a `serial_chain` net class as an extension point in the data model

## Spine-Based Routing — The Core Aesthetic Concept

### What is a spine?

Rather than routing pad-to-pad with a pathfinder, first compute a **spine** for each column and each row. The spine is a smooth curve — a Catmull-Rom spline or cubic Bézier — that passes through (or near) every pad in that net group.

### Example: column with stagger

For pads at positions like:
```
    •         (pinky, offset left)
      •       (ring)
        •     (middle)
       •      (index, less stagger)
     •        (inner)
```

The spine is a smooth curve threading through these points. Each actual trace is routed as a parallel offset from this spine, with short perpendicular stubs connecting to the actual pads. Multiple nets sharing the same corridor (e.g. adjacent column nets) become a **river** — parallel traces at fixed intervals from the spine, curving together.

### River routing

Where multiple column or row nets run in parallel, they must maintain equal spacing and curve together. This is the single biggest contributor to visual quality. The traces should look like a flowing river delta.

### Arc segments

KiCad 7+ supports arc trace segments natively (the `arc` segment type in `.kicad_pcb`). Use 45° entry/exit angles with arcs at turns rather than sharp corners. The prettiest boards use flowing curves, not right angles or even simple 45° chamfers.

### Trace flow follows key geometry

In a column-staggered board, column traces don't run in a global vertical — they follow the local axis of the column, curving gently as the stagger changes. The traces should look like they *belong* to the layout.

## Via Placement Strategy

### Matrix transition vias

Every switch sits at the intersection of one column net and one row net. Columns on F.Cu, rows on B.Cu. At every switch position, exactly one via transitions between layers (from switch pad to diode / from column to row layer).

Via placement is **deterministic** — a function of the switch+diode footprint. The via is placed at a consistent offset relative to the switch centre, in the switch's **local coordinate frame** (so it rotates with the switch).

This should be configurable:

```yaml
via_strategy:
  matrix_transition:
    offset: { x: 2.5, y: 3.0 }   # relative to switch centre, in local frame
    anchor: diode_pad_2            # or use absolute offset
    drill: 0.3
    annular_ring: 0.15
    layer_pair: [F.Cu, B.Cu]
```

The uniform placement creates a regular visual pattern that mirrors the key layout.

### Thumb cluster vias

The offset is in the switch's local coordinate frame, so when a thumb key is rotated (commonly 15-30°), the via rotates with it. Run a clearance check post-placement to ensure the rotated via doesn't collide with adjacent pads or traces.

### MCU fan-out vias

The MCU is where regularity breaks down. Column and row nets converge on GPIO pins. A small local fan-out router spreads traces from the MCU pads outward to meet the matrix spines, placing vias as needed. This is the one place where something closer to A* pathfinding may be warranted, but the search space is tiny (a few cm² around the MCU).

### Post-placement clearance

After placing all vias, run a clearance pass checking every via annular ring against adjacent traces and pads. If something violates minimum clearance: nudge the via along the local switch axis, adjust trace entry angle, or flag for manual review. Collisions are rare with standard MX (19.05mm) or Choc (18mm) spacing.

## Split Keyboard Handling

### Mirroring

Route the left half fully, then mirror all geometry around the split axis. This requires a clean separation between "logical routing decisions" and "physical coordinates". Route in logical space, transform to physical. The right half's routing must be a **perfect mirror** of the left — not "similar", identical under reflection.

### Thumb clusters

These break column regularity. Ergogen defines thumb keys with large rotations (15-30°). The spine generator must handle thumb clusters as a separate group with its own local coordinate frame. The routing from the thumb cluster back to the main matrix transitions between two spines — use a smooth Bézier to connect them.

### Interconnect routing

TRRS/USB-C jack is usually at the inner edge. Most split firmware (QMK/ZMK) uses serial or I²C, so only a few signals route to the jack, not the full matrix.

### MCU placement

Some splits have one MCU (left only, with communication link to right). Others have one per half. The tool must handle both configurations.

## Design Rules / Best Practices to Encode

- Minimum trace width signal: 0.25mm
- Minimum trace width power: 0.5mm
- Minimum clearance: 0.2mm
- Via drill: 0.3mm (safe for most fabs)
- Via annular ring: 0.15mm (0.6mm total diameter)
- USB D+/D- matched length, short as possible
- Ground pour on back layer
- Thermal relief on ground pads
- No acute angles in traces
- Traces stay away from board edges (min 0.25mm)
- Consistent via placement relative to switch footprint

These should all be configurable, with sensible defaults.

## KiCad File Format Notes

The `.kicad_pcb` format is S-expression based. Key elements to write:

- `(segment ...)` — straight trace segments with start/end coordinates, width, layer, net
- `(arc ...)` — arc trace segments (KiCad 7+) with start/mid/end points, width, layer, net
- `(via ...)` — vias with position, drill size, layer pair, net
- `(zone ...)` — copper pour zones (for ground pour)

The tool should parse the unrouted `.kicad_pcb` from Ergogen to extract pad positions, net assignments, and board outline, then write back a new `.kicad_pcb` with all the original content plus the generated traces, vias, and zones.

## CLI Interface

```
ergogen-route [OPTIONS] <ergogen.yaml> <input.kicad_pcb> -o <output.kicad_pcb>

Options:
  --config <config.yaml>    Custom routing config (trace widths, via sizes, etc.)
  --half <left|right|both>  Which half to route (default: both)
  --no-pour                 Skip ground pour generation
  --drc                     Run DRC checks after routing
  --verbose                 Show routing decisions
  --dry-run                 Parse and plan but don't write output
```

## Tech Stack Considerations

The developer has a strong background in functional programming (Haskell, Elixir) and prefers understanding underlying mechanisms over "magical" behaviour. The project involves:

- S-expression parsing (trivial in most languages)
- Geometric computation: Bézier curves, Catmull-Rom splines, parallel offsets, coordinate transforms, rotation matrices
- Declarative constraint expression
- Clean algebraic data types for the domain model

Haskell is a natural fit for the geometry and data modelling. Alternatively, if faster prototyping is preferred, Elixir or Python could work — though Python's `pcbnew` API is not required since we're writing S-expressions directly.

Whatever the language choice, the KiCad S-expression output should be written directly (no dependency on KiCad's scripting API). The format is well-documented and not complex.

## Suggested Development Order

1. **Parse Ergogen YAML** — extract column/row assignments, physical positions, rotations, split halves
2. **Parse `.kicad_pcb`** — extract pad coordinates, net names, board outline
3. **Net classifier** — categorise nets from the parsed data
4. **Spine generator** — compute Catmull-Rom splines for columns only, on a simple non-split layout
5. **Trace writer** — generate KiCad trace segments (line + arc) following the column spines, write to `.kicad_pcb`
6. **Open in KiCad and visually validate** — this is the first checkpoint
7. **Row spines** — add back-layer row routing
8. **Via stamping** — place matrix transition vias
9. **Thumb cluster handling** — separate spine groups with Bézier transitions
10. **Split mirroring** — mirror transform for the second half
11. **MCU fan-out** — route matrix nets to GPIO pins
12. **USB routing** — D+/D- with length matching
13. **Interconnect routing** — TRRS/USB-C nets
14. **Power distribution** — VCC traces + GND pour
15. **DRC** — clearance checking pass
16. **Config system** — YAML config for all tuneable parameters

## Extension Points (Future, Not Now)

- **LED serial chain routing** — `serial_chain` net class for WS2812 data lines, with per-LED via pairs and sequential hop routing
- **OLED I²C routing** — similar to LED chains but simpler (just SDA/SCL)
- **Per-switch RGB** — SK6812 mini-e or similar, even more constrained than WS2812
- **Multi-layer support** — 4-layer boards for complex builds
- **Interactive preview** — render the routing to SVG for quick visual review without opening KiCad
