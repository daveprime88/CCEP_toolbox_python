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
ccep --json image-register MRI.nii.gz CT.nii.gz new-registration --transform Rigid --seed 1729
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
