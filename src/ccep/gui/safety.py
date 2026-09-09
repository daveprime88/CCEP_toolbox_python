"""Stimulation geometry and historical study comparison controls."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from scipy.io import loadmat

from ccep.gui.canvas import PlotCanvas
from ccep.science.safety import stimulation_estimate


class SafetyViewer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CCEP Toolbox — historical stimulation comparisons")
        self.resize(1050, 750)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.addWidget(
            QLabel(
                "Original toolbox research context: these historical comparisons do not establish clinical safety."
            )
        )
        controls = QHBoxLayout()
        layout.addLayout(controls)
        form = QFormLayout()
        controls.addLayout(form)
        self.electrode_geometry = QComboBox()
        self.electrode_geometry.addItems(["Depth contact", "Disc contact"])
        form.addRow("Electrode geometry", self.electrode_geometry)
        self.inputs = {}
        for key, label, value in [
            ("diameter", "Diameter (mm)", 0.8),
            ("length", "Length (mm)", 2),
            ("current", "Current (mA)", 1),
            ("width", "Pulse width (ms)", 0.3),
        ]:
            box = QDoubleSpinBox()
            box.setDecimals(3)
            box.setRange(0.001, 1000)
            box.setValue(value)
            self.inputs[key] = box
            form.addRow(label, box)
            box.valueChanged.connect(self.redisplay)
        self.summary = QLabel()
        form.addRow(self.summary)
        load = QPushButton("Load MATLAB study table")
        form.addRow(load)
        load.clicked.connect(self._load)
        self.figure = Figure(layout="constrained")
        self.canvas = PlotCanvas(self.figure)
        self.axes = self.figure.add_subplot()
        controls.addWidget(self.canvas, 1)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["Publication", "Pulse width (ms)", "Maximum current (mA)"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        self.studies: list[tuple[str, float, float]] = []
        self.electrode_geometry.currentIndexChanged.connect(self.redisplay)
        self.table.itemSelectionChanged.connect(self.redisplay)
        self.redisplay()

    def load_studies(self, path: Path) -> None:
        raw = loadmat(path, simplify_cells=True)
        if "StudyDetails" not in raw:
            raise ValueError("Expected legacy StudyDetails MAT variable")
        rows = raw["StudyDetails"]
        rows = [rows] if isinstance(rows, dict) else list(rows)
        studies = [
            (str(row["Publication"]), float(row["PW"]), float(row["MaxCurrent"]))
            for row in rows
        ]
        self.studies = studies
        self.table.setRowCount(len(studies))
        for i, row in enumerate(studies):
            for j, value in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        self.redisplay()

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load study table", filter="MAT (*.mat)"
        )
        if path:
            try:
                self.load_studies(Path(path))
            except (OSError, ValueError, KeyError) as error:
                QMessageBox.warning(self, "Study table", str(error))

    def redisplay(self) -> None:
        geometry = "depth" if self.electrode_geometry.currentIndex() == 0 else "disc"
        self.inputs["length"].setEnabled(geometry == "depth")
        estimate = stimulation_estimate(
            geometry,
            self.inputs["diameter"].value(),
            self.inputs["length"].value(),
            self.inputs["current"].value(),
            self.inputs["width"].value(),
        )
        self.summary.setText(
            f"Area: {estimate.area_cm2:.5g} cm²\nCharge: {estimate.charge_microcoulomb:.4g} µC\nCharge density: {estimate.charge_density_microcoulomb_cm2:.4g} µC/cm²"
        )
        self.axes.clear()
        width = np.linspace(0.01, 3, 300)
        self.axes.plot(
            width,
            57 * estimate.area_cm2 / width,
            label="Historical 57 µC/cm² curve",
            color="red",
        )
        self.axes.plot(
            self.inputs["width"].value(),
            self.inputs["current"].value(),
            "ro",
            label="Entered parameters",
        )
        selection = {item.row() for item in self.table.selectedItems()}
        for i, (_publication, pw, current) in enumerate(self.studies):
            if not selection or i in selection:
                self.axes.plot(pw, current, "k*")
        self.axes.set(
            xlabel="Pulse width (ms)", ylabel="Current (mA)", xlim=(0, 3), ylim=(0, 15)
        )
        self.axes.legend()
        self.canvas.draw_idle()
