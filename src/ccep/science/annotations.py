"""Source-derived stimulation label/start-stop parsing; retain legacy corner cases."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ccep.models import Annotation
from ccep.science.signal import matlab_round


@dataclass(frozen=True)
class StimulationTrain:
    label: str
    level_ma: float
    start_sample: int
    end_sample: int | None
    pulse_samples: tuple[int, ...]
    frequency_hz: float | None


def stimulation_label(label: str) -> str:
    """StimLabelReorg: lower numeric contact token first."""
    pieces = label.split("-", 1)
    if len(pieces) != 2:
        raise ValueError(
            "Stimulation label requires two contacts separated by a hyphen"
        )
    numbers = ["".join(c for c in part if c.isdigit()) for part in pieces]
    if not all(numbers):
        raise ValueError("Stimulation contact label has no number")
    return "-".join(reversed(pieces)) if int(numbers[0]) > int(numbers[1]) else label


def stimulation_trains(
    annotations: list[Annotation], pulses: list[int], sampling_hz: float
) -> list[StimulationTrain]:
    """CCEPStimAnnotConvert. Pulse membership excludes both window endpoints.

    Unclosed starts remain visible with no frequency/end, as incomplete legacy
    records. Clinical small-train frequency is also .5 Hz because the source
    overwrites its tentative 50 Hz choice. Consumer validation rejects incomplete
    trains instead of inventing a stop time.
    """
    result = []
    current: StimulationTrain | None = None
    for annotation in annotations:
        text = annotation.text.lower()
        words = annotation.text.split(" ")
        if "stim start" in text:
            if len(words) < 3:
                raise ValueError("Malformed stimulation start annotation")
            level = 0.0
            if len(words) >= 4:
                try:
                    level = float(words[3])
                except ValueError:
                    level = float("nan")  # str2double(non-numeric) returns NaN.
            current = StimulationTrain(
                stimulation_label(words[2]), level, annotation.sample, None, (), None
            )
        elif "stim stop" in text and current is not None:
            # The original compares the stop token literally to the normalized start.
            if len(words) < 3 or words[2] != current.label:
                continue
            selected = tuple(
                p for p in pulses if current.start_sample < p < annotation.sample
            )
            if len(selected) > 2:
                interval = matlab_round(float(np.mean(np.diff(selected))))
                frequency = (
                    matlab_round((sampling_hz / interval) * 100) / 100
                    if interval
                    else float("inf")
                )
                if 0.4 < frequency < 0.6:
                    frequency = 0.5
            else:
                frequency = 0.5
            result.append(
                StimulationTrain(
                    current.label,
                    current.level_ma,
                    current.start_sample,
                    annotation.sample,
                    selected,
                    frequency,
                )
            )
            current = None
    if current is not None:
        result.append(current)
    return result
