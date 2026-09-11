# CCEP Toolbox Python initial port roadmap and work packages

Date: 9 September 2026

Status: High-level planning baseline after three interview rounds. The scope and scientific acceptance approach are agreed. Proposed implementation choices and later work-package decisions remain explicitly recorded below.

## Purpose and agreed direction

Port the complete functionality of the current MATLAB CCEP Toolbox to a maintainable Python project that researchers can use and contribute to. The first release must cover all existing toolbox capabilities, including imaging, electrode localization, stimulation safety, SEEG viewing and annotation editing, processing, results, and repository aggregation. Internal milestones can be small; a partial port does not meet the first-release requirement.

Preserve scientific behavior and familiar workflows with explicit evidence of equivalence. GUI controls, grouping, plots, selections, and task outcomes matter; matching pixel positions and widget appearance does not. Preserve existing file interfaces and add CSV and other suitable Python-oriented exports.

Deliver a typed Python library supporting Windows, macOS, and Linux, targeting Python 3.11 through 3.14. The first release must include a usable GUI, core CLI commands, and agent skills over those commands. Replace SPM processing with ANTsPy; released workflows must run without MATLAB/SPM. Begin with source installation; eventual distribution through PyPI should support pip and uv. The user prefers lightweight infrastructure; tests accompany each feature, while a small early CI matrix remains a recommendation.

## What the repository currently tells us

- The existing Python directory is `CCEP_toolbox_python`; at initial inspection it contained only Git metadata. It now also contains this roadmap. Use this directory for the port.
- The MATLAB source baseline inspected is commit `a25ed5d75536e5d3a8c2570c48f3196055a7f4bd` in the adjacent `CCEP_Toolbox` repository. Its working tree was clean at inspection.
- The original README describes SEEG viewing, rereferencing, filtering, annotations, stimulus timing, RMS analysis, connectivity reports, ERP viewing, stimulation safety, and electrode localization.
- The DOCX manual contains six embedded media items and covers imaging, SEEG processing, aggregate results, and individual-file ERP/rank results. Image relevance and captions still need a visual audit during conversion.
- The repository contains example spreadsheets, MAT assets, and bundled third-party code. These are inventory candidates, not yet validated regression fixtures.
- No EDF recordings or first-party tests surfaced in the initial file inventory. Historical installation guidance mentions Windows and MATLAB Runtime R2018a/9.4; this is not a verified execution baseline.
- No MATLAB executable was found on PATH or under the usual `/Applications/MATLAB*` location. The author confirms reference resources exist on another computer. Its runtime, toolbox versions, dataset contents, and access route have not yet been verified; reference capture will support execution there.

This is an initial inventory, not a completed functional audit or a claim that the MATLAB application has been executed successfully.

## Proposed work packages

| Package | Scope and principal outputs | Evidence required to finish |
| --- | --- | --- |
| WP1 — Documentation and project foundation | Inventory all first-party features, assets, dependencies, and existing notices. Convert the DOCX into a concise README plus supporting Markdown pages; retain relevant images and scientific context. Establish typed Python packaging, contribution guidance, pre-commit hooks, a test layout, and a lightweight check command. Recommend initial CI here. | A source-to-destination content and feature checklist covering the whole toolbox; each relevant manual section retained or condensed; image links render; a clean environment can install the skeleton and run checks. |
| WP2 — GUI workflows | Start with file selection, SEEG viewing/annotation editing, and results. Extend to all remaining MATLAB user workflows. Define interfaces to the shared library, prototype against fixtures, and connect to verified processing. | Automated interaction checks and author walkthroughs on matching fixtures; correct selections, references, annotations, plots, results, and saved outputs throughout every legacy workflow. |
| WP3 — Scientific processing and compatibility | Establish reference outputs first. WP3a ports signal processing, safety calculations, and file compatibility. WP3b replaces SPM imaging with ANTsPy and associated Python interfaces. Separate adapters and GUI state from calculations. | WP3a passes MATLAB parity checks. WP3b passes separately agreed imaging equivalence criteria. Every suspected legacy defect is characterized; correction PRs may follow each verified component. |
| WP4 — Test coverage and release readiness | Extend the tests delivered throughout the port; add difficult inputs, integration coverage, installation checks, contributor documentation, and eventual release automation. | Every legacy capability has acceptance evidence; supported OS/Python combinations are tested; known limitations are documented; reproducible package artifacts can be produced. |
| WP5 — CLI workflows | Expose core library operations through deterministic, non-interactive commands with explicit parameters, structured output, diagnostic codes, and provenance. Preserve existing exports and add CSV. | API/CLI equivalence tests, command contract tests, reproducibility checks, and complete fixture-based workflows run without a GUI or an agent. |
| WP6 — Agent skills | Build focused Markdown playbooks over tested CLI commands, inspired by config spine. Document discovery, execution, validation, diagnostics, and reporting; keep scientific logic in the library. | Each playbook has an executable command example, validated expected artifacts, failure guidance, and an end-to-end acceptance scenario. Both WP5 and WP6 are first-release gates. |

