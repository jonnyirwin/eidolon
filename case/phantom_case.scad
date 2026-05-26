// Phantom case — LEFT half.
// Outline built directly from the original PCB Edge.Cuts of lephantom.kicad_pcb
// (6 lines + 5 arcs, exact mm coordinates). The case footprint is the PCB
// outline grown outward by (gap + wall) so the PCB drops inside the walls:
//   gap  = 0.15mm clearance between PCB edge and inner wall
//   wall = 2.0mm  case wall thickness
// then extruded to 16mm. This pass produces the solid outer shape only.
//
//   openscad -o phantom_case.stl case/phantom_case.scad

gap    = 0.15;   // PCB-to-inner-wall clearance (per side)
wall   = 2.0;    // case wall thickness
height = 12.5;   // extrusion depth (mm) — matches Totem top shell
switch = 13.8;   // Choc switch plate cutout (mm square) — Kailh spec / Totem STEP
// Per-column keycap recess. Depth/corner from Totem STEP; opening sized to the
// keycap (not the switch) so caps drop in without catching. At 18mm column pitch
// an 18mm cap leaves no rib, so adjacent column recesses merge into field pockets
// (as on the Totem, whose real recesses are big multi-column pockets).
recess_d = 6.85; // recess depth from top (rim->switch-plate in Totem)
keycap_x = 18.0; // keycap footprint, horizontal
keycap_y = 17.0; // keycap footprint, vertical
key_clr  = 0.5;  // extra clearance per side so caps don't catch
recess_r = 1.6;  // recess corner fillet
arc_n  = 24;     // points sampled per arc corner
$fn = 64;

// ---- Edge.Cuts vertices (exact KiCad coords, mm, y-down) ----
P1  = [ 39.624000, 17.018000];
P2  = [105.918000, 15.240000];
P3  = [112.016555, 16.811266];
P4  = [143.816302, 31.614407];
P5  = [144.187844, 32.512000];
P6  = [144.272000, 66.802000];
P7  = [130.914271, 95.075525];
P8  = [123.190000, 98.806000];
P9  = [ 43.688000, 89.154000];
P10 = [ 35.014644, 79.908818];
P11 = [ 30.897623, 27.391512];

// arc midpoints (the stored "mid" of each gr_arc)
M_a = [ 33.354254, 20.600927];  // P1  <-> P11  (upper-left corner)
M_b = [ 37.978029, 85.819762];  // P10 <-> P9   (lower-left corner)
M_c = [127.498036, 97.864039];  // P8  <-> P7   (lower-right corner)
M_d = [144.091288, 32.026275];  // P5  <-> P4   (right corner)
M_e = [109.088492, 15.555164];  // P3  <-> P2   (upper-right corner)

// ---- arc through 3 points -> list of points (excludes p0, includes p1) ----
function _ctr(a,b,c) =
    let(d = 2*(a[0]*(b[1]-c[1]) + b[0]*(c[1]-a[1]) + c[0]*(a[1]-b[1])),
        ux = ((a[0]*a[0]+a[1]*a[1])*(b[1]-c[1])
            + (b[0]*b[0]+b[1]*b[1])*(c[1]-a[1])
            + (c[0]*c[0]+c[1]*c[1])*(a[1]-b[1])) / d,
        uy = ((a[0]*a[0]+a[1]*a[1])*(c[0]-b[0])
            + (b[0]*b[0]+b[1]*b[1])*(a[0]-c[0])
            + (c[0]*c[0]+c[1]*c[1])*(b[0]-a[0])) / d)
    [ux, uy];
function _ang(c,p) = atan2(p[1]-c[1], p[0]-c[0]);
function _norm(a)  = a - 360*floor(a/360);
function arc_pts(p0, pm, p1, n=arc_n) =
    let(c  = _ctr(p0,pm,p1),
        a0 = _ang(c,p0), am = _ang(c,pm), a1 = _ang(c,p1),
        dm = _norm(am-a0), de = _norm(a1-a0),
        sweep = (dm <= de) ? de : de-360,   // direction that passes through mid
        r  = norm(p0-c))
    [ for (i=[1:n]) let(t=i/n, a=a0+sweep*t) c + r*[cos(a), sin(a)] ];

// ---- assemble the closed perimeter, in connection order ----
outline = concat(
    [P2],
    [P1],                       // P2 -> P1   line (top edge)
    arc_pts(P1,  M_a, P11),     // P1 -> P11  arc
    [P10],                      // P11 -> P10 line (left edge)
    arc_pts(P10, M_b, P9),      // P10 -> P9  arc
    [P8],                       // P9 -> P8   line (bottom edge)
    arc_pts(P8,  M_c, P7),      // P8 -> P7   arc
    [P6],                       // P7 -> P6   line
    [P5],                       // P6 -> P5   line (right edge)
    arc_pts(P5,  M_d, P4),      // P5 -> P4   arc
    [P3],                       // P4 -> P3   line
    arc_pts(P3,  M_e, P2)       // P3 -> P2   arc (close)
);

// ---- Choc switch positions, from lephantom.kicad_pcb (KiCad coords) ----
// [x, y, rotation_deg] — the 15 SW_PG1350 footprints of the left half.
switches = [
    [ 80.000, 24.980,  0], [ 59.917, 28.163,  3], [ 98.000, 28.540,  0],
    [116.000, 37.270,  0], [ 41.507, 41.509,  5], [ 80.000, 41.970,  0],
    [ 60.806, 45.140,  3], [ 98.000, 45.540,  0], [116.000, 54.270,  0],
    [ 42.989, 58.444,  5], [ 80.000, 58.970,  0], [ 61.696, 62.122,  3],
    [ 98.000, 62.545,  0], [104.154, 83.063, -8], [121.957, 85.626, -8],
];

module switch_cutouts()
    for (s = switches)
        translate([s[0], s[1], -1])
            // negate: KiCad angle is CCW+, and the final mirror([0,1,0]) flips
            // rotation sense, so -s[2] keeps each cutout aligned to its column splay.
            rotate([0, 0, -s[2]])
                linear_extrude(height + 2)
                    square(switch, center = true);

// 2D rounded keycap-clearance pad for one switch (keycap + clearance, splayed).
module key_pad(i)
    translate([switches[i][0], switches[i][1]])
        rotate(-switches[i][2])
            offset(r = recess_r)
                square([keycap_x + 2*key_clr - 2*recess_r,
                        keycap_y + 2*key_clr - 2*recess_r], center = true);

// Single open recess (no ribs, as on the Totem): the union of every keycap pad.
// Pads overlap at 18x17 pitch so they merge into one well following the field,
// sunk recess_d from the top (does not pass through). Cutouts pierce its floor.
module recess_pockets()
    translate([0, 0, height - recess_d])
        linear_extrude(recess_d + 1)
            for (i = [0 : len(switches) - 1]) key_pad(i);

// y-down (KiCad) -> y-up (upright, matches PCB front view); grow by gap+wall.
// Body and cutouts share the KiCad frame, then the whole part is mirrored.
mirror([0, 1, 0])
    difference() {
        linear_extrude(height = height)
            offset(r = gap + wall)
                polygon(outline);
        switch_cutouts();
        recess_pockets();
    }