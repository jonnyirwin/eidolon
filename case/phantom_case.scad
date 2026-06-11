// Phantom case — BOTH halves (left geometry; right = mirrored build).
// Outline from the PCB Edge.Cuts of lephantom.kicad_pcb (6 lines + 5 arcs,
// exact mm coordinates) plus the two routing reliefs now carried by BOTH
// ergogen PCBs (P1/P2 top edge -0.3mm, P10/P11 pinky edge -0.7mm), so the two
// boards are exact mirror images and one case design fits both. The case
// footprint is the PCB outline grown outward by (gap + wall) so the PCB drops
// inside the walls:
//   gap  = 0.15mm clearance between PCB edge and inner wall
//   wall = 2.0mm  case wall thickness
// then extruded. This pass produces the solid outer shape only.
//
//   openscad -o phantom_case_left.stl  case/phantom_case.scad
//   openscad -D right=true -o phantom_case_right.stl case/phantom_case.scad
//
// Right-half fit (verified against the routed ergogen boards): every
// footprint origin mirrors exactly (x_left + x_right = 170, same y), and the
// four case bolts ARE the PCB mounting holes. The XIAO keeps its orientation
// under the PCB mirror, but its position mirrors and the pocket/USB cutout
// are symmetric about the pocket axis, so the mirrored case still fits; the
// power switch flips orientation but its body centre and actuator height are
// unchanged, so the mirrored wall slot lines up.
right = false;   // build the right-half case (mirror of the left)

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
usb_h    = 4.0;            // USB-C cutout height (3.2 socket + 0.8 clearance)
// SMD-mounted XIAO (castellated on PCB top): XIAO board sits on plate_bot with
// its own 1.0mm thickness, then the USB-C connector body extends ~3.16mm above
// that. Connector top is at plate_bot + 1.0 + 3.16 = plate_bot + 4.16. Place
// the cutout bottom 0.3mm below the XIAO PCB top to clear the connector body.
usb_z0   = plate_bot + 0.7;
// Acrylic cover over the XIAO through-hole: shallow rebate in the top deck,
// acrylic drops in flush with the deck top and rests on a ledge round the
// pocket. With SMD mount there's no MCU bump, so the rebate sits in the deck.
acrylic_t     = 1.5;       // acrylic thickness
acrylic_ledge = 1.0;       // ledge each side (rebate footprint > pocket footprint)
// Retention lips: deck material above the acrylic on the +/-y short ends that
// overhangs by lip_overhang, capturing the acrylic. One-time install: angle
// the acrylic to slip one short edge under one lip, then bow the acrylic
// slightly to push the other short edge past the second lip.
lip_t       = 0.6;        // lip vertical thickness (~3 print layers at 0.2mm)
lip_overhang= 0.8;        // lip A inward projection (full flat); lip B same width
                          // but flat for lip_b_flat with the rest chamfered.
lip_b_flat  = 0.4;        // lip B's flat retention width at the inner end
                          // (lip_overhang - lip_b_flat = chamfer width)
// Battery pocket — 301230 LiPo cell (3.0 x 12 x 30 mm) sits ON TOP of the PCB
// in the empty palm-rest area, hidden between the PCB and the underside of the
// deck. Pocket is cut UPWARD from plate_bot through the plate into the deck so
// the cell drops in from below before the PCB is seated; wires bend up to F.Cu
// pads on the PCB top (5mm apart, see footprints/battery.js). Bottom of the
// pocket is open to the under-PCB cavity (which the bottom shell will close).
bat_pos    = [59.625, 80.0]; // KiCad — palm-rest area, clear of every keycap pad
bat_rot    = 0;              // long axis along x (-90 = along y)
bat_x      = 38.75;          // pocket: 301230 cell (30) + 0.5 at +x + 8.25 wire
                             // well at -x. The well must hold the pad pair's
                             // 8.5mm copper span (TOTEM 5mm pitch, 2.5mm pads):
                             // moving the pads instead doesn't work — east puts
                             // pad-2 solder under the cell (0.25 margin), west
                             // pokes pad 1 out the wall. -x wall at 40.25 keeps
                             // 0.5 to pad-1 copper and 1.15 to the BL bolt shaft
