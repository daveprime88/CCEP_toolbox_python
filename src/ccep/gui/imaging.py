"""Orthogonal native-image review and endpoint acquisition without SPM."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ccep.gui.canvas import PlotCanvas
from ccep.imaging.geometry import voxel_to_world, world_to_voxel
from ccep.imaging.images import load_spatial_mm
from ccep.imaging.session import Electrode, ImagingSession, load_session, save_session
from ccep.reference import sha256


class ImagingViewer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CCEP Toolbox — Image review and contact acquisition")
        self.resize(1350, 750)
        self.session: ImagingSession | None = None
        self.volume: Any = None
        self.overlay: Any = None
        self.image_data: Any = None
        self.image_limits = (0.0, 1.0)
        self.overlay_data: Any = None
        self.mesial: tuple[float, float, float] | None = None
        self.lateral: tuple[float, float, float] | None = None
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        controls = QVBoxLayout()
        layout.addLayout(controls)
        for title, action in [
            ("Open native MRI / CT", self._open),
            ("Open overlay in same physical space", self._overlay),
            ("Load imaging session", self._load),
            ("Save new imaging session", self._save),
        ]:
            button = QPushButton(title)
            button.clicked.connect(action)
            controls.addWidget(button)
        self.overlay_visible = QCheckBox("Show overlay")
        controls.addWidget(self.overlay_visible)
        self.overlay_visible.toggled.connect(self.redisplay)
        self.status = QLabel("Load a 3D image to acquire contacts in native RAS mm.")
        self.status.setWordWrap(True)
        controls.addWidget(self.status)
        form = QFormLayout()
        controls.addLayout(form)
        self.voxel_controls = []
        for name in ("Voxel i", "Voxel j", "Voxel k"):
            box = QSpinBox()
            box.setRange(0, 0)
            form.addRow(name, box)
            box.valueChanged.connect(self.redisplay)
            self.voxel_controls.append(box)
        self.cursor_label = QLabel()
        form.addRow(self.cursor_label)
        self.electrode_name = QLineEdit("A")
        form.addRow("Electrode name", self.electrode_name)
        self.contact_count = QSpinBox()
        self.contact_count.setRange(3, 20)
        self.contact_count.setValue(10)
        form.addRow("Contact count", self.contact_count)
        self.endpoint_status = QLabel("Mesial: unset\nLateral: unset")
        form.addRow(self.endpoint_status)
        for title, action in [
            ("Set mesial endpoint", lambda: self.set_endpoint("mesial")),
            ("Set lateral endpoint", lambda: self.set_endpoint("lateral")),
            ("Add electrode", self._add),
            ("Remove selected electrode", self.remove_electrode),
        ]:
            button = QPushButton(title)
            button.clicked.connect(action)
            controls.addWidget(button)
        self.electrodes = QListWidget()
        controls.addWidget(self.electrodes)
        self.figure = Figure(layout="constrained")
        self.canvas = PlotCanvas(self.figure)
        layout.addWidget(self.canvas, 1)
        self.canvas.mpl_connect("button_press_event", self._click)
        self.axes: list[Any] = []
        self.redisplay()

    def open_image(self, path: Path) -> None:
        image = load_spatial_mm(path)
        data = np.asanyarray(image.dataobj)
        finite = data[np.isfinite(data)]
        if not finite.size:
            raise ValueError("Image contains no finite intensities")
        self.image_data = data
        self.image_limits = tuple(np.percentile(finite, [1, 99]).tolist())
        # Keep original array orientation; conversion to RAS happens through affine.
        self.volume = image
        self.overlay = None
        self.overlay_data = None
        self.overlay_visible.blockSignals(True)
        self.overlay_visible.setChecked(False)
        self.overlay_visible.blockSignals(False)
        self.session = ImagingSession(
            native_image=path.resolve(), native_sha256=sha256(path)
        )
        self.mesial = self.lateral = None
        self.endpoint_status.setText("Mesial: unset\nLateral: unset")
        self.electrodes.clear()
        for i, box in enumerate(self.voxel_controls):
            box.blockSignals(True)
            box.setRange(0, image.shape[i] - 1)
            box.setValue(image.shape[i] // 2)
            box.blockSignals(False)
        self.status.setText(
            f"{path.name} | native RAS mm | acquired contacts are not MNI coordinates"
        )
        self.redisplay()

    def open_overlay(self, path: Path) -> None:
        from nibabel.processing import resample_from_to

        if not self.session:
            raise ValueError("Open the native image first")
        image = load_spatial_mm(path)
        # Resampling honors physical coordinates; it does not estimate registration.
        self.overlay = resample_from_to(image, self.volume, order=1)
        self.overlay_data = np.asanyarray(self.overlay.dataobj)
        self.session = self.session.model_copy(
            update=dict(overlay_image=path.resolve(), overlay_sha256=sha256(path))
        )
        self.overlay_visible.setChecked(True)
        self.redisplay()

    def current_ras(self) -> tuple[float, float, float]:
        if self.volume is None:
            raise ValueError("Open an image first")
        value = voxel_to_world(
            np.array([[b.value() for b in self.voxel_controls]], dtype=float),
            self.volume.affine,
        )[0]
        return float(value[0]), float(value[1]), float(value[2])

    def set_endpoint(self, endpoint: str) -> None:
        if self.volume is None:
            return
        if endpoint == "mesial":
            self.mesial = self.current_ras()
        else:
            self.lateral = self.current_ras()
        self.endpoint_status.setText(
            f"Mesial RAS: {self.mesial}\nLateral RAS: {self.lateral}"
        )

    def add_electrode(self) -> None:
        if not self.session or self.mesial is None or self.lateral is None:
            raise ValueError("Set both endpoints before adding an electrode")
        electrode = Electrode(
            name=self.electrode_name.text().strip(),
            mesial_ras_mm=self.mesial,
            lateral_ras_mm=self.lateral,
            contacts=self.contact_count.value(),
        )
        if electrode.name in [e.name for e in self.session.electrodes]:
            raise ValueError(
                "Electrode name already exists; remove it explicitly before reacquiring"
            )
        self.session = self.session.model_copy(
            update=dict(electrodes=(*self.session.electrodes, electrode))
        )
        self.electrodes.addItem(f"{electrode.name}: {electrode.contacts} contacts")
        self.redisplay()

    def remove_electrode(self) -> None:
        index = self.electrodes.currentRow()
        if self.session and index >= 0:
            self.session = self.session.model_copy(
                update=dict(
                    electrodes=tuple(
                        e for i, e in enumerate(self.session.electrodes) if i != index
                    )
                )
            )
            self.electrodes.takeItem(index)
            self.redisplay()

    def redisplay(self) -> None:
        self.figure.clear()
        self.axes = []
        if self.volume is None:
            self.canvas.draw_idle()
            return
        index = [b.value() for b in self.voxel_controls]
        self.cursor_label.setText(
            "RAS mm: " + ", ".join(f"{v:.2f}" for v in self.current_ras())
        )
        arrays = self.image_data
        lo, hi = self.image_limits
        for axis in range(3):
            axes = self.figure.add_subplot(1, 3, axis + 1)
            self.axes.append(axes)
            other = [i for i in range(3) if i != axis]
            axes.imshow(
                np.take(arrays, index[axis], axis=axis).T,
                origin="lower",
                cmap="gray",
                vmin=lo,
                vmax=hi,
            )
            if self.overlay is not None and self.overlay_visible.isChecked():
                axes.imshow(
                    np.take(self.overlay_data, index[axis], axis=axis).T,
                    origin="lower",
                    cmap="magma",
                    alpha=0.4,
                )
            spacing = np.linalg.norm(self.volume.affine[:3, :3], axis=0)
            axes.set_aspect(spacing[other[1]] / spacing[other[0]])
            axes.axvline(index[other[0]], color="lime", linewidth=0.6)
            axes.axhline(index[other[1]], color="lime", linewidth=0.6)
            axes.set(
                xlabel=f"Voxel {'ijk'[other[0]]}",
                ylabel=f"Voxel {'ijk'[other[1]]}",
                title=f"{'ijk'[axis]} = {index[axis]}",
            )
            if self.session:
                for electrode in self.session.electrodes:
                    voxels = world_to_voxel(
                        np.array(electrode.positions()), self.volume.affine
                    )
                    near = np.abs(voxels[:, axis] - index[axis]) <= 0.75
                    axes.scatter(
                        voxels[near, other[0]],
                        voxels[near, other[1]],
                        s=18,
                        label=electrode.name,
                    )
        self.canvas.draw_idle()

    def _click(self, event: Any) -> None:
        if event.inaxes not in self.axes or event.xdata is None or event.ydata is None:
            return
        axis = self.axes.index(event.inaxes)
        others = [i for i in range(3) if i != axis]
        for i, value in zip(others, [event.xdata, event.ydata], strict=True):
            self.voxel_controls[i].setValue(int(np.floor(value + 0.5)))

    def _choose(self, action: Any) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open image", filter="Images (*.nii *.nii.gz *.img)"
        )
        if path:
            try:
                action(Path(path))
            except (OSError, ValueError, ImportError) as error:
                QMessageBox.warning(self, "Image input", str(error))

    def _open(self) -> None:
        self._choose(self.open_image)

    def _overlay(self) -> None:
        self._choose(self.open_overlay)

    def _add(self) -> None:
        try:
            self.add_electrode()
        except ValueError as error:
            QMessageBox.warning(self, "Electrode acquisition", str(error))

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load imaging session", filter="JSON (*.json)"
        )
        if path:
            try:
                session = load_session(Path(path))
                self.open_image(session.native_image)
                if session.overlay_image:
                    self.open_overlay(session.overlay_image)
                self.session = session
                self.electrodes.addItems(
                    [f"{e.name}: {e.contacts} contacts" for e in session.electrodes]
                )
                self.redisplay()
            except (OSError, ValueError, ImportError) as error:
                QMessageBox.warning(self, "Imaging session", str(error))

    def _save(self) -> None:
        if self.session:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save new imaging session", filter="JSON (*.json)"
            )
            if path:
                try:
                    save_session(Path(path), self.session)
                except (OSError, ValueError) as error:
                    QMessageBox.warning(self, "Imaging session", str(error))
