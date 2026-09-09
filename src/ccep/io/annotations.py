"""Legacy annotation MAT and additive JSON persistence.

MAT Times/Time and PulseTimes are one-based sample positions. JSON uses zero-based
sample offsets and records its schema. Legacy unknown fields/variables survive edits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat, savemat

from ccep.io.atomic import atomic_binary
from ccep.models import Annotation, AnnotationSet


def load_annotations(path: Path) -> AnnotationSet:
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text())
        if raw.get("schema_version") != 1 or raw.get("sample_origin") != 0:
            raise ValueError("Unsupported annotation schema/sample origin")
        return AnnotationSet(
            [Annotation.model_validate(a) for a in raw["annotations"]],
            _pulses(raw.get("automatic_pulses", []), 0),
            _pulses(raw.get("manual_pulses", []), 0),
        )
    raw = loadmat(path, simplify_cells=True)
    rows = raw.get("Annotations", [])
    rows = [rows] if isinstance(rows, dict) else list(rows)
    annotations = []
    fields = []
    for row in rows:
        position = float(row.get("Times", row.get("Time", -1)))
        if position < 1 or position != int(position):
            raise ValueError(
                "MAT annotation Times must be positive integer sample positions"
            )
        duration = np.asarray(row.get("DurationSeconds", 0)).reshape(-1)
        if duration.size > 1:
            raise ValueError("Annotation duration must be scalar")
        annotations.append(
            Annotation(
                sample=int(position) - 1,
                text=str(row["Comment"]),
                duration_seconds=float(duration[0]) if duration.size else 0,
            )
        )
        fields.append(dict(row))
    return AnnotationSet(
        annotations,
        _pulses(raw.get("PulseTimes", []), 1),
        [],
        fields,
        {
            k: v
            for k, v in raw.items()
            if not k.startswith("__") and k not in {"Annotations", "PulseTimes"}
        },
    )


def _pulses(values: Any, origin: int) -> list[int]:
    result = []
    for value in np.asarray(values).reshape(-1):
        if not np.isfinite(value) or value < origin or value != int(value):
            raise ValueError("Pulse times must be integer sample positions")
        result.append(int(value) - origin)
    return result


def save_annotations(
    path: Path, data: AnnotationSet, *, overwrite: bool = False
) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    if path.suffix.lower() == ".json":
        if data.extra_variables or any(data.legacy_fields):
            raise ValueError(
                "Use MAT to preserve unknown legacy metadata; JSON conversion is not lossless"
            )
        content = dict(
            schema_version=1,
            sample_origin=0,
            annotations=[a.model_dump() for a in data.annotations],
            automatic_pulses=data.automatic_pulses,
            manual_pulses=data.manual_pulses,
        )
        with atomic_binary(path, overwrite=overwrite) as stream:
            stream.write(
                (json.dumps(content, indent=2, allow_nan=False) + "\n").encode("utf-8")
            )
        return
    if path.suffix.lower() != ".mat":
        raise ValueError("Annotation output must be .mat or .json")
    rows = []
    for i, annotation in enumerate(data.annotations):
        row = dict(data.legacy_fields[i]) if i < len(data.legacy_fields) else {}
        old_time = row.get("Times")
        row.update(Times=annotation.sample + 1, Comment=annotation.text)
        if old_time != annotation.sample + 1 or "Time" not in row:
            row["Time"] = annotation.sample + 1
        if annotation.duration_seconds or "DurationSeconds" in row:
            row["DurationSeconds"] = annotation.duration_seconds
        rows.append(row)
    names = sorted({key for row in rows for key in row} | {"Times", "Time", "Comment"})
    struct = np.empty((1, len(rows)), dtype=[(name, object) for name in names])
    for i, row in enumerate(rows):
        for name in names:
            struct[name][0, i] = row.get(name, np.array([]))
    content = dict(
        data.extra_variables,
        Annotations=struct,
        PulseTimes=np.asarray(data.pulses, dtype=float).reshape(-1, 1) + 1,
    )
    with atomic_binary(path, overwrite=overwrite) as stream:
        savemat(stream, content, do_compression=False, long_field_names=True)
