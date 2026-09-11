# Roadmap progress checklist

Updated 11 September 2026. **The port is not at MATLAB version parity and is not
ready for the agreed complete first release.** It has an executable development
workflow and substantial tested components. There is both implementation work and
scientific acceptance work remaining; this is more than final packaging.

Crossed-off items mean the stated implementation exists. They do not mean its
MATLAB scientific equivalence has been accepted. None of the 36 capability groups
has completed matched MATLAB acceptance. No complete work package is signed off.

## WP1 — Documentation and foundation: substantially implemented, audit open

- [x] ~~Convert the manual into concise Markdown guidance and retain six images.~~
- [x] ~~Inventory 543 MATLAB files and define 36 capability groups.~~
- [x] ~~Create typed packaging, Ruff, Black, Pyright, pre-commit and CI.~~
- [x] ~~Version five symmetric 2009a T1/T2/GM/WM/CSF NIfTIs with Git LFS, licence, hashes and count checks.~~
- [ ] Finish runtime asset/dependency and documentation coverage audits.
- [ ] Resolve full ANTs imaging support on Python 3.14; core support is separate.

## WP2 — GUI workflows: partial implementation

- [x] ~~Implement EDF viewing, left channel selection, reference controls and plots.~~
- [x] ~~Implement annotation editing/persistence and automatic/manual pulse controls.~~
- [x] ~~Implement processing worker, ERP/rank results and channel highlighting.~~
- [x] ~~Implement initial stimulation geometry/study controls and image/contact review.~~
- [x] ~~Add automated Qt interaction checks.~~
- [ ] Complete repository search, anatomical connectivity and associated displays.
- [ ] Complete imaging registration/segmentation controls, 3D views and legacy sessions.
- [ ] Complete parameter, file/reference switching and study-detail/plot workflows.
- [ ] Measure realistic long-recording responsiveness and cancellation.
- [ ] Perform matched MATLAB/author walkthroughs on Windows, macOS and Linux.

## WP3a — Recording science and compatibility: partial implementation

- [x] ~~Implement continuous EDF calibration, annotation adapters and selected MAT/Excel readers.~~
- [x] ~~Implement reference/filter/pulse/epoch/baseline/RMS/statistical/ranking kernels.~~
- [x] ~~Implement explicit multi-train processing and CSV/XLSX/plot/NPZ exports.~~
- [x] ~~Provide MATLAB capture/replay and selected-metric comparison infrastructure.~~
- [ ] Complete real legacy metadata relabeling, companion discovery and MAT round trips.
- [ ] Implement repository compilation/search and participant/anatomical connectivity aggregation.
- [ ] Complete mixed-rate/discontinuous EDF, label and time-origin edge cases.
- [ ] Complete remaining safety-table, plot and reachable utility behavior.
- [ ] Capture real MATLAB references and verify intermediate/final outputs for all capabilities.

## WP3b — ANTs imaging: candidate implementation, scientific acceptance open

- [x] ~~Research SPM operations and ANTs alternatives; choose ANTs for production.~~
- [x] ~~Implement geometry/transform contracts, CT-to-MRI and T1-to-template recipes.~~
- [x] ~~Implement N4, six-prior Atropos candidate, staged normalization and modulation.~~
- [x] ~~Implement contact/ROI mapping, tissue sampling, SPM-field adapters and initial acquisition import.~~
- [x] ~~Run synthetic and historical ext55 template experiments; preserve observed failures.~~
- [x] ~~Validate 2009a image counts, tissue ranges/sum and brain-mask coverage.~~
- [ ] Implement the proposed three-class GM/WM/CSF production recipe with explicit brain-mask handling.
- [ ] Validate its tissue probabilities and contact assignments against matched SPM outcomes.
- [ ] Integrate the five-image repository subset into that recipe (the ZIP importer still expects the complete archive).
- [ ] Supply/verify a named anatomical region-label atlas and lookup table for regional reporting.
- [ ] Complete imaging formats, historical sessions and GUI integration; audit DICOM reachability.
- [ ] Calibrate registration, segmentation and ROI thresholds on representative real cases.

The three additional SPM classes (bone, other soft tissue, background) are internal
whole-head modeling categories. MATLAB CCEP consumes GM/WM/CSF downstream.
Missing extra priors are **not a blanket production blocker**. The existing Python
six-prior interface has not yet been changed; three-class processing needs its own
implementation and outcome checks. Tissue priors are not anatomical region labels.

## WP4 — Testing and release: infrastructure implemented, acceptance open

- [x] ~~Implement analytic, edge-case, persistence, GUI and API/CLI tests.~~
- [x] ~~Establish multi-OS CI, package build/install checks and a reference harness.~~
- [ ] Execute the capture harness on the reference computer and import verified artifacts.
- [ ] Establish fixture-specific tolerances and pass complete capability comparisons.
- [ ] Complete author acceptance, performance and supported-installation checks.
- [ ] Publish the complete release to PyPI after acceptance.

Last completed pre-LFS evidence: 101 local tests including the optional real ZIP
check; all 13 jobs passed at `9927266`. Automated checks are not MATLAB parity.
[CI evidence](https://github.com/daveprime88/CCEP_toolbox_python/actions/runs/34592375904).
The LFS change adds a dedicated real-asset check in one existing imaging job.

## WP5 — CLI: core commands implemented, scope incomplete

- [x] ~~Ship inspect/validate/process/export/comparison/annotation/reference and image commands.~~
- [x] ~~Test structured diagnostics, provenance and API/CLI equivalence.~~
- [ ] Expose the remaining repository, compatibility and imaging workflows as implemented.
- [ ] Verify complete first-release end-to-end command workflows on reference cases.

## WP6 — Agent skills: initial playbook implemented, acceptance open

- [x] ~~Package one authoritative Codex playbook with discovery/install commands.~~
- [x] ~~Exercise documented processing/imaging commands and failure contracts.~~
- [ ] Extend coverage alongside the remaining CLI operations.
- [ ] Complete a live agent-assisted researcher walkthrough.

## Roadmap and evidence index

- [Initial roadmap and decisions](../../Initial_port_roadmap_and_workpackages.md): planning/interview phase complete; implementation roadmap still active.
- [Implementation status](status.md): current work-package evidence and limitations.
- [Next work](next-work.md): ordered implementation and acceptance backlog.
- [Capability matrix](capabilities.md): 36 first-release obligations, all awaiting MATLAB acceptance.
- [GUI verification](gui-verification.md): implemented interactions and remaining walkthroughs.
- [Imaging verification](imaging-verification.md): engineering checks and scientific limitations.
- [2009a template report](icbm152_2009a.md): completed lightweight template checks.
- [SPM-to-Python trade study](../research/spm12_python_trade_study.md): research delivered; outcome validation still open.
- [ANTs implementation/experiments](../research/ants_icbm152_implementation.md): delivered candidate implementation and historical ext55 experiments.
- [Reference capture instructions](../../reference/README.md): ready for use on the reference computer; capture not completed.

Proceed with the three-class imaging integration, legacy metadata/analysis
compatibility, repository/connectivity workflows and remaining GUI operations.
Reference capture can run alongside implementation. Preserve the agreed separate
port-verification and scientific-correction changes; do not lower the full-release
scope to match what currently exists.
