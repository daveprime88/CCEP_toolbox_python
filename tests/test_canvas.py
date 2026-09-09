import gc

import pytest

pytest.importorskip("PySide6")
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget
from shiboken6 import isValid

from ccep.gui.canvas import PlotCanvas

pytestmark = pytest.mark.gui


def test_render_retains_native_owner_while_callbacks_release_last_reference(qtbot):
    owners = []

    def create():
        owner = QWidget()
        owners.append(owner)
        canvas = PlotCanvas(Figure())
        QVBoxLayout(owner).addWidget(canvas)
        return canvas

    canvas = create()
    canvas.figure.add_subplot().plot([1, 2, 3])
    observed = []

    def release_owner(_event):
        owners.clear()
        gc.collect()
        observed.append(isValid(canvas))

    canvas.mpl_connect("draw_event", release_owner)
    canvas.draw()
    assert observed and all(observed)
    gc.collect()
