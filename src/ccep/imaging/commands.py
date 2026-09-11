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
from ccep.imaging.settings import RegistrationSettings, RegistrationTask, task_settings
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
    transform: Transform | None = None,
    seed: int = 1729,
    settings: Path | None = None,
    task: RegistrationTask | None = None,
    fixed_mask: Path | None = None,
    moving_mask: Path | None = None,
) -> dict[str, Any]:
    """Register moving into fixed image space with ANTsPy; preserve original images."""
    from ccep.imaging.ants_backend import register

    if task is not None and settings is not None:
        raise ValueError("Choose a named task or a custom settings file, not both")
    task_transform = (
        Transform.syn if task == RegistrationTask.t1_to_template else Transform.rigid
    )
    if task is not None and transform is not None and transform != task_transform:
        raise ValueError(f"Task {task.value} requires {task_transform.value}")
    mode = cast(Literal["Rigid", "Affine", "SyN"], (transform or task_transform).value)
    recipe = (
        RegistrationSettings.model_validate_json(settings.read_text())
        if settings
        else task_settings(task) if task is not None else None
    )
    result = register(
        fixed,
        moving,
        output,
        transform=mode,
        seed=seed,
        settings=recipe,
        fixed_mask=fixed_mask,
        moving_mask=moving_mask,
    )
    return dict(
        task=task.value if task is not None else "generic",
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


class NormalizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image: Path
    mask: Path
    template: Path
    priors: list[Path]
    seed: int = 1729
    registration_settings: dict[str, Any] | None = None
    bias_mask: Path | None = None
    fixed_registration_mask: Path | None = None
    moving_registration_mask: Path | None = None


def image_normalize(config: Path, output: Path) -> dict[str, Any]:
    """N4/SyN/six-tissue pipeline from explicit template priors; SPM acceptance pending."""
    from ccep.imaging.normalization import normalize

    settings = NormalizationConfig.model_validate_json(config.read_text())
    base = config.parent
    manifest = normalize(
        base / settings.image,
        base / settings.mask,
        base / settings.template,
        [base / path for path in settings.priors],
        output,
        seed=settings.seed,
        settings=(
            RegistrationSettings.model_validate(settings.registration_settings)
            if settings.registration_settings
            else None
        ),
        bias_mask=base / settings.bias_mask if settings.bias_mask else None,
        fixed_registration_mask=(
            base / settings.fixed_registration_mask
            if settings.fixed_registration_mask
            else None
        ),
        moving_registration_mask=(
            base / settings.moving_registration_mask
            if settings.moving_registration_mask
            else None
        ),
    )
    return dict(
        artifacts=[dict(path=str(manifest.resolve()), sha256=sha256(manifest))],
        scientific_status="Unverified ANTs outcome candidate; inspect normalization QC and compare with SPM",
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


def image_template_install(archive: Path, output: Path) -> dict[str, Any]:
    """Import the supplied McGill ext55 ZIP into a new local template bundle."""
    from ccep.imaging.templates import install_icbm152, template_inspect

    manifest = install_icbm152(archive, output)
    return dict(manifest=str(manifest.resolve()), **template_inspect(manifest))


def image_template_inspect(manifest: Path) -> dict[str, Any]:
    """Verify template asset hashes and report exact space and available roles."""
    from ccep.imaging.templates import template_inspect

    return template_inspect(manifest)


def image_template_register(
    template_bundle: Path,
    moving: Path,
    output: Path,
    moving_mask: Path | None = None,
    seed: int = 1729,
) -> dict[str, Any]:
    """Register native T1 to an exact verified template with the ANTs CC candidate."""
    from ccep.imaging.ants_backend import register
    from ccep.imaging.templates import load_template

    bundle = load_template(template_bundle)
    result = register(
        template_bundle.parent / bundle.assets["t1"].path,
        moving,
        output,
        transform="SyN",
        seed=seed,
        settings=task_settings(RegistrationTask.t1_to_template),
        fixed_mask=template_bundle.parent / bundle.assets["mask"].path,
        moving_mask=moving_mask,
    )
    import json

    if load_template(template_bundle) != bundle:
        raise ValueError("Template manifest changed during registration")
    reference = dict(
        identity=bundle.identity,
        manifest_sha256=sha256(template_bundle),
        archive_sha256=bundle.archive_sha256,
        fixed_sha256=bundle.assets["t1"].sha256,
        template_mask_sha256=bundle.assets["mask"].sha256,
    )
    with atomic_binary(output / "template_reference.json") as stream:
        stream.write((json.dumps(reference, indent=2) + "\n").encode())
    return dict(
        manifest=str(result.manifest.resolve()),
        template_identity=bundle.identity,
        template_bundle_sha256=sha256(template_bundle),
        warped=str(result.warped.resolve()),
        transform_bundle=str((output / "transforms.json").resolve()),
        scientific_status="ANTs candidate; SPM acceptance pending",
    )


def image_reorient(image: Path, matrix: Path, output: Path) -> dict[str, Any]:
    """Apply an explicit rigid RAS-world JSON matrix to the header only."""
    import json

    from ccep.imaging.legacy_images import reorient_header
    from ccep.imaging.provenance import snapshot_inputs, verify_unchanged

    inputs = snapshot_inputs([image, matrix])
    reorient_header(
        image, np.asarray(json.loads(matrix.read_text()), dtype=float), output
    )
    verify_unchanged(inputs)
    return dict(
        output=str(output.resolve()),
        sha256=sha256(output),
        source_sha256=inputs[image],
        matrix_sha256=inputs[matrix],
        interpolation="none; header only",
    )


def image_spm_warp(
    native: Path, field: Path, output: Path, labels: bool = False
) -> dict[str, Any]:
    """Apply an explicitly identified SPM absolute-RAS pull field; never an ANTs displacement."""
    from ccep.imaging.legacy_images import apply_spm_pull
    from ccep.imaging.provenance import snapshot_inputs, verify_unchanged

    inputs = snapshot_inputs([native, field])
    apply_spm_pull(native, field, output, labels=labels)
    verify_unchanged(inputs)
    return dict(
        output=str(output.resolve()),
        sha256=sha256(output),
        source_sha256=inputs[native],
        field_sha256=inputs[field],
        field_convention="absolute source RAS mm on target grid",
        interpolation="nearest" if labels else "linear",
        scientific_status="Field adapter candidate; real SPM capture acceptance pending",
    )


class SamplingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tissue_maps: list[Path]
    native_points_ras_mm: list[list[float]]
    atlas: Path | None = None
    atlas_labels: dict[int, str] = {}
    template_centre_ras_mm: list[float] | None = None
    atlas_mode: Literal["exact", "legacy-closest-absolute"] = "exact"


def image_sample(config: Path, output: Path) -> dict[str, Any]:
    """Sample captured native tissue points and optionally a template-space atlas centre."""
    import json

    from ccep.imaging.anatomy import atlas_lookup, tissue_samples
    from ccep.imaging.images import load_spatial_mm
    from ccep.imaging.provenance import snapshot_inputs, verify_unchanged
    from ccep.imaging.transforms import Grid

    config_hash = sha256(config)
    settings = SamplingConfig.model_validate_json(config.read_text())
    if len(settings.tissue_maps) != 3:
        raise ValueError("Supply GM, WM, CSF maps in that order")
    paths = [config.parent / p for p in settings.tissue_maps]
    atlas_path = config.parent / settings.atlas if settings.atlas else None
    inputs = snapshot_inputs([config, *paths, *([atlas_path] if atlas_path else [])])
    if inputs[config] != config_hash:
        raise ValueError("Sampling configuration changed while reading")
    grid = Grid.from_image(paths[0])
    for path in paths[1:]:
        grid.check(path)
    images = [load_spatial_mm(p) for p in paths]
    points = np.asarray(settings.native_points_ras_mm)
    result: dict[str, Any] = dict(
        tissue=tissue_samples(
            [np.asarray(im.get_fdata(), dtype=np.float64) for im in images],
            np.asarray(grid.affine),
            points,
        ),
        native_points_ras_mm=points.tolist(),
    )
    if atlas_path:
        if settings.template_centre_ras_mm is None:
            raise ValueError(
                "Atlas sampling requires an explicit template-space centre"
            )
        atlas = load_spatial_mm(atlas_path)
        result["atlas"] = atlas_lookup(
            np.asarray(atlas.get_fdata(), dtype=np.float64),
            np.asarray(atlas.affine),
            np.asarray(settings.template_centre_ras_mm),
            settings.atlas_labels,
            mode=settings.atlas_mode,
            native_sample_count=len(points),
        )
    result["inputs"] = {str(p): digest for p, digest in inputs.items()}
    result["scientific_status"] = (
        "Source-derived sampling; SPM GUI text precision and corpus parity pending"
    )
    verify_unchanged(inputs)
    with atomic_binary(output) as stream:
        stream.write((json.dumps(result, indent=2) + "\n").encode())
    return dict(output=str(output.resolve()), sha256=sha256(output), **result)


def image_import_electrodes(source: Path, native: Path, output: Path) -> dict[str, Any]:
    """Import a MATLAB ElectrodeArray acquisition into a verified native session."""
    from ccep.imaging.legacy_session import import_electrodes

    session = import_electrodes(source, native, output)
    return dict(
        output=str(output.resolve()),
        sha256=sha256(output),
        electrodes=len(session.electrodes),
        legacy_sha256=session.legacy_sha256,
        scientific_status="Source-derived acquisition adapter; original MAT retained",
    )


def image_contact_warp(
    bundle: Path, native: Path, target: Path, point: Path, output: Path
) -> dict[str, Any]:
    """Compare legacy sphere-warp centroid with direct point mapping; keep both roles."""
    import json

    from ccep.imaging.ants_backend import warp_contact_sphere
    from ccep.imaging.geometry import ContactThresholdError
    from ccep.imaging.provenance import snapshot_inputs, verify_unchanged
    from ccep.imaging.transforms import apply_points

    input_hashes = snapshot_inputs([point, bundle, native, target])
    centre = np.asarray(json.loads(point.read_text()), dtype=float)
    direct = apply_points(bundle, centre.reshape(1, 3))[0]
    failure: str | None = None
    try:
        centroid = warp_contact_sphere(native, target, bundle, centre, output)
    except ContactThresholdError as error:
        centroid, failure = None, str(error)
    comparison = dict(
        passed=centroid is not None,
        legacy_centroid_ras_mm=centroid.tolist() if centroid is not None else None,
        legacy_failure=failure,
        direct_point_ras_mm=direct.tolist(),
        difference_mm=(
            float(np.linalg.norm(centroid - direct)) if centroid is not None else None
        ),
        rasterization="legacy-marsbar",
        point_sha256=input_hashes[point],
        note="Passed means both calculations completed, not scientific equivalence. Distinct outcomes; no equivalence tolerance applied",
        artifacts={p.name: sha256(p) for p in output.iterdir() if p.is_file()},
    )
    verify_unchanged(input_hashes)
    with atomic_binary(output / "comparison.json") as stream:
        stream.write((json.dumps(comparison, indent=2) + "\n").encode())
    return comparison


def image_auto_reorient(
    image: Path, template: Path, output: Path, seed: int = 1729
) -> dict[str, Any]:
    """Estimate ANTs rigid header reorientation against an explicit template."""
    from ccep.imaging.legacy_images import auto_reorient

    manifest = auto_reorient(image, template, output, seed=seed)
    return dict(
        manifest=str(manifest.resolve()),
        sha256=sha256(manifest),
        scientific_status="ANTs candidate; SPM comparison pending",
    )


def register_commands(app: typer.Typer) -> None:
    app.command("image-inspect")(image_inspect)
    app.command("image-register")(image_register)
    app.command("image-segment")(image_segment)
    app.command("image-contacts")(image_contacts)
    app.command("image-apply")(image_apply)
    app.command("image-transform-points")(image_transform_points)
    app.command("image-normalize")(image_normalize)
    app.command("image-template-install")(image_template_install)
    app.command("image-template-inspect")(image_template_inspect)
    app.command("image-template-register")(image_template_register)
    app.command("image-reorient")(image_reorient)
    app.command("image-spm-warp")(image_spm_warp)
    app.command("image-sample")(image_sample)
    app.command("image-import-electrodes")(image_import_electrodes)
    app.command("image-contact-warp")(image_contact_warp)
    app.command("image-auto-reorient")(image_auto_reorient)
