# Command-line workflow

Install from source, then use `ccep --help` in the activated environment.
With uv, prefix the commands below with `uv run --no-sync` to use the installed extras. JSON mode uses `ccep --json COMMAND`.
All commands are noninteractive; inputs and output paths are explicit. Exit codes:
0 success, 2 input/usage/collision failure, 3 comparison/completeness failure,
1 unexpected error. Diagnostics have stable machine-readable codes.

Generate and process a synthetic example from the repository root:

```sh
python tools/make_demo.py artifacts/demo
ccep --json inspect artifacts/demo/recording.edf --annotations artifacts/demo/annotations.json
ccep --json validate artifacts/demo/config.json
ccep --json process artifacts/demo/config.json artifacts/demo/result.npz
ccep --json export artifacts/demo/result.npz artifacts/demo/report.csv
```

The demo config illustrates all currently integrated fields. Paths are relative
to the config file. Select `unipolar` or `bipolar` and exact channel labels.
Each train provides either explicit zero-based `pulse_samples`, or an inclusive
`annotation_window` selecting pulses from the annotation file. Frequency is an
explicit scientific parameter. Filtering defaults are resolved and returned.
`baseline_windows` contains actual inclusive zero-based windows; their rounded
midpoints drive the legacy pseudo-pulse baseline calculation. Do not claim a
matching RNG seed establishes cross-language window equivalence.

The NPZ result contains non-pickled numeric arrays and JSON metadata (inputs,
hashes, versions, resolved config, units and axes). CSV/XLSX exports contain one
row per channel/pulse. They are additive outputs; the legacy anatomical workbook
and complete MAT analysis schemas remain separate compatibility obligations.
The GUI can open NPZ results and export the same tables. PNG/SVG/PDF ERP exports
require the `gui` extra's Matplotlib dependency but do not launch Qt.

`compare ACTUAL EXPECTED TOLERANCE.json` compares native results.
The tolerance JSON has an `arrays` object keyed by array name. Each numerical
array needs its own `absolute`, `relative`, `unit` and `rationale`; ERP units must
match the channel and metric/coefficient units are `dimensionless`. Sample indexes
and offsets always compare exactly. Use `inspect` to discover array names.
`reference-check BUNDLE --source-root MATLAB_TOOLBOX` verifies the portable
capture bundle's checksums/completeness; it does not certify numerical parity.

The authoritative Codex playbook is packaged at
`src/ccep/skills/ccep-process/SKILL.md`. Use `ccep --json skill-path` to locate it in an installed wheel.
Run `ccep --json install-skill PATH_TO_CODEX_SKILLS` to copy it into an explicit
Codex skill directory and discover it as `$ccep-process`. Existing skills are
not overwritten. Maintain the source here;
installed copies are deployment artifacts. `tests/test_skill_workflow.py` executes
the documented sequence and checks artifact contents and failure diagnostics.
A live Codex-assisted researcher walkthrough remains a release acceptance item.

Scoring is optional and explicit. Supply `scoring.sites` keyed by channel with
already relabeled `anatomical` text (plus both `contact_anatomy` strings for bipolar
channels), `stimulation_anatomy` keyed by train, and `distances_mm` keyed by train
then channel. Every selected channel/train must be represented, and baseline
windows are required. `distance_threshold_mm` defaults to the source's 10 mm;
`exclude_patterns` defaults to its anatomical regular expressions. Python regex
compatibility for custom MATLAB expressions still needs reference characterization.
The generated demo uses fictional anatomy solely to exercise this interface.
Saved results expose eligibility reasons and per-train Z scores, means, medians,
ranks and quartile values. Native comparisons always require exact eligibility
flags and quartile categories, regardless of numerical tolerances.

For existing MATLAB analyses, `inspect RMS.mat` reads `DataStruct`, `StimAnnot`
and pulse identities. `compare-mat PYTHON.npz MATLAB.mat TOLERANCE.json` compares
selected-reference RMS/std ratios, sample indexes and optional baseline windows.
It maps trains by exact pulse samples/frequency and channels by exact label.
It reports its limited scope: full filtering provenance, ERP amplitudes and
anatomical scoring still need additional captured artifacts. It accepts the same
array-specific tolerance format as native comparison.

`reference-replay BUNDLE TOLERANCE.json` checks the capture and replays the kernel
inputs. See [the reference guide](../reference/README.md) for comparison names.

Imaging commands use the same JSON envelope:

```sh
ccep --json image-inspect native.nii.gz
ccep --json image-register MRI.nii.gz CT.nii.gz new-registration --task ct-to-mri --seed 1729
ccep --json image-segment segmentation-config.json new-segmentation
ccep --json image-contacts imaging-session.json contacts.csv
```

