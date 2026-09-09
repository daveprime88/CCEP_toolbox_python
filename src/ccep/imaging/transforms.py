"""Explicit ANTs image/point direction and portable, verified transform artifacts.

An ANTs image transform is a pull mapping. The same ordered chain applied to
points therefore travels in the opposite anatomical direction. No inversion is
left to ANTs' filename/chain-length heuristics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from ccep.imaging.geometry import ras_lps
from ccep.imaging.images import load_spatial_mm
from ccep.models import FloatArray
from ccep.reference import sha256

Direction = Literal["moving-to-fixed", "fixed-to-moving"]


class TransformStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: Path
    invert: bool = False
    sha256: str


class Grid(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    shape: tuple[int, int, int]
    affine: list[list[float]]

    @classmethod
    def from_image(cls, path: Path) -> Grid:
        image = load_spatial_mm(path)
        return cls(
            shape=(image.shape[0], image.shape[1], image.shape[2]),
            affine=np.asarray(image.affine).tolist(),
        )

    def check(self, path: Path) -> None:
        actual = Grid.from_image(path)
        if actual.shape != self.shape or not np.allclose(
            actual.affine, self.affine, atol=1e-5, rtol=0
        ):
            raise ValueError("Image grid does not match the transform's declared space")


class TransformBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    fixed_grid: Grid
    moving_grid: Grid
    fixed_sha256: str
    moving_sha256: str
    forward: tuple[TransformStep, ...]
    inverse: tuple[TransformStep, ...]

    def steps(
        self, direction: Direction, *, points: bool = False
    ) -> tuple[TransformStep, ...]:
        if direction not in {"moving-to-fixed", "fixed-to-moving"}:
            raise ValueError("Unknown transform direction")
        forward = direction == "moving-to-fixed"
        if points:
            forward = not forward
        return self.forward if forward else self.inverse

    def source_grid(self, direction: Direction) -> Grid:
        return self.moving_grid if direction == "moving-to-fixed" else self.fixed_grid

    def target_grid(self, direction: Direction) -> Grid:
        return self.fixed_grid if direction == "moving-to-fixed" else self.moving_grid


def capture_bundle(
    fixed: Path,
    moving: Path,
    forward: tuple[Path, ...],
    inverse: tuple[Path, ...],
    directory: Path,
) -> TransformBundle:
    def step(path: Path, invert: bool) -> TransformStep:
        return TransformStep(
            path=path.resolve().relative_to(directory.resolve()),
            invert=invert,
            sha256=sha256(path),
        )

    return TransformBundle(
        fixed_grid=Grid.from_image(fixed),
        moving_grid=Grid.from_image(moving),
        fixed_sha256=sha256(fixed),
        moving_sha256=sha256(moving),
        forward=tuple(step(p, False) for p in forward),
        inverse=tuple(step(p, p.suffix == ".mat") for p in inverse),
    )


def load_bundle(path: Path) -> TransformBundle:
    bundle = TransformBundle.model_validate_json(path.read_text())
    # Verify both directions, including unused entries, before any native call.
    resolve_steps(bundle.forward + bundle.inverse, path.parent)
    return bundle


def resolve_steps(
    steps: tuple[TransformStep, ...], directory: Path
) -> tuple[list[str], list[bool]]:
    paths, inversion = [], []
    for step in steps:
        if step.path.is_absolute() or ".." in step.path.parts:
            raise ValueError(
                "Transform artifacts must use relative paths inside their bundle"
            )
        path = (directory / step.path).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Transform artifact escapes its bundle")
        if sha256(path) != step.sha256:
            raise ValueError(f"Transform checksum differs: {step.path}")
        if step.invert and path.suffix != ".mat":
            raise ValueError(
                "Only affine matrix artifacts can be inverted on application"
            )
        paths.append(str(path))
        inversion.append(step.invert)
    return paths, inversion


def read_ants_mm(path: Path) -> Any:
    """Check that ITK and NiBabel agree on the physical geometry; use float pixels."""
    from ccep.imaging.ants_backend import _ants

    image = load_spatial_mm(path)
    if not np.isfinite(np.asarray(image.dataobj)).all():
        raise ValueError("Imaging inputs must contain finite values")
    matrix = np.asarray(image.affine, dtype=float)
    directions = matrix[:3, :3] / np.linalg.norm(matrix[:3, :3], axis=0)
    if not np.allclose(directions.T @ directions, np.eye(3), atol=1e-5):
        raise ValueError(
            "Sheared image geometry requires explicit resampling before ANTs"
        )
    get_qform, get_sform = getattr(image, "get_qform", None), getattr(
        image, "get_sform", None
    )
    if get_qform and get_sform:
        qform, qcode = get_qform(coded=True)
        sform, scode = get_sform(coded=True)
        if qcode and scode and not np.allclose(qform, sform, atol=1e-4, rtol=0):
            raise ValueError(
                "Conflicting NIfTI qform/sform require a reviewed geometry choice"
            )
    result = _ants().image_read(str(path), pixeltype="float")
    actual = np.eye(4)
    actual[:3, :3] = np.diag([-1, -1, 1]) @ result.direction @ np.diag(result.spacing)
    actual[:3, 3] = np.asarray(result.origin) * [-1, -1, 1]
    if tuple(result.shape) != tuple(image.shape) or not np.allclose(
        actual, matrix, atol=1e-4, rtol=0
    ):
        raise ValueError("ANTs and NIfTI readers disagree on image geometry")
    return result


def apply_image(
    bundle_path: Path,
    image: Path,
    reference: Path,
    output: Path,
    *,
    direction: Direction = "moving-to-fixed",
    labels: bool = False,
) -> Path:
    """Apply a saved registration to an associated image, mask, atlas or probability."""
    from ccep.imaging.ants_backend import _ants

    if output.exists():
        raise FileExistsError(output)
    bundle = load_bundle(bundle_path)
    bundle.source_grid(direction).check(image)
    bundle.target_grid(direction).check(reference)
    paths, invert = resolve_steps(bundle.steps(direction), bundle_path.parent)
    fixed, moving = read_ants_mm(reference), read_ants_mm(image)
    values = moving.numpy()
    if labels and (
        not np.equal(values, np.floor(values)).all() or np.abs(values).max() > 2**24
    ):
        raise ValueError(
            "Label images require integer IDs exactly representable in float32"
        )
    warped = _ants().apply_transforms(
        fixed=fixed,
        moving=moving,
        transformlist=paths,
        whichtoinvert=invert,
        interpolator="genericLabel" if labels else "linear",
        defaultvalue=0,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    _ants().image_write(warped, str(output))
    return output


def apply_points(
    bundle_path: Path,
    points_ras_mm: FloatArray,
    *,
    direction: Direction = "moving-to-fixed",
) -> FloatArray:
    """Map finite RAS+ mm points, including the affine-only inverse case."""
    import pandas as pd

    from ccep.imaging.ants_backend import _ants

    lps = ras_lps(points_ras_mm)
    bundle = load_bundle(bundle_path)
    paths, invert = resolve_steps(
        bundle.steps(direction, points=True), bundle_path.parent
    )
    if len(lps) == 0 or not paths:
        return np.array(points_ras_mm, dtype=float, copy=True)
    result = _ants().apply_transforms_to_points(
        3,
        pd.DataFrame(lps, columns=["x", "y", "z"]),
        transformlist=paths,
        whichtoinvert=invert,
    )
    return ras_lps(result[["x", "y", "z"]].to_numpy(dtype=float))
