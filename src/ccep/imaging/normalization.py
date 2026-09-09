"""Explicit six-tissue ANTs normalization candidate, with separate output roles.

This staged N4/SyN/prior-transfer/Atropos pipeline is not SPM unified segmentation.
Templates and six-class priors are caller-supplied, never implicitly downloaded.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ccep.imaging.ants_backend import register, segment
from ccep.imaging.deformation import full_pull_field, pull_jacobian
from ccep.imaging.geometry import spm_pull_resample
from ccep.imaging.images import load_spatial_mm
from ccep.imaging.segmentation import (
    N4_SETTINGS,
    SPM_TISSUES,
    correct_bias,
    masked_image,
)
from ccep.imaging.settings import RegistrationSettings
from ccep.imaging.transforms import Grid, apply_image, read_ants_mm
from ccep.reference import sha256


def normalize(
    image: Path,
    mask: Path,
    template: Path,
    priors: list[Path],
    output: Path,
    *,
    seed: int = 1729,
    settings: RegistrationSettings | None = None,
) -> Path:
    """Write a new reviewable pipeline directory; final manifest marks completion.

    Required prior order is GM, WM, CSF, bone, soft tissue, background. A whole-head
    positive-intensity estimation mask is required if all six classes are wanted;
    a brain-only mask cannot estimate missing head tissues. Priors may sum to zero
    outside their template support, but must cover every native estimation voxel
    after transfer. No mask erosion or tissue substitution is performed silently.
    """
    if output.exists():
        raise FileExistsError(output)
    if len(priors) != 6:
        raise ValueError("Supply six template priors in SPM tissue order")
    _, native_mask = masked_image(image, mask)
    template_grid = Grid.from_image(template)
    read_ants_mm(template)
    for prior in priors:
        template_grid.check(prior)
        values = read_ants_mm(prior).numpy()
        if (values < 0).any() or (values > 1).any():
            raise ValueError("Template priors must contain probabilities in [0,1]")
    output.mkdir(parents=True)
    corrected = correct_bias(image, mask, output / "bias_corrected.nii.gz")
    registration = register(
        template,
        corrected,
        output / "registration",
        transform="SyN",
        seed=seed,
        settings=settings,
    )
    bundle = registration.manifest.parent / "transforms.json"
    transferred = [
        apply_image(
            bundle,
            prior,
            image,
            output / "transferred_priors" / f"{name}.nii.gz",
            direction="fixed-to-moving",
        )
        for name, prior in zip(SPM_TISSUES, priors, strict=True)
    ]
    import nibabel as nib

    native = load_spatial_mm(image)
    native_affine = np.asarray(native.affine, dtype=float)
    target_affine = np.asarray(template_grid.affine, dtype=float)
    probabilities = np.stack(
        [load_spatial_mm(path).get_fdata() for path in transferred]
    )
    total = probabilities.sum(axis=0)
    selected = native_mask.numpy() == 1
    if np.any(total[selected] <= 1e-8):
        raise ValueError(
            "Template priors do not cover the native estimation mask; inspect registration and template coverage"
        )
    normalized = np.divide(
        probabilities, total, out=np.zeros_like(probabilities), where=total[None] > 1e-8
    )

    def save(path: Path, values: Any, affine: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        volume = nib.Nifti1Image(np.asarray(values, dtype=np.float32), affine)
        volume.header.set_xyzt_units("mm")
        nib.save(volume, path)
        return path

    normalized_priors = [
        save(output / "native_priors" / f"{name}.nii.gz", values, native_affine)
        for name, values in zip(SPM_TISSUES, normalized, strict=True)
    ]
    labels, native_probabilities = segment(
        corrected,
        mask,
        normalized_priors,
        list(SPM_TISSUES),
        output / "native_segmentation",
        bias_correct=False,
    )
    template_probabilities = [
        apply_image(
            bundle, path, template, output / "normalized_probabilities" / path.name
        )
        for path in native_probabilities
    ]
    field = full_pull_field(
        bundle, image, template, output / "full_pull_displacement_lps.nii.gz"
    )
    jacobian = pull_jacobian(field, target_affine)
    if not np.isfinite(jacobian).all() or (jacobian <= 0).any():
        raise ValueError(
            "Nonpositive/nonfinite full-pull Jacobian; normalization requires review"
        )
    jacobian_path = save(output / "full_pull_jacobian.nii.gz", jacobian, target_affine)
    densities = []
    mass = {}
    for name, path in zip(SPM_TISSUES[:3], native_probabilities[:3], strict=True):
        values = np.asarray(load_spatial_mm(path).get_fdata(), dtype=float)
        density = spm_pull_resample(values, native_affine, field) * jacobian
        densities.append(
            save(
                output / "modulated_densities" / f"density_{name}.nii.gz",
                density,
                target_affine,
            )
        )
        native_mass = float(values.sum() * abs(np.linalg.det(native_affine[:3, :3])))
        target_mass = float(density.sum() * abs(np.linalg.det(target_affine[:3, :3])))
        mass[name] = dict(
            native_mm3=native_mass,
            normalized_mm3=target_mass,
            difference_mm3=target_mass - native_mass,
        )
    artifacts = {
        str(p.relative_to(output)): sha256(p) for p in output.rglob("*") if p.is_file()
    }
    manifest = output / "normalization.json"
    manifest.write_text(
        json.dumps(
            dict(
                schema_version=1,
                recipe="n4-syn-six-prior-atropos-v1",
                classes=SPM_TISSUES,
                inputs=dict(
                    image=sha256(image),
                    mask=sha256(mask),
                    template=sha256(template),
                    priors=[sha256(p) for p in priors],
                ),
                n4=N4_SETTINGS,
                registration="registration/registration.json",
                transform_bundle="registration/transforms.json",
                prior_transfer=dict(
                    direction="fixed-to-moving image",
                    interpolation="linear",
                    normalization="divide by six-class sum where >1e-8; reject uncovered mask voxels",
                ),
                roles=dict(
                    native_labels=str(labels.relative_to(output)),
                    native_probabilities=[
                        str(p.relative_to(output)) for p in native_probabilities
                    ],
                    normalized_probabilities=[
                        str(p.relative_to(output)) for p in template_probabilities
                    ],
                    modulated_densities=[str(p.relative_to(output)) for p in densities],
                    full_pull_jacobian=str(jacobian_path.relative_to(output)),
                ),
                modulation="linear native probability pull * signed full target-to-native RAS Jacobian; affine included; nonpositive determinants rejected; not SPM discrete push/splat",
                qc=dict(
                    jacobian_min=float(jacobian.min()),
                    jacobian_max=float(jacobian.max()),
                    tissue_mass=mass,
                    note="Mass differences include interpolation and cropping; no scientific acceptance limit applied",
                ),
                artifacts=artifacts,
                acceptance="unverified ANTs outcome candidate; matched SPM reference evaluation required",
            ),
            indent=2,
        )
        + "\n"
    )
    return manifest