Segmentation config supplies `image`, `mask`, six ordered `priors` paths, and six
matching unique `class_names`; paths resolve relative to that JSON. Registration
and segmentation require the ANTs extra and remain candidates for SPM outcome
acceptance. Inspect/contact export and native image review only require the GUI
extra's NIfTI dependency. Processing accepts explicit millimetre image headers;
unknown-unit and Analyze import adapters remain to be verified. Overlay display
resamples using existing physical coordinates; it does not estimate alignment.

### Verified imaging transforms

`image-register FIXED MOVING OUTPUT [--transform Rigid|Affine|SyN] [--settings recipe.json]`
now writes `transforms.json` alongside registration provenance. A settings JSON
uses the typed `RegistrationSettings` fields; omitted fields preserve the earlier
ANTs candidate defaults. All resolved settings are saved. These defaults are not
SPM's NMI/optimizer recipe.

```bash
ccep --json image-apply registration/transforms.json associated.nii.gz fixed.nii.gz warped.nii.gz
ccep --json image-apply registration/transforms.json atlas.nii.gz native.nii.gz native_atlas.nii.gz --direction fixed-to-moving --labels
ccep --json image-transform-points registration/transforms.json contacts.json normalized_contacts.json
```

Point input is a JSON array of `[x,y,z]` in RAS+ millimetres. Direction names always
refer to anatomical source/destination, for both image and point commands; the
adapter handles ANTs' opposite point convention. The bundle records ordered,
relative, checksummed artifacts and explicit affine inversion, including an
inverse chain containing only one affine. Copy the complete registration folder
to relocate it. Schema-1 `registration.json` alone is not a transform bundle;
recapture it with the updated registration API instead of guessing inversions.

Associated images must match the source grid and the reference must match the
target grid. Intensity/probability interpolation is linear; `--labels` uses
`genericLabel`. Headers must declare mm, and conflicting qform/sform, shear,
nonfinite pixels or ANTs/NIfTI geometry disagreements are rejected for review.

### Six-tissue normalization candidate

`ccep --json image-normalize normalization.json NEW_OUTPUT_DIRECTORY` accepts:

```json
{
  "image": "native_t1.nii.gz",
  "mask": "native_estimation_mask.nii.gz",
  "template": "explicit_template_t1.nii.gz",
  "priors": ["gm.nii.gz", "wm.nii.gz", "csf.nii.gz", "bone.nii.gz", "soft.nii.gz", "background.nii.gz"],
  "seed": 1729,
  "registration_settings": {"recipe": "explicit-v1"}
}
```

Paths are relative to the configuration. Priors must match the template grid and
use **GM, WM, CSF, bone, soft tissue, background** order. DeepAtropos's tissue
classes are different. Templates and atlases are not downloaded automatically.

The pipeline performs N4, affine/SyN registration, inverse transfer of template
priors, explicit six-prior renormalization, and native Atropos segmentation. It
writes native labels/probabilities, normalized probabilities, and three separately
named modulated density maps (GM/WM/CSF). Densities include the complete pull
Jacobian, including affine scaling; values can exceed one. This differs from
SPM's discrete `mwc` writer and remains an outcome-equivalence candidate.

The estimation mask must be binary, nonempty and contain positive MRI intensities.
All six priors must have support within it. A brain-only mask is not a substitute
for six whole-head tissues. An optional `bias_mask` separates N4 estimation from the Atropos mask;
iterative bias/segmentation refinement remains work for representative reference cases. CT HU data are not
silently shifted or sent through N4. Transferred priors must cover every estimation
voxel; a coverage failure requires reviewing registration/masks/template choice.

`normalization.json` is written only after completion. Preserve partial output
folders on failure for diagnosis and use a fresh folder for retry. The manifest
contains artifact hashes, input identities, class/output roles, Jacobian extrema
and native/normalized tissue masses. Cropping/interpolation can change mass;
these diagnostics have no automatically inferred scientific tolerance.

`explicit-v1` uses separate Affine and SyNOnly calls so affine schedules actually
take effect. ANTsPy 0.6.3's built-in SyN ignores those schedule arguments; the
preserved `ants-defaults-v1` recipe records the backend's hardcoded effective
schedule separately from requested settings. Neither recipe is accepted as SPM
scientific equivalence.

### ANTs-first templates and compatibility adapters

SimpleITK comparisons now run only through the manually dispatched release workflow;
ordinary CI and production imaging use ANTsPy. The imaging extra also retains
NiBabel for NIfTI geometry and the package's existing numerical dependencies.

```sh
ccep --json image-template-install ARCHIVE.zip NEW_TEMPLATE_DIRECTORY
ccep --json image-template-inspect NEW_TEMPLATE_DIRECTORY/template.json
ccep --json image-template-register NEW_TEMPLATE_DIRECTORY/template.json native_t1.nii.gz NEW_REGISTRATION --moving-mask native_mask.nii.gz
```