bat_y      = 14.0;           // pocket width (cell 12 + 1mm each side)
bat_depth  = 3.5;            // cell + 0.5 clearance above plate_bot
// MSK-12D19 power switch — through-hole SPDT on the PCB right edge with the
// actuator overhanging. The case needs a slot in the right wall for the
// actuator/slider; sized for 1.5mm slider travel + clearance.
sw_pos   = [145.5, 60.27]; // switch centre, KiCad — matches ergogen power placement
sw_z     = plate_bot + 1.5;// slot vertical centre = actuator height above the PCB
sw_slot_w = 8.0;           // slot width  (y, along slider travel + cap)
sw_slot_h = 4.0;           // slot height (z)
sw_slot_inward = 5.0;      // how much the slot extends into the case body (-x)
// M2 socket-cap case bolts at 4 corners (KiCad coords). Head sinks into a
// pocket on the deck top; shaft passes through PCB and into a hex-nut pocket
// in the bottom shell. Positions chosen to clear all switches, the MCU pocket,
// the battery pocket, and the power switch slot.
bolts = [
    [ 37,  22],   // TL — inside upper-left arc, above pinky col
    [115,  24],   // TR — above switch 3, clear of MCU pocket
    [ 38,  82],   // BL — left of battery pocket
    [137,  78],   // BR — between thumb 14 pad and right case wall, biased right
];
m2_head_d  = 4.5;  // socket cap head pocket dia (3.8mm head + 0.7 clearance)
m2_head_h  = 2.0;  // head pocket depth = head height -> head top flush w/ deck
m2_shaft_d = 2.2;  // bolt shaft clearance hole
arc_n  = 64;     // points sampled per arc corner
$fn = 128;

// ---- Edge.Cuts vertices (exact KiCad coords, mm, y-down) ----
P1  = [ 39.624000, 16.718000];  // -0.3mm top-edge relief (routing lanes; matches both PCBs)
P2  = [105.918000, 14.940000];  // -0.3mm top-edge relief (paired with P1)
P3  = [112.016555, 16.811266];
P4  = [143.816302, 31.614407];
P5  = [144.187844, 32.512000];
P6  = [144.272000, 66.802000];
P7  = [130.914271, 95.075525];
P8  = [123.190000, 98.806000];
P9  = [ 43.688000, 89.154000];
P10 = [ 34.314644, 79.908818];  // -0.7mm pinky-edge relief (S12/S13 pad 2 under mirror; matches both PCBs)
P11 = [ 30.197623, 27.391512];  // -0.7mm pinky-edge relief (paired with P10)

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
// (vertical) edge out by pcb_pad (the ergogen boards carry the same +pcb_pad
// edge). The upper-right corner — fillet tangent points T / P2t, arc mid M_t,
// and the vertical-edge corner Pc — is taken VERBATIM from the as-built
// ergogen board (output/pcbs/phantom_left.kicad_pcb Edge.Cuts, frame offset
// +80, +58.97). It was originally derived parametrically here; after the
// -0.3mm top-edge relief the board's stored arc is the source of truth, and
// re-deriving tangency would cut up to 0.15mm inside the PCB edge.
pcb_pad = 3.0;
P5e = P5 + [pcb_pad, 0];
P6e = P6 + [pcb_pad, 0];
T   = [110.723000, 16.209000];  // diagonal-side tangent point (board exact)
M_t = [108.435000, 15.451000];  // fillet arc mid                (board exact)
P2t = [106.034000, 14.937000];  // top-edge tangent point        (board exact)
Pc  = [147.189000, 33.098000];  // vertical edge ∩ diagonal      (board exact)

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

