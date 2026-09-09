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
) -> Registration:
    """Resample moving image into fixed image space; never overwrite source images."""
    settings = settings or RegistrationSettings()
    if not 0 <= seed < 2**32:
        raise ValueError("Seed must fit an unsigned 32-bit integer")
    if transform not in {"Rigid", "Affine", "SyN"}:
        raise ValueError("Unsupported registration transform")
    if output.exists():
        raise FileExistsError(output)
    load_spatial_mm(fixed)
    load_spatial_mm(moving)
    ants = _ants()
    fixed_image, moving_image = read_ants_mm(fixed), read_ants_mm(moving)
    if fixed_image.dimension != 3 or moving_image.dimension != 3:
        raise ValueError("Registration requires 3D volumes")
    output.mkdir(parents=True)
    with _REGISTRATION_LOCK:
        previous_seed = ants.config._random_seed
        previous_mode = ants.config._deterministic
        previous_threads = os.environ.get("ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS")
        numpy_state, random_state = np.random.get_state(), random.getstate()
        try:
            ants.config.set_ants_deterministic(True, seed_value=seed)
            arguments = settings.arguments()
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
    bundle = capture_bundle(fixed, moving, forward, inverse, output)
    bundle_path = output / "transforms.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n")
    manifest = output / "registration.json"
    manifest.write_text(
        json.dumps(
            dict(
                schema_version=2,
                backend="ANTsPy",
                version=ants.__version__,
                fixed_sha256=sha256(fixed),
                moving_sha256=sha256(moving),
                fixed=str(fixed.resolve()),
                moving=str(moving.resolve()),
                image_mapping="moving-to-fixed via ANTs apply_transforms",
                world_coordinates="ANTs LPS mm; public geometry uses RAS mm",
                transform=transform,
                requested_settings=settings.model_dump(mode="json"),
                effective_settings=settings.effective(transform),
                initialization=settings.initialization,
                seed=seed,
                threads=1,
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
    (output / "segmentation.json").write_text(
        json.dumps(
            dict(
                schema_version=1,
                backend="ANTsPy",
                version=ants.__version__,
                classes=class_names,
                image_sha256=sha256(image),
                mask_sha256=sha256(mask),
                prior_sha256=[sha256(p) for p in priors],
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
    transforms: list[Path],
    centre_ras_mm: Any,
    output: Path,
) -> Any:
    """Warp a native 1.5 mm sphere onto an explicit 1 mm grid, then centroid it."""
    import nibabel as nib
    import numpy as np

    from ccep.imaging.geometry import sphere, warped_roi_centroid

    if output.exists():
        raise FileExistsError(output)
    native = cast(nib.Nifti1Image, load_spatial_mm(native_image))
    target = cast(nib.Nifti1Image, load_spatial_mm(target_grid))
    if not np.allclose(target.header.get_zooms()[:3], [1, 1, 1]):
        raise ValueError("Legacy ROI workflow requires a 1 mm target grid")
    values = sphere(
        cast(tuple[int, int, int], native.shape[:3]),
        np.asarray(native.affine, dtype=np.float64),
        np.asarray(centre_ras_mm),
    )
    output.mkdir(parents=True)
    sphere_path = output / "native_sphere.nii.gz"
    sphere_image = nib.Nifti1Image(values, native.affine)
    sphere_image.header.set_xyzt_units("mm")
    nib.save(sphere_image, sphere_path)
    ants = _ants()
    warped = ants.apply_transforms(
        fixed=ants.image_read(str(target_grid)),
        moving=ants.image_read(str(sphere_path)),
        transformlist=[str(p) for p in transforms],
        interpolator="linear",
    )
    warped_path = output / "warped_sphere.nii.gz"
    ants.image_write(warped, str(warped_path))
    image = cast(nib.Nifti1Image, nib.load(warped_path))
    centroid = warped_roi_centroid(
        np.asarray(image.get_fdata(), dtype=np.float64),
        np.asarray(image.affine, dtype=np.float64),
    )
    (output / "contact.json").write_text(
        json.dumps(
            dict(
                radius_mm=1.5,
                centre_ras_mm=np.asarray(centre_ras_mm).tolist(),
                centroid_ras_mm=centroid.tolist(),
                native_sha256=sha256(native_image),
                target_sha256=sha256(target_grid),
                transforms=[dict(path=str(p), sha256=sha256(p)) for p in transforms],
                thresholds=[0.99, 0.95],
                interpolation="linear",
            ),
            indent=2,
        )
        + "\n"
    )
    return centroid
