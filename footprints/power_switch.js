// 3-pin SPDT slide power switch (SS-12D00 / SK-12D07 style), through-hole.
// Meant to sit at the board edge with the actuator overhanging so it protrudes
// from the case side. Pins in a row at 2.5mm pitch.
//
//   A: one throw  (wire to battery +)
//   B: common     (wire to XIAO BAT+)
//   C: other throw (off position; usually left unconnected)
module.exports = {
  params: {
    designator: 'SW',
    side: 'F',
    A: undefined,
    B: undefined,
    C: undefined
  },
  body: p => `
    (module power_switch_spdt (layer F.Cu) (tstamp 0)
      (descr "SPDT slide power switch, edge-mount (actuator overhangs)")
      (tags "power switch slide spdt")
      ${p.at}
      (fp_text reference "${p.ref}" (at 0 -3.2 ${p.r}) (layer ${p.side}.SilkS) ${p.ref_hide} (effects (font (size 1 1) (thickness 0.15))))
      (fp_text value "" (at 0 0) (layer ${p.side}.SilkS) hide (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "PWR" (at 0 2.6 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 0.8 0.8) (thickness 0.12))))
      ${'' /* switch body ~8 x 3.5mm; actuator side is +y (toward the board edge) */}
      (fp_line (start -4.0 -1.75) (end 4.0 -1.75) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start -4.0 1.75) (end 4.0 1.75) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start -4.0 -1.75) (end -4.0 1.75) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start 4.0 -1.75) (end 4.0 1.75) (layer ${p.side}.SilkS) (width 0.12))
      ${'' /* 3 pins at 2.5mm pitch */}
      (pad 1 thru_hole circle (at -2.5 0 ${p.r}) (size 1.6 1.6) (drill 0.9) (layers *.Cu *.Mask) ${p.A})
      (pad 2 thru_hole circle (at 0 0 ${p.r}) (size 1.6 1.6) (drill 0.9) (layers *.Cu *.Mask) ${p.B})
      (pad 3 thru_hole circle (at 2.5 0 ${p.r}) (size 1.6 1.6) (drill 0.9) (layers *.Cu *.Mask) ${p.C})
    )
  `
}
