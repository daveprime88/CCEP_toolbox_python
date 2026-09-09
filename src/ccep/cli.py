"""Noninteractive CLI with a single JSON envelope on success and failure."""

from __future__ import annotations

import json
import math
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import typer

from ccep.analysis import load_config, load_result, process, resolve_config, save_result
from ccep.imaging.commands import register_commands
from ccep.io.annotations import load_annotations
from ccep.io.edf import EDF
from ccep.io.exports import export_erp_plot, export_table
from ccep.reference import (
    ComparisonTolerances,
    Tolerance,
    compare_arrays,
    sha256,
    validate_bundle,
)

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="CCEP scientific workflows. Development port; MATLAB parity pending.",
)
register_commands(app)
DIAGNOSTICS = {
    "INPUT_NOT_FOUND",
    "OUTPUT_EXISTS",
    "INVALID_INPUT",
    "CLI_USAGE",
    "DEPENDENCY_MISSING",
    "COMPARISON_FAILED",
    "INTERNAL_ERROR",
}


@app.callback()
def options(
    json_output: bool = typer.Option(
        False, "--json", help="Emit one versioned JSON envelope."
    )
) -> None:
    pass


@app.command("inspect")
def inspect_file(path: Path, annotations: Path | None = None) -> dict[str, Any]:
    """Inspect EDF or saved Python result metadata without processing."""
    if path.suffix.lower() == ".edf":
        recording = EDF(path)
        rate = (
            recording.channels[0].samples_per_record / recording.record_seconds
            if recording.channels
            else 1
        )
        data: dict[str, Any] = dict(
            path=str(path.resolve()),
            sha256=sha256(path),
            records=recording.records,
            duration_seconds=recording.records * recording.record_seconds,
            channels=[
                dict(
                    label=s.label,
                    unit=s.unit,
                    sampling_hz=s.samples_per_record / recording.record_seconds,
                    samples=recording.records * s.samples_per_record,
                )
                for s in recording.channels
            ],
            annotations=[a.model_dump() for a in recording.annotations(rate)],
        )
        if annotations:
            edited = load_annotations(annotations)
            data["annotations"] = [a.model_dump() for a in edited.annotations]
            data["pulse_samples"] = edited.pulses
            data["annotation_sha256"] = sha256(annotations)
        return data
    if path.suffix.lower() == ".mat":
        from ccep.io.legacy_analysis import inspect_analysis

        return inspect_analysis(path)
    result = load_result(path)
    return dict(
        path=str(path.resolve()),
        sha256=sha256(path),
        metadata=result.metadata,
        arrays={key: list(value.shape) for key, value in result.arrays.items()},
    )


@app.command()
def validate(config: Path) -> dict[str, Any]:
    """Resolve explicit inputs/defaults and check channels, pulse windows and filters."""
    resolved = resolve_config(load_config(config))
    return dict(
        valid=True,
        effective_config=resolved.model_dump(mode="json"),
        scientific_status="source-derived; MATLAB parity pending",
    )


@app.command("process")
def process_command(config: Path, output: Path) -> dict[str, Any]:
    """Process selected pulse trains and write a new NPZ result artifact."""
    if output.exists():
        raise FileExistsError(output)
    result = process(load_config(config))
    save_result(output, result)
    return dict(
        artifacts=[dict(path=str(output.resolve()), sha256=sha256(output))],
        effective_config=result.metadata["config"],
        scientific_status=result.metadata["scientific_status"],
    )


@app.command("export")
def export_command(result: Path, output: Path) -> dict[str, Any]:
    """Export pulse metrics (CSV/XLSX) or ERP plots (PNG/SVG/PDF)."""
    data = load_result(result)
    if output.suffix.lower() in {".csv", ".xlsx"}:
        export_table(data, output)
    else:
        export_erp_plot(data, output)
    return dict(
        artifacts=[dict(path=str(output.resolve()), sha256=sha256(output))],
        source_sha256=sha256(result),
    )


def _discrete_unit(key: str) -> str | None:
    if key.endswith(("_offsets", "_source_indexes")):
        return "samples"
    if key.endswith(("_score_valid", "_qv")):
        return "dimensionless"
    return None


@app.command()
def compare(actual: Path, expected: Path, tolerance: Path) -> dict[str, Any]:
    """Compare native result arrays and scientific identities with explicit tolerances."""
    a, e = load_result(actual), load_result(expected)
    limits = ComparisonTolerances.model_validate_json(tolerance.read_text())
    differences = {}
    for key in ("channels", "trains"):
        if a.metadata[key] != e.metadata[key]:
            differences[key] = "Scientific identities or selection differ"
    if a.metadata["config"]["reference"] != e.metadata["config"]["reference"]:
        differences["reference"] = "Reference differs"
    for field in ("filtering", "baseline_windows", "scoring"):
        if a.metadata["config"].get(field) != e.metadata["config"].get(field):
            differences[field] = "Scientific processing settings differ"
    if a.metadata.get("inputs") != e.metadata.get("inputs"):
        differences["inputs"] = "Input identities differ"
    missing = sorted(set(a.arrays) ^ set(e.arrays))
    for key in set(a.arrays) & set(e.arrays):
        if _discrete_unit(key) is not None:
            continue
        if key not in limits.arrays:
            raise ValueError(f"Missing array-specific tolerance: {key}")
        match = re.fullmatch(r"t\d+_c(\d+)_erp", key)
        unit = (
            a.metadata["channels"][int(match[1])]["unit"] if match else "dimensionless"
        )
        if limits.arrays[key].unit != unit:
            raise ValueError(f"Tolerance unit for {key} must be {unit!r}")
    reports = {
        key: compare_arrays(
            a.arrays[key],
            e.arrays[key],
            (
                Tolerance(
                    absolute=0,
                    relative=0,
                    unit=_discrete_unit(key) or "dimensionless",
                    rationale="Exact discrete identity",
                )
                if _discrete_unit(key) is not None
                else limits.arrays[key]
            ),
        )
        for key in sorted(set(a.arrays) & set(e.arrays))
    }
    return dict(
        passed=not differences
        and not missing
        and all(r["passed"] for r in reports.values()),
        identity_differences=differences,
        missing_arrays=missing,
        comparisons=reports,
    )


