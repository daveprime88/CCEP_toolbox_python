"""Create a small synthetic EDF and explicit configuration, with no participant data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def make_demo(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    rate, seconds = 1000, 20
    times = np.arange(rate * seconds) / rate
    first = 20 * np.sin(2 * np.pi * 8 * times) + 4 * np.sin(2 * np.pi * 37 * times)
    second = 8 * np.sin(2 * np.pi * 8 * times + 0.2)
    pulses = [3000, 5000, 7000, 9000, 11000, 13000]
    for pulse in pulses:
        response = np.arange(400) / rate
        first[pulse : pulse + 400] += (
            80 * np.exp(-response * 15) * np.sin(2 * np.pi * 12 * response)
        )
    samples = [np.rint(first).astype("<i2"), np.rint(second).astype("<i2")]

    def field(value: object, width: int) -> bytes:
        encoded = str(value).encode("ascii")
        if len(encoded) > width:
            raise ValueError("EDF field exceeds width")
        return encoded.ljust(width, b" ")

    header = b"".join(
        field(v, n)
        for v, n in [
            (0, 8),
            ("Synthetic", 80),
            ("CCEP demo", 80),
            ("01.01.26", 8),
            ("00.00.00", 8),
            (768, 8),
            ("", 44),
            (seconds, 8),
            (1, 8),
            (2, 4),
        ]
    )
    for width, values in [
        (16, ["A1", "A2"]),
        (80, ["", ""]),
        (8, ["uV", "uV"]),
        (8, [-32768] * 2),
        (8, [32767] * 2),
        (8, [-32768] * 2),
        (8, [32767] * 2),
        (80, [""] * 2),
        (8, [rate] * 2),
        (32, [""] * 2),
    ]:
        header += b"".join(field(value, width) for value in values)
    with (directory / "recording.edf").open("xb") as stream:
        stream.write(header)
        for record in range(seconds):
            for channel in samples:
                stream.write(channel[record * rate : (record + 1) * rate].tobytes())
    (directory / "annotations.json").write_text(
        json.dumps(
            dict(
                schema_version=1,
                sample_origin=0,
                annotations=[
                    dict(
                        sample=2500,
                        text="Synthetic stimulation train",
                        duration_seconds=0,
                    )
                ],
                automatic_pulses=pulses,
                manual_pulses=[],
            ),
            indent=2,
        )
        + "\n"
    )
    (directory / "config.json").write_text(
        json.dumps(
            dict(
                schema_version=1,
                recording="recording.edf",
                annotations="annotations.json",
                reference="bipolar",
                channels=["A1-A2"],
                trains=[
                    dict(
                        name="Synthetic train",
                        frequency_hz=0.5,
                        annotation_window=[2500, 14000],
                    )
                ],
                filtering=dict(
                    enabled=True, highpass_hz=1, lowpass_hz=300, notch_hz=[48, 52]
                ),
                baseline_windows=[[16000, 16200], [17000, 17200], [18000, 18200]],
                scoring=dict(
                    sites={
                        "A1-A2": dict(
                            anatomical="Synthetic cortex A",
                            contact_anatomy=[
                                "Synthetic cortex A",
                                "Synthetic cortex A",
                            ],
                        )
                    },
                    stimulation_anatomy={"Synthetic train": "Synthetic cortex B"},
                    distances_mm={"Synthetic train": {"A1-A2": 20}},
                ),
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    make_demo(parser.parse_args().directory)
