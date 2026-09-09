import numpy as np
import pytest

from ccep.analysis import FilterSettings, PulseTrain, RunConfig, process, resolve_config
from ccep.science.scoring import ScoringSettings, SiteMetadata, score_train


def test_eligibility_boundaries_and_reference_specific_rules():
    sites = [
        SiteMetadata(
            anatomical=s, contact_anatomy=("OUT" if i == 2 else "Left A", "Left B")
        )
        for i, s in enumerate(
            ["Left A", "Left B", "Left C", "Right WM", "Right lesion", "Left D"]
        )
    ]
    kwargs = dict(
        actual=[np.arange(6.0) + i for i in range(6)],
        baseline=[np.arange(20.0) for _ in sites],
        sites=sites,
        distances_mm=[11, 10, 11, 11, 11, 11],
        stimulation_anatomy="Left A",
    )
    uni = score_train(**kwargs, reference="unipolar")
    bi = score_train(**kwargs, reference="bipolar")
    np.testing.assert_array_equal(uni.arrays["valid"], [1, 0, 1, 0, 0, 1])
    np.testing.assert_array_equal(bi.arrays["valid"], [0, 0, 0, 0, 0, 1])
    assert bi.reasons[0] == ["same_stimulation_anatomy"]
    assert bi.reasons[2] == ["outside_brain"]
    assert bi.arrays["rms_mean_rank"][-1] == 1
    kwargs["actual"] = [np.ones(5) for _ in sites]
    assert not score_train(**kwargs, reference="unipolar").arrays["valid"].any()


def test_nan_means_and_legacy_median_rank_mean_count_quirk():
    arrays = [
        np.ones(6),
        np.array([-np.inf, 2, 2, 2, 2, np.inf]),
        np.full(6, 3.0),
        np.array([np.nan, 4, 4, 4, 4, 4]),
    ]
    result = score_train(
        arrays,
        [np.ones(20)] * 4,
        [SiteMetadata(anatomical="Left A")] * 4,
        [20] * 4,
        reference="unipolar",
        stimulation_anatomy="Left B",
    )
    np.testing.assert_array_equal(result.arrays["valid"], np.ones(4))
    np.testing.assert_allclose(
        result.arrays["rms_mean"], [1, np.nan, 3, np.nan], equal_nan=True
    )
    # Median has 3 valid values but source assigns only 2 ranks, dividing by mean count 2.
    np.testing.assert_allclose(
        result.arrays["rms_median_rank"], [np.nan, 1, 1.5, np.nan], equal_nan=True
    )
    assert result.arrays["rms_median_qv"][2] == 4


def test_scoring_integrates_with_explicit_config(edf_file):
    config = RunConfig(
        recording=edf_file,
        reference="unipolar",
        channels=["A1", "A2"],
        trains=[
            PulseTrain(
                name="T", frequency_hz=0.5, pulse_samples=list(range(3000, 6000, 500))
            )
        ],
        filtering=FilterSettings(enabled=False),
        baseline_windows=[(6000, 6200)] * 20,
        scoring=ScoringSettings(
            sites={
                "A1": SiteMetadata(anatomical="Left A"),
                "A2": SiteMetadata(anatomical="OUT"),
            },
            stimulation_anatomy={"T": "Left B"},
            distances_mm={"T": {"A1": 20, "A2": 20}},
        ),
    )
    result = process(config)
    np.testing.assert_array_equal(result.arrays["t0_score_valid"], [1, 0])
    assert result.metadata["eligibility"]["T"]["A2"] == ["outside_brain"]
    with pytest.raises(ValueError, match="baseline windows"):
        resolve_config(config.model_copy(update={"baseline_windows": []}))


def test_rank_display_averages_trains_not_pooled_pulses():
    from ccep.science.scoring import aggregate_rankings

    metrics = (
        "zscore",
        "rms_mean_rank",
        "rms_median_rank",
        "rms_mean_qv",
        "rms_median_qv",
    )
    result = aggregate_rankings(
        [
            {m: np.array([1.0, 0.2, np.nan]) for m in metrics},
            {m: np.array([0.4, np.nan, np.nan]) for m in metrics},
        ]
    )
    np.testing.assert_allclose(
        result["rms_mean_rank"], [0.7, 0.2, np.nan], equal_nan=True
    )
