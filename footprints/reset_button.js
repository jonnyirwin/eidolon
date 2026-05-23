// Compact 2-pad SMD reset button (~4 x 2.4 mm body), replacing the large
// built-in `button` (a 6 mm ALPS tact switch). Suits a small SMD tactile
// reset such as the Panasonic EVQ-P / Alps SKRPABE family.
//
//   from / to: the two switch terminals (e.g. from=RST, to=GND)
//   side:      F or B (default F)
module.exports = {
  params: {
    designator: 'RST',
    side: 'F',
    from: undefined,
    to: undefined
  },
  body: p => `
    (module reset_button_smd (layer F.Cu) (tstamp 0)
      (descr "Compact SMD reset button")
      (tags "reset button SMD")
      ${p.at}
      (fp_text reference "${p.ref}" (at 0 -2.2) (layer ${p.side}.SilkS) ${p.ref_hide} (effects (font (size 1 1) (thickness 0.15))))
      (fp_text value "" (at 0 0) (layer ${p.side}.SilkS) hide (effects (font (size 1 1) (thickness 0.15))))
      ${'' /* body outline ~4.0 x 2.4 mm */}
      (fp_line (start -2.0 -1.2) (end 2.0 -1.2) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start -2.0 1.2) (end 2.0 1.2) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start -2.0 -1.2) (end -2.0 1.2) (layer ${p.side}.SilkS) (width 0.12))
      (fp_line (start 2.0 -1.2) (end 2.0 1.2) (layer ${p.side}.SilkS) (width 0.12))
      ${'' /* two terminals, 3 mm apart */}
      (pad 1 smd rect (at -1.5 0 ${p.r}) (size 1.0 1.4) (layers ${p.side}.Cu ${p.side}.Paste ${p.side}.Mask) ${p.from})
      (pad 2 smd rect (at 1.5 0 ${p.r}) (size 1.0 1.4) (layers ${p.side}.Cu ${p.side}.Paste ${p.side}.Mask) ${p.to})
    )
  `
}
