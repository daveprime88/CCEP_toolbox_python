import json

import numpy as np
import pytest

from ccep.reference import Tolerance, compare_arrays, sha256, validate_bundle


def test_comparison_discrete_nonfinite_and_location():
    tolerance = Tolerance(
        absolute=1e-6, relative=0, unit="uV", rationale="test contract"
    )
    report = compare_arrays(
        np.array([0.0, np.nan, np.inf, 3]),
        np.array([0.0, np.nan, -np.inf, 4]),
        tolerance,
    )
    assert (
        not report["passed"]
        and report["first_mismatch"] == [2]
        and report["mismatches"] == 2
    )
    assert not compare_arrays(np.zeros((2, 1)), np.zeros(2), tolerance)["passed"]


def test_reference_integrity_and_path_escape(tmp_path):
    artifact = tmp_path / "values.mat"
    artifact.write_bytes(b"fixture")
    manifest = dict(
        schema_version=1,
        kind="matlab-reference",
        stages=[
            dict(
                case_id="one",
                status="success",
                path="values.mat",
                sha256=sha256(artifact),
            )
        ],
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    assert not validate_bundle(tmp_path)["complete"]
    artifact.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        validate_bundle(tmp_path)
    manifest["stages"][0]["path"] = "../escape.mat"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="escapes"):
        validate_bundle(tmp_path)


def test_missing_provenance_cannot_certify_capture(tmp_path):
    from ccep.reference import REQUIRED_KERNELS

    artifact = tmp_path / "values.mat"
    artifact.write_bytes(b"fixture")
    manifest = dict(
        schema_version=1,
        kind="matlab-reference",
        stages=[
            dict(
                case_id=name,
                status="success",
                path="values.mat",
                sha256=sha256(artifact),
            )
            for name in REQUIRED_KERNELS
        ],
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    report = validate_bundle(tmp_path, source_root=tmp_path)
    assert not report["complete"] and not report["source_hashes_checked"]


def test_replay_uses_captured_expected_outputs(tmp_path):
    from scipy.io import savemat

    from ccep.reference import ComparisonTolerances
    from ccep.reference_replay import replay_kernels

    artifact = tmp_path / "metrics.mat"
    savemat(
        artifact,
        dict(
            response=np.array([[3.0, 4.0]]),
            baseline=np.array([[1.5, 2.0]]),
            rms=9.0,
            std=2.0,
        ),
    )
    manifest = dict(
        schema_version=1,
        kind="matlab-reference",
        stages=[
            dict(
                case_id="CCEPSimilarityDistanceMetricsRMSOnly",
                status="success",
                path="metrics.mat",
                sha256=sha256(artifact),
            )
        ],
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    limits = ComparisonTolerances(
        arrays={
            name: Tolerance(
                absolute=0,
                relative=0,
                unit="dimensionless",
                rationale="Independent analytic fixture",
            )
            for name in ("metrics.rms", "metrics.std")
        }
    )
    report = replay_kernels(tmp_path, limits)
    assert not report["passed"]
    assert not report["comparisons"]["metrics.rms"]["passed"]
    assert report["comparisons"]["metrics.std"]["passed"]
