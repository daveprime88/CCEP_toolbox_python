"""Keep a plot's owning Qt window alive throughout a deferred render."""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from shiboken6 import isValid


class PlotCanvas(FigureCanvasQTAgg):
    def draw(self) -> None:
        if not isValid(self):
            return
        # A queued Matplotlib callback retains the canvas Python wrapper, but Qt
        # owns its C++ widget through the top-level window. GC during Agg rendering
        # can otherwise destroy that owner before FigureCanvasQT calls update().
        owner = self.window()
        super().draw()
        # Keep the owner reference until rendering and the Qt update are complete.
        if not isValid(owner):
            return
