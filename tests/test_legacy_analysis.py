import numpy as np
import pytest
from scipy.io import savemat

from ccep.analysis import AnalysisResult
from ccep.io.legacy_analysis import compare_analysis, inspect_analysis
from ccep.reference import ComparisonTolerances, Tolerance


def test_mat_comparison_matches_by_samples_and_detects_metric_difference(tmp_path):
    path = tmp_path / "RMS.mat"
    savemat(
        path,
        dict(
            DataStruct=dict(
                Info=dict(Name="Synthetic", SamplingFreq=1000), Uni=dict(Label="A1")
            ),
            StimAnnot=dict(
                Label="A2-A3",
                Frequency=0.5,
                PulseTimes=np.array([[3001, 5001]]),
                PlotERPIndexes=np.array([[-1, 0, 1]]),
                ERPDataInds=np.array([[3000, 3001, 3002], [5000, 5001, 5002]]),
                Uni=dict(
                    Label="A1",
                    RMS=np.array([[2.0], [3.0]], dtype=np.float32),
                    StDev=np.array([[4.0], [5.0]], dtype=np.float32),
                ),
            ),
            Baseline=dict(Label="Baseline"),
        ),
    )
    summary = inspect_analysis(path)
    assert summary["patient"] == "Synthetic" and summary["trains"][0][
        "pulse_samples"
    ] == [3000, 5000]
    result = AnalysisResult(
        dict(
            channels=[dict(label="A1", sampling_hz=1000)],
            trains=[
                dict(
                    name="New display name",
                    frequency_hz=0.5,
                    pulse_samples=[3000, 5000],
                )
            ],
            config=dict(reference="unipolar"),
        ),
        dict(
            t0_offsets=np.array([-1.0, 0, 1]),
            t0_c0_source_indexes=np.array([[2999.0, 3000, 3001], [4999, 5000, 5001]]),
            t0_c0_rms=np.array([2.0, 3.0]),
            t0_c0_std=np.array([4.0, 5.0]),
        ),
    )
    limits = ComparisonTolerances(
        arrays={
            name: Tolerance(
                absolute=0,
                relative=0,
                unit="dimensionless",
                rationale="Independent synthetic oracle",
            )
            for name in ("t0_c0_rms", "t0_c0_std")
        }
    )
    assert compare_analysis(result, path, limits)["passed"]
    result.arrays["t0_c0_rms"][1] += 0.1
    report = compare_analysis(result, path, limits)
    assert not report["passed"] and report["comparisons"]["t0_c0_rms"][
        "first_mismatch"
    ] == [1]
    result.metadata["trains"][0]["pulse_samples"][0] += 1
    with pytest.raises(ValueError, match="unique"):
        compare_analysis(result, path, limits)
