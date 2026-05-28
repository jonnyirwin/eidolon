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
recess_r = 0;  // recess corner fillet
// Widen the recess on the RIGHT of the two leftmost columns (pinky+ring) by
// widen_f, extending them toward the next column to close the inter-column ribs.
// Top switches of the pinky+ring columns (the ones bordering the ribs); the
// bottom switch of each column (9, 11) is left at normal width.
widen_keys = [4, 1, 6];        // pinky-top, ring-top, ring-middle
widen_f    = 0.25;             // +25% width, added entirely on the right
// Stepped switch hole + plate (Totem STEP): below the recess floor sits a thin
// plate carrying the switch. The hole is 13.8mm for plate_t13 then opens to a
// 16mm counterbore for plate_t16; below the plate is a cavity for the PCB.
plate_t13 = 1.2;   // 13.8mm hole depth (upper, switch clips here)
plate_t16 = 0.75;  // 16mm counterbore depth (lower)
cbore     = 16.0;  // counterbore size
// derived z-levels (z=0 bottom, z=height top) — defined here so usb_z0 can use them
plate_top = height - recess_d;                 // recess floor / plate top (5.65)
plate_bot = plate_top - plate_t13 - plate_t16; // plate underside (3.70)
// XIAO BLE microcontroller — walled pocket on the right, a hole straight through
// the case (separate from the keycap recess). At the top (-y) end the slanted
// outer wall is flattened by a rounded-rectangular recess, and the USB-C socket
// cutout pierces that flat into the pocket. The PCB right edge is grown by
// pcb_pad (see outline) so the pocket has board under it + real walls.
xiao_l   = 20.0;            // board length (long axis, vertical / y)
xiao_w   = 17.5;           // board width (x)
xiao_clr = 0.4;            // clearance per side inside the pocket
xiao_pos = [137.0, 44.0];  // pocket center, KiCad coords — up near the top angle
xiao_rot = 0;              // deg; 0 = level with the right edge
// USB-C side: a rounded-rect recess cut into the top-right wall makes a flat
// face usb_wall in front of the pocket; the socket cutout goes through it.
flat_w   = 14.0;           // flat recess width  (x)
flat_h   = 9.0;            // flat recess height (z)
flat_r   = 2.0;            // flat recess corner radius
usb_wall = 2.0;            // wall left between the flat face and the pocket
usb_w    = 9.0;            // USB-C cutout width
usb_h    = 3.6;            // USB-C cutout height
usb_z0   = plate_bot + 0.8;// cutout bottom ~ connector height above the PCB
// Acrylic cover for the XIAO pocket: a shallow rebate cut into the TOP of the
// deck so a 3mm acrylic square drops in flush over the through-hole, resting
// on a small ledge of deck round the pocket.
acrylic_t     = 3.0;       // acrylic thickness = rebate depth
acrylic_ledge = 1.0;       // ledge each side (rebate footprint > pocket footprint)
// MSK-12D19 power switch — through-hole SPDT on the PCB right edge with the
// actuator overhanging. The case needs a slot in the right wall for the
// actuator/slider; sized for 1.5mm slider travel + clearance.
sw_pos   = [145.5, 60.27]; // switch centre, KiCad — matches ergogen power placement
sw_z     = plate_bot + 1.5;// slot vertical centre = actuator height above the PCB
sw_slot_w = 8.0;           // slot width  (y, along slider travel + cap)
sw_slot_h = 4.0;           // slot height (z)
sw_slot_inward = 5.0;      // how much the slot extends into the case body (-x)
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

// Local enlargement of the right edge to house the XIAO pocket: push the right
// (vertical) edge out by pcb_pad. AND smooth the upper-right kink — in the source
// PCB the diagonal (P3->P4) meets the corner arc (P3,M_e,P2) at ~7°, not tangent.
// We keep the corner arc as-is but shift the diagonal parallel-outward until
// it's TANGENT to that arc, replacing P3 with the tangent point T. The new
// top-right corner Pc = intersection of the (pushed) vertical edge with the
// (tangent-shifted) diagonal. Both edges stay on true PCB lines + the corner
// is now smooth. P7 (bottom) stays, so the lower-right line just tilts out.
function line_intersect(a, b, c, d) =
    let(r = b - a, s = d - c, rxs = r[0]*s[1] - r[1]*s[0])
    a + r * (((c[0]-a[0])*s[1] - (c[1]-a[1])*s[0]) / rxs);
