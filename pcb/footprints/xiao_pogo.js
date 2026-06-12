// Seeed XIAO (nRF52840 BLE) on pogo pins, mounted face-down over the PCB.
// Geometry adapted from jcmkk3/trochilidae `XiaoSimplePogo.kicad_mod`:
// 14 thru-hole pogo landing pads in two columns (2.54mm pitch, 15.33mm apart)
// plus a B+ battery pad. Footprint is ~17.8 x 21 mm; USB faces the +y (top) edge.
//
// Pad->pin mapping assumes the standard XIAO castellation mounted FACE-DOWN
// (USB toward +y). VERIFY against the XIAO datasheet before ordering; the user
// adapts firmware to whatever GPIO the matrix is wired to here.
//   left col  (x 1.25, top->bottom):  5V  GND 3V3 D10 D9 D8 D7
//   right col (x16.58, top->bottom):  D0  D1  D2  D3  D4 D5 D6
module.exports = {
  params: {
    designator: 'MCU',
    side: 'F',
    P5V: { type: 'net', value: 'P5V' },
    GND: { type: 'net', value: 'GND' },
    P3V3: { type: 'net', value: 'P3V3' },
    BAT: { type: 'net', value: 'BAT' },
    D0: { type: 'net', value: 'D0' }, D1: { type: 'net', value: 'D1' },
    D2: { type: 'net', value: 'D2' }, D3: { type: 'net', value: 'D3' },
    D4: { type: 'net', value: 'D4' }, D5: { type: 'net', value: 'D5' },
    D6: { type: 'net', value: 'D6' }, D7: { type: 'net', value: 'D7' },
    D8: { type: 'net', value: 'D8' }, D9: { type: 'net', value: 'D9' },
    D10: { type: 'net', value: 'D10' }
  },
  body: p => {
    // pad helper: thru-hole pogo landing
    const pad = (name, x, y, net) =>
      `(pad "${name}" thru_hole circle (at ${x} ${y} ${p.r}) (size 1.524 1.524) (drill 1) (layers *.Cu *.Mask) ${net})`
    return `
    (module xiao_pogo (layer F.Cu) (tstamp 0)
      (descr "Seeed XIAO on pogo pins (face-down), adapted from trochilidae XiaoSimplePogo")
      (tags "xiao nrf52840 ble pogo")
      ${p.at}
      (fp_text reference "${p.ref}" (at 8.9 -10.5) (layer ${p.side}.SilkS) ${p.ref_hide} (effects (font (size 1 1) (thickness 0.15))))
      (fp_text value "" (at 0 0) (layer ${p.side}.SilkS) hide (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "XIAO" (at 8.9 -8 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "USB" (at 8.9 -20 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 0.8 0.8) (thickness 0.12))))
      ${'' /* body outline ~17.8 x 21 mm */}
      (fp_line (start 0 0) (end 17.8 0) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start 0 -21) (end 17.8 -21) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start 0 0) (end 0 -21) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start 17.8 0) (end 17.8 -21) (layer ${p.side}.SilkS) (width 0.12))
      ${'' /* left column: 5V GND 3V3 D10 D9 D8 D7 (top->bottom) */}
      ${pad('5V',  1.25, -18.11782, p.P5V)}
      ${pad('GND', 1.25, -15.57782, p.GND)}
      ${pad('3V3', 1.25, -13.03782, p.P3V3)}
      ${pad('D10', 1.25, -10.49782, p.D10)}
      ${pad('D9',  1.25,  -7.95782, p.D9)}
      ${pad('D8',  1.25,  -5.41782, p.D8)}
      ${pad('D7',  1.25,  -2.87782, p.D7)}
      ${'' /* right column: D6 D5 D4 D3 D2 D1 D0 (bottom->top) */}
      ${pad('D6',  16.581, -2.87782, p.D6)}
      ${pad('D5',  16.581, -5.41782, p.D5)}
      ${pad('D4',  16.581, -7.95782, p.D4)}
      ${pad('D3',  16.581, -10.49782, p.D3)}
      ${pad('D2',  16.581, -13.03782, p.D2)}
      ${pad('D1',  16.581, -15.57782, p.D1)}
      ${pad('D0',  16.581, -18.11782, p.D0)}
      ${'' /* battery + landing (XIAO underside BAT+) */}
      (pad "B+" thru_hole oval (at 4.4705 -10.93409 ${p.r}) (size 1.5 1) (drill 0.508) (layers *.Cu *.Mask) ${p.BAT})
      ${'' /* copper-pour keepout under the whole XIAO so a ground plane never
            reaches the nRF52840 antenna (BLE detuning). From XiaoSimplePogo. */}
      (zone (net 0) (net_name "") (layers F&B.Cu) (hatch edge 0.508)
        (connect_pads (clearance 0)) (min_thickness 0.254)
        (keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour not_allowed) (footprints allowed))
        (fill (thermal_gap 0.508) (thermal_bridge_width 0.508))
        (polygon (pts (xy 0 0) (xy 17.8 0) (xy 17.8 -21) (xy 0 -21))))
    )
    `
  }
}
