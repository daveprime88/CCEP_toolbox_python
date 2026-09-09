"""EDF/continuous EDF+ reader with per-channel rates and physical calibration.

Header/calibration mapping follows EDF_Read.m and Get_EDF_FileHeaders.m.
Read windows use zero-based, half-open sample indexes. No implicit resampling.
Discontinuous EDF+D is detected and rejected until gaps have a verified contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ccep.models import Annotation, Channel


@dataclass(frozen=True)
class SignalHeader:
    label: str
    raw_label: str
    unit: str
    physical_min: float
    physical_max: float
    digital_min: int
    digital_max: int
    samples_per_record: int
    offset: int


class EDF:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        with self.path.open("rb") as stream:
            fixed = stream.read(256)
            if len(fixed) != 256 or fixed[:8].strip() != b"0":
                raise ValueError("Expected an EDF version 0 header")
            self.patient_id = fixed[8:88].decode("ascii").strip()
            self.recording_id = fixed[88:168].decode("ascii").strip()
            self.start_date = fixed[168:176].decode("ascii").strip()
            self.start_time = fixed[176:184].decode("ascii").strip()
            self.header_bytes = int(fixed[184:192])
            self.reserved = fixed[192:236].decode("ascii").strip()
            if self.reserved.startswith("EDF+D"):
                raise ValueError(
                    "EDF+D discontinuities are not implemented; do not flatten gaps"
                )
            records = int(fixed[236:244])
            self.record_seconds = float(fixed[244:252])
            count = int(fixed[252:256])
            if count <= 0 or self.header_bytes < 256 + 256 * count:
                raise ValueError("Invalid EDF signal count or header length")
            if not np.isfinite(self.record_seconds) or self.record_seconds <= 0:
                raise ValueError("EDF record duration must be positive")
            fields: list[list[str]] = []
            for width in (16, 80, 8, 8, 8, 8, 8, 80, 8, 32):
                block = stream.read(width * count)
                if len(block) != width * count:
                    raise ValueError("Truncated EDF signal headers")
                fields.append(
                    [
                        block[i * width : (i + 1) * width].decode("ascii").strip()
                        for i in range(count)
                    ]
                )
        self.signals: list[SignalHeader] = []
        offset = 0
        for i in range(count):
            label = re.sub(r"POL |EEG |-REF", "", fields[0][i], flags=re.I).strip()
            signal = SignalHeader(
                label,
                fields[0][i],
                fields[2][i],
                float(fields[3][i]),
                float(fields[4][i]),
                int(fields[5][i]),
                int(fields[6][i]),
                int(fields[8][i]),
                offset,
            )
            if (
                signal.samples_per_record <= 0
                or signal.digital_max <= signal.digital_min
            ):
                raise ValueError(f"Invalid EDF calibration/sample count: {label}")
            if not np.isfinite([signal.physical_min, signal.physical_max]).all():
                raise ValueError(f"Nonfinite EDF calibration: {label}")
            self.signals.append(signal)
            offset += signal.samples_per_record
        self.record_samples = offset
        data_bytes = self.path.stat().st_size - self.header_bytes
        actual_records, remainder = divmod(data_bytes, offset * 2)
        if (
            data_bytes < 0
            or remainder
            or records < -1
            or (records != -1 and records != actual_records)
        ):
            raise ValueError(
                "EDF record count does not match file length (truncated or extra data)"
            )
        self.records = actual_records
        labels = [s.label for s in self.signals if s.raw_label != "EDF Annotations"]
        if len(labels) != len(set(labels)):
            raise ValueError(
                "Ambiguous cleaned EDF channel labels; explicit disambiguation required"
            )

    @property
    def channels(self) -> list[SignalHeader]:
        return [s for s in self.signals if s.raw_label != "EDF Annotations"]

    def read(self, label: str, start: int = 0, stop: int | None = None) -> Channel:
        signal = next((s for s in self.channels if s.label == label), None)
        if signal is None:
            raise ValueError(f"Unknown channel: {label}")
        count = self.records * signal.samples_per_record
        stop = count if stop is None else stop
        if not 0 <= start <= stop <= count:
            raise ValueError(f"Window [{start}, {stop}) outside channel length {count}")
        samples = np.empty(stop - start, dtype=np.float64)
        # Seek only the records needed; don't load all channels to view one.
        with self.path.open("rb") as stream:
            for record in range(
                start // signal.samples_per_record,
                (stop + signal.samples_per_record - 1) // signal.samples_per_record,
            ):
                first = max(start, record * signal.samples_per_record)
                last = min(stop, (record + 1) * signal.samples_per_record)
                position = (
                    record * self.record_samples
                    + signal.offset
                    + first % signal.samples_per_record
                )
                stream.seek(self.header_bytes + 2 * position)
                raw = stream.read(2 * (last - first))
                if len(raw) != 2 * (last - first):
                    raise ValueError("EDF changed or was truncated during reading")
                samples[first - start : last - start] = np.frombuffer(raw, dtype="<i2")
        scale = (signal.physical_max - signal.physical_min) / (
            signal.digital_max - signal.digital_min
        )
        samples *= scale
        samples += signal.physical_max - scale * signal.digital_max
        return Channel(
            label, samples, signal.samples_per_record / self.record_seconds, signal.unit
        )

    def annotations(self, sampling_hz: float) -> list[Annotation]:
        result: list[Annotation] = []
        with self.path.open("rb") as stream:
            for record in range(self.records):
                for signal in self.signals:
                    if signal.raw_label != "EDF Annotations":
                        continue
                    stream.seek(
                        self.header_bytes
                        + 2 * (record * self.record_samples + signal.offset)
                    )
                    block = stream.read(signal.samples_per_record * 2)
                    for tal in block.split(b"\0"):
                        if not tal:
                            continue
                        parts = tal.split(b"\x14")
                        timing = parts[0].split(b"\x15")
                        onset = float(timing[0])
                        duration = float(timing[1]) if len(timing) > 1 else 0.0
                        for text in parts[1:]:
                            if text:
                                if onset < 0:
                                    raise ValueError(
                                        "Negative EDF annotation onset needs explicit handling"
                                    )
                                result.append(
                                    Annotation(
                                        sample=int(np.floor(onset * sampling_hz + 0.5)),
                                        text=text.decode("utf-8"),
                                        duration_seconds=duration,
                                    )
                                )
        return sorted(result, key=lambda annotation: annotation.sample)