// ---- Choc switch positions, from the routed ergogen board (KiCad coords) ----
// [x, y, rotation_deg] — the 15 PG1350 footprint origins of phantom_left,
// extracted from output/pcbs/phantom_left.kicad_pcb (frame offset +80, +58.97
// from the ergogen origin). These ARE the as-built positions; the previous
// list was traced from the original lephantom.kicad_pcb and deviated up to
// 0.154mm from the ergogen recreation.
switches = [
    [ 80.000000, 24.970000,  0],   // S3
    [ 59.920577, 28.166596,  3],   // S11
    [ 98.000000, 28.570000,  0],   // S6
    [116.000000, 37.270000,  0],   // S8
    [ 41.518352, 41.504690,  5],   // S13
    [ 80.000000, 41.970000,  0],   // S2
    [ 60.810289, 45.143298,  3],   // S10
    [ 98.000000, 45.570000,  0],   // S5
    [116.000000, 54.270000,  0],   // S7
    [ 43.000000, 58.440000,  5],   // S12
    [ 80.000000, 58.970000,  0],   // S1
    [ 61.700000, 62.120000,  3],   // S9
    [ 98.000000, 62.570000,  0],   // S4
    [104.000000, 83.070000, -8],   // S14
    [121.824825, 85.575116, -8],   // S15
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
                square([37, 45 + thumb_up]);

// XIAO cutout: rectangular hole straight through the deck above the XIAO so
// you can see/access the board from above. Long axis is vertical. Negate
// xiao_rot to match the final mirror, as with the switch holes.
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
                    cylinder(h = depth, r = r, $fn = 96);

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
            // stadium-shaped socket cutout (usb_w x usb_h, semicircular ends)
            translate([0, fy - 0.6 + (usb_wall + 4)/2, zc])
                rotate([90, 0, 0])
                    linear_extrude(usb_wall + 4, center = true)
                        offset(r = usb_h/2)
                            square([usb_w - usb_h, 0.001], center = true);
        }
}

// XIAO acrylic-cover rebate: stepped pocket in the top deck.
//   - Bottom acrylic_t mm: full footprint, where the acrylic sits.
//   - Upper lip_t mm: asymmetric lips on the +/-y short ends.
//       Lip A (+y): square — full lip_overhang flat overhang for firm retention.
//       Lip B (-y): lip_b_flat flat overhang at the inner tip, with the outer
//                   portion chamfered up to the deck top so the acrylic edge
//                   slides under during the one-time snap-in install.
module acrylic_rebate() {
    fw = xiao_w + 2*(xiao_clr + acrylic_ledge);
    fh = xiao_l + 2*(xiao_clr + acrylic_ledge);
    rebate_depth = acrylic_t + lip_t;
    // y extents of the lip-level cutout at the bottom (z = h - lip_t):
    //   lip A side: cutout up to (fh/2 - lip_overhang)  — lip A's flat
    //   lip B side: cutout down to (-fh/2 + lip_b_flat) — lip B's flat
    bot_y_min = -fh/2 + lip_b_flat;
    bot_y_max =  fh/2 - lip_overhang;
    // y extents at the top (z = h): both lips fully grown to lip_overhang.
    top_y_min = -fh/2 + lip_overhang;
    top_y_max =  fh/2 - lip_overhang;
    translate([xiao_pos[0], xiao_pos[1], 0])
        rotate([0, 0, -xiao_rot])
            union() {
                // Lip section: hull from the bottom (asymmetric y range, lip
                // B has lip_b_flat retention) to the top (both lips at full
                // lip_overhang). Slanted face on the -y side = lip B chamfer.
                hull() {
                    translate([0, (bot_y_min + bot_y_max)/2, height - lip_t])
                        linear_extrude(0.01)
                            square([fw, bot_y_max - bot_y_min], center = true);
                    translate([0, (top_y_min + top_y_max)/2, height - 0.01])
                        linear_extrude(0.02)
                            square([fw, top_y_max - top_y_min], center = true);
                }
                // Acrylic well
                translate([0, 0, height - rebate_depth])
                    linear_extrude(acrylic_t + 0.01)
                        square([fw, fh], center = true);
            }
}

