// Phantom case — BOTTOM SHELL.
// Nests inside phantom_case.scad. Sits below the PCB and pushes it up against
// the top case's plate. Shares outline / switches / bolts / plate_bot with
// the top SCAD via `include` (SUPPRESS_TOP=true skips the top render).
//
//   openscad -o phantom_case_bottom.stl case/phantom_case_bottom.scad
//
// Geometry (z-up, KiCad y-down — final mirror flips y):
//   z ∈ [-floor_t, 0] : exterior plate, outer = outline + gap + wall, matches
//                       the top case outer so the seam at z=0 is flush.
//   z ∈ [0, lip_h]    : nesting lip, outer = outline + gap - fit_clr, slips
//                       into the top case cavity from below.
//   lip_h = plate_bot - pcb_t = 2.10mm  (PCB underside rest plane).
// Cutouts:
//   - Kailh PG1350 hot-swap socket pockets at each switch — TOTEM silkscreen
//     outline (Z-shape, two bulges). The pockets cut all the way through the
//     lip (z=0 → z=lip_h) so a 1.8mm-tall socket fits, but the exterior
//     plate seals them at the bottom, so the sockets are not visible from
//     outside. Socket bottom ends ~0.3mm above the floor top.
//   - M2 hex-nut pockets in the bottom face at the four corner bolts.
//   - M2 shaft holes through the whole shell.

SUPPRESS_TOP = true;
include <phantom_case.scad>;

// === bottom-shell dimensions ===
pcb_t           = 1.6;                 // PCB thickness
floor_t         = 2.0;                 // exterior plate below z=0 (2mm min wall)
lip_h           = plate_bot - pcb_t;   // 2.10mm — nesting lip top = PCB underside
fit_clr         = 0.1;                 // lip-to-top-case-cavity slip clearance

// Kailh PG1350 hot-swap socket body outline in switch local frame, traced from
// TOTEM's Kailh_socket_PG1350_optional.kicad_mod silkscreen — a Z-shape with
// two rectangular bulges (one around each SMD pad) connected by curves. Pads
// are at (-3.275, -5.95) and (8.275, -3.75). The polygon hugs the body; a
// small inflation by socket_clr is applied at use to give plastic clearance.
socket_outline = [
    [-2.0,    -4.2  ], [-2.0,    -7.7  ],
    [-1.5,    -8.2  ], [ 1.5,    -8.2  ],
    [ 2.0,    -7.7  ], [ 2.0,    -6.7  ],
    [ 2.1464, -6.3464],                     // arc midpoint (lower inner corner)
    [ 2.5,    -6.2  ], [ 7.0,    -6.2  ],
    [ 7.0,    -1.5  ], [ 2.5,    -1.5  ],
    [ 2.5,    -2.2  ],
    [ 2.0607, -3.2607],                     // arc midpoint (upper inner corner)
    [ 1.0,    -3.7  ], [-1.5,    -3.7  ]
];
socket_clr = 0.3;  // inflate the outline by this much for socket plastic slop

// M2 hex nut: 4.0mm across flats. Hex circumradius = 4/√3 ≈ 2.31, plus slack.
m2_nut_af = 4.0;
m2_nut_h  = 1.8;   // nut thickness; pocket depth from the bottom face upward

module bottom_body()
    union() {
        translate([0, 0, -floor_t])
            linear_extrude(floor_t)
                offset(r = gap + wall) polygon(outline);
        linear_extrude(lip_h)
            offset(r = gap - fit_clr) polygon(outline);
    }

// Hot-swap socket pockets — through-cut the full lip height so a 1.8mm-tall
// socket fits. The exterior floor seals the cuts from outside; the socket
// bottom ends ~0.3mm above the floor top (z=0). Rotated per switch.
module socket_pockets()
    for (s = switches)
        translate([s[0], s[1], 0])
            rotate([0, 0, -s[2]])
                linear_extrude(lip_h + 0.01)
                    offset(r = socket_clr) polygon(socket_outline);

// Hex nut pockets in the bottom face (z = -floor_t), m2_nut_h deep upward.
module nut_pockets()
    for (b = bolts)
        translate([b[0], b[1], -floor_t - 0.01])
            linear_extrude(m2_nut_h + 0.01)
                circle(r = m2_nut_af / sqrt(3) + 0.07, $fn = 6);

// Bolt shaft holes — all the way through so the bolt can engage the nut.
module bolt_shafts()
    for (b = bolts)
        translate([b[0], b[1], -floor_t - 1])
            linear_extrude(lip_h + floor_t + 2)
                circle(d = m2_shaft_d, $fn = 32);

module bottom_case()
    mirror([0, 1, 0])
        difference() {
            bottom_body();
            socket_pockets();
            nut_pockets();
            bolt_shafts();
        }

// Preview: render top + bottom together for fit check. EXPLODED > 0 lifts the
// top by that many mm; 0 = fully assembled. `right` (from the included top
// SCAD, or -D right=true) mirrors the build for the right half:
//   openscad -D right=true -o phantom_case_bottom_right.stl case/phantom_case_bottom.scad
PREVIEW  = false;
EXPLODED = 6;

module bottom_build() {
    if (PREVIEW) {
        bottom_case();
        translate([0, 0, EXPLODED]) top_case();
    } else {
        bottom_case();
    }
}

if (right) mirror([1, 0, 0]) bottom_build();
else bottom_build();