WP4 consolidates quality work already underway. Unit tests and regression tests are part of each implementation package, not a cleanup phase at the end. Keep local checks simple from WP1; the proposed minimal CI does not require an elaborate deployment system. PyPI publishing comes later.

## Sequence and milestones

1. **Inventory the complete baseline.** Map every MATLAB user capability and file interface to Python work, fixtures, and acceptance evidence. Locate the reference environment and data; audit SPM-to-ANTsPy workflow coverage and dependency support early.
2. **Establish the foundation.** Complete the documentation inventory, create the package skeleton and CI, and capture the first reproducible MATLAB fixtures.
3. **Deliver one complete internal milestone.** A candidate is selecting one SEEG recording and its metadata, processing it, viewing RMS/ERP results, and exporting them through the API and GUI, then CLI. This is a development milestone, not a reduced first-release scope.
4. **Complete all capability groups.** Extend verified processing, compatibility adapters, and GUI behaviors together, including imaging, repository aggregation, and safety. Add CLI operations as their library interfaces stabilize; build skills over those tested commands.
5. **Validate the full port.** Run the comparison suite, author walkthroughs, and installation checks across the entire feature inventory.
6. **Correct discrepancies separately.** After demonstrating parity for each affected component, a separate delta PR may follow immediately, with before/after evidence, targeted tests, and a changelog entry. It need not wait for the entire port. The explicitly requested SPM-to-ANTsPy redesign is tracked separately as WP3b, with its own scientific acceptance criteria.

A GUI prototype can use fixed results while processing is being ported. Integrated GUI parity requires verified live processing. Estimates should follow the scope and reference-data audit.

## Conceptual architecture

Use a small set of clear boundaries: file readers and writers; explicit recording, annotation, electrode, parameter, and result data; scientific processing callable without a GUI; and GUI/CLI adapters invoking the same library API used by tests and scripts. Skills orchestrate the CLI and inspect its evidence. Scientific execution must not require an LLM.

Preserve a mapping from MATLAB features to Python modules and tests. Python folders need not copy MATLAB folders mechanically. Preserve scientific concepts, assets, and traceability while allowing an idiomatic package structure. GUI framework, additional native result formats, and detailed class design remain open.

## Python tooling and distribution

