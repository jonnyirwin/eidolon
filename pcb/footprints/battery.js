// Two LiPo battery solder pads (+/-) — TOTEM-style geometry: 2.5mm circular
// thru-hole pads with 1.25mm drill, spaced 5mm centre-to-centre. Sized to
// take stripped 30AWG ~ 28AWG battery leads with room for fillet.
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
      (descr "LiPo battery solder pads (+/-), TOTEM geometry")
      (tags "battery lipo totem")
      ${p.at}
      (fp_text reference "${p.ref}" (at 0 -3.0 ${p.r}) (layer ${p.side}.SilkS) ${p.ref_hide} (effects (font (size 1 1) (thickness 0.15))))
      (fp_text value "" (at 0 0) (layer ${p.side}.SilkS) hide (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "+" (at -2.5 -2.8 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "-" (at  2.5 -2.8 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 1 1) (thickness 0.15))))
      (fp_text user "BATT" (at 0 2.8 ${p.r}) (layer ${p.side}.SilkS) (effects (font (size 0.8 0.8) (thickness 0.12))))
      (pad 1 thru_hole circle (at -2.5 0 ${p.r}) (size 2.5 2.5) (drill 1.25) (layers *.Cu *.Mask) ${p.P})
      (pad 2 thru_hole circle (at  2.5 0 ${p.r}) (size 2.5 2.5) (drill 1.25) (layers *.Cu *.Mask) ${p.N})
    )
  `
}
