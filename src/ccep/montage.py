"""Source-derived channel parsing and adjacent-contact bipolar montage."""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

from ccep.models import Channel


def contact(label: str) -> tuple[str, int]:
    """LabelCheck.m conventions, including second implant labels such as A21."""
    if re.search(r"DC\d*", label):
        return "Other", 0
    if re.fullmatch(r"[a-zA-Z]{1,2}'?2[0-9]{1,2}", label):
        prefix = re.match(r"[a-zA-Z]{1,2}2'?", label)
        if prefix is None:
            raise ValueError(f"Legacy LabelCheck cannot parse {label!r}")
        return prefix[0], int(label[len(prefix[0]) :])
    match = re.fullmatch(r"([a-zA-Z]{1,2}'?)([0-9]{1,2})", label)
    return (match[1], int(match[2])) if match else ("Other", 0)


def pairs(labels: Sequence[str]) -> list[tuple[str, str, str]]:
    """Adjacent input order, mesial minus lateral; no inferred missing contacts."""
    result = []
    for left, right in zip(labels, labels[1:], strict=False):
        a, b = contact(left), contact(right)
        if a[1] and a[0] == b[0] and b[1] - a[1] == 1:
            result.append((f"{left}-{right}", left, right))
    return result


def bipolar(left: Channel, right: Channel, label: str) -> Channel:
    if left.sampling_hz != right.sampling_hz or left.unit != right.unit:
        raise ValueError(
            "Bipolar channels must have identical sampling rate and physical unit"
        )
    if left.samples.shape != right.samples.shape:
        raise ValueError("Bipolar channel lengths differ")
    return Channel(
        label,
        np.asarray(left.samples - right.samples, dtype=np.float64),
        left.sampling_hz,
        left.unit,
    )