@app.command("compare-mat")
def compare_mat(actual: Path, expected: Path, tolerance: Path) -> dict[str, Any]:
    """Compare saved Python metrics/sample indexes against an original MATLAB RMS MAT."""
    from ccep.io.legacy_analysis import compare_analysis

    return compare_analysis(
        load_result(actual),
        expected,
        ComparisonTolerances.model_validate_json(tolerance.read_text()),
    )


@app.command("reference-check")
def reference_check(bundle: Path, source_root: Path | None = None) -> dict[str, Any]:
    """Verify reference capture cases/checksums; does not certify numerical parity."""
    report = validate_bundle(bundle, source_root=source_root)
    return dict(report, passed=report["complete"])


@app.command("reference-replay")
def reference_replay(bundle: Path, tolerance: Path) -> dict[str, Any]:
    """Replay portable MATLAB kernel inputs with explicit array tolerances."""
    from ccep.reference_replay import replay_kernels

    return replay_kernels(
        bundle, ComparisonTolerances.model_validate_json(tolerance.read_text())
    )


@app.command("annotations")
def annotation_inspect(path: Path) -> dict[str, Any]:
    """Inspect MAT/JSON annotations and pulse sample offsets."""
    data = load_annotations(path)
    return dict(
        sample_origin=0,
        annotations=[a.model_dump() for a in data.annotations],
        automatic_pulses=data.automatic_pulses,
        manual_pulses=data.manual_pulses,
        sha256=sha256(path),
    )


@app.command("skill-path")
def skill_path() -> dict[str, Any]:
    """Locate the authoritative Codex playbook shipped in this installation."""
    location = Path(__file__).parent / "skills" / "ccep-process"
    if not (location / "SKILL.md").is_file():
        raise FileNotFoundError("Packaged CCEP skill is missing")
    return dict(path=str(location.resolve()))


@app.command("install-skill")
def install_skill(destination: Path) -> dict[str, Any]:
    """Copy the packaged playbook into an explicit agent skill directory."""
    import shutil

    source = Path(skill_path()["path"])
    output = destination / source.name
    shutil.copytree(source, output)
    return dict(path=str(output.resolve()), source_sha256=sha256(source / "SKILL.md"))


def _safe_json(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    return value


def run(argv: list[str]) -> int:
    json_mode = "--json" in argv
    command = next((arg for arg in argv if not arg.startswith("-")), "help")
    diagnostics: list[dict[str, str]] = []
    data: dict[str, Any] = {}
    exit_code = 0
    try:
        # Protect stdout even if a library prints progress. Help is ordinary text.
        if "--help" in argv or not argv:
            app(args=argv or ["--help"], standalone_mode=False)
            return 0
        with redirect_stdout(sys.stderr):
            result = app(args=argv, standalone_mode=False)
        data = result or {}
        if data.get("passed") is False:
            exit_code = 3
            diagnostics.append(
                dict(
                    code="COMPARISON_FAILED",
                    message="Comparison or reference completeness check failed",
                )
            )
    except FileNotFoundError as error:
        exit_code = 2
        diagnostics.append(dict(code="INPUT_NOT_FOUND", message=str(error)))
    except FileExistsError as error:
        exit_code = 2
        diagnostics.append(dict(code="OUTPUT_EXISTS", message=str(error)))
    except typer.TyperException as error:
        exit_code = 2
        diagnostics.append(dict(code="CLI_USAGE", message=error.format_message()))
    except (ValueError, OSError, KeyError) as error:
        exit_code = 2
        diagnostics.append(dict(code="INVALID_INPUT", message=str(error)))
    except ImportError as error:
        exit_code = 2
        diagnostics.append(dict(code="DEPENDENCY_MISSING", message=str(error)))
    except Exception as error:
        exit_code = 1
        diagnostics.append(
            dict(code="INTERNAL_ERROR", message=f"{type(error).__name__}: {error}")
        )
    envelope = dict(
        schema_version=1,
        command=command,
        status="success" if exit_code == 0 else "error",
        ok=exit_code == 0,
        exit_code=exit_code,
        diagnostics=diagnostics,
        data=data,
    )
    if json_mode:
        print(json.dumps(_safe_json(envelope), allow_nan=False))
    else:
        print(json.dumps(_safe_json(envelope), indent=2, allow_nan=False))
    return exit_code


def main() -> None:
    raise SystemExit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
