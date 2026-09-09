# Synthetic ANTsPy–SimpleITK registration experiments

Date: 2026-09-09. These are small, local engineering experiments with known synthetic transforms. **They are not SPM12 comparisons, patient-data validation, or evidence that either engine matches the CCEP MATLAB imaging workflow.** No SPM executable or matched clinical reference images were used.

Both packages recovered the transforms accurately on the three initial smooth phantoms. An additional noisy, larger-motion case caused the initial SimpleITK optimizer recipe to fail. A separately recorded recipe with controlled physical steps recovered that case. This illustrates the need to validate the complete registration configuration; it does not establish a generally superior library.

## Reproduction and preserved evidence

The authoritative experiment implementation is [`tools/benchmark_registration.py`](../../tools/benchmark_registration.py). Run from the repository root with the imaging dependencies and `SimpleITK>=2.5,<3` installed:

```bash
uv sync --python 3.11 --extra imaging --group imaging-benchmarks
.venv/bin/python tools/benchmark_registration.py \
  --output artifacts/trade-study/rigid-phantoms-initial --repeats 2
.venv/bin/python tools/benchmark_registration.py \
  --output artifacts/trade-study/rigid-phantoms-bounded --repeats 2 \
  --sitk-bounded-step
```

Existing output directories are refused. Each run preserves synthetic fixed/moving NIfTIs, independently sampled label images, the ground-truth ITK transform, identity initialization, LPS landmarks, estimated transforms, warped images/labels and `results.json`. Input SHA256 values, exact settings, versions, individual landmark errors, individual label Dice values, optimizer diagnostics when exposed, failures and timing are recorded. The generated image/result folders are ignored by Git; the script and this report are tracked.

Local experiment sequence:

| Artifact directory under `artifacts/trade-study/` | Purpose | SHA256 of `results.json` |
|---|---|---|
| `rigid-phantoms-v1` | Initial three cases, two engines, two repeats | Superseded by v2, inputs and results retained locally |
| `rigid-phantoms-v2` | Added fourth stress case; unchanged initial optimizer recipes | `cddcb6ffa42cdf26a0e5342e848e95434cf14c7356c9555882b1d9def32ea4cf` |
| `rigid-phantoms-v3` | Same four inputs; explicit second SimpleITK recipe | `c873f8c843a6e213088c9216579e93c9ee06be4f222159975a0f220c0ada6c1e` |

Environment: Python 3.11.15, NumPy 2.3.5, ANTsPy/`antspyx` 0.6.3, SimpleITK 2.5.6, macOS 26.6.2 ARM64. ITK uses one thread; sampling and phantom noise seed are 1729. Two identical-seed repetitions assess repeatability in this environment, **not variability across independent samples, platforms or seeds**. All successful estimated landmark coordinates and Dice values were identical across the two repeats for their case/recipe.

## Experimental design

The phantom is an analytic sum of five asymmetric Gaussian structures and a broad background envelope. Five ellipsoidal regions supply labels; they are sampled separately from intensity. The fixed and moving images are sampled directly from the analytic function at their respective physical coordinates, avoiding a synthetic intensity image made by repeatedly resampling the fixed grid.

| Case | Grid and geometry | Known fixed-to-moving transform | Intensity variation |
|---|---|---|---|
| Isotropic, same contrast | 56 × 60 × 52; 1 mm isotropic | Euler rotations (4, −3, 6) degrees; translation (4, −3, 2) mm | None |
| Isotropic, reversed contrast | Same grid | Same transform | Moving intensity `exp(-2.5 * intensity)` |
| Anisotropic, oblique | 0.9 × 1.2 × 1.6 mm; direction rotated 23° about z | Same transform | None |
| Oblique, noisy, larger motion | Same anisotropic/oblique grid | Euler rotations (12, −9, 17) degrees; translation (12, −9, 6) mm | Reversed contrast plus independent Gaussian noise, SD 0.03, in both images |

All grids have a nonzero physical origin. Both engines start with identity about the physical image center; neither receives the known motion. Labels and 11 landmark coordinates are withheld from optimization. The last case has greater cropping/partial anatomical coverage. The contrast reversal tests mutual-information behavior under a nonlinear intensity mapping; it does **not** realistically model postoperative CT, MR tissue contrast, electrodes, metal artifacts or field inhomogeneity.