- **Confirmed direction:** modern typed Python, pre-commit, Ruff, Black, and one type checker; Python 3.11–3.14 across Windows, macOS, and Linux. Use 3.11-compatible syntax and typing features, adding compatibility imports where necessary.
- **Proposed selection:** Ruff for lint and import sorting, Black as the sole formatter, and Pyright as the type checker, following config spine's type-checker choice. Avoid overlapping formatters; Ruff's documentation explicitly distinguishes its formatter from interchangeable ongoing Black use. See the [Ruff formatter documentation](https://docs.astral.sh/ruff/formatter/) and [Black configuration documentation](https://black.readthedocs.io/en/stable/usage_and_configuration/the_basics.html).
- **Typing boundary:** annotate public APIs and internal processing contracts, including array dtypes; validate dimensions, units, channel identities, coordinate frames, and parameter ranges at runtime. Document narrow exceptions for untyped external libraries.
- **Developer experience:** propose `pyproject.toml`, a `src/` package layout, uv-managed development dependencies, pytest, and pinned pre-commit hook versions. Run Ruff and Black in fast commit hooks; expose type checking and tests through documented local commands.
- **Installation:** document cross-platform source installation and development setup. A Bash helper can be optional; Windows installation must also work without Bash. Keep GUI/imaging dependencies in extras if this simplifies library use, while still documenting how to install the full toolbox.
- **Proposed minimal CI:** core install/tests on all three OSes at Python 3.11 and 3.14, intermediate Python versions on one OS, and representative GUI/imaging integration jobs. Check dependency availability before declaring the full support matrix achieved. Saved MATLAB fixtures keep routine CI independent of MATLAB licensing.
- **Later distribution:** build and test wheel/source distributions before publishing to PyPI. Package naming and publishing automation remain implementation decisions.

**Imaging dependency check, 9 September 2026:** ANTsPy's distribution is `antspyx` and includes compiled native code. Its upstream installation guidance notes that binaries are not available for every Python/platform combination. The inspected PyPI 0.6.3 release lists CPython 3.11–3.13 wheels for several platforms but no CPython 3.14 wheel. This is a packaging risk, not proof that 3.14 cannot work. Verify a reproducible install/build and execute imaging tests on the target matrix before claiming support; do not silently reduce the agreed Python range. Sources: [ANTsPy installation guidance](https://github.com/ANTsX/ANTsPy#installation), [antspyx release files](https://pypi.org/project/antspyx/0.6.3/#files).

## WP3b SPM to ANTsPy imaging replacement

**Confirmed:** replace all toolbox use of SPM with a MATLAB-free Python imaging workflow centered on ANTsPy. This is a deliberate algorithm and implementation change, not a literal SPM translation. MATLAB/SPM may be used to generate development reference artifacts but is not a runtime dependency of the released toolbox.

Inventory every SPM-dependent operation, including preprocessing, coregistration, segmentation, normalization, image/point transformations, atlas lookup, tissue probabilities, and interactive image review/electrode acquisition. ANTsPy supplies registration, transform application, and segmentation capabilities; these do not establish one-to-one equivalence with SPM methods. Map each legacy operation to a candidate replacement and verification artifact before choosing parameters. Sources: [ANTsPy registration](https://antspy.readthedocs.io/en/stable/registration.html), [ANTsPy segmentation](https://antspy.readthedocs.io/en/stable/segmentation.html).

Repository-specific details to retain in that map:

- `CCEPSegmentFunc.m` combines bias correction, six tissue priors, native GM/WM/CSF outputs, optional normalized maps, and a deformation field. A registration-only replacement is insufficient.
- `CCEPROICreateandWarp.m` derives MNI contact positions by warping a 1.5 mm sphere to a 1 mm grid and averaging coordinates of voxels above a threshold. Preserve this surrounding procedure when changing the backend; substituting a direct point transform would require its own explicitly reviewed algorithm change.
- `CCEPTissueProbCalc.m` samples tissue probabilities using configurable shapes and randomness in some paths. Capture the actual sample points in reference fixtures, as with random baseline windows in signal processing.
- Existing imaging sessions load MAT metadata, the original MRI, and SPM `y_*.nii` deformation fields. Their compatibility must be tested independently of generating new ANTs transforms.
- Manual origin/reorientation, crosshair coordinate acquisition, and review currently use SPM GUI functions. Image conversion helpers also exist, with some DICOM branches commented out in the main workflow; the feature inventory must distinguish active operations from dormant helpers.

Proposed stages:

1. **Reference and mapping:** capture SPM outputs and settings from matched MRI/CT cases; identify the SPM12-to-ANTsPy comparison mentioned by the author. The exact reference has not yet been identified in the initial search, so its conclusions are not assumed here.
2. **Geometry and compatibility:** define physical/voxel coordinates, orientation, units, image origin/direction/spacing, transform direction and composition, and interpolation rules. Test known landmarks and synthetic transformations before real registration. Preserve existing imaging file interfaces through explicit adapters; SPM deformation fields and ANTs transforms must not be treated as interchangeable files.
3. **Registration and normalization:** replace the required alignment and native/template workflows; test images and electrode points through the same documented coordinate mappings.
4. **Segmentation and anatomy:** implement tissue probability and atlas lookup workflows with explicit class/label mapping and recorded template/atlas versions. Verify effects on electrode classification and downstream anatomical connectivity, not just image appearance.
5. **Interactive workflow and release checks:** replace SPM-dependent viewers, manual alignment, coordinate acquisition, and review controls through the Python GUI. Verify complete imaging workflows and installation on the supported platform matrix.

**Confirmed acceptance model:** preserve user operations and scientific outputs, with predefined outcome-based criteria for changed imaging algorithms rather than demanding identical SPM arrays. Use independent landmarks, spatial error in millimetres, segmentation overlap where reference labels exist, tissue-probability differences, electrode/atlas assignments, and author-reviewed overlays. Examine individual failures and difficult boundary cases; dataset averages cannot hide a wrong hemisphere or transform direction. Exact geometry conventions and identity/known-transform tests remain strict. Directly ported calculations retain their stricter MATLAB parity requirements.

Set numerical limits after identifying image resolution, the reference corpus, and scientific requirements, before accepting implementation results. Preserve the frozen SPM comparison set and establish a separate ANTsPy regression set after acceptance. Record seeds, thread settings, versions, and repeatability limits. Algorithm changes within the accepted ANTsPy workflow then use separate reviewed delta PRs.

This imaging work is on the critical path to full functionality. A reduced imaging feature set or a hidden MATLAB fallback does not satisfy the agreed release scope.

## Existing files and additional exports

Preserve every existing read/write interface used by MATLAB workflows, including EDF inputs, annotation/electrode MAT files, saved analyses/repositories, Excel inputs/reports, plots, and imaging assets where applicable. Inventory actual MAT variants, structures, field names, shapes, and companion-file lookup rules before implementing adapters.

Add CSV exports without replacing existing interfaces. CSV is appropriate for tables; it does not by itself preserve nested metadata, multidimensional waveforms, or imaging coordinates. Select additional native formats after the result schema is understood, with explicit units and provenance. Verify legacy readers/writers using real workflow fixtures, and add round-trip tests where both tools consume a format. Exact file bytes need only match where meaningful; schema and scientific content must match.

## Non-regression testing plan

Build a capability matrix covering every legacy user operation: MATLAB entry point, inputs/defaults, persisted effects and outputs, Python API/GUI location, fixture, comparison rule, and verification status. Include non-numerical behavior and dependencies. Vendored libraries need a replacement/dependency decision and evidence for the behavior the toolbox uses, not necessarily a line-by-line translation.

### Capture a trustworthy reference

The author accepted establishing one reproducible MATLAB environment and a small representative corpus spanning all capabilities, including imaging, and confirms reference resources are on another computer. The exact machine/runtime/toolbox versions, access route, and dataset locations are inputs to reference capture, not blockers to completing this high-level roadmap.

Freeze the MATLAB revision, runtime and toolbox versions, input checksums, parameters, and execution route for every reference run. Record whether parameters came from an open GUI or function defaults, because the inspected filter code can behave differently in those contexts.

Build an export harness that records intermediate arrays as well as final results, with units, axes, channel order, electrode identity, sampling rates, and event times. Store the harness and a fixture manifest alongside the comparisons so another researcher can reproduce them. Ordinary Python CI should use saved MATLAB outputs without requiring a MATLAB license; reference regeneration should be a separate documented job.

`CCEPBaselineTimeGrabber.m` selects baseline windows randomly. Record the actual selected sample windows as well as the RNG state and algorithm. Reuse those windows for deterministic cross-language comparisons; a matching seed alone does not guarantee matching MATLAB and Python random draws. Test the sampling and exclusion rules separately.

Start with deterministic synthetic signals whose expected behavior is independently calculable, followed by small representative recordings with established permission for their intended storage and use. Include multiple sampling rates, reference montages, and relevant annotation paths. Keep large or restricted recordings outside public fixtures and record how authorized maintainers run those checks.

If a runnable MATLAB environment or representative recordings are unavailable, label parity evidence incomplete. Synthetic tests and source inspection can support progress, but cannot establish full equivalence alone.

### Reference capture on the other computer

Design the capture harness to run beside the original MATLAB toolbox on the computer holding the reference resources. It must not depend on this development machine's absolute paths or a live connection between computers.

1. Prepare a versioned capture bundle: harness scripts, fixture definitions, required MATLAB/SPM settings, and concise run instructions. The receiving machine supplies its own local input paths.
2. Record the actual toolbox revision, MATLAB/SPM and dependency versions, effective parameters, input hashes, selected baseline windows and tissue sample points, and execution success/failure for each case.
3. Export intermediate/final scientific artifacts, machine-readable metadata, logs, and representative GUI screenshots into a manifest-based result bundle. Separate restricted source data from artifacts suitable for transfer; retain input identities without requiring the raw recordings in the Python repository.
4. On the development machine, verify bundle checksums, schema, expected cases, and completeness before importing references. Report missing stages explicitly. Store provenance and reusable fixtures with the comparison suite, using appropriate storage for large or restricted artifacts.
5. Replay comparisons locally and in Python CI from captured artifacts. Document regeneration on the source computer so a future maintainer can repeat the process.

The exact SPM12/ANTsPy comparison resource remains to be identified when those materials are available. It can inform the imaging work, but its unknown contents are not evidence of equivalence. No remote access or artifact transfer has been performed during roadmap preparation.

### Compare at scientific boundaries

| Boundary | What to compare |
| --- | --- |
| Import and metadata | Signal scaling and units, sample count, channel labels/order, recording metadata, annotations, electrode mapping. |
| Rereferencing and filtering | Bipolar pairing and polarity, filter coefficients and response, delay handling, start/end behavior, and output waveforms. |
| Stimulus timing and epochs | Detected/manual event samples, timing conventions, inclusion/exclusion rules, epoch and baseline windows. |
| RMS, normalization, and ERP results | Intermediate values, aggregation axes, baseline statistics, normalized values, averaged waveforms, and missing-data behavior. |
| Connectivity, aggregation, and exports | Metric values, labels, ranks, threshold decisions, repository contents, and exported table meaning. |
| Imaging and electrode localization | Registration transforms, coordinate frames and orientation, electrode positions, atlas labels, tissue probabilities, and overlays on matched imaging fixtures. Establish scientifically justified tolerances before accepting a replacement imaging backend. |
| Stimulation safety tools | Legacy table lookup, calculations, parameter boundaries, displayed results, and plots against the frozen implementation and bundled tables. Preserve the original research-use context; parity is not a reassessment of the source recommendations. |

Require exact equality for identities, shapes, ordering, and discrete selections where the contract demands it. Set justified absolute and relative tolerances separately for numerical outputs, in meaningful units, before accepting the port. Check near-zero values, NaNs, infinities, ties, and threshold crossings explicitly. Do not choose one universal tolerance or loosen tolerances just to pass a failing comparison.

On a mismatch, report the affected stage, fixture, channel/time location, maximum error, and diagnostic overlays where useful. Review both numerical differences and changes in scientific interpretation.

### Test beyond agreement with MATLAB

Add independently calculated small examples and scientific properties: known pulse locations, known RMS values, predictable reference polarity, and amplitude scaling where the algorithm should obey it. Exercise empty selections, short recordings, boundary pulses, missing or duplicate metadata, no detected events, and zero-variance baselines where applicable.

Audit MATLAB-to-Python differences in sample indexing, inclusive windows, rounding, array orientation, reshape order, precision, and statistical defaults. The inspected filter implementation also warrants characterization of notch normalization, GUI-dependent settings, and delay compensation before translation.

In `CCEPMakeRMSZScores.m`, a `ZScore` is obtained from the `ranksum` statistic, not ordinary mean/standard-deviation standardization. Capture the actual MATLAB method, tie handling, and relevant statistical defaults. Baseline exclusion code also contains apparent inconsistencies requiring characterization.

A suspected MATLAB defect follows the confirmed two-step policy: first reproduce and verify the legacy behavior in Python; then correct it in a separate delta PR with a changelog entry and before/after tests. Record discoveries during porting without folding fixes into translation PRs. Keep legacy reference fixtures immutable and version any corrected expectations separately. If an independent scientific test exposes a known legacy discrepancy, document it explicitly alongside the passing parity test; do not imply that parity establishes scientific correctness. Never silently change reference outputs to match the new implementation.

## GUI equivalence verification plan

Confirmed core GUI requirements are EDF loading, channel selection down the left-hand side, visible reference selection/status, and loading, browsing, verifying, editing, and saving annotations. Preserve control grouping, plots, and high-level operations; alternate widget sizes and layout changes are acceptable. Treat the left-hand channel selector as the initial design requirement, with other controls free to move.

Map workflows from `CCEPGUIInit.m`, `FilePathMenu.m`, the dialogs in `CCEPProcessRMS.m`, `CCEPSEEGViewerCallback.m`, `CCEPERPFileMenu.m`, and `CCEPReposGUI.m`. Extend the map to every remaining viewer and imaging/safety interaction because the first release covers the whole toolbox.

For each agreed workflow, document the starting state, inputs, user actions, enabled controls, expected state changes, visible results, and saved outputs. Capture MATLAB reference screenshots at meaningful states using known fixtures and a recorded display size. The manual's images are useful historical references, but live behavior still needs verification.

| Verification layer | Acceptance evidence |
| --- | --- |
| Visual usability | Side-by-side views verify discoverable controls, labels, tables, plot axes, units, legends, and annotations. Layout may differ; pixel identity is not a requirement. Use screenshot regression within Python where it catches rendering defects. |
| Behavioral equivalence | Automated actions for EDF loading, left-side channel selection, reference switching, annotation browsing/editing/save/reopen, cancellation, parameter changes, navigation, plotting, and export. Assert application state and displayed data rather than screenshots alone. Verify edited annotations affect subsequent processing and preserve untouched events. |
| Scientific integration | The selected fixture and displayed parameters reach the processing API unchanged; plotted arrays and exported values match the verified result objects. Check stale results after changing inputs. |
| Researcher acceptance | The author completes representative tasks in both applications and records missing operations, misleading differences, and acceptable improvements. |

Include invalid or missing files, duplicate filenames in different directories, empty results, long computations, cancellation, and recoverable errors. Distinguish intentional UI presentation changes from processing behavior changes; handle legacy bugs through the separate delta-PR policy. Run representative GUI workflows across Windows, macOS, and Linux.

## CLI and agent skills inspired by config spine

Read-only inspection of `/Users/davidprime/gitlab/config_spine_project` found implemented patterns in `src/spine/cli/commands/execute.py`, `src/spine/driver.py`, `src/spine/runtime/provenance.py`, and CLI/skill contract tests. Its `.cursor/skills/` and `.claude/skills/` contain CLI-based Markdown playbooks. These patterns were inspected, not executed or modified.

Adopt the shared API, explicit configuration, diagnostics, provenance, and executable examples. The CCEP port does not need config spine's compiler architecture or optional MCP server to provide these features.

### WP5 command contract

Candidate command groups below are illustrative; they do not yet exist. Confirm the first agent workflows before finalizing command names and flags.

| Candidate command group | Purpose and result |
| --- | --- |
| `ccep inspect` | Read recording/result metadata, available channels/references, and annotations; return a concise structured summary. |
| `ccep validate` | Check an explicit analysis configuration and associated files before execution; report located diagnostic codes. |
| `ccep process` | Execute a reproducible analysis using selected channels, references, annotations, and parameters; return result artifact paths and a run summary. |
| `ccep export` | Write existing compatible reports/plots and additional CSV tables from saved results. |
| `ccep compare` | Compare results against a named reference fixture and emit numerical differences plus diagnostic artifacts. |
| `ccep annotations` | Inspect or apply explicit annotation edits with validation and a change record; mutation scope depends on the agreed agent workflow. |

Propose a thin Typer command layer, matching the local config spine pattern. Define a versioned serializable run configuration shared by API, GUI, and CLI; include input identities, processing parameters, selection state, output locations, and randomness controls. The resolved configuration must capture actual defaults so a GUI run can be reproduced headlessly.

Commands must run non-interactively, accept explicit paths, and expose documented exit codes. JSON mode should emit one schema-versioned result on stdout for success and failure, with progress/logs on stderr; large arrays belong in artifacts. Include status, diagnostic codes and locations, effective configuration, artifact paths, and provenance. Config spine has useful structured outputs but some shared error paths can print human diagnostics, so test this separation directly in CCEP rather than assuming it transfers automatically.

Record input hashes, annotation version, selected baseline windows, software/dependency versions, and output identities. Separate timestamps from deterministic scientific contents. Validate before processing, define output collision/overwrite behavior, and avoid implicit destructive edits to source recordings. Test CLI/API equivalence, JSON parsing, errors, exit codes, paths with spaces, repeatability, and artifact contents on Windows as well as POSIX systems.

### WP6 skill contract

The confirmed first workflow is to inspect an EDF and its annotations, validate an explicit processing configuration, execute it, and export results. Ship CLI commands and at least the skills needed for this workflow in the first release. Comparison/diagnostic skills are additional candidates. Annotation editing remains required in the GUI; additional agent-driven annotation mutation can follow the first skill workflow.

Each skill should describe prerequisites, input discovery, explicit assumptions, exact commands, validation of outcomes, diagnostic recovery, and a final evidence summary. Use CLI-reported metadata and configured scientific parameters rather than inferred labels or units. Skills contain orchestration instructions; scientific computation and validation stay in tested Python code. Apply the user's existing authorization to actions rather than adding confirmation to every command.

Execute the documented command sequences against small fixtures and test that referenced diagnostic codes and output schemas exist. Test missing inputs and processing failures as well as successful runs. Such tests verify the playbook's command contract, not every possible agent response; also perform a representative agent-assisted walkthrough.

**Confirmed initial host:** package and verify the first-release skills for Codex, maintaining one authoritative Markdown source. Add other agent host layouts later according to researcher demand. Their packaging must reuse the same CLI contracts and scientific verification; supporting additional hosts does not require duplicating processing logic.

## Interview design tree

The three interview rounds establish the following high-level decisions.

| Root decision | Confirmed answer | Decisions it unlocks |
| --- | --- | --- |
| First-release breadth | All current MATLAB toolbox functionality; no reduced public first release. | Complete feature matrix, reference corpus, imaging backend, release evidence. |
| Meaning of GUI similarity | Preserve controls/grouping, plots, channel and reference selection, EDF loading, annotation review/editing, and task outcomes; allow layout changes. | Framework evaluation, interaction specifications, usability checks. |
| Handling legacy scientific discrepancies | Port and verify original behavior first; separate corrective PRs may follow each verified component, with a changelog. | Versioned comparison expectations and regression evidence. |
| Existing-file compatibility | Preserve all existing interfaces; add CSV and suitable native exports. | MAT/schema audit, adapter and round-trip tests, additional format selection. |
| Users and platforms | Library-first; Windows/macOS/Linux; Python 3.11–3.14; eventual PyPI distribution. | Dependency feasibility, source installation, small test matrix. |
| Tooling | Typed Python, clean pre-commit, Ruff, Black, and a type checker. | Proposed Pyright selection and local check commands. |
| Automation | CLI commands and agent skills both ship in the first release. Begin with EDF/annotation inspection, explicit configuration validation, processing, and export. | Command contracts and skill packaging. |
| Reference strategy | Establish a reproducible MATLAB environment and a small corpus covering every capability, including imaging; support capture from the author's other computer. | Capture bundle, actual resource locations/access, and fixture coverage. |
| Imaging | Replace SPM workflows with ANTsPy; no MATLAB/SPM dependency in released execution. Assess changed imaging algorithms by scientific outcomes and preserved workflows, not identical SPM arrays. | Geometry contracts, numerical acceptance limits, dependency feasibility, comparison reference. |
| Agent hosts | Codex first, with one authoritative Markdown skill source; add other host layouts later. | First-release skill packaging and walkthrough tests. |

The high-level interview frontier is complete. The remaining questions depend on inventories, reference artifacts, or implementation evaluation and belong to the work packages rather than another general scoping round.

| Later decision or evidence | Resolve within | Prerequisite |
| --- | --- | --- |
| Actual reference computer setup, dataset coverage, and comparison-resource identification | WP1 / WP3 reference capture | Access to the author's reference materials. |
| Exact numerical and imaging acceptance limits, and release sign-off responsibility | WP3 / WP4 | Named fixtures, scientific endpoints, image resolution, and comparison measurements. Set limits before accepting the port. |
| GUI framework and detailed interaction specification | WP2 | Full legacy workflow inventory and a small prototype. |
| Realistic workload sizes, memory, and performance requirements | WP3 / WP4 | Representative recordings and imaging cases; measure MATLAB and Python on documented hardware. |
| MAT/deformation compatibility, annotation persistence details, and additional export schemas | WP3 / WP5 | File/schema audit and representative saved sessions. |
| Final dependency versions and installation matrix, especially ANTsPy/Python 3.14 | WP1 / WP3b / WP4 | Dependency installation/build and smoke-test results. |
| Exact command names, configuration schema, and Codex skill packaging | WP5 / WP6 | Stable library operations and the confirmed inspect/validate/process/export workflow. |

Reopen a high-level decision only if new evidence conflicts with an agreed requirement. Record the conflict and a concrete proposal rather than silently reducing scope or weakening acceptance tests.

## Decision record

- Confirmed: complete MATLAB functionality in the first release; functional GUI parity with flexible appearance; port then fix in separate PRs per verified component; ANTsPy replaces SPM with outcome-based imaging acceptance and no MATLAB runtime requirement; reference capture can run on the author's other computer; all existing file interfaces plus additive exports; typed Python 3.11–3.14 on Windows/macOS/Linux; library-first distribution; Ruff/Black/pre-commit; CLI and Codex skills ship in the first release with an inspect/validate/process/export workflow and one authoritative skill source.
- Proposed: work-package sequence, shared API architecture, Pyright, uv developer setup, Typer CLI, initial command groups, optional dependency extras, minimal CI matrix, and comparison strategy.
- Work-package inputs still required: actual reference environment/data access, the cited SPM12/ANTsPy comparison, detailed dependency/version support (especially ANTsPy on Python 3.14), fixture-specific numerical limits, detailed interface choices, and final acceptance responsibility.

Use this document as the high-level planning baseline. Next, elaborate WP1's complete feature/file inventory and WP3's portable reference-capture specification. Implementation and scientific acceptance remain separate from recording this roadmap.


### Template decision: symmetric ICBM152 2009a

The user-selected `mni_icbm152_nlin_sym_09a_nifti.zip` replaces ext55 as the
preferred template. It supplies GM/WM/CSF maps. A lightweight regression freezes
all ten original images' decoded nonzero voxel counts, grids and content counts
above 1e-6, with probability range/sum/brain-coverage checks. See
[template implementation](docs/port/icbm152_2009a.md). This does not change the
six-class normalization contract or establish SPM acceptance; the additional
whole-head classes remain separate inputs.

### Follow-up: repository assets and three-class production direction

The requested five unchanged 2009a T1/T2/GM/WM/CSF NIfTIs are versioned under
`MNI atlases` with Git LFS, provenance and the original licence. The plan is to use
GM/WM/CSF for production CCEP tissue calculations, with explicit brain-mask
handling and SPM outcome validation. Six-class support is an existing candidate,
not an inherent downstream requirement. The three-class recipe is not implemented
yet. See the [current checked-off roadmap](docs/port/roadmap-checklist.md); this
clarification supersedes the earlier blanket missing-six-prior blocker.
