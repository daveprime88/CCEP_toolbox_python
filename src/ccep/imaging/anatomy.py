"""Source-derived CCEP contact sampling independent of SPM viewer callbacks.

Preserves sample multiplicity and single-precision staging. SPM display-text
rounding still requires captured fixtures; these functions do not claim that GUI
numeric formatting is reproduced.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from ccep.imaging.geometry import _points, sample_nearest
from ccep.models import FloatArray


def legacy_rotation(points: FloatArray, angles: FloatArray) -> FloatArray:
    """RotationalAffine: row vectors right-multiply Rx Ry Rz; legacy degree rule."""
    points = _points(points)
    angles = np.asarray(angles, dtype=float)
    if angles.shape != (3,) or not np.isfinite(angles).all():
        raise ValueError("Expected three finite rotation angles")
    if np.max(np.abs(angles)) > 2 * np.pi:
        angles = np.deg2rad(angles)
    x, y, z = angles
    rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    return points @ rx @ ry @ rz


def legacy_shape(
    kind: Literal["cylinder", "cube", "rectangle", "cloud"],
    centre: FloatArray,
    normal: FloatArray,
    *,
    radius_mm: float = 2,
    captured_cloud_offsets: FloatArray | None = None,
) -> FloatArray:
    centre = _points(np.asarray(centre).reshape(1, 3))[0]
    normal = _points(np.asarray(normal).reshape(1, 3))[0]
    if np.linalg.norm(normal) == 0 or not np.isfinite(radius_mm) or radius_mm <= 0:
        raise ValueError("Shape needs a nonzero direction and positive radius")
    if kind == "cloud":
        if captured_cloud_offsets is None:
            raise ValueError(
                "Legacy random cloud requires captured offsets; a Python seed cannot reproduce MATLAB RNG"
            )
        return _points(captured_cloud_offsets) + centre
    if kind == "cylinder":
        # CCEPTissueProbCalc passes 'Shape', which its cylinder helper ignores.
        # Consequently this compatibility path always uses radius 2 and 11 segments.
        theta = np.linspace(0, 2 * np.pi, 12)
        shape = np.concatenate(
            [
                np.column_stack(
                    [2 * np.cos(theta), 2 * np.sin(theta), np.full(12, height)]
                )
                for height in (-1, 0, 1)
            ]
        )
        shape = legacy_rotation(shape, np.array([0, np.pi / 2, 0]))
    elif kind in {"cube", "rectangle"}:
        shape = np.array(
            [
                [1, 0, 0],
                [1, 1, 0],
                [0, 1, 0],
                [0, 1, 1],
                [0, 0, 1],
                [1, 1, 1],
                [1, 0, 1],
                [0.5, 0.5, 0.5],
                [0, 0, 0],
            ],
            dtype=float,
        )
        shape = shape * radius_mm * 2 - 1
        if kind == "rectangle":
            shape[:, 0] *= 1.5
    else:
        raise ValueError("Unknown legacy contact shape")
    elevation = np.arcsin(normal[2] / np.linalg.norm(normal))
    azimuth = -np.arctan2(normal[1], normal[0])
    return legacy_rotation(shape, np.array([0, elevation, azimuth])) + centre


def tissue_samples(
    maps: list[FloatArray], affine: FloatArray, points_ras_mm: FloatArray
) -> dict[str, object]:
    points = _points(points_ras_mm)
    if len(maps) != 3 or len(points) == 0:
        raise ValueError(
            "Provide GM, WM, CSF maps and a nonempty list of native samples"
        )
    if any(
        m.shape != maps[0].shape
        or not np.isfinite(m).all()
        or (m < 0).any()
        or (m > 1).any()
        for m in maps
    ):
        raise ValueError(
            "Tissue maps must share a grid and contain probabilities in [0,1]"
        )
    values = np.column_stack([sample_nearest(m, affine, points) for m in maps]).astype(
        np.float32
    )
    return dict(
        classes=["gray_matter", "white_matter", "csf"],
        sample_count=len(points),
        samples=values.tolist(),
        mean=values.mean(axis=0, dtype=np.float32).tolist(),
        precision="float32 samples and mean; SPM display-string rounding unverified",
    )


def atlas_lookup(
    data: FloatArray,
    affine: FloatArray,
    centre_ras_mm: FloatArray,
    labels: dict[int, str],
    *,
    mode: Literal["exact", "legacy-closest-absolute"] = "exact",
    native_sample_count: int = 1,
) -> dict[str, object]:
    if not labels or any(not label for label in labels.values()):
        raise ValueError(
            "Supply a nonempty explicit atlas ID/name table with nonempty names"
        )
    if native_sample_count < 1 or mode not in {"exact", "legacy-closest-absolute"}:
        raise ValueError("Invalid lookup mode or native sample count")
    sampled = float(
        np.float32(
            sample_nearest(data, affine, np.asarray(centre_ras_mm).reshape(1, 3))[0]
        )
    )
    if not np.isfinite(sampled):
        raise ValueError("Atlas sample is nonfinite")
    if mode == "exact":
        region = int(np.sign(sampled) * np.floor(abs(sampled) + 0.5))
    else:
        indexes = list(labels)
        region = indexes[int(np.argmin(np.abs(np.abs(indexes) - abs(sampled))))]
    if region == 0:
        name, frequency = "OUT", 1.0
    elif region not in labels:
        raise ValueError(f"Atlas ID {region} is absent from the supplied table")
    else:
        name = labels[region]
        frequency = (
            1 / native_sample_count if mode == "legacy-closest-absolute" else 1.0
        )
    return dict(
        index=region,
        label=name,
        sampled_value=sampled,
        legacy_frequency=frequency,
        mode=mode,
        note="Frequency is the legacy output convention, not statistical confidence",
    )
