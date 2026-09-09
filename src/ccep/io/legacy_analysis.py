"""Inspect preserved MATLAB RMS analyses and compare shared scientific outputs.

MAT structs remain structured arrays so unrelated metadata and MATLAB types are
not silently converted into cells. Mapping uses saved sample identities, never
filenames or a guessed patient identity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ccep.analysis import AnalysisResult
from ccep.io.legacy import read_mat
from ccep.reference import ComparisonTolerances, Tolerance, compare_arrays, sha256


def records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, np.ndarray) and value.dtype.names:
        return [
            {name: row[name] for name in value.dtype.names}
            for row in value.ravel(order="F")
        ]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, np.ndarray) and value.size == 0:
        return []
    raise ValueError("Expected a MATLAB struct array")


def text(value: Any) -> str:
    array = np.asarray(value)
    if array.dtype.kind not in {"U", "S"}:
        raise ValueError("Expected MATLAB character text")
    return "".join(str(v) for v in array.ravel()).rstrip()


def vector(value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim > 2 or (array.ndim == 2 and min(array.shape) > 1):
        raise ValueError("Expected a MATLAB row or column vector")
    return np.asarray(array, dtype=np.float64).ravel()


def sample_indexes(value: Any) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if (
        not np.isfinite(array).all()
        or (array < 1).any()
        or not np.equal(array, np.floor(array)).all()
    ):
        raise ValueError("MATLAB sample positions must be positive integers")
    return array - 1


def inspect_analysis(path: Path) -> dict[str, Any]:
    variables = read_mat(path)
    data = records(variables["DataStruct"])
    if len(data) != 1:
        raise ValueError("Expected one DataStruct")
    info = records(data[0]["Info"])[0]
    trains = records(variables["StimAnnot"])
    return dict(
        path=str(path.resolve()),
        sha256=sha256(path),
        patient=text(info["Name"]),
        sampling_hz=float(vector(info["SamplingFreq"])[0]),
        references={
            reference: [text(c["Label"]) for c in records(data[0][reference])]
            for reference in ("Uni", "Bi")
            if reference in data[0]
        },
        trains=[
            dict(
                index_zero_based=i,
                label=text(t["Label"]),
                frequency_hz=float(vector(t["Frequency"])[0]),
                pulse_samples=sample_indexes(vector(t["PulseTimes"])).tolist(),
            )
            for i, t in enumerate(trains)
        ],
        variables=list(variables),
        scientific_status="Legacy artifact; runtime/input provenance must be supplied separately",
    )


def compare_analysis(
    result: AnalysisResult, path: Path, limits: ComparisonTolerances
) -> dict[str, Any]:
    variables = read_mat(path)
    legacy = records(variables["StimAnnot"])
    base = records(variables["Baseline"])
    if len(base) != 1:
        raise ValueError("Expected a single legacy baseline train")
    info = records(records(variables["DataStruct"])[0]["Info"])[0]
    rate = float(vector(info["SamplingFreq"])[0])
    reference = "Uni" if result.metadata["config"]["reference"] == "unipolar" else "Bi"
    reports: dict[str, Any] = {}
    identities: list[str] = []
    for channel in result.metadata["channels"]:
        if channel["sampling_hz"] != rate:
            identities.append(f"Sampling frequency differs for {channel['label']}")

    def compare(name: str, expected: Any, *, discrete: bool = False) -> None:
        if name not in result.arrays:
            identities.append(f"Python result lacks {name}")
            return
        tolerance = (
            Tolerance(
                absolute=0,
                relative=0,
                unit="samples",
                rationale="Exact MATLAB sample identity",
            )
            if discrete
            else limits.arrays.get(name)
        )
        if tolerance is None:
            raise ValueError(f"Missing array-specific tolerance: {name}")
        if not discrete and tolerance.unit != "dimensionless":
            raise ValueError(f"Tolerance unit for {name} must be dimensionless")
        reports[name] = compare_arrays(
            result.arrays[name], np.asarray(expected, dtype=np.float64), tolerance
        )

    used: set[int] = set()
    for ti, train in enumerate(result.metadata["trains"]):
        matches = [
            i
            for i, row in enumerate(legacy)
            if np.array_equal(
                sample_indexes(vector(row["PulseTimes"])), train["pulse_samples"]
            )
            and float(vector(row["Frequency"])[0]) == train["frequency_hz"]
        ]
        if len(matches) != 1 or matches[0] in used:
            raise ValueError(
                "Legacy train mapping must be unique by saved pulse samples and frequency"
            )
        index = matches[0]
        used.add(index)
        original = legacy[index]
        compare(f"t{ti}_offsets", vector(original["PlotERPIndexes"]), discrete=True)
        channels = records(original[reference])
        for ci, channel in enumerate(result.metadata["channels"]):
            matched = [
                row for row in channels if text(row["Label"]) == channel["label"]
            ]
            if len(matched) != 1:
                raise ValueError(
                    f"Legacy channel mapping is ambiguous or missing: {channel['label']}"
                )
            for python_name, matlab_name in (("rms", "RMS"), ("std", "StDev")):
                compare(f"t{ti}_c{ci}_{python_name}", vector(matched[0][matlab_name]))
            compare(
                f"t{ti}_c{ci}_source_indexes",
                sample_indexes(original["ERPDataInds"]),
                discrete=True,
            )
    for ci, channel in enumerate(result.metadata["channels"]):
        if f"baseline_c{ci}_rms" not in result.arrays:
            continue
        matched = [
            row
            for row in records(base[0][reference])
            if text(row["Label"]) == channel["label"]
        ]
        if len(matched) != 1:
            raise ValueError("Missing or duplicate baseline channel")
        for python_name, matlab_name in (("rms", "RMS"), ("std", "StDev")):
            compare(f"baseline_c{ci}_{python_name}", vector(matched[0][matlab_name]))
        windows = sample_indexes(base[0]["BaselineTimes"])
        if not np.array_equal(windows, result.metadata["config"]["baseline_windows"]):
            identities.append("Baseline window identities differ")
    return dict(
        passed=not identities
        and bool(reports)
        and all(r["passed"] for r in reports.values()),
        reference_sha256=sha256(path),
        identity_differences=identities,
        comparisons=reports,
        matched_trains_zero_based=sorted(used),
        scope="Selected-reference metrics, sample indexes and optional baselines",
        limitations=[
            "ERP amplitudes, scoring metadata, filtering settings and original recording hashes require separate capture",
            "Passing this comparison does not certify full-file or full-toolbox parity",
        ],
    )