function _vlen(v)   = sqrt(v[0]*v[0] + v[1]*v[1]);
function _vunit(v)  = v / _vlen(v);
function _bisect(a, b) = _vunit(_vunit(a) + _vunit(b));
pcb_pad = 3.0;
P5e = P5 + [pcb_pad, 0];
P6e = P6 + [pcb_pad, 0];
// Upper-right corner: replace the source PCB's near-arc (kinks ~7° at the
// diagonal, ~1.56° at the top edge) with a PROPER FILLET of the same radius,
// tangent to both the (shifted) diagonal AND the top edge. Compute the new
// centre by intersecting the two lines offset inward by r_e, then drop
// perpendiculars to get the tangent points T (replaces P3) and P2t (replaces
// P2). M_t is a point on the new arc for arc_pts reconstruction.
C_ref = _ctr(P3, M_e, P2);                                    // original centre (sign reference)
r_e   = _vlen(P3 - C_ref);                                    // original PCB radius (kept)
u_d   = _vunit(P4 - P3);                                      // diagonal direction
u_t   = _vunit(P2 - P1);                                      // top-edge direction
n_d   = ([-u_d[1], u_d[0]] * (C_ref - P3) > 0)
            ? [-u_d[1],  u_d[0]] : [ u_d[1], -u_d[0]];        // inward normal (diag)
n_t   = ([-u_t[1], u_t[0]] * (C_ref - P2) > 0)
            ? [-u_t[1],  u_t[0]] : [ u_t[1], -u_t[0]];        // inward normal (top)
C_e   = line_intersect(P3 + r_e*n_d, P3 + r_e*n_d + u_d,
                       P1 + r_e*n_t, P1 + r_e*n_t + u_t);     // fillet centre
T     = P3 + u_d * ((C_e - P3) * u_d);                        // tangent point on diagonal
P2t   = P1 + u_t * ((C_e - P1) * u_t);                        // tangent point on top edge
M_t   = C_e + r_e * _bisect(T - C_e, P2t - C_e);              // mid of the new arc
Pc    = line_intersect(T, T + u_d, P5e, P6e);                 // vertical edge ∩ diag

