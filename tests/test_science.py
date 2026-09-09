import numpy as np
import pytest

from ccep.models import Annotation
from ccep.science.baseline import legacy_baseline_mask, select_baselines
from ccep.science.ranking import legacy_ranks, legacy_ranksum_z
from ccep.science.safety import stimulation_estimate
from ccep.science.signal import (
    apply_legacy_filter,
    epochs,
    frequency_window,
    legacy_filter_coefficients,
    legacy_trigger_samples,
    matlab_round,
    rms_ratios,
)


def test_metric_ratios_and_nonfinite_rows():
    response = np.array([[3.0, 4.0], [0, 0], [np.inf, 1], [2, 2]])
    baseline = np.array([[1.5, 2.0], [0, 0], [1, 1], [1, 1]])
    rms, std = rms_ratios(response, baseline)
    np.testing.assert_allclose(rms, [2, np.nan, np.nan, 2], equal_nan=True)
    np.testing.assert_allclose(std, [2, np.nan, np.nan, np.nan], equal_nan=True)


def test_epoch_inclusive_endpoints_and_first_pulse_stitch():
    data = np.arange(10000, dtype=float)
    result = epochs(data, [3000, 5000], 1000, 0.5)
    np.testing.assert_array_equal(result.response[0], np.arange(3010, 3111))
    np.testing.assert_array_equal(result.baseline[0], np.arange(895, 996))
    np.testing.assert_array_equal(result.baseline[1], np.arange(4895, 4996))
    np.testing.assert_array_equal(result.source_indexes[0], np.r_[895:1001, 3001:3111])
    assert result.plot.shape == (2, 216)
    assert result.plot_offsets[0] == -105 and result.plot_offsets[-1] == 110
    with pytest.raises(ValueError, match="outside"):
        epochs(data, [50], 1000, 0.5)
    with pytest.raises(ValueError, match="fractional"):
        epochs(data, [3000], 512, 0.5)


@pytest.mark.parametrize(
    "frequency,duration",
    [(0.5, 0.1), (5.04, 0.1), (5.06, 0.03), (39, 0.03), (40, 0.008)],
)
def test_frequency_branches(frequency, duration):
    assert frequency_window(frequency) == (duration, 0.01, 0.005)
    assert matlab_round(-0.5) == -1


def test_filter_tail_is_retained_not_zero_padded():
    data = np.arange(8, dtype=float)
    # Three taps with unit delay; expected shifted convolution is independently known.
    filtered = apply_legacy_filter(data, (np.array([0.25, 0.5, 0.25]),))
    np.testing.assert_allclose(filtered, [0.25, 1, 2, 3, 4, 5, 6, 7])
    band, notch = legacy_filter_coefficients(1000)
    assert band.shape == notch.shape == (501,)
    np.testing.assert_allclose(band, band[::-1], atol=1e-15)


def test_trigger_threshold_refractory_and_legacy_end_error():
    data = np.zeros(50)
    data[3:5] = 400001
    data[8:10] = 900000
    data[20:25] = 400000  # equality is not enough
    data[30:35] = 500000
    np.testing.assert_array_equal(legacy_trigger_samples(data), [3, 30])
    data[47:] = 500000
    with pytest.raises(ValueError, match="beyond"):
        legacy_trigger_samples(data)


def test_rank_ties_nan_and_exact_z():
    ranks, quartiles = legacy_ranks(np.array([4.0, 4.0, 1.0, np.nan]))
    np.testing.assert_allclose(ranks, [1, 2 / 3, 1 / 3, np.nan], equal_nan=True)
    np.testing.assert_allclose(quartiles, [4, 3, 2, np.nan], equal_nan=True)
    assert np.isnan(legacy_ranksum_z(np.arange(6.0), np.arange(6.0)))
    assert legacy_ranksum_z(np.arange(10.0), np.arange(10.0)) == 0
    z = legacy_ranksum_z(np.arange(10.0) + 20, np.arange(10.0))
    assert z == pytest.approx((100 - 50 - 0.5) / np.sqrt(100 * 21 / 12))
    assert legacy_ranksum_z(np.arange(10.0), np.arange(10.0) + 20) == pytest.approx(-z)


def test_baseline_exclusion_and_replay_windows():
    mask = legacy_baseline_mask(
        30000, 1000, [Annotation(sample=15000, text="mark")], [(20000, 21000)]
    )
    assert mask[13999] and not mask[14000] and not mask[16000] and mask[16001]
    windows = select_baselines(mask, 1000, 8, 200, rng=np.random.default_rng(42))
    assert windows.shape == (8, 2)
    assert all(mask[a : b + 1].all() for a, b in windows)
    assert np.all(windows[:, 1] - windows[:, 0] == 200)


def test_historical_charge_geometry():
    estimate = stimulation_estimate("depth", 1, 2, 3, 0.5)
    assert estimate.area_cm2 == pytest.approx(np.pi * 0.02)
    assert estimate.charge_microcoulomb == 1.5
    assert estimate.charge_density_microcoulomb_cm2 == pytest.approx(
        1.5 / (np.pi * 0.02)
    )
