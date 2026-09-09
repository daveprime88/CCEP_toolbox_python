import numpy as np
import pytest

pytest.importorskip("PySide6")
from ccep.analysis import AnalysisResult
from ccep.gui.rankings import RankingsViewer
from ccep.gui.results import ResultsViewer

pytestmark = pytest.mark.gui


def test_rank_sort_train_selection_and_channel_selection(qtbot):
    metrics = (
        "zscore",
        "rms_mean_rank",
        "rms_median_rank",
        "rms_mean_qv",
        "rms_median_qv",
    )
    arrays = {
        f"t{ti}_score_{metric}": np.array([0.8, 0.2] if ti == 0 else [0, 1.0])
        for ti in range(2)
        for metric in metrics
    }
    for ti in range(2):
        arrays[f"t{ti}_offsets"] = np.arange(3.0)
        for ci in range(2):
            arrays[f"t{ti}_c{ci}_erp"] = np.zeros((6, 3))
            arrays[f"t{ti}_c{ci}_rms"] = np.ones(6)
            arrays[f"t{ti}_c{ci}_std"] = np.ones(6)
    result = AnalysisResult(
        dict(
            channels=[dict(label=n, sampling_hz=1000, unit="uV") for n in ("A1", "A2")],
            trains=[dict(name=n, pulse_samples=list(range(6))) for n in ("T1", "T2")],
            config=dict(
                reference="unipolar",
                recording="synthetic.edf",
                scoring=dict(
                    sites={n: dict(anatomical="Left A") for n in ("A1", "A2")},
                    distances_mm={
                        t: {n: 20 for n in ("A1", "A2")} for t in ("T1", "T2")
                    },
                ),
            ),
            eligibility={},
        ),
        arrays,
    )
    parent = ResultsViewer(result)
    window = RankingsViewer(parent)
    qtbot.addWidget(parent)
    qtbot.addWidget(window)
    window.show()
    assert window.table.item(0, 0).text() == "A1"
    window.trains.item(1).setSelected(True)
    assert window.table.item(0, 0).text() == "A2"
    rect = window.table.visualItemRect(window.table.item(0, 0))
    from PySide6.QtCore import Qt

    qtbot.mouseClick(
        window.table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
    )
    assert [item.text() for item in parent.channels.selectedItems()] == ["A2"]
    window.trains.clearSelection()
    assert window.table.rowCount() == 0
