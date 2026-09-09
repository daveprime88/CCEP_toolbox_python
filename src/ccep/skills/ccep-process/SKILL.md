---
name: ccep-process
description: Process SEEG recordings or run CCEP image registration, normalization and contact transforms through the CCEP Toolbox CLI.
---

# Process CCEP recordings

Use the installed `ccep` command, or `python -m ccep.cli` in the project's Python
environment. Read `ccep --help` to discover the installed command interface.
Commands accept `--json` **before** the command and return one schema-versioned
JSON envelope. Check `ok`, `exit_code`, and `diagnostics` on every invocation.

For image registration, normalization, atlas resampling or contact transforms,
read [references/imaging.md](references/imaging.md) and follow that branch.

## Recording workflow

1. Inspect the requested EDF and, when present, its edited annotation file:
   `ccep --json inspect RECORDING --annotations ANNOTATIONS`.
   Record the exact available channel labels, physical units, sampling rates,
   annotation timebase and pulse samples. Completion means the requested inputs
   are readable and their identities are established.
2. Use the researcher's explicit JSON configuration. Paths in that file are
   relative to its directory. Run `ccep --json validate CONFIG`; inspect
   `data.effective_config`. It must express the intended channels, reference,
   filter settings, pulse trains/frequencies and actual baseline windows.
   Ask for missing scientific choices rather than infer them from filenames.
3. Run `ccep --json process CONFIG NEW_RESULT.npz`. Completion requires a success
   envelope and the returned artifact. Retain its SHA-256 and effective config.
4. Run `ccep --json export NEW_RESULT.npz NEW_REPORT.csv` (or `.xlsx`, `.png`,
   `.svg`, `.pdf` as requested). Inspect the result metadata and exported content
   before reporting completion. Report paths, hashes, selections and the
   `scientific_status` returned by processing.

Python sample offsets are zero-based. The current MAT annotation adapter expects
positive one-based sample positions and preserves unknown MAT metadata. Real-file
sample-origin compatibility is still awaiting MATLAB capture. If an annotation
file supplies the pulses, configure `annotation_window` instead of a copied
`pulse_samples` list so subsequent annotation edits feed processing.

The current development pipeline computes source-derived RMS/std ratios and ERPs;
full anatomical eligibility, normalized connectivity reports and MATLAB parity
remain incomplete. Treat the status returned by the CLI as part of the result.
A successful command or synthetic test is not a validated scientific port.

## Recover from diagnostics

- `INPUT_NOT_FOUND`: locate the requested input and correct its explicit path.
- `INVALID_INPUT`: inspect the reported schema, channel, sample-window or format
  problem. Keep scientific parameters under the researcher's control.
- `OUTPUT_EXISTS`: choose a new result name; inspect existing outputs if deciding
  whether the requested run already completed. Commands do not overwrite results.
- `CLI_USAGE`: inspect that installed command's `--help` and correct its arguments.
- `DEPENDENCY_MISSING`: install the relevant documented extra in the selected
  environment when installation is within the user's task scope.
- `COMPARISON_FAILED`: preserve actual and reference artifacts and report the
  mismatch locations. Use an explicit array-specific tolerance JSON with `ccep --json compare`;
  establish tolerance/units/rationale before acceptance.
- `INTERNAL_ERROR`: report the diagnostic and reproducible invocation; preserve
  inputs and any prior successful outputs.

Use the user's existing authorization for the requested processing and exports.
Keep source recordings intact. Additional agent-driven annotation mutation is
outside this first playbook; annotation review/editing is available in the GUI.
