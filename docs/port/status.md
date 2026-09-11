# Implementation and verification status

Updated 11 September 2026. This is a working development port, **not the complete
first release**. Source-derived behavior and synthetic checks do not establish
MATLAB parity. No MATLAB run, real recording comparison, or author acceptance
walkthrough has occurred on this machine.

See [ANTs implementation and McGill template checks](../research/ants_icbm152_implementation.md)
for the new template, masking, contact sampling, SPM-field and acquisition-session
adapters. SimpleITK is now restricted to the optional release comparison workflow.

## Work packages

| Package | Implemented | Remaining first-release gates |
| --- | --- | --- |
| WP1 | Concise README/illustrated guide, complete manual transcription and six original images; 543-file hash inventory, 101 source candidates and 36 capability groups; typed package, Ruff/Black/Pyright, pre-commit and CI | Final asset/runtime dependency audit; complete capability coverage |
| WP2 | Qt EDF selection/viewing, left channel selector, unipolar/bipolar reference, gain/time/scroll, filtering, annotation add/edit/delete/save/reopen, automatic/manual pulse controls, processing worker/cancellation, saved ERP/result viewer, train-dependent rankings and channel highlighting, historical stimulation geometry/study controls, native image/overlay review and contact acquisition | MATLAB walkthrough; repository/anatomical workflows; registration/segmentation controls, full imaging session compatibility; long-recording performance/cancellation; Windows/Linux GUI acceptance |
| WP3a | EDF/EDF+ continuous reading/calibration, annotation MAT/JSON, MAT numeric/cell/struct reader candidates, descending-contact Excel map reader, stimulation annotation parser, FIR/epochs/RMS/std/baseline/rank-sum/rank/geometry kernels, explicit anatomy eligibility/scoring, MAT analysis inspection/direct metric comparison; explicit multi-train processing and additive CSV/XLSX/plot/NPZ exports | Reference capture; legacy metadata relabeling and connectivity/repository integration; complete legacy MAT analysis writers/readers and companion discovery; mixed-rate/discontinuous EDF and label corner cases; file-level sample-rate/time-origin quirks |
| WP3b | Strict geometry, endpoint interpolation, SPM-style absolute pull evaluation, ANTs registration with explicit recipes and portable transform bundles, six-prior segmentation, staged template normalization, full-Jacobian density modulation, image/contact mapping and sphere-warp centroid candidates; executed synthetic ANTs/SimpleITK comparisons | Matched SPM corpus, calibrated scientific criteria, normalization/template choices, atlas/tissue shape sampling, legacy imaging session adapters, manual reorientation and full viewers; ANTsPy Python 3.14 installation/build |
| WP4 | Analytic, edge, GUI interaction, API/CLI equivalence, JSON-error, reference-integrity, persistence and packaged-playbook tests; isolated Python 3.11 and 3.14 environments | Full capability coverage and corpus parity, author acceptance, OS matrix, performance, final package publication |
| WP5 | inspect/validate/process/export/compare/compare-mat/annotations/reference-check/reference-replay and image commands, structured diagnostics, provenance, explicit config and collision handling | Extend commands as remaining scientific workflows are verified |
| WP6 | One authoritative Codex playbook shipped in the package; discovery/install commands, packaged imaging branch; executable end-to-end recording/normalization commands and failure tests | Live agent-assisted researcher walkthrough and complete first-release scientific operations |

## Evidence and limits

- macOS arm64 Python 3.11.15: **83 tests pass**, including Qt and ANTsPy 0.6.3.
  Ruff, Black and Pyright pass in this full environment.
- Earlier pre-recreation macOS arm64 Python 3.14.6 run: **55 tests passed**, one ANTs test module was skipped.
  Core, Qt and NIfTI review install and execute with independent resolution.
  The full type-check command reports the missing optional `ants` import here;
  full source type checking was performed in the 3.11 environment.
- ANTsPy binary-only installation probe for Python 3.14: **no usable wheel**.
  A source build was not attempted. Full imaging support on 3.14 is unresolved.
- `uv.lock` currently reflects ANTsPy's SciPy constraint (SciPy 1.15.3). Use
  Python 3.11 with this full-development lock. Python 3.14 core/GUI was tested
  through an independent pip-style resolution using newer SciPy, not this lock.
- Restored GitHub CI passed for the normalization implementation at `0876fea`: core
  Python 3.11/3.14 on Windows/macOS/Linux, core 3.12/3.13 on Linux, integrated
  Qt/ANTs/type checks on Linux 3.11, and package build/install.
  [Completed run](https://github.com/daveprime88/CCEP_toolbox_python/actions/runs/34361112425).
  The expanded 14-job matrix passed at `34e78d6`, including Qt/ANTs on
  macOS/Windows 3.11 and Linux 3.13 and the ANTs/SimpleITK benchmark.
  [Expanded run](https://github.com/daveprime88/CCEP_toolbox_python/actions/runs/34361288259).
  The final input-change regression fix at `de4f98a` also passed all 14 jobs.
  [Regression-fix run](https://github.com/daveprime88/CCEP_toolbox_python/actions/runs/34361969605).
  Core resolves independently; imaging jobs use the full lock.
- The manual media were checked visually; Python interaction tests inspect actual
  state and plotted arrays. Screenshots alone do not certify GUI parity.
- Kernel reference harness calls five original functions plus MATLAB ranksum and exports
  versioned/checksummed artifacts. It is ready for execution on the data-holding
  computer, but has not itself been runtime-validated in MATLAB.

- Updated wheel and source distributions build successfully. A fresh Python 3.11
  wheel installation outside the checkout includes the imaging playbook reference
  and exposes normalization help without requiring optional imaging imports.
  Earlier package validation: The noneditable wheel was
  installed into a separate Python 3.14 environment and its packaged skill,
  validate/process/export commands executed from outside the source checkout.
- A Qt/Matplotlib deferred-render lifetime failure was reproduced by a targeted
  test and fixed by retaining the owning window through rendering. The unprotected
  canvas fails that test; the shared Python canvas passes.

## Work that needs the reference computer

Provide or run the bundle in [reference/README.md](../../reference/README.md).
Then establish matched cases for each capability, the actual MATLAB/SPM versions,
real annotation/electrode/result files, and the SPM12/ANTs comparison resource.
Set scientific tolerances before accepting results. Port verification and any
scientific correction remain separate commits/PRs; no legacy defect has been
silently corrected as an accepted change.

The remaining implementation work listed above is also outstanding; availability
of reference data alone will not make this first release complete. Continue with
legacy metadata adapters and repository/connectivity integration, then complete imaging
interaction and compatibility, guided by those captured cases.

Detailed continuation tasks are in [next-work.md](next-work.md).
