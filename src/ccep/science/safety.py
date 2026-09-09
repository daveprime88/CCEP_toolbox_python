"""Historical CCEPSafetyEstimate geometry/calculation, without recommendations."""

from dataclasses import dataclass
from math import isfinite, pi
from typing import Literal


@dataclass(frozen=True)
class StimulationEstimate:
    area_cm2: float
    charge_microcoulomb: float
    charge_density_microcoulomb_cm2: float


def stimulation_estimate(
    geometry: Literal["depth", "disc"],
    diameter_mm: float,
    length_mm: float,
    current_ma: float,
    pulse_width_ms: float,
) -> StimulationEstimate:
    values = (diameter_mm, length_mm, current_ma, pulse_width_ms)
    if (
        not all(isfinite(v) for v in values)
        or diameter_mm <= 0
        or current_ma < 0
        or pulse_width_ms < 0
    ):
        raise ValueError("Invalid electrode/stimulation dimensions")
    if geometry == "depth":
        if length_mm <= 0:
            raise ValueError("Depth contact length must be positive")
        area = pi * diameter_mm / 10 * length_mm / 10
    elif geometry == "disc":
        area = pi * (diameter_mm / 20) ** 2
    else:
        raise ValueError("Geometry must be depth or disc")
    charge = current_ma * pulse_width_ms
    return StimulationEstimate(area, charge, charge / area)