The supported archive is McGill `icbm152_ext55_model_sym_2020_nifti.zip`. The
installer preserves original images, licensing, exact geometry and asset hashes.
`image-template-register` uses the named T1 affine/CC-SyN candidate with the supplied
template mask. It performs registration only: the archive contains no six-tissue
priors. `image-register` now accepts `--fixed-mask` and `--moving-mask` for all stages.
Library users can select `task_settings(RegistrationTask.ct_to_mri)` for rigid
Mattes MI or `task_settings(RegistrationTask.t1_to_template)` for affine/CC SyN.
CT must remain rigid; pass `transform="Rigid"` to the generic API for that task.

`image-normalize` now defaults to the T1/CC candidate when no explicit settings
are supplied. Its configuration additionally accepts `bias_mask`,
`fixed_registration_mask` and `moving_registration_mask`. `mask` remains the
six-tissue Atropos estimation mask; `bias_mask` defaults to it for compatibility.
Resolved candidate settings and mask hashes are recorded; omission does not mean
these values have been accepted against SPM.

```sh
ccep --json image-spm-warp native.nii.gz y_field.nii.gz warped.nii.gz
ccep --json image-reorient native.nii.gz rigid_ras_matrix.json reoriented.nii.gz
ccep --json image-import-electrodes 'Participant Electrodes.mat' native.nii.gz session.json
ccep --json image-contact-warp registration/transforms.json native.nii.gz template_1mm.nii.gz centre.json NEW_CONTACT_DIRECTORY
ccep --json image-sample samples.json tissue_result.json
```

SPM field input must be explicitly known to contain absolute source RAS mm on the
target grid, with layout `(x,y,z,1,3)` or `(x,y,z,3)`. `--labels` requests nearest
interpolation. A filename alone cannot distinguish SPM coordinates from ANTs
LPS displacement. Intensity interpolation is linear, not an assertion of SPM's
order-4 reslicing parity. Header reorientation consumes a JSON 4×4 proper rigid
RAS-world matrix and writes new headers with unchanged decoded voxel values.

Electrode import requires `ElectrodeArray` fields `ElectrodeName`, `StartMM`,
`EndMM`, `NumContacts`, `PosMM`; saved contacts must match linear interpolation.
The explicit native image must be the image whose geometry gave those coordinates.
Original MAT metadata remains in the untouched source, linked by checksum. The
resulting session opens in the current image viewer; it is not a full historical
MAT-session importer/exporter.

Contact warp consumes a JSON `[x,y,z]` native centre. It retains the original
MarsBaR sphere rasterization and 0.99/0.95 centroid thresholds, recording the direct
point result separately. If no warped voxels meet either threshold, it reports the
legacy failure rather than silently substituting the transformed centre.

Tissue sampling config example (paths relative to JSON):

```json
{
  "tissue_maps": ["gm.nii.gz", "wm.nii.gz", "csf.nii.gz"],
  "native_points_ras_mm": [[10,20,30], [10,20,30], [11,20,30]],
  "atlas": "atlas.nii.gz",
  "atlas_labels": {"0":"OUT", "1":"supplied region name"},
  "template_centre_ras_mm": [12,18,28],
  "atlas_mode": "exact"
}
```

Atlas fields are optional. The centre must be in that atlas's exact space; this
command performs no registration. Duplicate sample points retain their weight.
`legacy-closest-absolute` selects the integrated MATLAB lookup convention and
reports its `1/sample_count` frequency for nonzero labels. This is not a statistical
confidence. `legacy_shape()` exposes source-derived cylinder/cube/rectangle and
captured-cloud positions for the library; SPM GUI string-rounding remains unverified.

`image-auto-reorient IMAGE TEMPLATE NEW_DIRECTORY` is the automatic ANTs candidate:
12 mm FWHM smoothing of the source, rigid fitting to the explicit template, then
header-only application to the original decoded voxels. It writes the smoothed
source, registration and `reorientation.json` for review. It does not reproduce
SPM affreg's optimizer or choose a template implicitly.

Registration calls use a fresh ANTs worker process with one ITK thread configured
at startup. This is automatic for library and CLI use, including notebooks that
have already used ANTs. The worker preserves the caller's random state and thread
environment. The same build/fixture has API/CLI equality checks; cross-platform
or cross-version bitwise equality is not promised.

Use `image-register MRI CT NEW --task ct-to-mri` to select the named rigid Mattes
recipe, or `--task t1-to-template` for explicit Affine + CC SyN. A named task cannot
be combined with `--settings` or a conflicting transform. Without a task, the
existing generic rigid default and custom settings interface remain available.
`image-template-register` selects the T1 task and records the supplied McGill
bundle identity automatically.
