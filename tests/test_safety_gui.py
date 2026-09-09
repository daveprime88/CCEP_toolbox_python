import numpy as np
import pytest

pytest.importorskip("PySide6")
from ccep.gui.safety import SafetyViewer  # noqa: E402

pytestmark = pytest.mark.gui


def test_geometry_controls_update_curve(qtbot):
    view = SafetyViewer()
    qtbot.addWidget(view)
    view.inputs["diameter"].setValue(2)
    view.inputs["length"].setValue(3)
    widths = view.axes.lines[0].get_xdata()
    np.testing.assert_allclose(
        view.axes.lines[0].get_ydata(), 57 * np.pi * 0.2 * 0.3 / widths
    )
    view.electrode_geometry.setCurrentIndex(1)
    assert not view.inputs["length"].isEnabled()
    np.testing.assert_allclose(
        view.axes.lines[0].get_ydata(), 57 * np.pi * 0.1**2 / widths
    )
