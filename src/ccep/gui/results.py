"""Saved result exploration: channel/train selection, ERPs and metric summaries."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ccep.analysis import AnalysisResult, save_result
from ccep.gui.canvas import PlotCanvas
from ccep.io.exports import export_table


class ResultsViewer(QMainWindow):
    def __init__(self, result: AnalysisResult) -> None:
        super().__init__()
        self.ranking_windows: list[QMainWindow] = []
        self.result = result
        self.setWindowTitle("CCEP Toolbox — ERP and pulse metrics")
        self.resize(1280, 800)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        reference = result.metadata["config"]["reference"]
        layout.addWidget(
            QLabel(
                f"{reference.title()} reference | {result.metadata['config']['recording']}"
            )
        )
        self.status = QLabel(
            "Source-derived results; anatomy eligibility/ranking integration and MATLAB parity pending."
        )
        layout.addWidget(self.status)
        split = QSplitter()
        layout.addWidget(split, 1)
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        controls_layout.addWidget(QLabel("Channels (up to 12 plots)"))
        self.channels = QListWidget()
        self.channels.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.channels.addItems([c["label"] for c in result.metadata["channels"]])
        controls_layout.addWidget(self.channels)
        controls_layout.addWidget(QLabel("Pulse trains to display"))
        self.trains = QListWidget()
        self.trains.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.trains.addItems([t["name"] for t in result.metadata["trains"]])
        controls_layout.addWidget(self.trains)
        split.addWidget(controls)
        self.figure = Figure(layout="constrained")
        self.canvas = PlotCanvas(self.figure)
        split.addWidget(self.canvas)
        split.setSizes([230, 1000])
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Channel", "Pulses", "RMS mean", "RMS median", "Std ratio mean"]
        )
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        save = QPushButton("Save result")
        export = QPushButton("Export pulse metrics")
        actions.addWidget(save)
        actions.addWidget(export)
        rankings = QPushButton("Response rankings")
        rankings.setEnabled("eligibility" in result.metadata)
        rankings.setToolTip(
            "Requires results processed with explicit scoring metadata and baseline windows"
        )
        rankings.clicked.connect(self._rankings)
        actions.addWidget(rankings)
        save.clicked.connect(self._save)
        export.clicked.connect(self._export)
        self.channels.itemSelectionChanged.connect(self.redisplay)
        self.trains.itemSelectionChanged.connect(self.redisplay)
        if self.channels.count():
            self.channels.item(0).setSelected(True)
        if self.trains.count():
            self.trains.item(0).setSelected(True)
        self.redisplay()

    def redisplay(self) -> None:
        channel_indexes = [
            self.channels.row(item) for item in self.channels.selectedItems()
        ]
        train_indexes = [self.trains.row(item) for item in self.trains.selectedItems()]
        self.status.setText(
            "Source-derived results; MATLAB parity pending. "
            + (
                "Eligibility and rankings use supplied metadata."
                if "eligibility" in self.result.metadata
                else "Anatomy eligibility was not requested for this result."
            )
        )
        self.figure.clear()
        self.table.setRowCount(0)
        if len(channel_indexes) > 12:
            self.status.setText("Select at most 12 channels to plot.")
            self.canvas.draw_idle()
            return
        for position, ci in enumerate(channel_indexes):
            channel = self.result.metadata["channels"][ci]
            axes = self.figure.add_subplot(
                max(1, (len(channel_indexes) + 1) // 2),
                min(2, len(channel_indexes)),
                position + 1,
            )
            rms, std = [], []
            for ti in train_indexes:
                train = self.result.metadata["trains"][ti]
                times = (
                    self.result.arrays[f"t{ti}_offsets"] * 1000 / channel["sampling_hz"]
                )
                axes.plot(
                    times,
                    self.result.arrays[f"t{ti}_c{ci}_erp"].mean(axis=0),
                    label=train["name"],
                )
                rms.extend(self.result.arrays[f"t{ti}_c{ci}_rms"])
                std.extend(self.result.arrays[f"t{ti}_c{ci}_std"])
            axes.axvline(0, color="red", linestyle="--")
            axes.set(xlabel="Time (ms)", ylabel=channel["unit"], title=channel["label"])
            if train_indexes:
                axes.legend()
            self.table.insertRow(position)
            values = [
                channel["label"],
                len(rms),
                np.mean(rms) if rms else "",
                np.median(rms) if rms else "",
                np.mean(std) if std else "",
            ]
            for column, value in enumerate(values):
                self.table.setItem(position, column, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        self.canvas.draw_idle()

    def _rankings(self) -> None:
        from ccep.gui.rankings import RankingsViewer

        window = RankingsViewer(self)
        self.ranking_windows.append(window)
        window.show()

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save new result", filter="CCEP result (*.npz)"
        )
        if path:
            try:
                save_result(Path(path), self.result)
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Result save failed", str(error))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export new table", filter="CSV (*.csv);;Excel (*.xlsx)"
        )
        if path:
            try:
                export_table(self.result, Path(path))
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Export failed", str(error))
