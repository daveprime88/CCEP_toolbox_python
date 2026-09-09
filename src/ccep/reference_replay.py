"""Replay captured kernel inputs; MATLAB artifacts remain an independent oracle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat

from ccep.models import Annotation, FloatArray
from ccep.reference import (
    ComparisonTolerances,
    Tolerance,
    compare_arrays,
    validate_bundle,
)
from ccep.science.baseline import legacy_baseline_mask
from ccep.science.ranking import legacy_ranksum_z
from ccep.science.signal import (
    apply_legacy_filter,
    frequency_window,
    legacy_filter_coefficients,
    legacy_trigger_samples,
    rms_ratios,
)


def replay_kernels(directory: Path, limits: ComparisonTolerances) -> dict[str, Any]:
    integrity = validate_bundle(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    reports: dict[str, Any] = {}
    checks: dict[str, Any] = {}

    def compare(
        name: str,
        actual: FloatArray,
        expected: FloatArray,
        *,
        exact: bool = False,
        unit: str = "dimensionless",
    ) -> None:
        if exact:
            tolerance = Tolerance(
                absolute=0, relative=0, unit=unit, rationale="Exact discrete identity"
            )
        else:
            if name not in limits.arrays:
                raise ValueError(f"Missing array-specific tolerance: {name}")
            tolerance = limits.arrays[name]
            if tolerance.unit != unit:
                raise ValueError(f"Tolerance unit for {name} must be {unit!r}")
        reports[name] = compare_arrays(
            np.asarray(actual), np.asarray(expected), tolerance
        )

    for stage in manifest["stages"]:
        if stage["status"] != "success":
            continue
        values = loadmat(directory / stage["path"], simplify_cells=True)
        case = stage["case_id"]
        if case == "CCEPSimilarityDistanceMetricsRMSOnly":
            rms, std = rms_ratios(
                np.atleast_2d(values["response"]), np.atleast_2d(values["baseline"])
            )
            compare("metrics.rms", rms, np.atleast_1d(values["rms"]))
            compare("metrics.std", std, np.atleast_1d(values["std"]))
        elif case == "StimPulseFinder":
            pulses = legacy_trigger_samples(np.atleast_1d(values["data"]))
            compare(
                "triggers.samples",
                pulses.astype(float),
                np.atleast_1d(values["pulses_one_based"]) - 1,
                exact=True,
                unit="samples",
            )
        elif case == "CCEPStimFreqDataTimeAllocation":
            actual = np.array(
                [
                    frequency_window(float(f))
                    for f in np.atleast_1d(values["frequencies"])
                ]
            )
            compare(
                "epochs.windows",
                actual,
                np.atleast_2d(values["windows"]),
                exact=True,
                unit="seconds",
            )
        elif case == "CCEPFilterFunction":
            data = np.atleast_1d(values["data"])
            band, notch = legacy_filter_coefficients(float(values["sampling_hz"]))
            captured_band, captured_notch = np.atleast_1d(
                values["band_coefficients"]
            ), np.atleast_1d(values["notch_coefficients"])
            compare("filter.band_coefficients", band, captured_band)
            compare("filter.notch_coefficients", notch, captured_notch)
            for reference, filters, captured in [
                ("uni", (band, notch), (captured_band, captured_notch)),
                ("bi", (band,), (captured_band,)),
            ]:
                compare(
                    f"filter.{reference}",
                    apply_legacy_filter(data, filters),
                    np.atleast_1d(values[f"filtered_{reference}"]),
                    unit="synthetic amplitude",
                )
                compare(
                    f"filter.{reference}_captured_coefficients",
                    apply_legacy_filter(data, captured),
                    np.atleast_1d(values[f"filtered_{reference}"]),
                    unit="synthetic amplitude",
                )
        elif case == "ranksum":
            compare(
                "ranksum.z",
                np.asarray(
                    legacy_ranksum_z(
                        np.atleast_1d(values["actual"]),
                        np.atleast_1d(values["baseline"]),
                    )
                ),
                np.asarray(values["z"]),
            )
            checks["ranksum.small_sample_z_absent"] = (
                "zval" not in values["small_stats"]
            )
        elif case == "CCEPBaselineTimeGrabber":
            samples, rate = int(values["samples"]), float(values["sampling_hz"])
            annotation_samples = np.atleast_1d(values["annotation_samples_one_based"])
            texts = np.atleast_1d(values["annotation_text"])
            annotations = [
                Annotation(sample=int(t) - 1, text=str(text))
                for t, text in zip(annotation_samples, texts, strict=True)
            ]
            train_windows = [
                tuple(int(x) - 1 for x in row)
                for row in np.atleast_2d(values["train_windows_one_based"])
            ]
            mask = legacy_baseline_mask(
                samples, rate, annotations, [(row[0], row[1]) for row in train_windows]
            )
            raw = np.atleast_2d(values["windows_one_based"])
            if (
                raw.shape[1] != 2
                or not np.isfinite(raw).all()
                or not np.equal(raw, np.floor(raw)).all()
            ):
                raise ValueError(
                    "Captured baseline windows must be integer endpoint pairs"
                )
            windows = raw.astype(np.int64) - 1
            checks["baseline.captured_window_membership"] = bool(
                all(
                    5 * rate - 1 <= start <= samples - 6 * rate - 1
                    and end < samples
                    and end - start == int(values["window_samples"])
                    and mask[start : end + 1].all()
                    for start, end in windows
                )
            )
        else:
            checks[f"unsupported_case.{case}"] = False
    return dict(
        passed=integrity["complete"]
        and bool(reports)
        and all(r["passed"] for r in reports.values())
        and all(checks.values()),
        capture=integrity,
        comparisons=reports,
        checks=checks,
        limitations=[
            "Kernel coverage only; no full workflow or imaging acceptance",
            "Baseline checks replay captured endpoints; NumPy and MATLAB RNG streams are not equivalent",
        ],
    )
