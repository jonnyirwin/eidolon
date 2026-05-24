// Simple 2-pad LiPo battery connection (solder the battery leads here).
// Adapted from the trochilidae BatteryPads concept, single-sided.
//   P: battery positive (route to the power switch)
//   N: battery negative (GND)
module.exports = {
  params: {
    designator: 'BT',
    side: 'F',
    P: undefined,
    N: undefined
  },
  body: p => `
    (module battery_pads (layer F.Cu) (tstamp 0)
      (descr "LiPo battery solder pads (+/-)")
      (tags "battery lipo")
      ${p.at}
      (fp_text reference "${p.ref}" (at 0 -2.6 ${p.r}) (layer ${p.side}.SilkS) ${p.ref_hide} (effects (font (size 1 1) (thickness 0.15))))
      (fp_text value "" (at 0 0) (layer ${p.side}.SilkS) hide (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "+" (at -1.95 -2.4 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "-" (at 1.95 -2.4 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "BATT" (at 0 2.4 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 0.8 0.8) (thickness 0.12))))
      (pad 1 thru_hole circle (at -1.95 0 ${p.r}) (size 2.0 2.0) (drill 1.2) (layers *.Cu *.Mask) ${p.P})
      (pad 2 thru_hole circle (at 1.95 0 ${p.r}) (size 2.0 2.0) (drill 1.2) (layers *.Cu *.Mask) ${p.N})
    )
  `
}
