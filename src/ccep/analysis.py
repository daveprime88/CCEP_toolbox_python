"""Explicit, reproducible pulse-train processing shared by GUI and CLI.

This internal milestone computes source-derived metrics and ERPs. Full legacy
anatomy eligibility, repository aggregation and file-level parity remain gates.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ccep.io.annotations import load_annotations
from ccep.io.atomic import atomic_binary
from ccep.io.edf import EDF
from ccep.models import FloatArray
from ccep.montage import bipolar, pairs
from ccep.reference import sha256
from ccep.science.scoring import ScoringSettings, score_train
from ccep.science.signal import (
    apply_legacy_filter,
    epochs,
    legacy_filter_coefficients,
    rms_ratios,
)


class PulseTrain(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1)
    frequency_hz: float = Field(gt=0, allow_inf_nan=False)
    pulse_samples: list[int] = Field(default_factory=list)
    annotation_window: tuple[int, int] | None = None

    @model_validator(mode="after")
    def validate_source(self) -> PulseTrain:
        if bool(self.pulse_samples) == (self.annotation_window is not None):
            raise ValueError(
                "Provide pulse_samples or an annotation_window, exclusively"
            )
        if any(p < 0 for p in self.pulse_samples):
            raise ValueError("Pulse samples use nonnegative zero-based offsets")
        if (
            self.annotation_window
            and not 0 <= self.annotation_window[0] <= self.annotation_window[1]
        ):
            raise ValueError(
                "Annotation window must have ordered nonnegative endpoints"
            )
        return self


class FilterSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    highpass_hz: float = Field(default=1, gt=0, allow_inf_nan=False)
    lowpass_hz: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    notch_hz: tuple[float, float] = (48, 52)


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    recording: Path
    annotations: Path | None = None
    reference: Literal["unipolar", "bipolar"]
    channels: list[str] = Field(min_length=1)
    trains: list[PulseTrain] = Field(min_length=1)
    filtering: FilterSettings = Field(default_factory=FilterSettings)
    scoring: ScoringSettings | None = None
    # Actual windows from reference capture, inclusive and zero-based.
    baseline_windows: list[tuple[int, int]] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_identities(self) -> RunConfig:
        if len(self.channels) != len(set(self.channels)):
            raise ValueError("Channel selections must be unique")
        names = [t.name for t in self.trains]
        if len(names) != len(set(names)):
            raise ValueError("Pulse train names must be unique")
        if any(t.annotation_window for t in self.trains) and self.annotations is None:
            raise ValueError("annotation_window requires an annotation file")
        return self


def load_config(path: Path) -> RunConfig:
    config = RunConfig.model_validate_json(path.read_text())
    update: dict[str, Any] = {"recording": (path.parent / config.recording).resolve()}
    if config.annotations:
        update["annotations"] = (path.parent / config.annotations).resolve()
    return config.model_copy(update=update)


def resolve_config(config: RunConfig) -> RunConfig:
    """Resolve annotation pulses and rate-dependent defaults; validate before output."""
    recording = EDF(config.recording)
    labels = [s.label for s in recording.channels]
    montage = {p[0]: p[1:] for p in pairs(labels)}
    source_labels = []
    for name in config.channels:
        if config.reference == "bipolar":
            if name not in montage:
                raise ValueError(f"Unknown bipolar channel: {name}")
            source_labels.extend(montage[name])
        elif name in labels:
            source_labels.append(name)
        else:
            raise ValueError(f"Unknown channel: {name}")
    selected = [s for s in recording.channels if s.label in source_labels]
    rates = {s.samples_per_record / recording.record_seconds for s in selected}
    if len(rates) != 1:
        raise ValueError(
            "Processing requires one explicit sampling rate; resampling is not implemented"
        )
    rate = rates.pop()
    count = recording.records * selected[0].samples_per_record
    annotations = load_annotations(config.annotations) if config.annotations else None
    trains = []
    for train in config.trains:
        pulses = train.pulse_samples
        if train.annotation_window is not None:
            assert annotations is not None
            start, end = train.annotation_window
            pulses = [p for p in annotations.pulses if start <= p <= end]
        if not pulses:
            raise ValueError(f"No pulses selected for train {train.name}")
        # Validate epoch windows without allocating a full recording.
        from ccep.science.signal import frequency_window, integer_sample, matlab_round

        duration, stim, base = frequency_window(train.frequency_hz)
        integer_sample((duration + stim) * rate)
        integer_sample(base * rate)
        for i, pulse in enumerate(pulses):
            lower = pulse - matlab_round(
                ((2 if i == 0 else 0) + duration + base) * rate
            )
            upper = pulse + integer_sample((duration + stim) * rate)
            if lower < 0 or upper >= count:
                raise ValueError(
                    f"Epoch outside recording in train {train.name}, pulse {pulse}"
                )
        trains.append(
            train.model_copy(
                update={"pulse_samples": pulses, "annotation_window": None}
            )
        )
    for start, end in config.baseline_windows:
        if not 0 <= start <= end < count:
            raise ValueError("Baseline window outside recording")
        from ccep.science.signal import integer_sample, matlab_round

        midpoint = matlab_round((start + end) / 2)
        if (
            midpoint - matlab_round(0.105 * rate) < 0
            or midpoint + integer_sample(0.11 * rate) >= count
        ):
            raise ValueError("Baseline epoch outside recording")
    if config.scoring:
        if not config.baseline_windows:
            raise ValueError("Scoring requires explicit baseline windows")
        scoring = config.scoring
        if set(scoring.sites) != set(config.channels):
            raise ValueError("Scoring sites must exactly match selected channels")
        names = {train.name for train in trains}
        if (
            set(scoring.distances_mm) != names
            or set(scoring.stimulation_anatomy) != names
        ):
            raise ValueError("Scoring metadata must exactly match pulse train names")
        for distances in scoring.distances_mm.values():
            if set(distances) != set(config.channels):
                raise ValueError(
                    "Scoring distances must exactly match selected channels"
                )
        if config.reference == "bipolar" and any(
            s.contact_anatomy is None for s in scoring.sites.values()
        ):
            raise ValueError("Bipolar scoring requires both unipolar contact anatomies")
    filtering = config.filtering
    if filtering.lowpass_hz is None:
        filtering = filtering.model_copy(update={"lowpass_hz": 0.3 * rate})
    if filtering.enabled:
        legacy_filter_coefficients(
            rate, filtering.highpass_hz, filtering.lowpass_hz, filtering.notch_hz
        )
    return config.model_copy(
        update={
            "recording": config.recording.resolve(),
            "trains": trains,
            "filtering": filtering,
        }
    )


@dataclass(frozen=True)
class AnalysisResult:
    metadata: dict[str, Any]
    arrays: dict[str, FloatArray]


def process(
    config: RunConfig, *, cancelled: Callable[[], bool] | None = None
) -> AnalysisResult:
    input_hashes = {"recording": sha256(config.recording)}
    if config.annotations:
        input_hashes["annotations"] = sha256(config.annotations)
    resolved = resolve_config(config)
    recording = EDF(resolved.recording)
    metadata: dict[str, Any] = dict(
        schema_version=1,
        kind="ccep-analysis",
        scientific_status="source-derived; MATLAB parity pending",
        limitations=[
            "Full anatomy eligibility and repository normalization are not yet integrated"
        ],
        sample_origin=0,
        config=resolved.model_dump(mode="json"),
        versions={name: version(name) for name in ("ccep-toolbox", "numpy", "scipy")},
        inputs=input_hashes,
        channels=[],
        trains=[],
    )
    arrays: dict[str, FloatArray] = {}
    montage = {p[0]: p[1:] for p in pairs([s.label for s in recording.channels])}
    for ci, name in enumerate(resolved.channels):
        if cancelled and cancelled():
            raise InterruptedError("Processing cancelled before the next channel")
        channel = (
            bipolar(
                recording.read(montage[name][0]), recording.read(montage[name][1]), name
            )
            if resolved.reference == "bipolar"
            else recording.read(name)
        )
        data = channel.samples
        if resolved.filtering.enabled:
            band, notch = legacy_filter_coefficients(
                channel.sampling_hz,
                resolved.filtering.highpass_hz,
                resolved.filtering.lowpass_hz,
                resolved.filtering.notch_hz,
            )
            data = apply_legacy_filter(
                data, (band, notch) if resolved.reference == "unipolar" else (band,)
            )
            arrays["band_coefficients"] = band
            if resolved.reference == "unipolar":
                arrays["notch_coefficients"] = notch
        metadata["channels"].append(
            dict(label=name, sampling_hz=channel.sampling_hz, unit=channel.unit)
        )
        for ti, train in enumerate(resolved.trains):
            if cancelled and cancelled():
                raise InterruptedError(
                    "Processing cancelled before the next pulse train"
                )
            extracted = epochs(
                data, train.pulse_samples, channel.sampling_hz, train.frequency_hz
            )
            rms, std = rms_ratios(extracted.response, extracted.baseline)
            key = f"t{ti}_c{ci}"
            # Store the MATLAB single-precision metric values, with a consistent
            # float64 container for portable comparisons. ERP remains double.
            arrays[key + "_rms"] = rms.astype(np.float32).astype(np.float64)
            arrays[key + "_std"] = std.astype(np.float32).astype(np.float64)
            arrays[key + "_erp"] = extracted.plot
            arrays[key + "_source_indexes"] = extracted.source_indexes.astype(
                np.float64
            )
            arrays[f"t{ti}_offsets"] = extracted.plot_offsets.astype(np.float64)
            if ci == 0:
                metadata["trains"].append(train.model_dump(mode="json"))
        if resolved.baseline_windows:
            # CCEPProcessRMSFile uses the rounded window midpoint as a pseudo-pulse.
            from ccep.science.signal import matlab_round

            pulses = [matlab_round((a + b) / 2) for a, b in resolved.baseline_windows]
            extracted = epochs(
                data, pulses, channel.sampling_hz, 0.5, first_pulse_shift=False
            )
            rms, std = rms_ratios(extracted.response, extracted.baseline)
            arrays[f"baseline_c{ci}_rms"] = rms.astype(np.float32).astype(np.float64)
            arrays[f"baseline_c{ci}_std"] = std.astype(np.float32).astype(np.float64)
    if resolved.scoring:
        settings = resolved.scoring
        metadata["eligibility"] = {}
        for ti, train in enumerate(resolved.trains):
            scored = score_train(
                [arrays[f"t{ti}_c{ci}_rms"] for ci in range(len(resolved.channels))],
                [arrays[f"baseline_c{ci}_rms"] for ci in range(len(resolved.channels))],
                [settings.sites[name] for name in resolved.channels],
                [settings.distances_mm[train.name][name] for name in resolved.channels],
                reference=resolved.reference,
                stimulation_anatomy=settings.stimulation_anatomy[train.name],
                distance_threshold_mm=settings.distance_threshold_mm,
                exclude_patterns=settings.exclude_patterns,
            )
            arrays.update(
                {f"t{ti}_score_{name}": value for name, value in scored.arrays.items()}
            )
            metadata["eligibility"][train.name] = dict(
                zip(resolved.channels, scored.reasons, strict=True)
            )
        metadata["limitations"] = [
            "Scoring uses supplied relabeled metadata; full legacy file and repository integration pending"
        ]
    # Detect input mutation rather than attach stale provenance to results.
    if sha256(resolved.recording) != metadata["inputs"]["recording"]:
        raise ValueError("Recording changed during processing")
    if (
        resolved.annotations
        and sha256(resolved.annotations) != metadata["inputs"]["annotations"]
    ):
        raise ValueError("Annotations changed during processing")
    return AnalysisResult(metadata, arrays)


def save_result(path: Path, result: AnalysisResult) -> None:
    payload: dict[str, Any] = dict(result.arrays)
    with atomic_binary(path) as stream:
        np.savez_compressed(
            stream,
            metadata=json.dumps(result.metadata, allow_nan=False),
            **payload,
        )


def load_result(path: Path) -> AnalysisResult:
    with np.load(path, allow_pickle=False) as bundle:
        metadata = json.loads(str(bundle["metadata"]))
        if (
            metadata.get("schema_version") != 1
            or metadata.get("kind") != "ccep-analysis"
        ):
            raise ValueError("Unsupported result schema")
        arrays = {
            key: np.asarray(bundle[key], dtype=np.float64)
            for key in bundle.files
            if key != "metadata"
        }
    for ti, train in enumerate(metadata["trains"]):
        pulses = len(train["pulse_samples"])
        offsets = arrays[f"t{ti}_offsets"]
        for ci, _ in enumerate(metadata["channels"]):
            for metric in ("rms", "std"):
                if arrays[f"t{ti}_c{ci}_{metric}"].shape != (pulses,):
                    raise ValueError("Result metric dimensions disagree with metadata")
            if arrays[f"t{ti}_c{ci}_erp"].shape != (pulses, len(offsets)):
                raise ValueError("Result ERP dimensions disagree with metadata")
    return AnalysisResult(metadata, arrays)
