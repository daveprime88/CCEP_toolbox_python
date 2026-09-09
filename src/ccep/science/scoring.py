"""Source-derived eligibility and summaries from CCEPMakeRMSZScores.m.

Anatomical strings must already have passed legacy hemisphere/acronym relabeling.
No seizure-zone or kurtosis exclusion is applied: those inputs are inactive in
this frozen MATLAB implementation. This stage does not infer contact metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ccep.models import FloatArray
from ccep.science.ranking import legacy_ranksum_z

DEFAULT_EXCLUSIONS = (
    "CYST",
    "lesion",
    "IH",
    "ventricle",
    "hetereotopia",
    "hamartoma",
    "gliosis",
    "flat signal",
    "tissue",
    "sylfis",
)


class SiteMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    anatomical: str = Field(min_length=1)
    # Bipolar channels require the anatomy of both underlying unipolar contacts.
    contact_anatomy: tuple[str, str] | None = None


class ScoringSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sites: dict[str, SiteMetadata]
    stimulation_anatomy: dict[str, str]
    # Explicit distances in mm, keyed by train and then recording channel.
    distances_mm: dict[str, dict[str, float]]
    distance_threshold_mm: float = Field(default=10, ge=0, allow_inf_nan=False)
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUSIONS

    @field_validator("exclude_patterns")
    @classmethod
    def valid_patterns(cls, patterns: tuple[str, ...]) -> tuple[str, ...]:
        for pattern in patterns:
            re.compile(pattern, re.IGNORECASE)
        return patterns

    @field_validator("distances_mm")
    @classmethod
    def finite_distances(
        cls, distances: dict[str, dict[str, float]]
    ) -> dict[str, dict[str, float]]:
        if any(
            not np.isfinite(d) or d < 0
            for sites in distances.values()
            for d in sites.values()
        ):
            raise ValueError(
                "Stimulation distances must be finite, nonnegative millimetres"
            )
        return distances


@dataclass(frozen=True)
class Scores:
    arrays: dict[str, FloatArray]
    reasons: list[list[str]]


def _rank(values: FloatArray, mean_count: int) -> tuple[FloatArray, FloatArray]:
    """The source median loop uses the mean count, including its NaN corner case."""
    valid_count = int((~np.isnan(values)).sum())
    order = np.argsort(-np.where(np.isnan(values), -np.inf, values), kind="stable")
    ranks = np.full(values.size, np.nan)
    if mean_count:
        ranks[order[:mean_count]] = (valid_count - np.arange(mean_count)) / mean_count
    # Source uses <= .25 -> 1, even if a mismatched count gives a zero rank.
    quartiles = np.where(np.isnan(ranks), np.nan, np.clip(np.ceil(ranks * 4), 1, 4))
    return ranks, quartiles


def score_train(
    actual: list[FloatArray],
    baseline: list[FloatArray],
    sites: list[SiteMetadata],
    distances_mm: list[float],
    *,
    reference: Literal["unipolar", "bipolar"],
    stimulation_anatomy: str,
    distance_threshold_mm: float = 10,
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUSIONS,
) -> Scores:
    count = len(sites)
    if not len(actual) == len(baseline) == len(distances_mm) == count:
        raise ValueError("Scoring inputs must align by channel")
    if len({a.size for a in actual}) > 1:
        raise ValueError("Scored channels must contain the same pulse train")
    reasons: list[list[str]] = []
    valid = np.ones(count, dtype=np.float64)
    z, mean, median = (np.full(count, np.nan) for _ in range(3))
    for i, site in enumerate(sites):
        if actual[i].ndim != 1 or baseline[i].ndim != 1:
            raise ValueError("Scoring requires one-dimensional per-pulse RMS arrays")
        if reference == "bipolar" and site.contact_anatomy is None:
            raise ValueError("Bipolar scoring requires both unipolar contact anatomies")
        rejection = []
        if actual[i].size <= 5:
            rejection.append("five_or_fewer_pulses")
        if distances_mm[i] <= distance_threshold_mm:
            rejection.append("within_stimulation_distance")
        outside = (
            "OUT" in site.contact_anatomy
            if reference == "bipolar" and site.contact_anatomy
            else site.anatomical == "OUT"
        )
        if outside:
            rejection.append("outside_brain")
        if site.anatomical in ("Left WM", "Right WM"):
            rejection.append("white_matter")
        if reference == "bipolar" and site.anatomical == stimulation_anatomy:
            rejection.append("same_stimulation_anatomy")
        if any(re.search(p, site.anatomical, re.IGNORECASE) for p in exclude_patterns):
            rejection.append("excluded_anatomical_label")
        reasons.append(rejection)
        if rejection:
            valid[i] = 0
            continue
        # Preserve single-precision mean/median of legacy RMS vectors and NaNs;
        # ranksum removes NaNs, while mean/median propagate them.
        values = actual[i].astype(np.float32)
        z[i] = legacy_ranksum_z(values.astype(np.float64), baseline[i])
        with np.errstate(invalid="ignore", over="ignore"):
            mean[i], median[i] = np.mean(values), np.median(values)
    mean_rank, mean_qv = _rank(mean, int((~np.isnan(mean)).sum()))
    median_rank, median_qv = _rank(median, int((~np.isnan(mean)).sum()))
    return Scores(
        dict(
            valid=valid,
            zscore=z,
            rms_mean=mean,
            rms_median=median,
            rms_mean_rank=mean_rank,
            rms_mean_qv=mean_qv,
            rms_median_rank=median_rank,
            rms_median_qv=median_qv,
        ),
        reasons,
    )


def aggregate_rankings(
    train_scores: list[dict[str, FloatArray]],
) -> dict[str, FloatArray]:
    """CCEPRankingSort: average per-train scores with omitnan; do not rerank."""
    if not train_scores:
        raise ValueError("Select at least one pulse train")
    output = {}
    for metric in (
        "zscore",
        "rms_mean_rank",
        "rms_median_rank",
        "rms_mean_qv",
        "rms_median_qv",
    ):
        values = np.stack([scores[metric] for scores in train_scores])
        count = np.sum(~np.isnan(values), axis=0)
        output[metric] = np.divide(
            np.nansum(values, axis=0),
            count,
            out=np.full(count.shape, np.nan),
            where=count > 0,
        )
    return output
