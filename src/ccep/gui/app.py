"""SEEG review workflow using the same recording and annotation interfaces as scripts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ccep.analysis import (
    AnalysisResult,
    FilterSettings,
    PulseTrain,
    RunConfig,
    load_result,
    process,
)
from ccep.gui.canvas import PlotCanvas
from ccep.gui.results import ResultsViewer
from ccep.io.annotations import load_annotations, save_annotations
from ccep.io.edf import EDF
from ccep.models import Annotation, AnnotationSet, Channel
from ccep.montage import bipolar, pairs
from ccep.science.signal import (
    apply_legacy_filter,
    legacy_filter_coefficients,
    legacy_trigger_samples,
)


class AnalysisWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, config: RunConfig) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            result = process(self.config, cancelled=self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.completed.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class Viewer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CCEP Toolbox — SEEG review")
        self.resize(1280, 800)
        self.tool_windows: list[QMainWindow] = []
        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction("Stimulation comparisons", self._open_safety)
        tools_menu.addAction("Image review and contacts", self._open_imaging)
        self.recording: EDF | None = None
        self.annotations = AnnotationSet()
        self.sampling_hz = 1.0
        self.dirty = False
        self.worker: AnalysisWorker | None = None
        self.results_windows: list[ResultsViewer] = []
        self.filter_cache: dict[str, Channel] = {}
        self.plotted_channels: list[Channel] = []
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)
        for label, callback in (
            ("Open EDF", self._open),
            ("Load annotations", self._load_annotations),
            ("Save annotations", self._save_annotations),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        self.reference = QComboBox()
        self.reference.addItems(["Unipolar", "Bipolar"])
        toolbar.addWidget(QLabel("Reference"))
        toolbar.addWidget(self.reference)
        self.span = QDoubleSpinBox()
        self.span.setRange(0.1, 300)
        self.span.setValue(10)
        self.span.setSuffix(" s")
        toolbar.addWidget(QLabel("Time span"))
        toolbar.addWidget(self.span)
        self.gain = QDoubleSpinBox()
        self.gain.setRange(0.001, 1e9)
        self.gain.setValue(50)
        toolbar.addWidget(QLabel("Gain (channel units)"))
        toolbar.addWidget(self.gain)
        self.filter_toggle = QCheckBox("Filtered")
        self.filter_toggle.setEnabled(True)
        self.filter_toggle.setToolTip(
            "Source-derived legacy FIR; full-channel filtering may take time"
        )
        toolbar.addWidget(self.filter_toggle)
        splitter = QSplitter()
        layout.addWidget(splitter, 1)
        self.channels = QListWidget()
        self.channels.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.channels.setMinimumWidth(180)
        splitter.addWidget(self.channels)
        self.figure = Figure(layout="constrained")
        self.canvas = PlotCanvas(self.figure)
        self.axes = self.figure.add_subplot()
        splitter.addWidget(self.canvas)
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.addWidget(QLabel("Annotations and pulse times"))
        self.annotation_list = QListWidget()
        editor_layout.addWidget(self.annotation_list)
        self.annotation_sample = QSpinBox()
        self.annotation_sample.setRange(0, 2_147_483_647)
        editor_layout.addWidget(QLabel("Sample offset (zero-based)"))
        editor_layout.addWidget(self.annotation_sample)
        self.annotation_text = QLineEdit()
        editor_layout.addWidget(self.annotation_text)
        self.add_button = QPushButton("Add annotation")
        self.replace_button = QPushButton("Replace annotation")
        self.delete_button = QPushButton("Delete annotation")
        self.pulse_button = QPushButton("Mark pulse at sample")
        self.undo_button = QPushButton("Remove last manual pulse")
        for button in (
            self.add_button,
            self.replace_button,
            self.delete_button,
            self.pulse_button,
            self.undo_button,
        ):
            editor_layout.addWidget(button)
        splitter.addWidget(editor)
        splitter.setSizes([190, 780, 310])
        processing = QHBoxLayout()
        layout.addLayout(processing)
        self.frequency = QDoubleSpinBox()
        self.frequency.setRange(0.01, 1000)
        self.frequency.setValue(0.5)
        self.process_button = QPushButton("Process selected channels and pulses")
        self.cancel_button = QPushButton("Cancel processing")
        self.cancel_button.setEnabled(False)
        open_results = QPushButton("Open result")
        acquire = QPushButton("Acquire pulses from selected raw channel")
        processing.addWidget(QLabel("Train frequency (Hz)"))
        processing.addWidget(self.frequency)
        processing.addWidget(self.process_button)
        processing.addWidget(self.cancel_button)
        processing.addWidget(open_results)
        processing.addWidget(acquire)
        self.process_button.clicked.connect(self._process)
        self.cancel_button.clicked.connect(self._cancel)
        open_results.clicked.connect(self._open_result)
        acquire.clicked.connect(lambda: self._guard(self._acquire_pulses))
        self.filter_toggle.toggled.connect(self.redisplay)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        layout.addWidget(self.slider)
        self.status = QLabel(
            "Open an EDF to begin. Development port; MATLAB comparison pending."
        )
        layout.addWidget(self.status)
        self.reference.currentTextChanged.connect(self._populate_channels)
        self.channels.itemSelectionChanged.connect(self.redisplay)
        self.span.valueChanged.connect(self.redisplay)
        self.gain.valueChanged.connect(self.redisplay)
        self.slider.valueChanged.connect(self.redisplay)
        self.annotation_list.currentRowChanged.connect(self._select_annotation)
        self.add_button.clicked.connect(lambda: self._edit("add"))
        self.replace_button.clicked.connect(lambda: self._edit("replace"))
        self.delete_button.clicked.connect(lambda: self._edit("delete"))
        self.pulse_button.clicked.connect(self._mark_pulse)
        self.undo_button.clicked.connect(self._undo_pulse)
        self.canvas.mpl_connect("button_press_event", self._click_plot)

    def _guard(self, callback: Any) -> None:
        try:
            callback()
        except (OSError, ValueError, IndexError) as error:
            self.status.setText(str(error))
            QMessageBox.warning(self, "Cannot complete action", str(error))

    def _discard_edits(self) -> bool:
        return (
            not self.dirty
            or QMessageBox.question(
                self, "Unsaved annotations", "Discard unsaved annotation/pulse edits?"
            )
            == QMessageBox.StandardButton.Yes
        )

    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open recording", filter="EDF (*.edf)"
        )
        if path and self._discard_edits():
            self._guard(lambda: self.open_recording(Path(path)))

    def open_recording(self, path: Path) -> None:
        recording = EDF(path)
        if not recording.channels:
            raise ValueError("EDF contains no signal channels")
        rate = recording.channels[0].samples_per_record / recording.record_seconds
        annotations = AnnotationSet(recording.annotations(rate))
        self.recording, self.sampling_hz, self.annotations = (
            recording,
            rate,
            annotations,
        )
        self.dirty = False
        self.filter_cache.clear()
        self.slider.setRange(
            0, max(0, int(recording.records * recording.record_seconds * 1000) - 1)
        )
        self.slider.setValue(0)
        self.annotation_sample.setMaximum(
            max(0, round(recording.records * recording.record_seconds * rate) - 1)
        )
        self._populate_channels()
        self._refresh_annotations()
        self.status.setText(
            f"{path} | {rate:g} Hz annotation timebase | {self.reference.currentText()} reference"
        )

    def _populate_channels(self) -> None:
        self.filter_cache.clear()
        self.channels.blockSignals(True)
        self.channels.clear()
        if self.recording:
            labels = [s.label for s in self.recording.channels]
            if self.reference.currentText() == "Bipolar":
                labels = [p[0] for p in pairs(labels)]
            self.channels.addItems(labels)
            if labels:
                self.channels.item(0).setSelected(True)
        self.channels.blockSignals(False)
        if self.recording:
            self.status.setText(
                f"{self.recording.path} | {self.sampling_hz:g} Hz annotation timebase | {self.reference.currentText()} reference"
            )
        self.redisplay()

    def redisplay(self) -> None:
        self.axes.clear()
        self.plotted_channels = []
        if self.recording:
            start_seconds = self.slider.value() / 1000
            mappings = {
                p[0]: p[1:] for p in pairs([s.label for s in self.recording.channels])
            }
            for item in self.channels.selectedItems():
                label = item.text()

                def read(name: str) -> Channel:
                    assert self.recording is not None
                    header = next(s for s in self.recording.channels if s.label == name)
                    rate = header.samples_per_record / self.recording.record_seconds
                    end = min(
                        self.recording.records * header.samples_per_record,
                        int((start_seconds + self.span.value()) * rate),
                    )
                    return self.recording.read(name, int(start_seconds * rate), end)

                try:
                    channel = (
                        bipolar(
                            read(mappings[label][0]), read(mappings[label][1]), label
                        )
                        if label in mappings
                        and self.reference.currentText() == "Bipolar"
                        else read(label)
                    )
                    if self.filter_toggle.isChecked():
                        if label not in self.filter_cache:
                            if self.reference.currentText() == "Bipolar":
                                full = bipolar(
                                    self.recording.read(mappings[label][0]),
                                    self.recording.read(mappings[label][1]),
                                    label,
                                )
                            else:
                                full = self.recording.read(label)
                            band, notch = legacy_filter_coefficients(full.sampling_hz)
                            values = apply_legacy_filter(
                                full.samples,
                                (
                                    (band, notch)
                                    if self.reference.currentText() == "Unipolar"
                                    else (band,)
                                ),
                            )
                            self.filter_cache[label] = Channel(
                                label, values, full.sampling_hz, full.unit
                            )
                        full = self.filter_cache[label]
                        start = int(start_seconds * full.sampling_hz)
                        channel = Channel(
                            label,
                            full.samples[start : start + len(channel.samples)],
                            full.sampling_hz,
                            full.unit,
                        )
                except (ValueError, OSError) as error:
                    self.status.setText(str(error))
                    continue
                self.plotted_channels.append(channel)
                index = len(self.plotted_channels) - 1
                times = (
                    np.arange(channel.samples.size) / channel.sampling_hz
                    + start_seconds
                )
                self.axes.plot(
                    times,
                    channel.samples / self.gain.value() - index * 3,
                    linewidth=0.7,
                    label=f"{label} ({channel.unit})",
                )
            for annotation in self.annotations.annotations:
                time = annotation.sample / self.sampling_hz
                if start_seconds <= time <= start_seconds + self.span.value():
                    self.axes.axvline(time, color="#b83232", linewidth=0.8)
                    self.axes.text(
                        time,
                        0.98,
                        annotation.text,
                        transform=self.axes.get_xaxis_transform(),
                        rotation=90,
                        va="top",
                        fontsize=8,
                    )
            for sample in self.annotations.pulses:
                time = sample / self.sampling_hz
                if start_seconds <= time <= start_seconds + self.span.value():
                    self.axes.axvline(time, color="black", linewidth=0.8)
            self.axes.set_xlim(start_seconds, start_seconds + self.span.value())
            if self.plotted_channels:
                self.axes.legend(loc="upper right")
        self.axes.set_xlabel("Time (s)")
        self.axes.set_ylabel("Amplitude / selected gain + channel offset")
        self.axes.set_title(f"{self.reference.currentText()} reference")
        self.axes.grid(True, alpha=0.2)
        self.canvas.draw_idle()

    def _refresh_annotations(self) -> None:
        self.annotation_list.clear()
        self.annotation_list.addItems(
            [
                f"{a.sample / self.sampling_hz:.3f} s — {a.text}"
                for a in self.annotations.annotations
            ]
        )

    def _select_annotation(self, row: int) -> None:
        if 0 <= row < len(self.annotations.annotations):
            annotation = self.annotations.annotations[row]
            self.annotation_text.setText(annotation.text)
            self.annotation_sample.setValue(annotation.sample)
            self.slider.setValue(
                max(
                    0,
                    int(
                        (annotation.sample / self.sampling_hz - self.span.value() / 2)
                        * 1000
                    ),
                )
            )

    def _edit(self, operation: str) -> None:
        if not self.recording:
            return
        index = self.annotation_list.currentRow()
        if operation != "add" and index < 0:
            return
        if operation == "delete":
            self.annotations.annotations.pop(index)
            if index < len(self.annotations.legacy_fields):
                self.annotations.legacy_fields.pop(index)
        else:
            annotation = Annotation(
                sample=self.annotation_sample.value(), text=self.annotation_text.text()
            )
            if operation == "add":
                self.annotations.annotations.append(annotation)
                self.annotations.legacy_fields.extend(
                    {}
                    for _ in range(
                        len(self.annotations.annotations)
                        - len(self.annotations.legacy_fields)
                    )
                )
            else:
                self.annotations.annotations[index] = self.annotations.annotations[
                    index
                ].model_copy(
                    update={"sample": annotation.sample, "text": annotation.text}
                )
        self.dirty = True
        self._refresh_annotations()
        self.redisplay()

    def _mark_pulse(self) -> None:
        if self.recording:
            self.annotations.manual_pulses.append(self.annotation_sample.value())
            self.dirty = True
            self.redisplay()

    def _undo_pulse(self) -> None:
        if self.annotations.manual_pulses:
            self.annotations.manual_pulses.pop()
            self.dirty = True
            self.redisplay()

    def _click_plot(self, event: Any) -> None:
        if event.inaxes == self.axes and event.xdata is not None:
            self.annotation_sample.setValue(
                int(np.floor(event.xdata * self.sampling_hz + 0.5))
            )

    def _load_annotations(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load annotations", filter="Annotations (*.mat *.json)"
        )
        if path and self._discard_edits():
            self._guard(lambda: self.open_annotations(Path(path)))

    def open_annotations(self, path: Path) -> None:
        data = load_annotations(path)
        if not self.recording:
            raise ValueError("Open a recording before its annotations")
        limit = self.annotation_sample.maximum()
        if any(
            sample > limit
            for sample in [a.sample for a in data.annotations] + data.pulses
        ):
            raise ValueError("Annotations/pulses lie outside this recording")
        self.annotations = data
        self.dirty = False
        self._refresh_annotations()
        self.redisplay()

    def _save_annotations(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save annotations", filter="MAT (*.mat);;JSON (*.json)"
        )
        if path:
            self._guard(lambda: self.write_annotations(Path(path), overwrite=True))

    def write_annotations(self, path: Path, *, overwrite: bool = False) -> None:
        save_annotations(path, self.annotations, overwrite=overwrite)
        self.dirty = False
        self.status.setText(f"Saved {path}")

    def _open_imaging(self) -> None:
        from ccep.gui.imaging import ImagingViewer

        window = ImagingViewer()
        self.tool_windows.append(window)
        window.show()

    def _open_safety(self) -> None:
        from ccep.gui.safety import SafetyViewer

        window = SafetyViewer()
        self.tool_windows.append(window)
        window.show()

    def _acquire_pulses(self) -> None:
        if (
            not self.recording
            or self.reference.currentText() != "Unipolar"
            or len(self.channels.selectedItems()) != 1
        ):
            raise ValueError("Select one raw unipolar trigger channel")
        channel = self.recording.read(self.channels.selectedItems()[0].text())
        if channel.sampling_hz != self.sampling_hz:
            raise ValueError("Trigger and annotation timebases differ")
        self.annotations.automatic_pulses.extend(
            legacy_trigger_samples(channel.samples).tolist()
        )
        self.dirty = True
        self.redisplay()

    def _process(self) -> None:
        if not self.recording:
            return

        def start() -> None:
            assert self.recording is not None
            config = RunConfig(
                recording=self.recording.path,
                reference=(
                    "unipolar"
                    if self.reference.currentText() == "Unipolar"
                    else "bipolar"
                ),
                channels=[item.text() for item in self.channels.selectedItems()],
                trains=[
                    PulseTrain(
                        name="Selected pulses",
                        frequency_hz=self.frequency.value(),
                        pulse_samples=self.annotations.pulses.copy(),
                    )
                ],
                filtering=FilterSettings(enabled=self.filter_toggle.isChecked()),
            )
            self.worker = AnalysisWorker(config)
            self.worker.completed.connect(self._show_result)
            self.worker.failed.connect(self.status.setText)
            self.worker.finished.connect(self._processing_finished)
            self.process_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.status.setText(
                "Processing a snapshot of the current channels, reference, pulses and parameters…"
            )
            self.worker.start()

        self._guard(start)

    def _processing_finished(self) -> None:
        self.process_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def _cancel(self) -> None:
        if self.worker:
            self.worker.requestInterruption()
            self.status.setText(
                "Cancellation requested; waiting for the current calculation to finish."
            )

    def _show_result(self, result: AnalysisResult) -> None:
        window = ResultsViewer(result)
        self.results_windows.append(window)
        window.show()
        self.status.setText(
            "Processing complete. Result window identifies the input snapshot used."
        )

    def _open_result(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open result", filter="CCEP result (*.npz)"
        )
        if path:
            self._guard(lambda: self._show_result(load_result(Path(path))))

    def closeEvent(self, event: Any) -> None:
        if self.worker and self.worker.isRunning():
            self._cancel()
            event.ignore()
            return
        if self._discard_edits():
            event.accept()
        else:
            event.ignore()


def main() -> None:
    application = QApplication.instance() or QApplication(sys.argv)
    viewer = Viewer()
    if len(sys.argv) > 1:
        viewer.open_recording(Path(sys.argv[1]))
    viewer.show()
    application.exec()


if __name__ == "__main__":
    main()
