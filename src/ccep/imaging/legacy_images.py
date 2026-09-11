"""Explicit SPM absolute-coordinate field and header-only reorientation adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ccep.imaging.geometry import spm_pull_resample, voxel_to_world
from ccep.imaging.images import load_spatial_mm
from ccep.imaging.provenance import snapshot_inputs, verify_unchanged
from ccep.io.atomic import atomic_binary
from ccep.models import FloatArray


def load_spm_pull(path: Path) -> tuple[FloatArray, FloatArray]:
    """Read explicitly identified SPM y/iy field: absolute source RAS mm, target grid.

    Accept MATLAB/SPM's (x,y,z,1,3) and portable (x,y,z,3) layouts. Filenames do not
    establish direction; the caller chooses the corresponding source image.
    This never interprets an ANTs LPS displacement as an SPM coordinate field.
    """
    import nibabel as nib
    from nibabel.spatialimages import SpatialImage

    image = nib.load(path)
    if not isinstance(image, SpatialImage) or image.affine is None:
        raise ValueError("Expected spatial deformation image")
    if getattr(image.header, "get_xyzt_units", lambda: (None, None))()[0] != "mm":
        raise ValueError("SPM field must declare millimetre units")
    values = np.asarray(image.get_fdata(), dtype=float)
    if values.ndim == 5 and values.shape[-2:] == (1, 3):
        values = values[..., 0, :]
    if values.ndim != 4 or values.shape[-1] != 3 or not np.isfinite(values).all():
        raise ValueError(
            "Expected finite absolute RAS field of shape (x,y,z,3) or (x,y,z,1,3)"
        )
    affine = np.asarray(image.affine, dtype=float)
    voxel_to_world(np.zeros((1, 3)), affine)
    if abs(np.linalg.det(affine[:3, :3])) < 1e-12:
        raise ValueError("Field geometry is singular")
    return values, affine


def _save(image: Any, path: Path) -> None:
    # Serialize to a private sibling before atomic no-replace publication.
    import tempfile

    import nibabel as nib

    if not str(path).endswith((".nii", ".nii.gz")):
        raise ValueError("Output must be NIfTI (.nii or .nii.gz)")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent) as temporary:
        staged = Path(temporary) / path.name
        nib.save(image, staged)
        with atomic_binary(path) as destination, staged.open("rb") as source:
            import shutil

            shutil.copyfileobj(source, destination)


def apply_spm_pull(
    native: Path, field: Path, output: Path, *, labels: bool = False
) -> Path:
    import nibabel as nib

    if output.exists():
        raise FileExistsError(output)
    inputs = snapshot_inputs([native, field])
    image = load_spatial_mm(native)
    coordinates, affine = load_spm_pull(field)
    values = spm_pull_resample(
        np.asarray(image.get_fdata(), dtype=np.float64),
        np.asarray(image.affine),
        coordinates,
        labels=labels,
    )
    result = nib.Nifti1Image(values, affine)
    result.header.set_xyzt_units("mm")
    verify_unchanged(inputs)
    _save(result, output)
    return output


def reorient_header(image: Path, world_transform: FloatArray, output: Path) -> Path:
    """Apply a caller-supplied rigid RAS-world header change without interpolation."""
    import nibabel as nib

    if output.exists():
        raise FileExistsError(output)
    inputs = snapshot_inputs([image])
    original = load_spatial_mm(image)
    matrix = np.asarray(world_transform, dtype=float)
    voxel_to_world(np.zeros((1, 3)), matrix)
    if not np.allclose(
        matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-6
    ) or not np.isclose(np.linalg.det(matrix[:3, :3]), 1):
        raise ValueError("Header reorientation requires a proper rigid RAS transform")
    affine = matrix @ original.affine
    # Use decoded values and new matching forms; do not reuse stale scaling/forms.
    result = nib.Nifti1Image(np.asarray(original.dataobj), affine)
    result.header.set_xyzt_units("mm")
    result.set_sform(affine, code=1)
    directions = affine[:3, :3] / np.linalg.norm(affine[:3, :3], axis=0)
    if np.allclose(directions.T @ directions, np.eye(3), atol=1e-6):
        result.set_qform(affine, code=1)
    else:
        result.set_qform(
            None, code=0
        )  # qform cannot represent shear; preserve exact sform.
    verify_unchanged(inputs)
    _save(result, output)
    return output


def auto_reorient(
    image: Path, template: Path, output: Path, *, seed: int = 1729
) -> Path:
    """ANTs candidate for AutoReorient: smooth source, fit rigid, update header.

    Preserves original sampling. ANTs rigid fitting replaces SPM affreg's rigid
    regularization and SVD projection; template and optimizer identity remain
    explicit and require outcome comparison.
    """
    import json

    from ccep.imaging.ants_backend import _ants, register
    from ccep.imaging.settings import RegistrationTask, task_settings
    from ccep.imaging.transforms import apply_points, read_ants_mm
    from ccep.reference import sha256

    if output.exists():
        raise FileExistsError(output)
    inputs = snapshot_inputs([image, template])
    native = read_ants_mm(image)
    read_ants_mm(template)
    output.mkdir(parents=True)
    smoothed = _ants().smooth_image(
        native, sigma=12, sigma_in_physical_coordinates=True, FWHM=True
    )
    smooth_path = output / "smoothed_source.nii.gz"
    _ants().image_write(smoothed, str(smooth_path))
    registration = register(
        template,
        smooth_path,
        output / "registration",
        transform="Rigid",
        seed=seed,
        settings=task_settings(RegistrationTask.ct_to_mri),
    )
    probes = np.vstack([np.zeros(3), np.eye(3) * 1000])
    mapped = apply_points(registration.manifest.parent / "transforms.json", probes)
    matrix = np.eye(4)
    linear = ((mapped[1:] - mapped[0]) / 1000).T
    u, _, vh = np.linalg.svd(linear)
    rotation = u @ vh  # Remove float32 point-evaluation noise only.
    if np.linalg.det(rotation) <= 0:
        raise ValueError("Estimated header reorientation contains a reflection")
    matrix[:3, :3] = rotation
    matrix[:3, 3] = mapped[0]
    reoriented = reorient_header(image, matrix, output / "reoriented.nii.gz")
    verify_unchanged(inputs)
    manifest = output / "reorientation.json"
    manifest.write_text(
        json.dumps(
            dict(
                schema_version=1,
                image_sha256=inputs[image],
                template_sha256=inputs[template],
                smoothing_fwhm_mm=12,
                header_ras_matrix=matrix.tolist(),
                interpolation="none in final image",
                output_sha256=sha256(reoriented),
                registration="registration/registration.json",
                acceptance="ANTs candidate; not SPM affreg equivalence",
            ),
            indent=2,
        )
        + "\n"
    )
    return manifest
