# Body model credits

`frontend/public/models/body.glb` is built by `build_body_model.mjs` from the sources below.
The combined model is licensed **CC BY-SA 4.0**. Anyone who reuses or adapts it must credit
the sources below and share their adaptation under the same licence.

| Organ node | Source | Licence | Notes |
|---|---|---|---|
| skeleton, brain, heart, liver, pancreas, intestines, kidneys, skin | BodyParts3D 4.0 | CC BY-SA 2.1 JP | Simplified with meshoptimizer |
| thyroid, stomach, bladder | Z-Anatomy | CC BY-SA 4.0 | Subdivided once and smoothed. The stomach's display window was closed and faired |
| lungs | Z-Anatomy, five lobes | CC BY-SA 4.0 | Small hilum openings closed |
| uterus, ovaries | Procedural (`female_pelvis.mjs`) | CC BY-SA 4.0 | **Illustrative**, see below |
| eye_left, eye_right | Procedural (`eyes.mjs`, added by `add_eyes.mjs` after the build) | CC BY-SA 4.0 | **Illustrative**: globe, cornea, painted iris and pupil, optic nerve to the chiasm; textbook adult sizes placed in the BodyParts3D head |

## BodyParts3D

BodyParts3D, (c) The Database Center for Life Science, licensed under CC BY-SA 2.1 Japan.
https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/partof_BP3D_4.0_obj_99.zip
Licence: https://creativecommons.org/licenses/by-sa/2.1/jp/deed.en

## Z-Anatomy

Z-Anatomy, the libre 3D atlas of anatomy (Gauthier Kervyn and contributors), licensed under
CC BY-SA 4.0. Z-Anatomy is itself derived from BodyParts3D.
https://github.com/Z-Anatomy/Models-of-human-anatomy

The meshes are read from the glTF export of Z-Anatomy's `Startup.blend` published in
github.com/DrMuratAltun/anatomi-simulatoru (CC BY-SA 4.0), pinned to commit 37e85df:
`systems/ic-organlar.glb`. Z-Anatomy uses the BodyParts3D scale but sits 74.7 mm higher and
98.2 mm further back. That offset was measured on the kidneys, which match BodyParts3D to 0.1 mm,
and is removed so that every organ shares one frame.
Licence: https://creativecommons.org/licenses/by-sa/4.0/

## Illustrative organs

BodyParts3D and Z-Anatomy both come from a male donor, so neither has a uterus or ovaries.
No source that was free, openly licensed and downloadable without an account was found, so these
organs are generated procedurally by `female_pelvis.mjs` from standard adult textbook
proportions:

- uterus about 7.5 x 5 x 3 cm, anteverted and anteflexed, resting above the bladder
- uterine tubes about 10 cm, with isthmus, ampulla, infundibulum and fimbriae
- ligaments of the ovary
- ovaries about 3 x 2 x 1.5 cm, in the ovarian fossa

They are placed in the BodyParts3D pelvis. They are an illustration, not measured anatomy, and
`organs.json` and each node's glTF extras mark them `"illustrative": true`. Because the pelvis
around them is male, their fit is approximate. The procedural geometry is released under
CC BY-SA 4.0 with the rest of the model.

## Licence compatibility

CC BY-SA 2.1 JP lets adaptations be released under a later version of the same licence, so the
BodyParts3D parts can be combined with the CC BY-SA 4.0 Z-Anatomy parts under CC BY-SA 4.0.
The glTF `asset.copyright` field and the scene extras carry the combined credit line.
