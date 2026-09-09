"""Explicit units and sample conventions shared by scripts, GUI and CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

FloatArray = NDArray[np.float64]


class Annotation(BaseModel):
    """Zero-based sample offset; duration is in seconds."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    sample: int = Field(ge=0)
    text: str
    duration_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)


@dataclass
class AnnotationSet:
    annotations: list[Annotation] = field(default_factory=list)
    automatic_pulses: list[int] = field(default_factory=list)
    manual_pulses: list[int] = field(default_factory=list)
    # Preserve MAT fields that the current editor does not understand.
    legacy_fields: list[dict[str, Any]] = field(default_factory=list)
    extra_variables: dict[str, Any] = field(default_factory=dict)

    @property
    def pulses(self) -> list[int]:
        return self.automatic_pulses + self.manual_pulses


@dataclass(frozen=True)
class Channel:
    label: str
    samples: FloatArray
    sampling_hz: float
    unit: str

    def __post_init__(self) -> None:
        if self.samples.ndim != 1:
            raise ValueError("Channel samples must have one time axis")
        if not np.isfinite(self.sampling_hz) or self.sampling_hz <= 0:
            raise ValueError("Sampling frequency must be finite and positive")
        if not self.label:
            raise ValueError("Channel label cannot be empty")
