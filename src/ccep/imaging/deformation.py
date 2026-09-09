"""Full pull-field geometry and volume modulation, independent of SPM algorithms.

Density = native probability evaluated at T(target) times det(DT). T includes
all affine and nonlinear components. This is a continuum change of variables,
not SPM's discrete push/splat writer and not an ordinary probability image.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ccep.imaging.geometry import spm_pull_resample
from ccep.imaging.transforms import load_bundle, read_ants_mm, resolve_steps
from ccep.models import FloatArray


def full_pull_field(
    bundle_path: Path, native: Path, target: Path, output: Path
) -> FloatArray:
    """Compose every moving→fixed image step; return absolute native RAS mm."""
    from ccep.imaging.ants_backend import _ants

    if output.exists():
        raise FileExistsError(output)
    if not str(output).endswith(".nii.gz"):
        raise ValueError("Composite displacement output must end in .nii.gz")
    bundle = load_bundle(bundle_path)
    bundle.moving_grid.check(native)
    bundle.fixed_grid.check(target)
    paths, invert = resolve_steps(bundle.forward, bundle_path.parent)
    output.parent.mkdir(parents=True, exist_ok=True)
    # ANTs appends 'comptx.nii.gz' to a compose prefix. Stage beside the output.
    import tempfile

    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        composed = _ants().apply_transforms(
            fixed=read_ants_mm(target),
            moving=read_ants_mm(native),
            transformlist=paths,
            whichtoinvert=invert,
            compose=str(Path(temporary) / "full_"),
        )
        image = _ants().image_read(composed)
        field = np.asarray(image.numpy(), dtype=float) * [-1, -1, 1]
        if field.shape != (*bundle.fixed_grid.shape, 3) or not np.isfinite(field).all():
            raise ValueError("Invalid composed displacement field")
        # Save the backend displacement unchanged; returned array has a distinct,
        # explicit absolute-RAS convention for portable calculations below.
        Path(composed).rename(output)
    affine = np.asarray(bundle.fixed_grid.affine)
    for axis in range(3):
        positions = np.arange(bundle.fixed_grid.shape[axis])
        shape = [1, 1, 1, 1]
        shape[axis] = len(positions)
        field += positions.reshape(shape) * affine[:3, axis]
    field += affine[:3, 3]
    return field


def pull_jacobian(
    absolute_ras_field: FloatArray, target_affine: FloatArray
) -> FloatArray:
    """Signed det d(native RAS)/d(target RAS), including affine scale and shear.

    Central finite differences in the interior; one-sided differences at edges.
    Negative determinants are retained so folds cannot hide behind clipping/logs.
    """
    field = np.asarray(absolute_ras_field, dtype=float)
    affine = np.asarray(target_affine, dtype=float)
    if (
        field.ndim != 4
        or field.shape[-1] != 3
        or min(field.shape[:3]) < 2
        or not np.isfinite(field).all()
    ):
        raise ValueError(
            "Expected a finite absolute RAS field with at least two voxels per axis"
        )
    if (
        affine.shape != (4, 4)
        or not np.isfinite(affine).all()
        or not np.allclose(affine[3], [0, 0, 0, 1])
        or abs(np.linalg.det(affine[:3, :3])) < 1e-12
    ):
        raise ValueError("Expected a finite nonsingular target affine")
    derivative = np.empty((*field.shape[:3], 3, 3), dtype=float)
    for component in range(3):
        for axis in range(3):
            derivative[..., component, axis] = np.gradient(
                field[..., component], axis=axis
            )
    derivative = derivative @ np.linalg.inv(affine[:3, :3])
    return np.asarray(np.linalg.det(derivative), dtype=float)


def modulated_density(
    native_probability: FloatArray,
    native_affine: FloatArray,
    absolute_ras_field: FloatArray,
    target_affine: FloatArray,
) -> tuple[FloatArray, FloatArray]:
    values = np.asarray(native_probability, dtype=float)
    if (
        values.ndim != 3
        or not np.isfinite(values).all()
        or (values < 0).any()
        or (values > 1).any()
    ):
        raise ValueError("Native tissue input must contain probabilities in [0,1]")
    jacobian = pull_jacobian(absolute_ras_field, target_affine)
    if (jacobian <= 0).any():
        raise ValueError(
            "Nonpositive full-pull Jacobian: folding/singular mapping requires review"
        )
    warped = spm_pull_resample(values, native_affine, absolute_ras_field)
    return warped * jacobian, jacobian


def spm_one_based_affine(matrix: FloatArray) -> FloatArray:
    """Convert a captured SPM V.mat to zero-based voxels; not for NiBabel affines."""
    from ccep.imaging.geometry import voxel_to_world

    matrix = np.asarray(matrix, dtype=float)
    voxel_to_world(np.zeros((1, 3)), matrix)  # Validate the homogeneous affine.
    shift = np.eye(4)
    shift[:3, 3] = 1
    return matrix @ shift
