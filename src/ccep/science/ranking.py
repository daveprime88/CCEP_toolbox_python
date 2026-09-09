"""Rank-sum score and normalized ordering used by CCEPMakeRMSZScores.m."""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata

from ccep.models import FloatArray


def legacy_ranksum_z(actual: FloatArray, baseline: FloatArray) -> float:
    """Default two-sided MATLAB ranksum zval; exact-method cases become NaN.

    https://www.mathworks.com/help/stats/ranksum.html documents the default method,
    continuity correction and tie adjustment. The legacy wrapper catches missing
    zval. Historical runtime behavior still needs MATLAB reference confirmation.
    """
    x = np.asarray(actual).ravel()
    y = np.asarray(baseline).ravel()
    x, y = x[~np.isnan(x)], y[~np.isnan(y)]
    n, m = x.size, y.size
    if n == 0 or m == 0 or (min(n, m) < 10 and n + m < 20):
        return float("nan")
    values = np.concatenate((x, y))
    ranks = rankdata(values, method="average")
    delta = ranks[:n].sum() - n * (n + m + 1) / 2
    _, counts = np.unique(values, return_counts=True)
    tie_correction = np.sum(counts**3 - counts) / ((n + m) * (n + m - 1))
    variance = n * m * (n + m + 1 - tie_correction) / 12
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(np.divide(delta - 0.5 * np.sign(delta), np.sqrt(variance)))


def legacy_ranks(values: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Stable descending ranks; ties keep input order rather than averaging ranks."""
    if values.ndim != 1:
        raise ValueError("Rank values must have one channel axis")
    valid = ~np.isnan(values)
    sortable = np.where(valid, values, -np.inf)
    order = np.argsort(-sortable, kind="stable")
    count = int(valid.sum())
    ranks = np.full(values.size, np.nan)
    # This also retains the legacy -Inf/NaN ordering corner case.
    ranks[order[:count]] = np.arange(count, 0, -1) / max(count, 1)
    quartiles = np.ceil(ranks * 4)
    return ranks, quartiles
