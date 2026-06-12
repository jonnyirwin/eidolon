// SOD-123 diode, single-side SMD. Default side F so it can sit in the Choc
// south LED gap on the TOP of the board — keeping the bottom clear for hotswap
// sockets only (so the case bottom needs just socket pockets).
//   from: anode   (per-key matrix node)
//   to:   cathode (bar end) -> row net   [COL2ROW]
module.exports = {
  params: {
    designator: 'D',
    side: 'F',
    from: undefined,
    to: undefined
  },
  body: p => `
    (module diode_sod123 (layer F.Cu) (tstamp 0)
      (descr "SOD-123 diode, single-side SMD (Choc LED-gap placement)")
      (tags "diode sod123")
      ${p.at}
      (fp_text reference "${p.ref}" (at 0 1.6 ${p.r}) (layer ${p.side}.SilkS) ${p.ref_hide} (effects (font (size 0.7 0.7) (thickness 0.1))))
      (fp_text value "" (at 0 0) (layer ${p.side}.SilkS) hide (effects (font (size 0.7 0.7) (thickness 0.1))))
      ${'' /* body + cathode bar (pad 2 / "to" is the cathode) */}
      (fp_line (start -1.0 -0.85) (end 1.0 -0.85) (layer ${p.side}.SilkS) (width 0.1))
      (fp_line (start -1.0 0.85) (end 1.0 0.85) (layer ${p.side}.SilkS) (width 0.1))
      (fp_line (start 1.0 -0.85) (end 1.0 0.85) (layer ${p.side}.SilkS) (width 0.12))
      (pad 1 smd rect (at -1.65 0 ${p.r}) (size 0.9 1.2) (layers ${p.side}.Cu ${p.side}.Paste ${p.side}.Mask) ${p.from})
      (pad 2 smd rect (at 1.65 0 ${p.r}) (size 0.9 1.2) (layers ${p.side}.Cu ${p.side}.Paste ${p.side}.Mask) ${p.to})
    )
  `
}
