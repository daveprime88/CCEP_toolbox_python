"""CCEPFilterFunction, StimPulseFinder and CCEPProcessRMSFile calculations.

Copyright 2020 QIMR Berghofer Medical Research Institute; GPL-3.0-or-later.
Source-derived behavior, including known quirks, pending captured MATLAB parity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import firwin, lfilter

from ccep.models import FloatArray


def matlab_round(value: float) -> int:
    if not np.isfinite(value):
        raise ValueError("Cannot round a nonfinite sample position")
    return int(np.copysign(np.floor(abs(value) + 0.5), value))


def integer_sample(value: float) -> int:
    """Reject fractional MATLAB subscripts rather than silently round them."""
    rounded = round(value)
    if not np.isclose(value, rounded, atol=1e-9, rtol=0):
        raise ValueError(f"Legacy expression produces fractional sample index: {value}")
    return rounded


def legacy_trigger_samples(data: FloatArray) -> NDArray[np.int64]:
    """Zero-based pulse offsets. Preserve >400000, ten samples and edge errors."""
    if data.ndim != 1 or data.size < 2:
        raise ValueError("StimPulseFinder requires at least two samples")
    position, pulses = 1, []
    while position < data.size - 1:
        if data[position] - data[position - 1] > 400000:
            pulses.append(position)
            position += 10
            if position >= data.size:
                raise ValueError(
                    "Legacy StimPulseFinder reads beyond the final sample after a trigger"
                )
        else:
            position += 1
    return np.asarray(pulses, dtype=np.int64)


def legacy_filter_coefficients(
    sampling_hz: float,
    highpass_hz: float = 1,
    lowpass_hz: float | None = None,
    notch_hz: tuple[float, float] = (48, 52),
) -> tuple[FloatArray, FloatArray]:
    """501-tap Hamming FIR. Preserve legacy double normalization of the notch.

    SciPy firwin is a candidate replacement for MATLAB fir1; capture coefficients
    before setting parity tolerances. Recorded MATLAB coefficients can be replayed
    through apply_legacy_filter independently of this design step.
    """
    nyquist = sampling_hz / 2
    lowpass_hz = 0.3 * sampling_hz if lowpass_hz is None else lowpass_hz
    if not 0 < highpass_hz < lowpass_hz < nyquist:
        raise ValueError("Require 0 < highpass < lowpass < Nyquist")
    band = firwin(501, [highpass_hz, lowpass_hz], pass_zero=False, fs=sampling_hz)
    notch = firwin(501, np.asarray(notch_hz) / nyquist, pass_zero=True, fs=sampling_hz)
    return np.asarray(band), np.asarray(notch)


def apply_legacy_filter(
    data: FloatArray, coefficients: tuple[FloatArray, ...]
) -> FloatArray:
    """Causal FIR with delay shift and untouched trailing samples, as in MATLAB."""
    if data.ndim != 1:
        raise ValueError("Filter expects one channel")
    result = np.array(data, dtype=np.float64, copy=True)
    for taps in coefficients:
        delay = (len(taps) - 1) // 2
        if len(taps) % 2 != 1 or delay < 1:
            raise ValueError(
                "Legacy delay handling requires odd-length symmetric FIR taps"
            )
        filtered = lfilter(taps, [1.0], result)
        if result.size > delay:
            result[:-delay] = filtered[delay:]
    return result


def frequency_window(frequency_hz: float) -> tuple[float, float, float]:
    """CCEPStimFreqDataTimeAllocation: duration, post-stim offset, base offset (s)."""
    if not np.isfinite(frequency_hz) or frequency_hz <= 0:
        raise ValueError("Stimulation frequency must be positive and finite")
    duration = (
        0.1
        if matlab_round(frequency_hz * 10) / 10 <= 5
        else 0.03 if frequency_hz < 40 else 0.008
    )
    return duration, 0.010, 0.005


@dataclass(frozen=True)
class Epochs:
    response: FloatArray  # pulse, sample
    baseline: FloatArray
    plot: FloatArray
    plot_offsets: NDArray[np.int64]
    source_indexes: NDArray[np.int64]


def epochs(
    data: FloatArray,
    pulse_samples: list[int],
    sampling_hz: float,
    frequency_hz: float,
    *,
    first_pulse_shift: bool = True,
) -> Epochs:
    """Inclusive windows and first-pulse baseline stitching from CCEPProcessRMSFile."""
    if data.ndim != 1 or not pulse_samples or sampling_hz <= 0:
        raise ValueError("Require a channel, pulses and positive sampling frequency")
    duration, stim, base = frequency_window(frequency_hz)
    response_start = matlab_round(stim * sampling_hz)
    response_end = integer_sample((duration + stim) * sampling_hz)
    plot_start = -matlab_round((duration + base) * sampling_hz)
    responses, baselines, plots, indexes = [], [], [], []

    def window(start: int, stop: int) -> NDArray[np.int64]:
        if start < 0 or stop >= data.size or stop < start:
            raise ValueError(
                f"Legacy epoch [{start}, {stop}] outside {data.size} samples"
            )
        return np.arange(start, stop + 1, dtype=np.int64)

    for index, pulse in enumerate(pulse_samples):
        if not isinstance(pulse, (int, np.integer)):
            raise ValueError("Pulse sample positions must be integers")
        shift = 2 if index == 0 and first_pulse_shift else 0
        response = window(pulse + response_start, pulse + response_end)
        baseline = window(
            pulse - matlab_round((shift + duration + base) * sampling_hz),
            pulse - integer_sample((shift + base) * sampling_hz),
        )
        if shift:
            plot = np.concatenate(
                (
                    window(
                        pulse - matlab_round((shift + duration + base) * sampling_hz),
                        pulse - matlab_round(shift * sampling_hz),
                    ),
                    window(pulse + 1, pulse + response_end),
                )
            )
        else:
            plot = window(pulse + plot_start, pulse + response_end)
        responses.append(data[response])
        baselines.append(data[baseline])
        plots.append(data[plot])
        indexes.append(plot)
    return Epochs(
        np.stack(responses),
        np.stack(baselines),
        np.stack(plots),
        np.arange(plot_start, response_end + 1, dtype=np.int64),
        np.stack(indexes),
    )


def rms_ratios(
    response: FloatArray, baseline: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """CCEPSimilarityDistanceMetricsRMSOnly; invalid rows become 0/0 → NaN."""
    if response.ndim != 2 or response.shape != baseline.shape or response.shape[1] == 0:
        raise ValueError(
            "Response/baseline must have identical nonempty (pulse, sample) shape"
        )
    response, baseline = response.copy(), baseline.copy()
    invalid = ~np.isfinite(response).all(axis=1) | ~np.isfinite(baseline).all(axis=1)
    response[invalid] = 0
    baseline[invalid] = 0
    with np.errstate(divide="ignore", invalid="ignore"):
        rms = np.sqrt(np.mean(response**2, axis=1)) / np.sqrt(
            np.mean(baseline**2, axis=1)
        )
        ddof = 1 if response.shape[1] > 1 else 0
        std = np.std(response, axis=1, ddof=ddof) / np.std(baseline, axis=1, ddof=ddof)
    return rms, std
