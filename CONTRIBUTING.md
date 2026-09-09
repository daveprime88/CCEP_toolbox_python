# Contributing

Use Python 3.11-compatible syntax and explicit types. Install with
`uv sync --python 3.11 --extra gui --extra imaging --group gui-tests`, then run
`uv run --no-sync python tools/check.py`.
The check runner executes Ruff, Black (check), Pyright and pytest without shell
syntax, so it also works on Windows. `uv run --no-sync pre-commit install` installs the
fast lint/format hooks. Format with `uv run black .` and sort imports with
`uv run ruff check --fix .`.

Scientific code belongs in the library; the GUI and CLI call that same code.
Preserve physical units, coordinate frames, channel identity, array axes and
sample conventions explicitly. A passing synthetic test is not MATLAB parity.
Keep reference artifacts immutable, record their origin, and label evidence
as source-derived, analytically checked, MATLAB-compared or author-accepted.

For each port commit identify the MATLAB entry point, local tests and remaining
reference cases. Characterize apparent legacy bugs first. Submit any correction
as a separate change after verification, with a changelog and before/after tests.
Do not relax numerical tolerances to make an unexplained mismatch pass.

Never put participant recordings or identifying metadata in public test fixtures.
Small generated signals and images are appropriate for routine CI. Reference
capture on the data-holding computer is described under `reference/` when available.

No publishing credentials or automated PyPI upload are configured yet. Building
packages and running the declared matrix precede any first-release claim.
