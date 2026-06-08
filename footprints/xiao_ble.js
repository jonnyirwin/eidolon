// Seeed XIAO BLE (nRF52840) surface-mount castellated footprint.
// Adapted from GEIGEIGEIST/TOTEM v0.3 "xiao-ble-smd-cutout.kicad_mod":
//   - 14 thru-hole oval pads at x=±7.62, 2.54mm pitch, drill 1mm with the
//     drill OFFSET 0.475 toward the board center -> half-holes for soldering
//     to the XIAO's castellated edge, while keeping a normal copper pad on
//     the inside that can route on either layer.
//   - 4 inner thru-hole pads near the USB end aligning with the XIAO's underside
//     SWD debug group (SWDIO / SWCLK / RESET / GND). Left UNCONNECTED here --
//     access holes only. (Verified against GEIGEIGEIST/TOTEM: these are the
//     debug pads, NOT the battery -- an earlier revision had this backwards.)
//   - 2 thru-hole pads at the side reaching the XIAO underside BAT + GND -- this
//     is the actual battery connection (cell -> power switch -> BATT -> here).
//
// Local frame: USB end at -y, far end at +y. XIAO is mounted FACE-UP on top
// of the keyboard PCB so component-side pins map directly (no x-mirror).
// The existing Phantom config uses rotate: 0, which puts the XIAO USB toward
// the KiCad -y direction (top-right of the source PCB) — this matches.
//
// Net mapping (face-up XIAO, USB at local -y):
//   left col  (x = -7.62), -y -> +y:  D0 D1 D2 D3 D4 D5 D6
//   right col (x = +7.62), -y -> +y:  D7 D8 D9 D10 3V3 GND 5V
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
    // castellated half-hole: drill offset 0.475mm toward board centre (+x for
    // left col, -x for right col), so the drilled cylinder breaks out as a
    // half-cylinder on the board edge.
    const cast = (name, x, y, net) => {
      const off = x < 0 ? '0.475 0' : '-0.475 0';
      return `(pad "${name}" thru_hole oval (at ${x} ${y} ${p.r}) (size 2.75 1.8) (drill 1 (offset ${off})) (layers *.Cu *.Mask) ${net})`;
    };
    // inner access hole: small thru-hole 1.397 dia, 1.016 drill
    const access = (name, x, y, net) =>
      `(pad "${name}" thru_hole circle (at ${x} ${y} ${p.r}) (size 1.397 1.397) (drill 1.016) (layers *.Cu *.Mask) ${net})`;
    return `
    (module xiao_ble (layer F.Cu) (tstamp 0)
      (descr "Seeed XIAO BLE (nRF52840) castellated SMT mount, TOTEM-style")
      (tags "xiao nrf52840 ble castellated")
      ${p.at}
      (fp_text reference "${p.ref}" (at 0 11 ${p.r}) (layer ${p.side}.SilkS) ${p.ref_hide} (effects (font (size 1 1) (thickness 0.15))))
      (fp_text value "" (at 0 0) (layer ${p.side}.SilkS) hide (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "XIAO" (at 0 8.5 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "USB" (at 0 -9.5 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 0.8 0.8) (thickness 0.12))))
      ${'' /* board outline 17.78 x 21 mm */}
      (fp_line (start -8.89 -10.5) (end  8.89 -10.5) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start -8.89  10.5) (end  8.89  10.5) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start -8.89 -10.5) (end -8.89  10.5) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start  8.89 -10.5) (end  8.89  10.5) (layer ${p.side}.SilkS) (width 0.12))
      ${'' /* left col (x = -7.62): D0..D6, USB end (-y) -> far end (+y) */}
      ${cast('1',  -7.62, -7.62, p.D0)}
      ${cast('2',  -7.62, -5.08, p.D1)}
      ${cast('3',  -7.62, -2.54, p.D2)}
      ${cast('4',  -7.62,  0,    p.D3)}
      ${cast('5',  -7.62,  2.54, p.D4)}
      ${cast('6',  -7.62,  5.08, p.D5)}
      ${cast('7',  -7.62,  7.62, p.D6)}
      ${'' /* right col (x = +7.62): D7..D10, 3V3, GND, 5V, USB end (-y) -> far end (+y) */}
      ${cast('14',  7.62, -7.62, p.D7)}
      ${cast('13',  7.62, -5.08, p.D8)}
      ${cast('12',  7.62, -2.54, p.D9)}
      ${cast('11',  7.62,  0,    p.D10)}
      ${cast('10',  7.62,  2.54, p.P3V3)}
      ${cast('9',   7.62,  5.08, p.GND)}
      ${cast('8',   7.62,  7.62, p.P5V)}
      ${'' /* SWD debug group on the XIAO underside near the USB end
            (SWDIO/SWCLK/RESET/GND). Left UNCONNECTED -- access holes only, not
            wired into the keyboard. NOTE: these are NOT battery pads. */}
      ${access('SWDIO',  -1.27, -8.572, '')}
      ${access('SWCLK',   1.27, -8.572, '')}
      ${access('RESET',  -1.27, -6.032, '')}
      ${access('DBG_GND', 1.27, -6.032, '')}
      ${'' /* Battery: the XIAO underside BAT pad + adjacent GND, at the side
            ~mid-board. The cell connects here via the power switch on BATT. */}
      ${access('BAT', -4.445, -0.317, p.BAT)}
      ${access('GND', -4.445, -2.222, p.GND)}
    )
    `;
  }
};
