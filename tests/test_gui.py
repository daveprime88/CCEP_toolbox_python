import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt

from ccep.gui.app import Viewer

pytestmark = pytest.mark.gui


def test_select_reference_edit_save_reopen(qtbot, edf_file, tmp_path):
    viewer = Viewer()
    qtbot.addWidget(viewer)
    viewer.open_recording(edf_file)
    viewer.show()
    assert viewer.channels.count() == 2
    viewer.channels.item(1).setSelected(True)
    assert len(viewer.plotted_channels) == 2
    viewer.reference.setCurrentText("Bipolar")
    assert "Bipolar reference" in viewer.status.text()
    assert viewer.channels.item(0).text() == "A1-A2"
    np.testing.assert_array_equal(viewer.plotted_channels[0].samples[:4], [0, 1, 1, 2])
    viewer.annotation_list.setCurrentRow(0)
    viewer.annotation_text.setText("verified start")
    qtbot.mouseClick(viewer.replace_button, Qt.MouseButton.LeftButton)
    viewer.annotation_sample.setValue(5000)
    viewer.annotation_text.setText("new annotation")
    qtbot.mouseClick(viewer.add_button, Qt.MouseButton.LeftButton)
    viewer.annotations.automatic_pulses = [100]
    qtbot.mouseClick(viewer.pulse_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(viewer.undo_button, Qt.MouseButton.LeftButton)
    assert viewer.annotations.pulses == [100]
    path = tmp_path / "edited.mat"
    viewer.write_annotations(path)
    viewer.open_annotations(path)
    assert [a.text for a in viewer.annotations.annotations] == [
        "verified start",
        "new annotation",
    ]
    assert viewer.annotations.pulses == [100]
    viewer.annotation_list.setCurrentRow(1)
    qtbot.mouseClick(viewer.delete_button, Qt.MouseButton.LeftButton)
    assert len(viewer.annotations.annotations) == 1
    viewer.dirty = False


def test_results_selection_plots_the_saved_arrays(qtbot, edf_file):
    from ccep.analysis import FilterSettings, PulseTrain, RunConfig, process
    from ccep.gui.results import ResultsViewer

    result = process(
        RunConfig(
            recording=edf_file,
            reference="unipolar",
            channels=["A1", "A2"],
            trains=[
                PulseTrain(name="T1", frequency_hz=0.5, pulse_samples=[3000, 5000])
            ],
            filtering=FilterSettings(enabled=False),
        )
    )
    view = ResultsViewer(result)
    qtbot.addWidget(view)
    view.channels.item(1).setSelected(True)
    assert len(view.figure.axes) == 2
    np.testing.assert_array_equal(
        view.figure.axes[1].lines[0].get_ydata(),
        result.arrays["t0_c1_erp"].mean(axis=0),
    )
    assert view.table.rowCount() == 2


def test_gui_processing_uses_selected_controls(qtbot, edf_file):
    viewer = Viewer()
    qtbot.addWidget(viewer)
    viewer.open_recording(edf_file)
    viewer.reference.setCurrentText("Bipolar")
    viewer.annotations.manual_pulses = [3000, 5000]
    viewer.frequency.setValue(0.5)
    viewer._process()
    qtbot.waitUntil(lambda: len(viewer.results_windows) == 1, timeout=10000)
    result = viewer.results_windows[0].result
    assert result.metadata["config"]["channels"] == ["A1-A2"]
    assert result.metadata["config"]["reference"] == "bipolar"
    assert result.metadata["trains"][0]["pulse_samples"] == [3000, 5000]
    viewer.worker.wait()
    viewer.results_windows[0].close()