// Battery pocket: cut from plate_bot upward to plate_bot+bat_depth, in an
// empty area of the plate/deck above the PCB (no switches there). Pocket
// floor is the PCB top; pocket open at the bottom into the under-PCB cavity.
module battery_pocket()
    translate([bat_pos[0], bat_pos[1], plate_bot - 0.5])
        rotate([0, 0, -bat_rot])
            linear_extrude(bat_depth + 0.5)
                square([bat_x, bat_y], center = true);

// Power-switch actuator slot: rectangular hole pierced through the right wall
// at sw_pos and actuator z, generous in y for the slider's travel. Also
// extended sw_slot_inward into the case body (-x) to make room for the switch
// body to sit when the PCB is seated.
module power_slot() {
    length = 10 + sw_slot_inward;
    r = 1.5;  // corner radius (<= sw_slot_h/2 = 2)
    translate([sw_pos[0] - sw_slot_inward, sw_pos[1], sw_z])
        rotate([0, 90, 0])
            linear_extrude(length)
                offset(r = r)
                    square([sw_slot_h - 2*r, sw_slot_w - 2*r], center = true);
}

// Recess = union of every keycap pad (the field-following shape) + the extended
// thumb recess. Widened pinky+ring pads (see widen_keys) close the inter-column
// ribs. Sunk recess_d from the top (does not pass through). Cutouts pierce floor.
module recess_pockets()
    translate([0, 0, height - recess_d])
        linear_extrude(recess_d + 1) {
            for (i = [0 : len(switches) - 1]) key_pad(i);
            thumb_recess();
        }

// Outer body: vertical wall from z=0 to z=height, outline grown by gap+wall.
// The top outside edge is filleted by minkowski-summing an inset prism with an
// upper-hemisphere kernel of radius top_r — only the top edge rounds; the
// bottom stays sharp (sits flat) and the vertical sides stay vertical.
top_r = 1.0;  // top outside edge fillet radius
module body()
    minkowski() {
        linear_extrude(height - top_r)
            offset(r = gap + wall - top_r) polygon(outline);
        intersection() {
            sphere(r = top_r, $fn = 48);
            translate([0, 0, top_r / 2])
                cube([2*top_r + 0.1, 2*top_r + 0.1, top_r + 0.1], center = true);
        }
    }

// Bolt holes: head pocket recessed into the deck top, shaft hole through.
module bolt_holes()
    for (b = bolts) {
        translate([b[0], b[1], height - m2_head_h])
            linear_extrude(m2_head_h + 0.1)
                circle(d = m2_head_d, $fn = 96);
        translate([b[0], b[1], -1])
            linear_extrude(height + 2)
                circle(d = m2_shaft_d, $fn = 96);
    }

// Full top-case shape (y-down KiCad frame, then mirror([0,1,0]) flips to the
// upright view). Exposed as a module so phantom_case_bottom.scad can include
// it in a preview render.
module top_case()
    mirror([0, 1, 0])
        difference() {
            body();
            switch_cutouts();
            recess_pockets();
            cavity();
            xiao_cutout();
            acrylic_rebate();
            usb_port();
            battery_pocket();
            power_slot();
            bolt_holes();
        }

// SUPPRESS_TOP lets phantom_case_bottom.scad `include` this file for shared
// geometry (outline, switches, bolts, top_case module) without also rendering
// the top case here. `right` mirrors the build for the right half.
if (is_undef(SUPPRESS_TOP)) {
    if (right) mirror([1, 0, 0]) top_case();
    else top_case();
}