Both candidates use rigid transforms, Mattes mutual information with 32 histogram bins, 50% metric sampling, linear intensity interpolation, shrink factors `(4, 2, 1)` and Gaussian smoothing `(2, 1, 0)` mm. ANTs uses `Rigid`, iterations `(300, 150, 75)` and double-precision registration. SimpleITK uses Euler3D and gradient-descent line search, up to 300 iterations per level, physical-shift optimizer scales, convergence minimum 1e-6 and a 10-iteration convergence window. These are comparable task recipes, **not identical algorithms or optimizer schedules**. API choices follow the [ANTsPy registration documentation](https://antspy.readthedocs.io/en/latest/registration.html), [SimpleITK registration overview](https://simpleitk.readthedocs.io/en/master/registrationOverview.html) and [SimpleITK registration example](https://simpleitk.readthedocs.io/en/master/link_ImageRegistrationMethod4_docs.html).

The initial SimpleITK recipe estimates learning rate once, uses the default automatic physical-step setting (`0.0`) and line-search upper factor 5. The second recipe estimates it each iteration, requests a 1 mm physical-step scale and reduces the line-search upper factor to 2. This is a recorded change after observing a failure, not a preset selected before all experiments. The ANTs recipe is unchanged between v2 and v3.

## Coordinate and measurement contract

All landmark calculations use **LPS physical millimetres**. The known transform maps fixed points to moving points. The analytic moving image is generated using its inverse. SimpleITK's estimated transform is used as the pull transform for resampling moving intensity onto the fixed grid.

The ANTs forward *image* transform list, applied to *points* without inversion, maps fixed points to moving points for this rigid case. The script independently checks this direction by applying the known ITK transform through ANTs' point API and comparing with SimpleITK's known point mapping. This distinction matters because ANTs explicitly documents opposite directions for point and image mapping; filenames alone should not determine a transform's meaning. See [ANTs point-transform documentation](https://antspy.readthedocs.io/en/latest/registration.html#ants.apply_transforms_to_points).

Target registration error (TRE) is Euclidean distance between estimated and known moving positions of each fixed landmark, in mm. Reported mean TRE averages the 11 landmarks; maximum TRE is their maximum. Reported Dice is an unweighted mean over the five labels after nearest-neighbor resampling. Timing covers the backend runner including image reads, registration, transform application and artifact writes; it excludes Python imports and phantom generation. No acceptance threshold was selected from these measurements.

Even the known transform produces imperfect label Dice because labels occupy finite voxels and nearest-neighbor interpolation quantizes their boundaries. Known-transform mean Dice is 0.9397 for the isotropic cases, 0.8939 for the anisotropic case and 0.9004 for the stress case. These are contextual reference measurements, not strict mathematical upper bounds: small transform errors can coincidentally improve overlap of rasterized boundaries.

## Results: initial recipes

Values below are from v2. Timing averages the two repeats; spatial metrics are identical across those repeats.

| Case | Engine | Mean TRE (mm) | Maximum TRE (mm) | Mean label Dice | Time (s) |
|---|---|---:|---:|---:|---:|
| Isotropic, same contrast | ANTsPy | 0.0382 | 0.0571 | 0.9394 | 0.853 |
| Isotropic, same contrast | SimpleITK initial | 0.0164 | 0.0247 | 0.9403 | 0.856 |
| Isotropic, reversed contrast | ANTsPy | 0.0353 | 0.0544 | 0.9390 | 0.477 |
| Isotropic, reversed contrast | SimpleITK initial | 0.0054 | 0.0086 | 0.9393 | 1.768 |
| Anisotropic, oblique | ANTsPy | 0.0264 | 0.0324 | 0.8911 | 0.741 |
| Anisotropic, oblique | SimpleITK initial | 0.0498 | 0.0752 | 0.8901 | 1.021 |
| Oblique, noisy, larger motion | ANTsPy | 0.0316 | 0.0544 | 0.9001 | 0.787 |
| Oblique, noisy, larger motion | SimpleITK initial | Failed both repeats | — | — | 0.041 |

Unregistered mean TRE is 5.5691 mm for the first three cases and 16.6661 mm for the stress case. The failed SimpleITK runs raised a Mattes mutual-information exception after transformed samples left the moving buffer. The inputs initially share their grid; therefore the exception should not be interpreted as proof that their initial image domains have no overlap. It is a failure of this optimizer trajectory/configuration on this case.

## Results: second SimpleITK recipe

The explicit physical-step recipe was rerun on all four cases to check that addressing the stress-case failure did not merely replace the earlier evidence. ANTs spatial results remained exactly those above.

| Case | Mean TRE (mm) | Maximum TRE (mm) | Mean label Dice | Time (s) |
|---|---:|---:|---:|---:|
| Isotropic, same contrast | 0.0284 | 0.0458 | 0.9396 | 0.871 |
| Isotropic, reversed contrast | 0.0200 | 0.0305 | 0.9396 | 1.014 |
| Anisotropic, oblique | 0.0577 | 0.0974 | 0.8926 | 0.846 |
| Oblique, noisy, larger motion | 0.0435 | 0.0728 | 0.8998 | 0.879 |

The second recipe completes all four cases. It is slightly less accurate by TRE on the first three smooth cases than the initial SimpleITK recipe. These differences are much smaller than their voxel spacings and cannot rank clinical performance. They show that a robust configuration decision has tradeoffs and should be made on representative external data.

## Implications for the CCEP port

1. Both engines are credible candidates for rigid alignment primitives. Keep explicit transform/coordinate contracts, reproducible settings and output provenance regardless of backend.
2. Retain ANTsPy as the principal candidate where its registration/normalization and segmentation pipeline is already used. This experiment supplies no reason to replace ANTs with a generic SimpleITK call throughout the project.
3. If SimpleITK rigid registration is exposed as an alternative, ship a named, explicit recipe and diagnostics. Do not treat its low-level defaults as an SPM12 coregistration equivalent; a usable alternative requires further validation.
4. Real CT–MRI, MR–MR and template normalization studies remain necessary. They should use matched SPM outputs, independently reviewed anatomical landmarks, native/normalized contact coordinates, atlas labels, tissue fractions and registration QC. Define acceptance tolerances before evaluating the held-out corpus.
5. Add a separate nonlinear experiment and external SPM normalization comparison before claiming SyN equivalence. This study estimates rigid transforms only. It does not test SPM's unified segmentation, ANTs Atropos/N4, deformable displacement conventions or the legacy sphere-based electrode normalization path.

No library backend or scientific acceptance threshold was changed by this benchmark script itself.
