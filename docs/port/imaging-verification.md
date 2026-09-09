# Imaging implementation and evidence

`ccep.imaging.geometry` provides zero-based voxel/RAS+ mm affine transforms,
RAS↔LPS conversion, endpoint contact interpolation, nearest-neighbour sampling,
a native 1.5 mm sphere, threshold centroid extraction and an explicit absolute
SPM-style pull-field evaluator. Oblique-affine and identity-field tests check
geometry independently of ANTs.

`ccep.imaging.ants_backend` executes rigid/affine/SyN registration, N4 plus
six-prior Atropos segmentation, and sphere warping onto an explicit 1 mm target
grid. The caller supplies images, masks, six ordered priors, templates and target
grids. No atlas download, implicit class identification or SPM fallback occurs.
Output files and manifests preserve backend/settings/input identities.

Local macOS/Python 3.11 tests execute ANTsPy 0.6.3: identity registration on an
asymmetric synthetic volume, sphere centroid preservation and six-class prior
segmentation with probability sums. These are execution/geometry checks, not
SPM scientific acceptance.

ANTsPy 0.6.3's installed registration implementation reads its package random
seed configuration; the older `random_seed` kwarg is ignored. Registration calls
through this module are serialized, use the current deterministic configuration,
and restore Python/NumPy RNG state and environment settings afterward. External
concurrent calls directly into ANTs are not coordinated by this module. Run
imaging jobs in separate processes when mixing third-party ANTs code.

On 9 September 2026 an isolated Python 3.14 installation succeeded for core/Qt,
but `uv pip install --only-binary=:all: --dry-run antspyx` reported no usable wheel.
No native source build was attempted. Full 3.14 imaging support remains a release
blocker; the agreed version target has not been relaxed.

Remaining: matched MRI/CT/SPM reference cases, fitted parameter choices and
scientific acceptance limits, registration/segmentation outcomes, deformation
session compatibility, exact MarsBaR sphere rasterization, tissue shape sampling,
atlas labels and all interactive imaging workflows. No current test certifies
those obligations.

## Native review and command integration

The native image viewer and JSON session now support slice/cursor review,
physical-space overlays, contact endpoint acquisition, interpolation and CSV
export. Tests use a reflected, anisotropic affine and assert coordinates and
plotted arrays. They also check session input hashes and overlay visibility.
The viewer preserves array orientation and labels voxel axes; public contact
coordinates use the image's RAS affine in millimetres.

Image processing currently requires an explicit `mm` header and a finite,
nonsingular 3D affine. Unknown-unit, metre/micron and Analyze imports are rejected
until a reviewed unit/geometry adapter exists; they are remaining compatibility
work, not silently interpreted as millimetres. `image-inspect` reports declared
units without rewriting an image. Native image review works on Python 3.14
without ANTs; registration and segmentation still require ANTs.

CLI commands expose image inspection, rigid/affine/SyN registration, six-prior
segmentation and contact export. A real registration subprocess test checks JSON
stdout and exact reproducibility against the API on the synthetic fixture.
Registration/segmentation GUI controls, manual reorientation and all legacy
imaging-session workflows remain unfinished. Synthetic checks do not replace
SPM outcome comparisons.

## Trade study and transform contracts (9 September 2026)

See the [primary-source trade study](../research/spm12_python_trade_study.md),
[exact source mapping](../research/spm_operation_mapping.md), and
[reproducible rigid comparison](../research/registration_benchmarks.md).
ANTsPy remains the primary candidate; SimpleITK is an optional benchmark group.
The study distinguishes ITK from SimpleITK, SPM's joint segmentation from N4 plus
Atropos, and modulated densities from ordinary probabilities.

Registration now persists a portable transform bundle with explicit ordered
inversion flags, input grids and artifact hashes. Image and contact commands use
anatomical direction names and adapt ANTs' opposite point convention. A known
nonzero LPS affine verifies image/point agreement, inverse round trips, portable
bundles and corruption rejection. Oblique/reflected images are read consistently;
conflicting NIfTI transforms and shear are rejected. Configurable registration
recipes persist their effective parameters. These engineering tests do not
measure SPM equivalence or select a clinically accepted recipe.

## Normalization implementation (10 September 2026)

The `image-normalize` candidate now performs explicit N4 → template registration
→ inverse six-prior transfer/renormalization → native Atropos → normalized
probabilities and GM/WM/CSF modulated densities. Its manifest distinguishes every
output role and reports hashes, full-pull Jacobian extrema and tissue mass changes.
Masks, positivity, prior support/range/sums and posterior simplex checks precede
acceptance of artifacts. The shared N4/Atropos estimation mask and staged, single
pass design remain limitations relative to SPM's joint estimation.

Analytic tests verify the signed full-pull Jacobian in oblique, anisotropic and
sheared coordinate systems, affine volume scaling, folded-map rejection and
change-of-variables mass preservation. Actual ANTs composition is tested against
a known scaling/translation; explicit affine+SyN retains a nonidentity initial
transform. A six-tissue synthetic pipeline executes through both API and CLI,
checks probability sums and artifact hashes, and compares normalized contacts
through a forward/inverse nonlinear round trip. Native input data are retained.

A test exposed ANTsPy 0.6.3's hardcoded affine schedule inside `SyN`. The named
`explicit-v1` recipe now runs Affine followed by SyNOnly to honor configured
schedules. Built-in candidate behavior is retained as `ants-defaults-v1`, with
requested/effective settings distinguished. This is a Python adapter correction,
not an accepted correction to the original MATLAB science.

SPM `mwc` output uses push/splat with voxel-volume scaling; this implementation's
linear pull × full Jacobian is a separate numerical algorithm. Nonpositive signed
Jacobians are rejected rather than hidden by logarithms/clipping. Real corpus
comparisons must establish acceptable contact, tissue and mass differences.
