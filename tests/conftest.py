from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def edf_file(tmp_path: Path) -> Path:
    """Hand-encoded EDF+ fixture; digital samples equal physical microvolts."""

    def field(value, width):
        return str(value).encode("ascii").ljust(width, b" ")

    count, records, rate, tal_samples = 3, 10, 1000, 64
    header = b"".join(
        field(v, n)
        for v, n in [
            (0, 8),
            ("Synthetic", 80),
            ("Test", 80),
            ("01.01.26", 8),
            ("00.00.00", 8),
            (256 * (count + 1), 8),
            ("EDF+C", 44),
            (records, 8),
            (1, 8),
            (count, 4),
        ]
    )
    for width, values in [
        (16, ["POL A1", "POL A2", "EDF Annotations"]),
        (80, ["", "", ""]),
        (8, ["uV", "uV", ""]),
        (8, [-32768] * 3),
        (8, [32767] * 3),
        (8, [-32768] * 3),
        (8, [32767] * 3),
        (80, [""] * 3),
        (8, [rate, rate, tal_samples]),
        (32, [""] * 3),
    ]:
        header += b"".join(field(value, width) for value in values)
    path = tmp_path / "recording with spaces.edf"
    with path.open("wb") as stream:
        stream.write(header)
        for r in range(records):
            samples = np.arange(r * rate, (r + 1) * rate, dtype="<i2")
            stream.write(samples.tobytes())
            stream.write((samples // 2).astype("<i2").tobytes())
            tal = f"+{r}\x14\x14\0".encode()
            if r == 2:
                tal += b"+2.5\x150.1\x14Stim start\x14\0"
            stream.write(tal.ljust(tal_samples * 2, b"\0"))
    return path
