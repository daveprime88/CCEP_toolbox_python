# CCEP imaging commands

Inspect installed `image-* --help` interfaces. Use `--json` before the command and
require a successful envelope plus the named artifacts. Keep input images intact.

For CT→MRI alignment, use `image-register MRI CT NEW_DIRECTORY --task ct-to-mri`.
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


Use the supplied **symmetric ICBM152 2009a** archive with `image-template-install`
into a new folder, then `image-template-check MANIFEST --baseline
reference/imaging/icbm152_sym_2009a_content.json` from the checkout. Omit the baseline
option outside the checkout for the bundle's stored-count/range/coverage checks.
This is a lightweight content check, not a registration or SPM acceptance run.
The manifest exposes GM/WM/CSF priors; it does not contain the extra three classes
needed by `image-normalize` or a labeled anatomical region atlas. Preserve the
original maps. Use `image-template-register` for the ANTs T1 candidate with its
explicit derived binary brain mask. Historical ext55 bundles remain usable only
when explicitly selected. SimpleITK is not part of production imaging.

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

For `image-contact-warp`, exit code 3 can indicate that neither original threshold
selected a voxel. Inspect `contact_failure.json` and the retained sphere images.
The comparison keeps the direct point with a null legacy centroid/distance; do not
substitute it or lower thresholds to turn the failure into success. `passed` marks
calculation completeness, not scientific equivalence.
