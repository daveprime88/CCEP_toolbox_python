"""Additive table/plot exports; legacy MAT schema adaptation is a separate interface."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import numpy as np
from openpyxl import Workbook

from ccep.analysis import AnalysisResult
from ccep.io.atomic import atomic_binary

COLUMNS = (
    "train",
    "frequency_hz",
    "reference",
    "channel",
    "pulse_sample_zero_based",
    "rms_ratio",
    "std_ratio",
)


def rows(result: AnalysisResult) -> list[tuple[Any, ...]]:
    data = []
    for ti, train in enumerate(result.metadata["trains"]):
        for ci, channel in enumerate(result.metadata["channels"]):
            for pi, pulse in enumerate(train["pulse_samples"]):
                data.append(
                    (
                        train["name"],
                        train["frequency_hz"],
                        result.metadata["config"]["reference"],
                        channel["label"],
                        pulse,
                        float(result.arrays[f"t{ti}_c{ci}_rms"][pi]),
                        float(result.arrays[f"t{ti}_c{ci}_std"][pi]),
                    )
                )
    return data


def export_table(result: AnalysisResult, path: Path) -> None:
    if path.exists():
        raise FileExistsError(path)
    if path.suffix.lower() == ".csv":
        with atomic_binary(path) as binary:
            stream = io.TextIOWrapper(binary, newline="", encoding="utf-8")
            try:
                writer = csv.writer(stream)
                writer.writerow(COLUMNS)
                writer.writerows(rows(result))
                stream.flush()
            finally:
                stream.detach()
    elif path.suffix.lower() == ".xlsx":
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "Pulse metrics"
        sheet.append(COLUMNS)
        for row in rows(result):
            sheet.append(
                [
                    str(x) if isinstance(x, float) and not np.isfinite(x) else x
                    for x in row
                ]
            )
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        with atomic_binary(path) as stream:
            workbook.save(stream)
    else:
        raise ValueError("Table exports must be .csv or .xlsx")


def export_erp_plot(result: AnalysisResult, path: Path, *, train: int = 0) -> None:
    from matplotlib.figure import Figure

    if path.exists():
        raise FileExistsError(path)
    if path.suffix.lower() not in {".png", ".svg", ".pdf"}:
        raise ValueError("Plot output must be PNG, SVG or PDF")
    if not 0 <= train < len(result.metadata["trains"]):
        raise ValueError("Unknown pulse train")
    figure = Figure(
        figsize=(10, max(3, len(result.metadata["channels"]) * 2.5)),
        layout="constrained",
    )
    for ci, channel in enumerate(result.metadata["channels"]):
        axes = figure.add_subplot(len(result.metadata["channels"]), 1, ci + 1)
        times = result.arrays[f"t{train}_offsets"] * 1000 / channel["sampling_hz"]
        axes.plot(times, result.arrays[f"t{train}_c{ci}_erp"].mean(axis=0))
        axes.axvline(0, color="red", linestyle="--")
        axes.set(xlabel="Time (ms)", ylabel=channel["unit"], title=channel["label"])
    with atomic_binary(path) as stream:
        figure.savefig(stream, format=path.suffix[1:])
