"""Source-derived CCEPBaselineTimeGrabber mask and explicit window replay."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ccep.models import Annotation
from ccep.science.signal import integer_sample


def legacy_baseline_mask(
    samples: int,
    sampling_hz: float,
    annotations: list[Annotation],
    train_windows: list[tuple[int, int]],
) -> NDArray[np.bool_]:
    mask = np.ones(samples, dtype=bool)

    def exclude(start: int, stop: int) -> None:
        if start < 0 or stop >= samples:
            raise ValueError("Legacy exclusion window exceeds recording bounds")
        mask[start : stop + 1] = False

    for start, stop in train_windows:
        exclude(start, stop)
    ten_seconds = integer_sample(10 * sampling_hz)
    one_second = integer_sample(sampling_hz)
    for annotation in annotations:
        time = annotation.sample  # Convert comparisons from one-based MATLAB.
        if time + 1 <= ten_seconds:
            exclude(0, time + ten_seconds)
        elif time + 1 >= samples - ten_seconds:
            exclude(time - ten_seconds, samples - 1)
        else:
            exclude(time - one_second, time + one_second)
    # The original seizure pass only indexes DataMask; it does not assign false.
    # Preserve that no-op, including its possible indexing failure.
    for annotation in annotations:
        if any(
            word in annotation.text.upper()
            for word in ("ONSET", "EEG", "SZ", "SEIZURE", "END")
        ):
            margin = integer_sample(600 * sampling_hz)
            time = annotation.sample
            if time + 1 <= margin and time + margin >= samples:
                raise ValueError("Legacy seizure-mask read exceeds recording bounds")
            if time + 1 > margin and time + 1 >= samples - margin and time - margin < 0:
                raise ValueError("Legacy seizure-mask read precedes recording")
    return mask


def select_baselines(
    mask: NDArray[np.bool_],
    sampling_hz: float,
    count: int,
    window_samples: int,
    *,
    rng: np.random.Generator,
) -> NDArray[np.int64]:
    """Legacy rejection rules with NumPy RNG; replay saved windows for parity.

    Returned endpoints are inclusive and zero-based. RNG streams are not claimed
    to match MATLAB. The returned actual windows must be persisted in provenance.
    """
    if count < 1 or window_samples < 1 or mask.ndim != 1:
        raise ValueError("Invalid baseline selection dimensions")
    lower = integer_sample(5 * sampling_hz) - 1
    upper = len(mask) - integer_sample(6 * sampling_hz) - 1
    if upper < lower or lower < 0 or upper + window_samples >= len(mask):
        raise ValueError("Recording is too short for legacy baseline sampling")
    windows = []
    rejections = 1
    while len(windows) < count:
        start = int(rng.integers(lower, upper + 1))
        if mask[start : start + window_samples + 1].all():
            windows.append((start, start + window_samples))
            rejections = 1
        else:
            rejections += 1
        if rejections >= 100000:
            raise ValueError("Too many legacy baseline rejections")
    return np.asarray(windows, dtype=np.int64)
