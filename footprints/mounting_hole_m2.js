// M2 mounting hole — NPTH, 2.2mm clearance for an M2 case-to-case bolt.
// Used at the four corners of the PCB so the top + bottom case halves can be
// bolted together with the shaft passing through the PCB.
module.exports = {
  params: {
    designator: 'MH',
    side: 'F'
  },
  body: p => `
    (module mounting_hole_m2 (layer F.Cu) (tstamp 0)
      (descr "M2 NPTH mounting hole, 2.2mm clearance for case bolts")
      (tags "mounting hole m2 npth")
      ${p.at}
      (fp_text reference "${p.ref}" (at 0 2.5 ${p.r}) (layer ${p.side}.SilkS) ${p.ref_hide} (effects (font (size 0.6 0.6) (thickness 0.1))))
      (fp_text value "" (at 0 0) (layer ${p.side}.SilkS) hide (effects (font (size 1 1) (thickness 0.15))))
      (pad "" np_thru_hole circle (at 0 0) (size 2.2 2.2) (drill 2.2) (layers *.Cu *.Mask))
    )
  `
};
