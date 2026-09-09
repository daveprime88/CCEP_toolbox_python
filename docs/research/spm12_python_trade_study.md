# SPM12 to Python imaging trade study

Research date: 9 September 2026. Scope: the structural imaging operations used by
the CCEP Toolbox, rather than replacing every statistical and electrophysiology
feature in SPM. This is a source and literature comparison; it does **not** report
a completed patient-data benchmark. Numerical acceptance against the author's
MATLAB/SPM reference resources remains pending.

## Recommendation

Keep **ANTsPy (`antspyx`, imported as `ants`) as the primary imaging backend**.
Build explicit CCEP workflows around its registration, N4 bias correction and
prior-informed Atropos segmentation. Keep geometry, file contracts, quality
assessment and scientific acceptance independent of that backend. Add SimpleITK
as an optional comparison backend for rigid MRI/CT registration and N4, if the
comparison justifies the maintenance cost. Do not silently switch algorithms
when a dependency is missing.

This is an engineering recommendation based on the operations and existing code,
not a finding that ANTs outperforms SPM on the CCEP data. The ANTsPy API directly
exposes the required algorithm families, while the project already has working
adapters and synthetic tests. [ANTsPy project](https://github.com/antsx/antspy)

There is **no verified single Python package that reproduces SPM12's complete
structural pipeline with the same model and outputs**. In particular, SPM's
segmentation, bias estimation and normalization are coupled. A sequence of N4,
registration and Atropos is an alternative scientific implementation whose
outcomes require comparison. [Unified segmentation paper](https://www.fil.ion.ucl.ac.uk/~karl/Unified%20segmentation.pdf)

## Clarifying the package family

ANTsPy wraps the **ANTs C++ framework**, which uses ITK. SimpleITK is another C++
interface built on ITK, with wrappers for Python and other languages. ANTsPy is
therefore not a wrapper around SimpleITK. Their common foundation does not imply
identical optimization, image conversion, interpolation or defaults.
[ANTsPy architecture](https://github.com/antsx/antspy),
[SimpleITK architecture](https://github.com/SimpleITK/SimpleITK)

Searches for the exact phrase “SimpleITK Enhanced Py” did not identify an
authoritative project under that name. Two plausible intended packages are:

- **SimpleElastix / `SimpleITK-SimpleElastix`**: an extension of SimpleITK that
  exposes elastix and transformix, including configurable registration recipes.
  It is a registration framework, not SPM's unified segmentation model.
  [SimpleElastix introduction](https://simpleelastix.readthedocs.io/Introduction.html)
- **ITKElastix / `itk-elastix`**: elastix bindings through ITK Python, imported as
  `itk`, with native wheels and a separate experimental WebAssembly interface.
  This is distinct from installing standard SimpleITK.
  [ITKElastix project](https://github.com/InsightSoftwareConsortium/ITKElastix)

The exact intended name remains unresolved; the supplied ANTsPy link is
unambiguous and suitable for the main workstream.

## What the original CCEP implementation actually requests

The compatibility reference is the local MATLAB source frozen in the inventory,
not generic SPM defaults or a modern SPM tutorial. The source tree is the
[original CCEP project](https://github.com/Qseeg/CCEP_Toolbox); the following
observations come from its local files under `CCEP Toolbox/MRI and CT
Coregistration routine`.

| Legacy operation | Observed CCEP behavior | Python mapping and acceptance |
| --- | --- | --- |
| `Preprocess/CoregFunc.m` | SPM coregister estimate-and-write; default normalized mutual information (`nmi`), separations `[4,2]`, FWHM `[7,7]`, interpolation order 4; first moving image determines the transform for other supplied images | ANTs rigid registration of CT to MRI; one transform applied to every associated image. Mattes MI is a candidate metric, **not the same objective as SPM NMI**. Compare landmark error and CT/MRI overlays. |
| `Preprocess/AutoReorient.m` | Smooths at 12 mm, estimates rigid alignment to `canonical/avg152T1.nii`, orthogonalizes rotation, updates the NIfTI matrix | Separate header reorientation from resampling. Preserve original data and retain the explicit matrix. A generic full reslice is behaviorally different. |
| `Preprocess/CCEPSegmentFunc.m` | Six TPM classes, Gaussian mixture counts `[2,2,2,3,4,2]`, bias regularization `0.001`, bias FWHM 60, MRF and cleanup enabled; native outputs for classes 1–3; forward deformation output | N4 + explicitly aligned six-class priors + Atropos + template registration is an outcome-equivalent candidate, not an implementation-equivalent port. |
| Normalized outputs in `CCEPSegmentFunc.m` | Optional `mwc1–3` modulated tissue outputs; original image normalized to 1 mm grid with bounding box `[-78,-112,-70]` to `[78,76,85]`, interpolation order 4 | Distinguish tissue probability from tissue density. Modulation needs an explicitly defined Jacobian and transform direction. Preserve the target grid and output role. |
| `CoOrdGrabGui/CCEPROICreateandWarp.m` | MarsBaR native sphere of radius 1.5 mm; linear warp to explicit 1 mm grid; centroid of voxels at least 0.99, fallback 0.95 | Retain sphere-warp-centroid as the compatibility operation. Directly transforming the center is a separate comparison output, not an interchangeable shortcut. |
| `CoOrdGrabGui/CCEPTissueProbCalc.m` | Samples tissue maps and anatomical atlas through SPM viewer callbacks using nearest-neighbor interpolation; multiple contact/shape sampling cases | Typed array-based sampling removes GUI dependency while preserving coordinates, sample points, rounding and class identities. Capture legacy random samples before assessing parity. |
| `Preprocess/CCEPGetMNIAnatomicalAreas.m` | Atlas lookup at MNI coordinates with nearest-neighbor interpolation and label mapping | Explicit atlas image + exact lookup table + template identity; compare discrete labels and boundary cases. |
| DICOM, Analyze/NIfTI, realignment and interactive review | Additional source functions and workflows | Separate import/reorientation/realignment work packages; a successful ANTs registration alone does not cover them. |

SPM distinguishes coregistration that changes headers from reslicing. Its
documentation also shows segmentation-derived deformation fields being applied
to images already aligned to the structural MRI. These distinctions justify
keeping image identity and transform composition explicit.
[SPM preprocessing documentation](https://www.fil.ion.ucl.ac.uk/spm/docs/tutorials/beginners/fmri/preprocessing/)

## Candidate comparison

The rankings below assess fitness for this port. They are not measured accuracy
scores; assigning numerical weights before obtaining representative CCEP data
would imply precision we do not have.

| Candidate | Main strengths for CCEP | Main limitation | Decision |
| --- | --- | --- | --- |
| ANTsPy / ANTs | Named rigid/affine/SyN recipes, N4, Atropos, image/point transforms; current project integration | Different model from SPM; six-prior preparation and workflow still need implementation; Python 3.14 wheel gap | Primary backend |
| SimpleITK | Flexible explicit registration, filtering, transforms, N4; broad current wheel coverage | We must own the recipe and tuning; no direct SPM unified-segmentation workflow | Optional comparator and supporting import/filter operations |
| ITKElastix | Configurable elastix recipes, including normalized MI; transformix and serializable parameter maps | Another backend and parameter space; segmentation still needs another method | Strong second registration comparator if ANTs rigid proves inadequate |
| SimpleITK-SimpleElastix | Convenient elastix access for an existing SimpleITK user | Current listed distribution is an alpha; shares the SimpleITK import namespace, so treat environments carefully | Investigate in isolation; not the default dependency |
| DIPY | Python-facing affine and symmetric diffeomorphic registration | Different implementation and defaults; not the complete six-class SPM pipeline | Reserve alternative; no present reason to replace the working ANTs integration |
| ANTsPyNet / DeepAtropos | Pretrained brain extraction and tissue segmentation; potentially useful later | Different tissue taxonomy, preprocessing and learned model; larger runtime/model dependencies | Separate future scientific comparison |
| SPM-Python / Nipype SPM | Can help drive genuine SPM reference runs | Calls SPM/MATLAB machinery; does not satisfy removal of that runtime from the released toolbox | Reference generation only |

SimpleITK exposes transform, metric, optimizer, sampling and multiresolution
choices rather than one universally appropriate configuration. Its standard
metric list includes Mattes MI and joint-histogram MI; neither should be labeled
SPM's `nmi`. Elastix offers a specifically named normalized mutual information
metric, but matching a metric name still does not match SPM's complete optimizer
or histogram implementation.
[SimpleITK registration overview](https://simpleitk.readthedocs.io/en/master/registrationOverview.html),
[elastix normalized MI](https://elastix.dev/doxygen/classelastix_1_1NormalizedMutualInformationMetric.html)

DIPY implements affine and symmetric diffeomorphic registration, including CC,
SSD and EM options. This makes it a genuine alternative algorithm implementation,
not an ANTsPy alias. [DIPY registration documentation](https://docs.dipy.org/stable/interfaces/registration_flow.html)

The official SPM-Python interface currently requires a corresponding MATLAB
runtime and documents Python/MATLAB version coupling. Nipype provides SPM
interfaces rather than reimplementing those algorithms. Both can be useful on
the reference computer, but neither removes the SPM dependency.
[SPM-Python](https://github.com/spm/spm-python),
[Nipype SPM interfaces](https://nipype.readthedocs.io/en/latest/api/generated/nipype.interfaces.spm.preprocess.html)

## Registration and normalization design

Use separate, named task configurations:

1. **CT to native MRI:** rigid transform, multimodal metric, explicit masks and
   initialization where supplied. Do not make affine scaling or nonlinear
   deformation the default for electrode localization. Keep any brain-shift
   correction a separately validated scientific feature.
2. **Native T1 to a specified template:** linear initialization followed by SyN,
   with explicit metric, iterations, shrink factors, smoothing and precision.
   Compare the existing candidate against a CC-based nonlinear stage on the
   T1-to-T1 task. Do not apply a CT recipe unchanged to this task.
3. **Applying a transform:** require the moving image, fixed output grid,
   transform sequence, inversion flags and interpolation. Resample a composed
   chain once where possible; repeated interpolation can change contact masks
   and boundaries.

These are proposed CCEP task definitions, not a claim that specific parameter
values have already been scientifically selected. ANTsPy provides several named
recipes and explicit arguments; defaults must be captured in provenance rather
than assumed to remain stable across releases.
[ANTsPy registration API](https://antspyx.readthedocs.io/en/stable/registration.html)

For a comparison study, hold the fixed/moving images, physical domains,
initialization, evaluation landmarks and output sampling fixed. Report both
default-recipe and tuned-recipe results. A comparison that tunes one backend and
uses another's default cannot isolate algorithm superiority.

SPM's template normalization is not synonymous with “any MNI image.” Distinct
linear/nonlinear, symmetric/asymmetric MNI templates exist. The new workflow
must record the exact template and atlas checksums and declared space; changing
the template changes the anatomical coordinate interpretation even if both
files are called MNI. [TemplateFlow template identities](https://www.templateflow.org/python-client/master/notebooks/01_quickstart.html)

## Segmentation: the largest scientific gap

Atropos is an EM finite-mixture framework that can use probability priors and
MRF regularization. In ANTsPy, supplying ordered priors establishes output class
order; without priors, class ordering follows image intensity. Explicit prior
identity is therefore essential for a GM/WM/CSF interface.
[Atropos paper](https://pubmed.ncbi.nlm.nih.gov/21373993/),
[ANTsPy segmentation API](https://antspyx.readthedocs.io/en/stable/segmentation.html)

The existing `segment()` requires six priors **already in the subject grid**.
That is a useful primitive, but it does not solve the template-to-subject
registration that SPM estimates within segmentation. The next complete workflow
should accept a template image, ordered priors, a subject image and masks; estimate
and record a template transform; pull the priors into subject space; validate
their support and values; then run N4/Atropos. A refinement loop using the
estimated tissue maps is a later, separately tested candidate.

SPM's multiple Gaussians per tissue class are not reproduced by merely choosing
six Atropos labels. Its regularization, bias model, cleanup and tissue priors
also differ. Native posterior agreement, tissue volumes, contact-level tissue
fractions and atlas outcomes are more informative acceptance targets than raw
equality of intermediate arrays. The reference must retain all settings in the
legacy batch above, including the relatively coarse `samp=7`.

N4 corrects intensity nonuniformity using a different method from SPM's bias
model. ANTs guidance recommends explicitly setting spline spacing for human T1
data, and requires positive intensities in the estimation region because the
method operates in the log domain. A binary mask, nonempty support and valid
intensities should be validated before executing a native call. N4 should not
be applied automatically to CT Hounsfield units.
[ANTs N4 guidance](https://github.com/ANTsX/ANTs/wiki/N4BiasFieldCorrection)

An iterative N4/Atropos workflow exists in ANTs' `antsAtroposN4.sh`. It is useful
as a reference for a future coupled workflow, but porting its orchestration
still does not recreate the SPM objective. Keep the simple current candidate
and iterative candidate distinguishable in reports.
[ANTs iterative script](https://github.com/ANTsX/ANTs/blob/main/Scripts/antsAtroposN4.sh)

**DeepAtropos is not a six-class SPM substitute.** Its documented labels are
CSF, gray matter, white matter, deep gray matter, brain stem and cerebellum, plus
background. That differs from the SPM whole-head tissue categories. Its training
preprocessing includes N4, denoising, brain extraction and affine alignment.
Keep it out of the compatibility path until a separate taxonomy and validation
study is approved. [DeepAtropos source](https://github.com/ANTsX/ANTsPyNet/blob/main/antspynet/utilities/deep_atropos.py)

Normalized tissue **probability** maps and modulated tissue **density** maps
are separate output types. The legacy optional `mwc` output must not be replaced
with an ordinary warped probability map. Establish whether the full or nonlinear
Jacobian is used, its mapping direction and affine contribution, then test
mass preservation with an analytic expansion before any patient comparison.
SPM explicitly distinguishes modulation in its morphometry workflow.
[SPM VBM image processing](https://www.fil.ion.ucl.ac.uk/spm/docs/tutorials/vbm/image_processing/)

## Coordinates, fields and contact locations

Adopt one public contract: zero-based voxel indices and RAS+ world coordinates
in millimetres. Keep the affine and units with every array. ITK-backed APIs use
physical origin, spacing and direction, not just array indices; dropping those
properties creates a valid-looking but wrong image.
[SimpleITK physical image concepts](https://simpleitk.readthedocs.io/en/master/fundamentalConcepts.html)

The transform manifest should record source and target spaces, hashes, ordered
files, inversion flags, physical convention, interpolation and reference grid.
An ANTs affine `.mat` is not a MATLAB analysis `.mat`. A deformation volume is
not self-describing enough to infer its use from its filename.

Image resampling is a pull operation: each output location requests an input
location. Point transformation and image warping can therefore use apparently
opposite directions. ANTs' own guidance gives different transform-list usage
for images and point sets. An implementation must demonstrate the direction
with a nonzero translation and a rotated, anisotropic image, then test the
inverse round trip. Identity-only tests cannot detect a reversed direction.
[ANTs transform direction guide](https://github.com/ANTsX/ANTs/wiki/Forward-and-inverse-warps-for-warping-images,-pointsets-and-Jacobians)

The same ANTs guide reports a Jacobian-calculation bug fixed in May 2025 and
states that its geometric Jacobian option was unaffected. Before implementing
modulation, record the underlying ANTs build and chosen Jacobian method and
verify both on analytic fields; a package version alone is not a mass-preservation
test. [ANTs Jacobian update](https://github.com/ANTsX/ANTs/wiki/Forward-and-inverse-warps-for-warping-images,-pointsets-and-Jacobians#computing-the-jacobian)

For imported SPM fields, require an explicit field convention and grid. The
current absolute RAS pull-field evaluator should remain a separate adapter
until genuine `y_*.nii` and inverse-field fixtures establish compatibility.
Do not reinterpret an absolute-coordinate field as an ANTs displacement field,
or negate a nonlinear displacement to obtain its inverse.

Retain both contact calculations in the comparison harness: (a) the original
native sphere → warped threshold → centroid, and (b) transformed center.
Nonlinear deformation, finite sampling and thresholds can make them differ.
Use nearest-neighbor or label-preserving interpolation for an atlas, linear
interpolation for the legacy contact sphere, and an explicit chosen scheme for
intensity images. Any improvement to the original sampling belongs in a separate
scientific delta, as agreed in the roadmap.

## What published comparisons do and do not establish

| Primary study | Useful evidence | Limit on the inference for CCEP |
| --- | --- | --- |
| [Klein et al., 2009: 14 nonlinear registration algorithms](https://pubmed.ncbi.nlm.nih.gov/19195496/) | Broad comparison on manually labeled human brain MRI; relevant justification for considering ANTs/SyN | Predates SPM12 and current ANTsPy; not a validation of the current CCEP pipeline, CT registration or electrode coordinates |
| [Avants et al., 2011: ANTs similarity metrics](https://pubmed.ncbi.nlm.nih.gov/20851191/) | Controlled affine/deformable metric comparison on LPBA40 T1 images; supports evaluating MI linear plus CC nonlinear stages | Task and templates differ from CCEP; does not imply CC is best for CT-to-MRI |
| [Avants et al., 2011: Atropos](https://pubmed.ncbi.nlm.nih.gov/21373993/) | Prior/MRF segmentation evaluated using public ground-truth data, including BrainWeb and atlas-driven labels | Does not establish equality to CCEP's SPM six-class mixture or contact tissue assignments |
| [Tustison et al., 2010: N4ITK](https://pubmed.ncbi.nlm.nih.gov/20378467/) | Bias correction assessed on simulated and acquired images; establishes an independently evaluated method | Not proof of equivalence to SPM's joint bias/segmentation estimation |
| [SimpleElastix developers' 2016 paper](https://mstaring.github.io/assets/pdf/2016_c_WBIRa.pdf) | Describes elastix integration, parameter maps and practical scripting | Engineering/accessibility evidence, not a head-to-head SPM12 CCEP acceptance study |

No located study establishes a universal one-to-one SPM12→ANTsPy mapping for
this toolbox. Published overlap rankings justify candidate selection; they do
not replace a matched local study. No patient MRI/CT experiment was run as part
of this document. Existing synthetic execution checks are documented separately
in [imaging verification](../port/imaging-verification.md).

## Proposed comparison studies and release gates

These are concrete study protocols, not completed experiments or approved
clinical thresholds. Freeze each candidate recipe before evaluating held-out
cases, and distinguish development/tuning cases from acceptance cases.

| Study | Inputs and comparisons | Required report |
| --- | --- | --- |
| A: geometry and transform algebra | Synthetic oblique, reflected and anisotropic grids; identity, translation, rotation, scale and smooth warp; ANTs, SimpleITK and SPM adapter where available | World-coordinate landmark errors, inverse consistency, bounds behavior, output affine/units, label-set preservation; exact checks where algebra permits |
| B: within-subject CT/MRI registration | De-identified MRI/CT pairs with independently marked landmarks; SPM legacy batch vs explicit ANTs rigid vs SimpleITK rigid; optional elastix NMI | Per-landmark target registration error in mm, distribution and worst cases, overlays, failures, runtime and memory; avoid treating the optimized MI score as independent truth |
| C: template normalization | Same T1 inputs and exact target/template assets; SPM segment-derived warp vs ANTs SyN variants | Landmark error, atlas-region overlap, inverse consistency, Jacobian/folding checks, contact displacement and atlas-label changes |
| D: tissue segmentation and bias | Same native MRI and reference outputs; current N4/Atropos vs prior-alignment workflow, later iterative candidate | GM/WM/CSF overlap, posterior error, tissue-volume differences, probability normalization, bias-field behavior, contact tissue-fraction differences; explicit taxonomy |
| E: complete contact workflow | Known native endpoints, identical interpolated contacts, captured random sample positions and target grid | Electrode/contact identity, sphere/centroid displacement, tissue classification, atlas labels and final export fields; identify boundary-dependent disagreements |
| F: reproducibility and deployment | Pinned versions, repeated runs/seeds, documented precision/threads; supported OS/Python combinations | Repeatability bounds, dependency resolution, installation and CLI smoke results; software support is separate from scientific acceptance |

For the reference corpus, collect raw inputs or approved derived fixtures,
their checksums, SPM/MATLAB versions, the generated batch, all templates/priors,
native/normalized tissue images, corrected image, transforms, endpoints,
sampled contact positions and expected final labels. The original input image
headers must be captured before and after header-mutating SPM operations.

Use scanner resolution and annotation repeatability to help set physical error
bounds with the author. Record median, upper-tail and maximum error rather than
only a mean. A case that fails registration must remain in the denominator.
Report systematic label changes near anatomical boundaries separately from
large spatial failures. Passing an SPM agreement bound alone does not establish
scientific correctness: retain independent landmark and geometry checks.

Determinism needs both random-state and thread controls. SimpleITK documents
sampling randomness and multithreaded floating-point variability. Record the
actual ANTs/ITK build and effective options as well as the Python seed. Use
separate processes for independent backend studies to avoid shared global
runtime settings. [SimpleITK reproducibility guidance](https://simpleitk.readthedocs.io/en/master/registrationOverview.html#reproducibility)

## Packaging, platforms and assets

This is a **wheel-metadata snapshot**, not a claim that every listed combination
has been installed or tested here. “Python >=” metadata alone is insufficient
evidence for native-library availability.

| Distribution inspected | Observed released wheels | Consequence |
| --- | --- | --- |
| `antspyx` 0.6.3 | CPython 3.11–3.13 on Windows x86-64, Linux x86-64, macOS Intel 15+ and arm64 14+; no 3.14 wheel listed | Keep full 3.14 imaging support explicitly unresolved; do not pretend an optional-extra skip completes that release requirement. [PyPI files](https://pypi.org/project/antspyx/) |
| `SimpleITK` 2.5.6 | `cp311-abi3` for standard CPython 3.11+ on Windows x86-64, Linux x86-64/arm64 and macOS Intel/arm64; separate 3.14 free-threaded wheels | Strong candidate for 3.14 comparator jobs, subject to installation/execution checks. [PyPI files](https://pypi.org/project/simpleitk/) |
| `itk-elastix` 0.25.4 | `cp311-abi3` Windows x86-64, Linux x86-64/arm64, macOS arm64 15+; no Intel macOS wheel in this release's list | Resolve the complete ITK dependency set before claiming 3.14 support. [PyPI files](https://pypi.org/project/itk-elastix/) |
| `SimpleITK-SimpleElastix` 3.0.0a1.post183 | Alpha, `cp311-abi3` Windows x86-64, Linux x86-64 and macOS arm64 15+ | Installation candidate, not production selection based solely on convenience. Isolate from standard SimpleITK. [PyPI files](https://pypi.org/project/simpleitk-simpleelastix/) |

ANTsPy, SimpleITK and ITKElastix identify Apache licensing in their primary
project/package materials. Record the resolved versions and accompanying
notices rather than assuming that all transitive assets share the library's
license. [ANTsPy package metadata](https://pypi.org/project/antspyx/),
[SimpleITK license](https://github.com/SimpleITK/SimpleITK),
[ITKElastix metadata](https://pypi.org/project/itk-elastix/)

Templates, TPMs, anatomical lookup tables and pretrained model weights require
their own identity, provenance and redistribution decision. TemplateFlow
explicitly requires template-specific licensing and attribution. A GPL toolbox
does not itself establish permission to redistribute every atlas it can load.
Use caller-supplied assets with checksums now; add an explicit, documented asset
installer only after that review. [TemplateFlow contribution requirements](https://www.templateflow.org/contributing/guidelines/)

For DICOM conversion, evaluate dcm2niix as a dedicated external converter rather
than assuming generic image reading reproduces SPM DICOM handling. Its project
documents vendor-aware conversion and associated metadata. A chosen executable
would add a packaging dependency, and conversion orientation/scaling needs its
own fixtures. [dcm2niix project](https://github.com/rordenlab/dcm2niix)

## Actionable implementation order

1. **Harden the current ANTs primitives:** validate finite scalar 3D geometry,
   masks and priors before native calls; record effective settings and input
   identity; reject incomplete outputs; keep atomic/no-overwrite behavior.
2. **Implement explicit transform application for images and points:** inversion
   flags, source/target identity, reference grids, artifact hashes and nonidentity
   geometry tests. Keep original sphere behavior available.
3. **Add an explicit MRI-template/prior preparation workflow:** named tissue
   classes, prior support checks, native and normalized output roles. Separate
   template registration from CT registration.
4. **Expose tissue/atlas sampling without GUI callbacks:** compare a captured
   list of sample positions first, then port generation of each shape while
   preserving the documented legacy behavior.
5. **Add optional SimpleITK comparison recipes and a reproducible benchmark
   runner:** identical inputs and evaluation metrics, backend/version settings
   saved in artifacts. Do not add a silent fallback or infer a winner from a
   synthetic identity experiment.
6. **Complete modulation, original field/session import and reorientation:**
   these need dedicated contracts and reference artifacts; do not disguise them
   as covered by generic image warping.
7. **Run the matched corpus and accept components:** only then promote candidate
   configurations to verified CCEP defaults. Subsequent scientific corrections
   remain separate changes with their own before/after reports.

The unresolved items are concrete: the intended “Enhanced Py” package identity,
matched MATLAB/SPM fixtures, approved physical/tissue acceptance thresholds,
template and atlas distribution choices, and full ANTs operation on Python
3.14. They do not block the independent geometry, API, workflow, test and CI
improvements above.
