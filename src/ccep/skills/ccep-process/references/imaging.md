# CCEP imaging commands

Inspect installed `image-* --help` interfaces. Use `--json` before the command and
require a successful envelope plus the named artifacts. Keep input images intact.

For CT→MRI alignment, use `image-register MRI CT NEW_DIRECTORY --transform Rigid`.
For a supplied registration, use its `transforms.json` bundle. Copy the complete
folder when relocating it: ordered transform artifacts are relative and checksummed.
Use `image-apply BUNDLE ASSOCIATED_IMAGE TARGET_REFERENCE NEW_IMAGE` to reuse one
registration for related images. Add `--labels` for discrete atlas/segmentation
IDs; ordinary probabilities use linear interpolation.

Use `image-transform-points BUNDLE POINTS_JSON NEW_RESULT_JSON` for contact mapping.
Input is an array of `[x,y,z]` in RAS+ millimetres. Direction defaults to
`moving-to-fixed`; `--direction fixed-to-moving` reverses anatomical direction for
both image and point commands. The adapter handles ANTs' opposite point convention.
Completion includes verifying the requested source/target spaces and retaining
bundle/input/output hashes. Direct point mapping differs from the MATLAB
sphere-warp centroid method; report which outcome the researcher requested.

For six-tissue normalization, use `image-normalize CONFIG NEW_DIRECTORY` only when
the researcher supplied a template, six ordered priors, a native estimation mask
and the intended registration recipe. Config paths are relative to the JSON file:

```json
{
  "image": "native_t1.nii.gz",
  "mask": "native_estimation_mask.nii.gz",
  "template": "template_t1.nii.gz",
  "priors": ["gm.nii.gz", "wm.nii.gz", "csf.nii.gz", "bone.nii.gz", "soft.nii.gz", "background.nii.gz"],
  "registration_settings": {"recipe": "explicit-v1"}
}
```

Prior order is SPM GM, WM, CSF, bone, soft tissue, background. DeepAtropos supplies
a different taxonomy. The mask must be binary/nonempty, contain positive MRI
intensities and retain support for all six classes. Supply a separate `bias_mask` when the N4 estimation region differs from
the Atropos mask. A missing input or scientific choice needs clarification; elapsed time or
an available template is not a choice of scientific protocol.

Completion requires `normalization.json`, verified artifact hashes and review of
its output roles and QC. Report Jacobian extrema and native/normalized mass
changes with the returned unverified scientific status. Normalized probabilities
and modulated densities serve different roles; density values can exceed one.
The candidate uses full pull-Jacobian modulation, which differs from SPM's discrete
writer. Successful execution does not establish SPM equivalence.

For coverage, positivity, grid or Jacobian failures, preserve the partial folder
and report the diagnostic. Correct explicit inputs/settings and use a new output
folder after review. Never manufacture tissue identity, alter coordinate frames,
or choose acceptance tolerances merely to make a comparison pass.


For the McGill ext55 archive, use `image-template-install` into a new local folder,
then `image-template-inspect` to verify it. The archive has a CerebrA region atlas,
not six tissue priors or an atlas ID/name table. `image-template-register` performs
T1 registration with the ANTs CC candidate; it does not manufacture segmentation
inputs. SimpleITK is not part of this production workflow.

For saved MATLAB acquisitions, `image-import-electrodes MAT NATIVE NEW_SESSION`
imports validated endpoint/contact data and retains the source identity. The
researcher must identify the native image in the coordinates' original space.
For explicit SPM absolute-RAS fields, use `image-spm-warp`; for an explicit rigid
RAS header matrix use `image-reorient`. ANTs displacement files need `image-apply`.

For the original contact method, use `image-contact-warp` with the transform
bundle, native image, 1mm target, JSON centre and new output directory. It reports
sphere-centroid and direct-point outcomes separately. For tissue/atlas values use
`image-sample` with captured native sample points, ordered GM/WM/CSF maps and,
optionally, an explicit atlas table and template-space centre. Use installed
command help and preserve reported precision/legacy-frequency limitations.
