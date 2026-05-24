// Phantom — Totem-style 3D-printed case, LEFT half.
// Follows the PHANTOM outline/key layout, with proportions measured from the
// real Totem BLE STEP files: sunken switches (recessed switchplate, keycaps
// nearly flush with a raised rim), chamfered edges, ~ Totem heights.
//   - TOP body: chamfered shell + recessed switchplate (14mm Choc holes) set
//     ~recess below a raised rim; the key cluster is an open recess, controller
//     wing is closed on top. USB (top edge) + power-switch (right edge) cutouts.
//   - BOTTOM: flat plate with hotswap-socket cutouts (sockets poke through).
// Imports the Ergogen outline DXFs so it tracks the board. Units = mm.
//   openscad -o case.png case/case_left.scad
//   openscad -D 'part="top"'    -o top_left.stl    case/case_left.scad
//   openscad -D 'part="bottom"' -o bottom_left.stl case/case_left.scad
part = "both";

DXF   = "../output/outlines/";
board = str(DXF, "board_left.dxf");
plate = str(DXF, "plate_left.dxf");          // board - 14mm switch holes
socks = str(DXF, "socketpockets_left.dxf");  // hotswap socket cutouts
field = str(DXF, "keyfield_left.dxf");        // merged key-cluster region
caps  = str(DXF, "keycaps_left.dxf");          // per-key keycap openings

// ---- proportions (Totem-derived) ----
wall      = 2.4;    // perimeter wall thickness
bottom_t  = 1.6;    // flat bottom plate
pcb_t     = 1.6;
plate_gap = 2.2;    // PCB top -> switchplate underside
plate_t   = 1.2;    // switchplate (Totem-measured)
recess    = 6.85;   // switchplate top -> rim top (Totem-measured: deep recess)
rim_t     = 1.6;    // raised rim / top-shell thickness
chamf     = 2.5;    // top-edge chamfer
bchamf    = 1.0;    // bottom-plate edge chamfer
clr       = 0.2;
$fn = 64;

// z = 0 at PCB underside (mating face between top body and bottom tray)
plate_bot = pcb_t + plate_gap;        // 3.8
plate_top = plate_bot + plate_t;      // 5.0
rim_top   = plate_top + recess;       // 11.85

// deep bottom tray (battery space below the PCB; sockets hang in the cavity)
tray_floor = 1.7;     // tray floor thickness
tray_cav   = 3.8;     // cavity depth (LiPo + socket clearance)
tray_bot   = -(tray_floor + tray_cav);  // tray outer-bottom z

// --- M2 screw bosses joining the halves (screw from bottom into top boss) ---
screw_pos = [[-45, 18], [-32, -26], [50, -33], [62, 16]];
boss_r  = 2.4;    // boss outer radius
pilot_r = 0.8;    // pilot for M2 thread-forming
clr_r   = 1.25;   // M2 clearance in the bottom
head_r  = 2.2;    // counterbore for the head
head_d  = 1.8;
module at_screws(z) for (p = screw_pos) translate([p[0], p[1], z]) children();

module board2d() import(board);
module plate2d() import(plate);
module socks2d() import(socks);
module field2d() import(field);
module caps2d()  import(caps);
module outer2d() offset(r = wall) board2d();
module holes2d() difference() { board2d(); plate2d(); }   // 14mm key cutouts
module wing2d()  translate([55, 4]) square([28, 54], center = true);  // controller area
// thumb cluster: open it to the bottom/outer edge (no raised rim, Totem-style)
module thumb_open2d() translate([33, -31]) rotate(-8) square([46, 32], center = true);

// wall openings (shared Ergogen frame)
module usb_cut() translate([54.9, 42, pcb_t + 2.6]) cube([11, 24, 5], center = true);
module pwr_cut() translate([70, -1.3, pcb_t + 1.8]) cube([26, 7.5, 4.5], center = true);

// chamfered outer shell, solid, z 0..rim_top
module outer_shell() {
  linear_extrude(rim_top - chamf) outer2d();
  translate([0, 0, rim_top - chamf])
    hull() {
      linear_extrude(0.02) outer2d();
      translate([0, 0, chamf]) linear_extrude(0.02) offset(r = -chamf) outer2d();
    }
}

module top_body() {
  difference() {
    union() {
      // hollow chamfered shell -> outer walls
      difference() {
        outer_shell();
        translate([0, 0, -0.1]) linear_extrude(rim_top + 0.2) offset(r = clr) board2d();
      }
      // recessed switchplate (14mm holes), controller wing left open for the XIAO
      difference() {
        translate([0, 0, plate_bot]) linear_extrude(plate_t) outer2d();
        translate([0, 0, plate_bot - 0.1]) linear_extrude(plate_t + 0.2) holes2d();
        translate([0, 0, plate_bot - 0.1]) linear_extrude(plate_t + 0.2) wing2d();
      }
      // raised rim + closed wing top; open over the sunken key cluster
      difference() {
        translate([0, 0, rim_top - rim_t]) linear_extrude(rim_t) outer2d();
        translate([0, 0, rim_top - rim_t - 0.1]) linear_extrude(rim_t + 0.2) field2d();
      }
      // internal ribs between keys, rising to 1.5mm below the rim (Totem)
      translate([0, 0, plate_top])
        linear_extrude(rim_top - 1.5 - plate_top)
          difference() { field2d(); caps2d(); }
      // M2 screw bosses (solid posts up to the rim)
      at_screws(0) cylinder(h = rim_top, r = boss_r);
    }
    // openings: USB, power, and the open thumb cluster (rim removed above plate)
    usb_cut();
    pwr_cut();
    translate([0, 0, plate_top]) linear_extrude(rim_top - plate_top + 1) thumb_open2d();
    // screw pilot holes (thread-forming for M2)
    at_screws(0.8) cylinder(h = rim_top, r = pilot_r);
  }
}

// DEEP bottom tray: floor + perimeter walls, open cavity for the LiPo battery
// (the hotswap sockets hang in this cavity), chamfered bottom edge, screw posts
// with clearance holes + head counterbores on the outer bottom face.
module bottom_tray() {
  difference() {
    union() {
      // chamfered floor
      translate([0, 0, tray_bot + bchamf]) linear_extrude(tray_floor - bchamf) outer2d();
      translate([0, 0, tray_bot]) hull() {
        linear_extrude(0.02) offset(r = -bchamf) outer2d();
        translate([0, 0, bchamf]) linear_extrude(0.02) outer2d();
      }
      // perimeter walls up to the mating face (PCB rests on these)
      translate([0, 0, tray_bot + tray_floor])
        linear_extrude(-tray_bot - tray_floor)
          difference() { outer2d(); offset(r = -wall) outer2d(); }
      // screw posts spanning the tray
      at_screws(tray_bot) cylinder(h = -tray_bot, r = boss_r);
    }
    // screw clearance + head counterbore on the outer bottom
    at_screws(tray_bot - 0.1) cylinder(h = -tray_bot + 0.2, r = clr_r);
    at_screws(tray_bot - 0.1) cylinder(h = head_d + 0.1, r = head_r);
  }
}

if (part == "bottom") bottom_tray();
if (part == "top")    top_body();
if (part == "both") { top_body(); translate([0, 0, -22]) bottom_tray(); }
