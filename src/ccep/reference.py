"""Validate portable MATLAB bundles and compare numerical artifacts explicitly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ccep.models import FloatArray

REQUIRED_KERNELS = frozenset(
    {
        "CCEPSimilarityDistanceMetricsRMSOnly",
        "StimPulseFinder",
        "CCEPStimFreqDataTimeAllocation",
        "CCEPFilterFunction",
        "CCEPBaselineTimeGrabber",
        "ranksum",
    }
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Tolerance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    absolute: float = Field(ge=0, allow_inf_nan=False)
    relative: float = Field(ge=0, allow_inf_nan=False)
    unit: str
    rationale: str = Field(min_length=1)


class ComparisonTolerances(BaseModel):
    model_config = ConfigDict(extra="forbid")
    arrays: dict[str, Tolerance]


def compare_arrays(
    actual: FloatArray, expected: FloatArray, tolerance: Tolerance
) -> dict[str, Any]:
    if actual.shape != expected.shape:
        return dict(
            passed=False,
            reason="shape",
            actual_shape=list(actual.shape),
            expected_shape=list(expected.shape),
        )
    with np.errstate(invalid="ignore", over="ignore"):
        equal = np.isclose(
            actual,
            expected,
            atol=tolerance.absolute,
            rtol=tolerance.relative,
            equal_nan=True,
        )
        finite = np.isfinite(actual) & np.isfinite(expected)
        errors = np.abs(actual[finite] - expected[finite])
    failures = np.argwhere(~equal)
    return dict(
        passed=bool(equal.all()),
        mismatches=int((~equal).sum()),
        maximum_absolute_error=float(errors.max()) if errors.size else None,
        first_mismatch=failures[0].tolist() if failures.size else None,
        tolerance=tolerance.model_dump(),
    )


def validate_bundle(
    directory: Path, *, source_root: Path | None = None
) -> dict[str, Any]:
    root = directory.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    if (
        manifest.get("schema_version") != 1
        or manifest.get("kind") != "matlab-reference"
    ):
        raise ValueError("Unsupported reference bundle schema")
    stages = manifest.get("stages", [])
    if not isinstance(stages, list):
        raise ValueError("Bundle stages must be a list")
    ids = [stage["case_id"] for stage in stages]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate reference cases")
    problems = []
    for field in (
        "matlab_version",
        "computer",
        "dependencies",
        "expected_revision",
        "rng_before",
        "rng_after",
        "sources",
    ):
        if not manifest.get(field):
            problems.append(f"Missing capture provenance: {field}")
    for stage in stages:
        if stage.get("status") != "success":
            problems.append(
                f"{stage['case_id']}: {stage.get('error', 'capture failed')}"
            )
            continue
        relative = Path(stage["path"])
        artifact = (root / relative).resolve()
        if (
            relative.is_absolute()
            or not artifact.is_relative_to(root)
            or artifact == root
        ):
            raise ValueError("Reference artifact escapes bundle directory")
        if not artifact.is_file() or sha256(artifact) != stage["sha256"]:
            raise ValueError(
                f"Reference artifact missing or checksum mismatch: {relative}"
            )
    missing = sorted(REQUIRED_KERNELS - set(ids))
    if source_root:
        for source in manifest.get("sources", []):
            artifact = (source_root / source["path"]).resolve()
            if (
                not artifact.is_relative_to(source_root.resolve())
                or not artifact.is_file()
            ):
                raise ValueError("Reference source path is invalid")
            if sha256(artifact) != source["sha256"]:
                raise ValueError(f"Reference source changed: {source['path']}")
    return dict(
        complete=not missing and not problems,
        missing_cases=missing,
        failed_cases=problems,
        source_hashes_checked=source_root is not None and bool(manifest.get("sources")),
        matlab_version=manifest.get("matlab_version"),
        stages=len(stages),
    )
