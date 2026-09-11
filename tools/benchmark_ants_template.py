"""ANTs-only known-motion checks on an explicit McGill template bundle.

These derived-template cases test geometry and execution, not intersubject or
SPM equivalence. They never manufacture six tissue priors from CerebrA labels.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from ccep.imaging.ants_backend import _ants, register
from ccep.imaging.geometry import voxel_to_world
from ccep.imaging.settings import RegistrationTask, task_settings
from ccep.imaging.templates import load_template
from ccep.imaging.transforms import apply_points, read_ants_mm
from ccep.reference import sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output folder")
    import nibabel as nib

    bundle = load_template(args.template)
    args.output.mkdir(parents=True)
    ants = _ants()
    assets = {}
    for role in ["t1", "t2", "mask", "atlas"]:
        original = args.template.parent / bundle.assets[role].path
        sampled = ants.resample_image(
            read_ants_mm(original),
            (2, 2, 2),
            use_voxels=False,
            interp_type=1 if role in {"mask", "atlas"} else 0,
        )
        assets[role] = args.output / f"{role}_2mm.nii.gz"
        ants.image_write(sampled, str(assets[role]))
    fixed = nib.load(assets["t1"])
    valid = np.argwhere(nib.load(assets["mask"]).get_fdata() > 0.5)
    selected = valid[np.random.default_rng(1729).choice(len(valid), 20, replace=False)]
    fixed_points = voxel_to_world(
        selected.astype(float), np.asarray(fixed.affine, dtype=float)
    )
    theta = np.deg2rad(4)
    motion = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0, 3],
            [np.sin(theta), np.cos(theta), 0, -2],
            [0, 0, 1, 1],
            [0, 0, 0, 1.0],
        ]
    )
    moving_points = voxel_to_world(fixed_points, motion)
    report = dict(
        template_identity=bundle.identity,
        template_bundle_sha256=sha256(args.template),
        antspy_version=ants.__version__,
        seed=1729,
        threads=1,
        scope="Known rigid motion applied to 2mm template headers; no independent patient or SPM reference",
        cases=[],
    )
    for modality, task, transform in [
        ("t1", RegistrationTask.t1_to_template, "SyN"),
        ("t2", RegistrationTask.ct_to_mri, "Rigid"),
    ]:
        image = nib.load(assets[modality])
        moved = nib.Nifti1Image(image.get_fdata(), motion @ image.affine)
        moved.header.set_xyzt_units("mm")
        moving_path = args.output / f"moving_{modality}.nii.gz"
        nib.save(moved, moving_path)
        mask = nib.load(assets["mask"])
        moved_mask = nib.Nifti1Image(mask.get_fdata(), motion @ mask.affine)
        moved_mask.header.set_xyzt_units("mm")
        mask_path = args.output / f"moving_{modality}_mask.nii.gz"
        nib.save(moved_mask, mask_path)
        # Fixed explicit study schedule, separate from the full production candidate.
        settings = task_settings(task).model_copy(
            update=dict(aff_iterations=(300, 150, 75, 20), reg_iterations=(20, 10, 0))
        )
        started = time.perf_counter()
        result = register(
            assets["t1"],
            moving_path,
            args.output / modality,
            transform=transform,
            settings=settings,
            fixed_mask=assets["mask"],
            moving_mask=mask_path,
        )
        transformed = apply_points(
            result.manifest.parent / "transforms.json", moving_points
        )
        back = apply_points(
            result.manifest.parent / "transforms.json",
            transformed,
            direction="fixed-to-moving",
        )
        error = np.linalg.norm(transformed - fixed_points, axis=1)
        case = dict(
            modality=modality,
            task=task.value,
            elapsed_seconds=time.perf_counter() - started,
            settings=settings.model_dump(mode="json"),
            tre_mean_mm=float(error.mean()),
            tre_max_mm=float(error.max()),
            inverse_max_mm=float(np.linalg.norm(back - moving_points, axis=1).max()),
            fixed_points_ras_mm=fixed_points.tolist(),
            moving_points_ras_mm=moving_points.tolist(),
            recovered_points_ras_mm=transformed.tolist(),
            inputs={p.name: sha256(p) for p in (assets["t1"], moving_path, mask_path)},
            note=(
                "T2 is a real template contrast comparison, not a CT substitute"
                if modality == "t2"
                else "Affine plus CC SyN on known-motion T1 template"
            ),
        )
        report["cases"].append(case)
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(case), flush=True)


if __name__ == "__main__":
    main()