// ---- assemble the closed perimeter, in connection order ----
outline = concat(
    [P2t],
    [P1],                       // P2t -> P1  line (top edge, tangent-trimmed)
    arc_pts(P1,  M_a, P11),     // P1 -> P11  arc
    [P10],                      // P11 -> P10 line (left edge)
    arc_pts(P10, M_b, P9),      // P10 -> P9  arc
    [P8],                       // P9 -> P8   line (bottom edge)
    arc_pts(P8,  M_c, P7),      // P8 -> P7   arc
    [P6e],                      // P7 -> P6   line (tilts out to the moved P6)
    [Pc],                       // P6 -> corner: vertical edge, +pcb_pad out
    [T],                        // corner -> T   (tangent point, diagonal side)
    arc_pts(T,   M_t, P2t)      // T  -> P2t arc (fillet tangent at BOTH ends)
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

// Stepped switch hole: 13.8mm through the upper plate (and up into the recess),
// opening to a 16mm counterbore that meets the cavity below the plate.
// Negate s[2]: KiCad angle is CCW+, and the final mirror([0,1,0]) flips rotation
// sense, so -s[2] keeps each hole aligned to its column splay.
module switch_cutouts()
    for (s = switches)
        translate([s[0], s[1]])
            rotate([0, 0, -s[2]]) {
                translate([0, 0, plate_bot + plate_t16])      // 13.8mm, 4.45 -> top
                    linear_extrude(height) square(switch, center = true);
                translate([0, 0, plate_bot - 0.01])           // 16mm counterbore
                    linear_extrude(plate_t16 + 0.02) square(cbore, center = true);
            }

// PCB cavity below the plate (open bottom): leaves the plate as a thin floor.
module cavity()
    translate([0, 0, -1])
        linear_extrude(plate_bot + 1)
            offset(r = gap) polygon(outline);

function in_list(i, lst) = len([for (x = lst) if (x == i) 1]) > 0;

// 2D keycap-clearance pad for one switch (keycap + clearance, splayed). Keys in
// widen_keys are stretched +widen_f on their right (local +x), the extra added
// only on that side so the left edge stays put.
module key_pad(i) {
    w  = keycap_x + 2*key_clr;
    h  = keycap_y + 2*key_clr;
    pw = in_list(i, widen_keys) ? w * (1 + widen_f) : w;
    translate([switches[i][0], switches[i][1]])
        rotate(-switches[i][2])
            translate([(pw - w) / 2, 0])      // keep left edge, grow to the right
                offset(r = recess_r)
                    square([pw - 2*recess_r, h - 2*recess_r], center = true);
}

// Thumb recess: the original angled rectangle, with the right and bottom edges
// run out past the case (so, clipped by the body, they meet the outer edge -> no
// rim wall there), and the top edge extended straight up along the recess's own
// axis (same 8 deg angle) until it reaches the 4th-column corner, joining the
// recesses. thumb_up grows only the top edge.
thumb_up = 3;   // extend the recess top up to reach the 4th-column corner
module thumb_recess()
    translate([switches[13][0], switches[13][1]])
        rotate(-switches[13][2])
            translate([-(keycap_x/2 + key_clr), -(keycap_y/2 + key_clr) - thumb_up])
                square([60, 45 + thumb_up]);

// XIAO cutout: full-height rectangular hole straight through the case, sized to
// the board + clearance. Long axis is vertical. Negate xiao_rot to match the
// final mirror, as with the switch holes.
module xiao_cutout()
    translate([xiao_pos[0], xiao_pos[1], -0.5])
        rotate([0, 0, -xiao_rot])
            linear_extrude(height + 1)
                square([xiao_w + 2*xiao_clr, xiao_l + 2*xiao_clr], center = true);

// Rounded-rectangle prism of width w (x) and height h (z), extending +y by depth
// — used to carve a flat-faced recess into a wall. Corners rounded by r.
module rrect_y(w, h, depth, r)
    hull()
        for (sx = [-1, 1], sz = [-1, 1])
            translate([sx*(w/2 - r), 0, sz*(h/2 - r)])
                rotate([-90, 0, 0])
                    cylinder(h = depth, r = r, $fn = 32);

// USB-C port: flatten the slanted top-right wall with a rounded-rect recess that
// stops usb_wall short of the pocket (leaving a flat face), then drive the
// socket cutout through that flat into the pocket. Built in the XIAO's local
// frame (-y = toward the USB end) so it follows xiao_pos / xiao_rot.
module usb_port() {
    pe = -(xiao_l/2 + xiao_clr);   // pocket -y edge (local)
    fy = pe - usb_wall;            // flat face position (local y)
    zc = usb_z0 + usb_h/2;         // recess vertical centre
    translate([xiao_pos[0], xiao_pos[1], 0])
        rotate([0, 0, -xiao_rot]) {
            translate([0, fy - 20, zc])           // recess: outward 20mm to the flat
                rrect_y(flat_w, flat_h, 20, flat_r);
            translate([-usb_w/2, fy - 0.6, usb_z0])  // socket: flat -> into pocket
                cube([usb_w, usb_wall + 4, usb_h]);
        }
}

// XIAO acrylic-cover rebate: shallow pocket in the top deck, acrylic_t deep,
// larger than the XIAO pocket by acrylic_ledge per side so the acrylic drops
// in from above and rests on a ledge of deck round the pocket.
module acrylic_rebate()
    translate([xiao_pos[0], xiao_pos[1], height - acrylic_t])
        rotate([0, 0, -xiao_rot])
            linear_extrude(acrylic_t + 0.1)
                square([xiao_w + 2*(xiao_clr + acrylic_ledge),
                        xiao_l + 2*(xiao_clr + acrylic_ledge)], center = true);

// Power-switch actuator slot: rectangular hole pierced through the right wall
// at sw_pos and actuator z, generous in y for the slider's travel. Also
// extended sw_slot_inward into the case body (-x) to make room for the switch
// body to sit when the PCB is seated.
module power_slot()
    translate([sw_pos[0] - sw_slot_inward,
               sw_pos[1] - sw_slot_w/2,
               sw_z - sw_slot_h/2])
        cube([10 + sw_slot_inward, sw_slot_w, sw_slot_h]);

// Recess = union of every keycap pad (the field-following shape) + the extended
// thumb recess. Widened pinky+ring pads (see widen_keys) close the inter-column
// ribs. Sunk recess_d from the top (does not pass through). Cutouts pierce floor.
module recess_pockets()
    translate([0, 0, height - recess_d])
        linear_extrude(recess_d + 1) {
            for (i = [0 : len(switches) - 1]) key_pad(i);
            thumb_recess();
        }

// y-down (KiCad) -> y-up (upright, matches PCB front view); grow by gap+wall.
// Body and cutouts share the KiCad frame, then the whole part is mirrored.
mirror([0, 1, 0])
    difference() {
        linear_extrude(height = height)
            offset(r = gap + wall)
                polygon(outline);
        switch_cutouts();
        recess_pockets();
        cavity();
        xiao_cutout();
        acrylic_rebate();
        usb_port();
        power_slot();
    }