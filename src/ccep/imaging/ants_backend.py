"""ANTsPy implementation candidates with explicit artifacts and class ordering.

These operations execute ANTs; they do not establish SPM equivalence. Full imaging
acceptance requires the external reference corpus and author-reviewed outcomes.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Literal, cast

import numpy as np

from ccep.imaging.images import load_spatial_mm
from ccep.imaging.provenance import snapshot_inputs, verify_unchanged
from ccep.imaging.settings import RegistrationSettings
from ccep.imaging.transforms import capture_bundle, read_ants_mm
from ccep.reference import sha256

_REGISTRATION_LOCK = RLock()


def _ants() -> Any:
    try:
        import ants
    except ImportError as error:
        raise ImportError("Install the imaging extra to use ANTsPy") from error
    return ants


@dataclass(frozen=True)
class Registration:
    warped: Path
    forward_transforms: tuple[Path, ...]
    inverse_transforms: tuple[Path, ...]
    manifest: Path


def register(
    fixed: Path,
    moving: Path,
    output: Path,
    *,
    transform: Literal["Rigid", "Affine", "SyN"] = "Rigid",
    seed: int = 1729,
    settings: RegistrationSettings | None = None,
    fixed_mask: Path | None = None,
    moving_mask: Path | None = None,
) -> Registration:
    """Register in an isolated ANTs process with a single thread from startup.

    ITK caches thread settings on first use; changing the environment later is
    insufficient in notebooks that have already loaded/processed an ANTs image.
    Paths cross the worker boundary, avoiding copies of large volumes over IPC.
    """
    from ccep.imaging.registration_worker import RegistrationRequest, run_registration

    return run_registration(
        RegistrationRequest(
            fixed=fixed.resolve(),
            moving=moving.resolve(),
            output=output.resolve(),
            transform=transform,
            seed=seed,
            settings=settings or RegistrationSettings(),
            fixed_mask=fixed_mask.resolve() if fixed_mask is not None else None,
            moving_mask=moving_mask.resolve() if moving_mask is not None else None,
        )
    )


def _register_in_process(
    fixed: Path,
    moving: Path,
    output: Path,
    *,
    transform: Literal["Rigid", "Affine", "SyN"] = "Rigid",
    seed: int = 1729,
    settings: RegistrationSettings | None = None,
    fixed_mask: Path | None = None,
    moving_mask: Path | None = None,
) -> Registration:
    """Resample moving image into fixed image space; never overwrite source images."""
    settings = settings or RegistrationSettings()
    if not 0 <= seed < 2**32:
        raise ValueError("Seed must fit an unsigned 32-bit integer")
    if transform not in {"Rigid", "Affine", "SyN"}:
        raise ValueError("Unsupported registration transform")
    if output.exists():
        raise FileExistsError(output)
    input_hashes = snapshot_inputs(
        [fixed, moving, *[p for p in (fixed_mask, moving_mask) if p is not None]]
    )
    load_spatial_mm(fixed)
    load_spatial_mm(moving)
    ants = _ants()
    fixed_image, moving_image = read_ants_mm(fixed), read_ants_mm(moving)
    if fixed_image.dimension != 3 or moving_image.dimension != 3:
        raise ValueError("Registration requires 3D volumes")
    from ccep.imaging.segmentation import registration_mask

    fixed_mask_image = registration_mask(fixed, fixed_mask) if fixed_mask else None
    moving_mask_image = registration_mask(moving, moving_mask) if moving_mask else None
    output.mkdir(parents=True)
    with _REGISTRATION_LOCK:
        previous_seed = ants.config._random_seed
        previous_mode = ants.config._deterministic
        previous_threads = os.environ.get("ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS")
        numpy_state, random_state = np.random.get_state(), random.getstate()
        try:
            ants.config.set_ants_deterministic(True, seed_value=seed)
            arguments = settings.arguments()
            arguments.update(
                mask=fixed_mask_image,
                moving_mask=moving_mask_image,
                mask_all_stages=True,
            )
            backend_transform = transform
            if transform == "SyN" and settings.recipe == "explicit-v1":
                # ANTs 0.6.3's built-in SyN ignores the affine schedule kwargs.
                # Separate stages make caller-selected schedules effective.
                affine_result = ants.registration(
                    fixed=fixed_image,
                    moving=moving_image,
                    type_of_transform="Affine",
                    **arguments,
                    outprefix=str(output / "prealignment_"),
                    verbose=False,
                )
                arguments["initial_transform"] = affine_result["fwdtransforms"]
                backend_transform = "SyNOnly"
            result = ants.registration(
                fixed=fixed_image,
                moving=moving_image,
                type_of_transform=backend_transform,
                **arguments,
                outprefix=str(output / "registration_"),
                verbose=False,
            )
        finally:
            ants.config.set_ants_deterministic(previous_mode, seed_value=previous_seed)
            np.random.set_state(numpy_state)
            random.setstate(random_state)
            if previous_threads is None:
                os.environ.pop("ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS", None)
            else:
                os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = previous_threads
    warped = output / "moving_in_fixed.nii.gz"
    ants.image_write(result["warpedmovout"], str(warped))
    forward = tuple(Path(p).resolve() for p in result["fwdtransforms"])
    inverse = tuple(Path(p).resolve() for p in result["invtransforms"])
    verify_unchanged(input_hashes)
    bundle = capture_bundle(fixed, moving, forward, inverse, output)
    bundle_path = output / "transforms.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n")
    verify_unchanged(input_hashes)
    manifest = output / "registration.json"
    manifest.write_text(
        json.dumps(
            dict(
                schema_version=2,
                backend="ANTsPy",
                version=ants.__version__,
                fixed_sha256=input_hashes[fixed],
                moving_sha256=input_hashes[moving],
                fixed=str(fixed.resolve()),
                moving=str(moving.resolve()),
                image_mapping="moving-to-fixed via ANTs apply_transforms",
                world_coordinates="ANTs LPS mm; public geometry uses RAS mm",
                transform=transform,
                masks={
                    "fixed": input_hashes[fixed_mask] if fixed_mask else None,
                    "moving": input_hashes[moving_mask] if moving_mask else None,
                    "all_stages": True,
                },
                requested_settings=settings.model_dump(mode="json"),
                effective_settings=settings.effective(transform),
                initialization=settings.initialization,
                seed=seed,
                threads=1,
                execution="isolated worker; ITK thread setting present at startup",
                transform_bundle="transforms.json",
                transform_bundle_sha256=sha256(bundle_path),
                forward=[str(p) for p in forward],
                inverse=[str(p) for p in inverse],
                artifacts={p.name: sha256(p) for p in {warped, *forward, *inverse}},
                acceptance="unverified against SPM",
            ),
            indent=2,
        )
        + "\n"
    )
    return Registration(warped, forward, inverse, manifest)


def segment(
    image: Path,
    mask: Path,
    priors: list[Path],
    class_names: list[str],
    output: Path,
    *,
    bias_correct: bool = True,
) -> tuple[Path, list[Path]]:
    """N4 + prior-informed six-class Atropos candidate for the SPM workstream.

    Priors MUST already be in the image grid. Class identity follows prior order;
    priors/templates are explicit inputs, never downloaded or inferred silently.
    """
    if len(priors) != 6 or len(class_names) != 6 or len(set(class_names)) != 6:
        raise ValueError(
            "Provide six priors and six unique class names in matching order"
        )
    if any(not name.replace("_", "").isalnum() for name in class_names):
        raise ValueError("Class names may contain letters, numbers and underscores")
    if output.exists():
        raise FileExistsError(output)
    from ccep.imaging.segmentation import N4_SETTINGS, masked_image, validate_priors

    ants = _ants()
    input_hashes = snapshot_inputs([image, mask, *priors])
    original, mask_image = masked_image(image, mask)
    prior_images = validate_priors(image, mask_image, priors)
    output.mkdir(parents=True)
    with _REGISTRATION_LOCK:
        corrected = (
            ants.n4_bias_field_correction(original, mask=mask_image, **N4_SETTINGS)
            if bias_correct
            else original
        )
        result = ants.atropos(
            a=corrected,
            x=mask_image,
            i=prior_images,
            m="[0.1,1x1x1]",
            c="[5,0]",
            priorweight=0.25,
            r=0,  # ANTs fixed internal seed; no wall-clock random initialization.
        )
    posteriors = np.stack([p.numpy() for p in result["probabilityimages"]])
    selected = posteriors[:, mask_image.numpy() == 1]
    if (
        not np.isfinite(posteriors).all()
        or (posteriors < 0).any()
        or (posteriors > 1).any()
        or not np.allclose(selected.sum(axis=0), 1, atol=1e-4)
    ):
        raise ValueError("Atropos returned invalid posterior probabilities")
    segmentation = output / "segmentation.nii.gz"
    ants.image_write(corrected, str(output / "bias_corrected.nii.gz"))
    ants.image_write(result["segmentation"], str(segmentation))
    probabilities = []
    for name, probability in zip(class_names, result["probabilityimages"], strict=True):
        path = output / f"probability_{name}.nii.gz"
        ants.image_write(probability, str(path))
        probabilities.append(path)
    verify_unchanged(input_hashes)
    (output / "segmentation.json").write_text(
        json.dumps(
            dict(
                schema_version=1,
                backend="ANTsPy",
                version=ants.__version__,
                classes=class_names,
                image_sha256=input_hashes[image],
                mask_sha256=input_hashes[mask],
                prior_sha256=[input_hashes[p] for p in priors],
                bias_correction=(
                    N4_SETTINGS if bias_correct else "already corrected; N4 skipped"
                ),
                atropos_use_random_seed=False,
                output_sha256={
                    p.name: sha256(p)
                    for p in [
                        segmentation,
                        *probabilities,
                        output / "bias_corrected.nii.gz",
                    ]
                },
                priorweight=0.25,
                convergence="[5,0]",
                mrf="[0.1,1x1x1]",
                acceptance="unverified against SPM; outcome acceptance required",
            ),
            indent=2,
        )
        + "\n"
    )
    return segmentation, probabilities


def warp_contact_sphere(
    native_image: Path,
    target_grid: Path,
    transforms: list[Path] | Path,
    centre_ras_mm: Any,
    output: Path,
    *,
    rasterization: Literal["legacy-marsbar", "world-sphere"] = "legacy-marsbar",
) -> Any:
    """Warp a native 1.5 mm sphere onto an explicit 1 mm grid, then centroid it."""
    import nibabel as nib
    import numpy as np

    from ccep.imaging.geometry import (
        ContactThresholdError,
        marsbar_sphere,
        sphere,
        warped_roi_centroid,
    )

    if output.exists():
        raise FileExistsError(output)
    paths = [native_image, target_grid]
    if isinstance(transforms, Path):
        from ccep.imaging.transforms import load_bundle

        bundle = load_bundle(transforms)
        paths.extend(
            [
                transforms,
                *[
                    transforms.parent / step.path
                    for step in (*bundle.forward, *bundle.inverse)
                ],
            ]
        )
    else:
        paths.extend(transforms)
    input_hashes = snapshot_inputs(paths)
    native = cast(nib.Nifti1Image, load_spatial_mm(native_image))
    target = cast(nib.Nifti1Image, load_spatial_mm(target_grid))
    if not np.allclose(target.header.get_zooms()[:3], [1, 1, 1]):
        raise ValueError("Legacy ROI workflow requires a 1 mm target grid")
    if rasterization not in {"legacy-marsbar", "world-sphere"}:
        raise ValueError("Unknown sphere rasterization")
    rasterizer = marsbar_sphere if rasterization == "legacy-marsbar" else sphere
    values = rasterizer(
        cast(tuple[int, int, int], native.shape[:3]),
        np.asarray(native.affine, dtype=np.float64),
        np.asarray(centre_ras_mm),
    )
    output.mkdir(parents=True)
    sphere_path = output / "native_sphere.nii.gz"
    sphere_image = nib.Nifti1Image(values, native.affine)
    sphere_image.header.set_xyzt_units("mm")
    nib.save(sphere_image, sphere_path)
    warped_path = output / "warped_sphere.nii.gz"
    if isinstance(transforms, Path):
        from ccep.imaging.transforms import apply_image

        apply_image(transforms, sphere_path, target_grid, warped_path)
        transform_provenance = dict(bundle_sha256=sha256(transforms))
    else:
        ants = _ants()
        warped = ants.apply_transforms(
            fixed=read_ants_mm(target_grid),
            moving=read_ants_mm(sphere_path),
            transformlist=[str(p) for p in transforms],
            whichtoinvert=[False] * len(transforms),
            interpolator="linear",
        )
        ants.image_write(warped, str(warped_path))
        transform_provenance = dict(
            forward=[
                dict(path=str(p), sha256=sha256(p), invert=False) for p in transforms
            ]
        )
    image = cast(nib.Nifti1Image, nib.load(warped_path))
    warped_values = np.asarray(image.get_fdata(), dtype=np.float64)
    try:
        centroid = warped_roi_centroid(
            warped_values, np.asarray(image.affine, dtype=np.float64)
        )
    except ContactThresholdError as error:
        verify_unchanged(input_hashes)
        failure = dict(
            status="threshold-failure",
            message=str(error),
            centre_ras_mm=np.asarray(centre_ras_mm).tolist(),
            warped_peak=float(warped_values.max()),
            thresholds=[0.99, 0.95],
            radius_mm=1.5,
            rasterization=rasterization,
            interpolation="linear",
            native_sha256=input_hashes[native_image],
            target_sha256=input_hashes[target_grid],
            transforms=transform_provenance,
            warped_sha256=sha256(warped_path),
        )
        (output / "contact_failure.json").write_text(
            json.dumps(failure, indent=2) + "\n"
        )
        raise
    verify_unchanged(input_hashes)
    (output / "contact.json").write_text(
        json.dumps(
            dict(
                radius_mm=1.5,
                centre_ras_mm=np.asarray(centre_ras_mm).tolist(),
                centroid_ras_mm=centroid.tolist(),
                native_sha256=input_hashes[native_image],
                target_sha256=input_hashes[target_grid],
                transforms=transform_provenance,
                rasterization=rasterization,
                thresholds=[0.99, 0.95],
                interpolation="linear",
            ),
            indent=2,
        )
        + "\n"
    )
    return centroid
