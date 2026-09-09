"""Rank selection follows the per-train omitnan aggregation in CCEPRankingSort."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QListWidget,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ccep.science.scoring import aggregate_rankings

if TYPE_CHECKING:
    from ccep.gui.results import ResultsViewer

METRICS = {
    "Z score": "zscore",
    "Mean rank": "rms_mean_rank",
    "Median rank": "rms_median_rank",
    "Mean quartile value": "rms_mean_qv",
    "Median quartile value": "rms_median_qv",
}


class RankingsViewer(QMainWindow):
    def __init__(self, parent: ResultsViewer) -> None:
        super().__init__(parent)
        self.results = parent
        self.result = parent.result
        self.setWindowTitle("CCEP Toolbox — Response rankings")
        self.resize(1100, 700)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.addWidget(
            QLabel(
                "Rankings use supplied anatomy and distance metadata. MATLAB verification pending."
            )
        )
        self.ranking_metric = QComboBox()
        self.ranking_metric.addItems(list(METRICS))
        layout.addWidget(self.ranking_metric)
        self.trains = QListWidget()
        self.trains.setMaximumHeight(140)
        self.trains.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.trains.addItems([t["name"] for t in self.result.metadata["trains"]])
        layout.addWidget(self.trains)
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            ["Channel", "Anatomy", "Pulses", "Mean distance (mm)", *METRICS]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        self.ranking_metric.currentTextChanged.connect(self.redisplay)
        self.trains.itemSelectionChanged.connect(self.redisplay)
        self.table.cellClicked.connect(self.select_channel)
        parent.channels.itemSelectionChanged.connect(self.redisplay)
        self.trains.item(0).setSelected(True)

    def redisplay(self) -> None:
        indices = [self.trains.row(item) for item in self.trains.selectedItems()]
        self.table.setRowCount(0)
        if not indices:
            return
        scores = aggregate_rankings(
            [
                {
                    metric: self.result.arrays[f"t{ti}_score_{metric}"]
                    for metric in METRICS.values()
                }
                for ti in indices
            ]
        )
        metric = scores[METRICS[self.ranking_metric.currentText()]]
        # MATLAB MissingPlacement='last' keeps NaNs behind even genuine -Inf.
        order = sorted(
            range(metric.size),
            key=lambda i: (
                np.isnan(metric[i]),
                -metric[i] if not np.isnan(metric[i]) else 0,
            ),
        )
        config = self.result.metadata["config"]["scoring"]
        selected = {item.text() for item in self.results.channels.selectedItems()}
        self.table.setRowCount(len(order))
        for row, ci in enumerate(order):
            label = self.result.metadata["channels"][ci]["label"]
            trains = [self.result.metadata["trains"][ti] for ti in indices]
            values = [
                label,
                config["sites"][label]["anatomical"],
                sum(len(t["pulse_samples"]) for t in trains),
                np.mean([config["distances_mm"][t["name"]][label] for t in trains]),
                *(scores[m][ci] for m in METRICS.values()),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, ci)
                if label in selected:
                    item.setBackground(QColor("#fff4b3"))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def select_channel(self, row: int, column: int) -> None:
        item = self.table.item(row, column)
        if item is None:
            return
        ci = item.data(Qt.ItemDataRole.UserRole)
        self.results.channels.clearSelection()
        self.results.channels.item(ci).setSelected(True)
