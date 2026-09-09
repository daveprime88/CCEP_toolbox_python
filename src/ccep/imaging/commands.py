"""Thin image command adapters; optional imaging libraries import on invocation."""

from __future__ import annotations

import csv
import io
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import typer
from pydantic import BaseModel, ConfigDict

from ccep.imaging.session import load_session
from ccep.io.atomic import atomic_binary
from ccep.reference import sha256


class Transform(StrEnum):
    rigid = "Rigid"
    affine = "Affine"
    syn = "SyN"


class SegmentationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image: Path
    mask: Path
    priors: list[Path]
    class_names: list[str]


def image_inspect(path: Path) -> dict[str, Any]:
    """Inspect NIfTI/Analyze geometry; does not reorient or register the image."""
    import nibabel as nib
    from nibabel.spatialimages import SpatialImage

    image = nib.load(path)
    if not isinstance(image, SpatialImage) or image.affine is None:
        raise ValueError("Expected a spatial image")
    return dict(
        path=str(path.resolve()),
        sha256=sha256(path),
        shape=list(image.shape),
        voxel_to_world=np.asarray(image.affine).tolist(),
        spatial_units=getattr(
            image.header, "get_xyzt_units", lambda: ("unknown", "unknown")
        )()[0],
        axis_codes=list(nib.aff2axcodes(image.affine)),
        voxel_spacing=list(map(float, image.header.get_zooms())),
        coordinate_convention="zero-based voxels; RAS world axes in declared spatial units",
    )


def image_register(
    fixed: Path,
    moving: Path,
    output: Path,
    transform: Transform = Transform.rigid,
    seed: int = 1729,
    settings: Path | None = None,
) -> dict[str, Any]:
    """Register moving into fixed image space with ANTsPy; preserve original images."""
    from ccep.imaging.ants_backend import register

    mode = cast(Literal["Rigid", "Affine", "SyN"], transform.value)
    # Enum validation belongs to the CLI; library validates its own string input.
    from ccep.imaging.settings import RegistrationSettings

    recipe = (
        RegistrationSettings.model_validate_json(settings.read_text())
        if settings
        else None
    )
    result = register(fixed, moving, output, transform=mode, seed=seed, settings=recipe)
    return dict(
        warped=str(result.warped.resolve()),
        transform_bundle=str((output / "transforms.json").resolve()),
        forward_transforms=list(map(str, result.forward_transforms)),
        inverse_transforms=list(map(str, result.inverse_transforms)),
        artifacts=[
            dict(path=str(result.manifest.resolve()), sha256=sha256(result.manifest))
        ],
        scientific_status="ANTs implementation candidate; SPM outcome acceptance pending",
    )


def image_segment(config: Path, output: Path) -> dict[str, Any]:
    """Run N4 and six-prior Atropos from an explicit JSON configuration."""
    from ccep.imaging.ants_backend import segment

    settings = SegmentationConfig.model_validate_json(config.read_text())
    segmentation, probabilities = segment(
        config.parent / settings.image,
        config.parent / settings.mask,
        [config.parent / p for p in settings.priors],
        settings.class_names,
        output,
    )
    paths = [segmentation, *probabilities, output / "segmentation.json"]
    return dict(
        artifacts=[dict(path=str(p.resolve()), sha256=sha256(p)) for p in paths],
        scientific_status="ANTs implementation candidate; six-class SPM outcome acceptance pending",
    )


def image_contacts(session: Path, output: Path) -> dict[str, Any]:
    """Export acquired contacts in native RAS mm from a checksummed imaging session."""
    data = load_session(session)
    if output.suffix.lower() != ".csv":
        raise ValueError("Contact export must be CSV")
    with atomic_binary(output) as binary:
        stream = io.TextIOWrapper(binary, encoding="utf-8", newline="")
        try:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "electrode",
                    "contact",
                    "x_ras_mm",
                    "y_ras_mm",
                    "z_ras_mm",
                    "space",
                    "image_sha256",
                ]
            )
            for electrode in data.electrodes:
                for number, position in enumerate(electrode.positions(), 1):
                    writer.writerow(
                        [
                            electrode.name,
                            number,
                            *position,
                            data.coordinate_space,
                            data.native_sha256,
                        ]
                    )
            stream.flush()
        finally:
            stream.detach()
    return dict(
        artifacts=[dict(path=str(output.resolve()), sha256=sha256(output))],
        contacts=sum(e.contacts for e in data.electrodes),
        coordinate_space=data.coordinate_space,
    )


class MappingDirection(StrEnum):
    moving_to_fixed = "moving-to-fixed"
    fixed_to_moving = "fixed-to-moving"


def image_apply(
    bundle: Path,
    image: Path,
    reference: Path,
    output: Path,
    direction: MappingDirection = MappingDirection.moving_to_fixed,
    labels: bool = False,
) -> dict[str, Any]:
    """Apply verified transforms to an associated image; use --labels for atlas IDs."""
    from ccep.imaging.transforms import Direction, apply_image

    apply_image(
        bundle,
        image,
        reference,
        output,
        direction=cast(Direction, direction.value),
        labels=labels,
    )
    return dict(
        artifacts=[dict(path=str(output.resolve()), sha256=sha256(output))],
        transform_bundle_sha256=sha256(bundle),
        source_sha256=sha256(image),
        reference_sha256=sha256(reference),
        direction=direction.value,
        interpolation="genericLabel" if labels else "linear",
    )


def image_transform_points(
    bundle: Path,
    points: Path,
    output: Path,
    direction: MappingDirection = MappingDirection.moving_to_fixed,
) -> dict[str, Any]:
    """Transform a JSON array of [x,y,z] RAS-mm contacts with explicit direction."""
    import json

    from ccep.imaging.transforms import Direction, apply_points

    values = np.asarray(json.loads(points.read_text()), dtype=float)
    mapped = apply_points(bundle, values, direction=cast(Direction, direction.value))
    payload = dict(
        coordinates_ras_mm=mapped.tolist(),
        direction=direction.value,
        transform_bundle_sha256=sha256(bundle),
        source_sha256=sha256(points),
    )
    with atomic_binary(output) as stream:
        stream.write((json.dumps(payload, indent=2) + "\n").encode())
    return dict(
        artifacts=[dict(path=str(output.resolve()), sha256=sha256(output))], **payload
    )


def register_commands(app: typer.Typer) -> None:
    app.command("image-inspect")(image_inspect)
    app.command("image-register")(image_register)
    app.command("image-segment")(image_segment)
    app.command("image-contacts")(image_contacts)
    app.command("image-apply")(image_apply)
    app.command("image-transform-points")(image_transform_points)
