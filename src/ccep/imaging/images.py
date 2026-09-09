"""Spatial-image boundary: geometry used by this port is explicitly millimetres."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from nibabel.spatialimages import SpatialImage


def load_spatial_mm(path: Path) -> SpatialImage:
    import nibabel as nib
    from nibabel.spatialimages import SpatialImage

    image = nib.load(path)
    if not isinstance(image, SpatialImage) or image.affine is None:
        raise ValueError("Expected an image with voxel-to-world geometry")
    if (
        len(image.shape) != 3
        or not np.isfinite(image.affine).all()
        or abs(np.linalg.det(image.affine[:3, :3])) < 1e-12
    ):
        raise ValueError("Expected a 3D image with finite nonsingular geometry")
    spatial_unit = getattr(
        image.header, "get_xyzt_units", lambda: ("unknown", "unknown")
    )()[0]
    if spatial_unit != "mm":
        raise ValueError(
            "Image must explicitly declare millimetre spatial units; unknown/Analyze/metre units require a reviewed import adapter"
        )
    return image
