"""Physical geometry independent of an imaging engine or GUI."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates

from ccep.models import FloatArray


def _points(points: FloatArray) -> FloatArray:
    values = np.asarray(points, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3 or not np.isfinite(values).all():
        raise ValueError(
            "Coordinates must be finite (point, xyz) arrays in millimetres"
        )
    return values


def voxel_to_world(points: FloatArray, affine: FloatArray) -> FloatArray:
    points = _points(points)
    affine = np.asarray(affine, dtype=float)
    if (
        affine.shape != (4, 4)
        or not np.isfinite(affine).all()
        or not np.allclose(affine[3], [0, 0, 0, 1])
    ):
        raise ValueError("Expected a finite homogeneous 4x4 voxel-to-RAS affine")
    return points @ affine[:3, :3].T + affine[:3, 3]


def world_to_voxel(points: FloatArray, affine: FloatArray) -> FloatArray:
    return voxel_to_world(points, np.asarray(np.linalg.inv(affine), dtype=np.float64))


def ras_lps(points: FloatArray) -> FloatArray:
    """Symmetric conversion; never reverse array axes to convert world coordinates."""
    return _points(points) * np.array([-1.0, -1.0, 1.0])


def contact_positions(
    start_mm: FloatArray, end_mm: FloatArray, count: int
) -> FloatArray:
    """CCEPEndCoOrdAcquire endpoint interpolation, mesial to lateral."""
    points = _points(np.stack((start_mm, end_mm)))
    if not 3 <= count <= 20:
        raise ValueError("Legacy electrode controls allow 3–20 contacts")
    return np.linspace(points[0], points[1], count)


def sample_nearest(
    data: FloatArray, affine: FloatArray, points_mm: FloatArray
) -> FloatArray:
    """Nearest-neighbour samples; out-of-volume coordinates are errors, not zero tissue."""
    if data.ndim != 3:
        raise ValueError("Expected a three-dimensional image")
    voxels = np.floor(world_to_voxel(points_mm, affine) + 0.5).astype(np.int64)
    if np.any(voxels < 0) or np.any(voxels >= np.asarray(data.shape)):
        raise ValueError("Tissue/atlas sample lies outside the image")
    return np.asarray(data[tuple(voxels.T)], dtype=float)


def sphere(
    shape: tuple[int, int, int],
    affine: FloatArray,
    centre_mm: FloatArray,
    radius_mm: float = 1.5,
) -> NDArray[np.float32]:
    centre = _points(np.asarray(centre_mm).reshape(1, 3))
    if not np.isfinite(radius_mm) or radius_mm <= 0:
        raise ValueError("Sphere radius must be positive")
    voxel_centre = world_to_voxel(centre, affine)[0]
    extent = radius_mm / np.linalg.svd(affine[:3, :3], compute_uv=False).min()
    lower = np.maximum(0, np.floor(voxel_centre - extent).astype(int))
    upper = np.minimum(shape, np.ceil(voxel_centre + extent).astype(int) + 1)
    output = np.zeros(shape, dtype=np.float32)
    if np.any(lower >= upper):
        raise ValueError("Contact sphere does not intersect image")
    grid = np.stack(
        np.meshgrid(
            *(np.arange(a, b) for a, b in zip(lower, upper, strict=True)), indexing="ij"
        ),
        axis=-1,
    )
    points = voxel_to_world(grid.reshape(-1, 3), affine)
    mask = (np.linalg.norm(points - centre, axis=1) <= radius_mm).reshape(
        grid.shape[:3]
    )
    output[tuple(slice(a, b) for a, b in zip(lower, upper, strict=True))] = mask
    if not output.any():
        raise ValueError("No voxel centres lie within contact sphere")
    return output


def warped_roi_centroid(data: FloatArray, affine: FloatArray) -> FloatArray:
    """CCEPROICreateandWarp >=.99 selection, then >=.95 fallback, mean world XYZ."""
    if data.ndim != 3 or not np.isfinite(data).all():
        raise ValueError("Warped ROI must be a finite three-dimensional image")
    coordinates = np.argwhere(data >= 0.99)
    if not len(coordinates):
        coordinates = np.argwhere(data >= 0.95)
    if not len(coordinates):
        raise ValueError("Could not find warped ROI coordinates at legacy thresholds")
    return voxel_to_world(coordinates.astype(float), affine).mean(axis=0)


def spm_pull_resample(
    native: FloatArray,
    native_affine: FloatArray,
    absolute_ras_field: FloatArray,
    *,
    labels: bool = False,
) -> FloatArray:
    """Evaluate an SPM-style absolute pull field, never an ANTs displacement.

    Field shape is (target x,y,z,3): each vector gives native RAS mm at a target
    voxel. The caller supplies/retains the target grid affine separately.
    Native image and deformation roles must be confirmed for each legacy session.
    """
    if (
        native.ndim != 3
        or absolute_ras_field.ndim != 4
        or absolute_ras_field.shape[-1] != 3
    ):
        raise ValueError("Expected native 3D image and target-grid XYZ pull field")
    coordinates = world_to_voxel(absolute_ras_field.reshape(-1, 3), native_affine)
    return np.asarray(
        map_coordinates(
            native,
            coordinates.T,
            order=0 if labels else 1,
            mode="constant",
            cval=0,
            prefilter=False,
        ),
        dtype=float,
    ).reshape(absolute_ras_field.shape[:3])
