"""Reproducible synthetic rigid-registration study; this is NOT SPM validation.

Run with the imaging environment plus SimpleITK installed. Results and input
volumes are local research artifacts, not normative acceptance fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any

# Set before native-library imports; do not benchmark a user's live session.
os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] = "1"
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/ccep-mpl")

import ants  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import SimpleITK as sitk  # noqa: E402

SEED = 1729
ANT_SETTINGS = {
    "type_of_transform": "Rigid",
    "aff_metric": "mattes",
    "aff_sampling": 32,
    "aff_random_sampling_rate": 0.5,
    "aff_iterations": (300, 150, 75),
    "aff_shrink_factors": (4, 2, 1),
    "aff_smoothing_sigmas": (2, 1, 0),
    "smoothing_in_mm": True,
    "singleprecision": False,
}
SITK_SETTINGS = {
    "transform": "Euler3D",
    "metric": "MattesMutualInformation",
    "histogram_bins": 32,
    "sampling": "RANDOM",
    "sampling_fraction": 0.5,
    "optimizer": "GradientDescentLineSearch",
    "learning_rate": 1.0,
    "iterations_per_level": 300,
    "convergence_minimum": 1e-6,
    "convergence_window": 10,
    "scales": "physical_shift",
    "estimate_learning_rate": "Once",
    "maximum_step_size_mm": 0.0,
    "line_search_upper_limit": 5.0,
    "shrink_factors": [4, 2, 1],
    "smoothing_sigmas_mm": [2, 1, 0],
}


def transform_points(transform: Any, points: np.ndarray) -> np.ndarray:
    return np.asarray([transform.TransformPoint(tuple(p)) for p in points])


def phantom(points: np.ndarray, center: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Analytic, asymmetric blobs: intensity and discrete labels sampled separately."""
    local = points - center
    intensity = 0.12 * np.exp(-np.sum((local / [18, 21, 17]) ** 2, axis=-1) / 2)
    labels = np.zeros(points.shape[:-1], dtype=np.uint8)
    for index, (offset, scale, amplitude) in enumerate(
        [
            ([-10, -9, -5], [5, 7, 6], 0.9),
            ([9, -7, 7], [6, 5, 4], 0.7),
            ([-7, 10, 8], [4, 6, 5], 0.55),
            ([8, 9, -8], [7, 4, 5], 0.8),
            ([0, 1, 0], [3, 4, 3], 0.45),
        ],
        start=1,
    ):
        distance = np.sum(((local - offset) / scale) ** 2, axis=-1)
        intensity += amplitude * np.exp(-distance / 2)
        labels[distance < 1] = index
    return intensity, labels


def make_case(
    folder: Path, *, oblique: bool, contrast: bool, stress: bool = False
) -> dict[str, Any]:
    folder.mkdir(parents=True)
    size = (56, 60, 52)
    spacing = (0.9, 1.2, 1.6) if oblique else (1.0, 1.0, 1.0)
    angle = np.deg2rad(23 if oblique else 0)
    direction = np.array(
        [
            [np.cos(angle), -np.sin(angle), 0],
            [np.sin(angle), np.cos(angle), 0],
            [0, 0, 1],
        ]
    )
    origin = np.array([-30.0, -40.0, 12.0])
    center = origin + direction @ ((np.asarray(size) - 1) * spacing / 2)
    z, y, x = np.indices(size[::-1], dtype=float)
    points = origin + np.stack([x, y, z], axis=-1) * spacing @ direction.T
    known = sitk.Euler3DTransform()
    known.SetCenter(tuple(center))
    rotation = [12, -9, 17] if stress else [4, -3, 6]
    translation = [12.0, -9.0, 6.0] if stress else [4.0, -3.0, 2.0]
    known.SetRotation(*np.deg2rad(rotation))
    known.SetTranslation(tuple(translation))
    inverse = known.GetInverse()
    inverse_matrix = np.linalg.inv(np.asarray(known.GetMatrix()).reshape(3, 3))
    moving_points_in_fixed = (
        points - center - known.GetTranslation()
    ) @ inverse_matrix.T + center
    fixed, fixed_labels = phantom(points, center)
    moving, moving_labels = phantom(moving_points_in_fixed, center)
    if contrast:
        # A smooth invertible contrast reversal, not a biological CT/MR simulator.
        moving = np.exp(-2.5 * moving)
    if stress:
        rng = np.random.default_rng(SEED)
        fixed += rng.normal(0, 0.03, fixed.shape)
        moving += rng.normal(0, 0.03, moving.shape)
    for name, array in {
        "fixed": fixed.astype(np.float64),
        "moving": moving.astype(np.float64),
        "fixed_labels": fixed_labels,
        "moving_labels": moving_labels,
    }.items():
        image = sitk.GetImageFromArray(array)
        image.SetSpacing(spacing)
        image.SetOrigin(tuple(origin))
        image.SetDirection(tuple(direction.ravel()))
        sitk.WriteImage(image, str(folder / f"{name}.nii.gz"))
    sitk.WriteTransform(known, str(folder / "ground_truth_fixed_to_moving.tfm"))
    initial = sitk.Euler3DTransform()
    initial.SetCenter(tuple(center))
    sitk.WriteTransform(initial, str(folder / "initial_identity.tfm"))
    landmarks = center + np.array(
        [
            [-10, -9, -5],
            [9, -7, 7],
            [-7, 10, 8],
            [8, 9, -8],
            [0, 1, 0],
            [-15, 0, 0],
            [15, 0, 0],
            [0, -15, 0],
            [0, 15, 0],
            [0, 0, -15],
            [0, 0, 15],
        ]
    )
    expected = transform_points(known, landmarks)
    # Independent round-trip checks establish the direction before optimization.
    np.testing.assert_allclose(
        transform_points(inverse, expected), landmarks, atol=1e-10
    )
    metadata = {
        "size_xyz": size,
        "spacing_mm_xyz": spacing,
        "origin_lps_mm": origin.tolist(),
        "direction": direction.tolist(),
        "contrast_reversal": contrast,
        "independent_gaussian_noise_sd": 0.03 if stress else 0.0,
        "known_fixed_to_moving": {
            "rotation_degrees": rotation,
            "translation_mm": translation,
            "center_lps_mm": center.tolist(),
        },
        "fixed_landmarks_lps_mm": landmarks.tolist(),
        "expected_moving_landmarks_lps_mm": expected.tolist(),
    }
    (folder / "ground_truth.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def dice(first: np.ndarray, second: np.ndarray) -> dict[str, float]:
    return {
        str(label): float(
            2
            * np.count_nonzero((first == label) & (second == label))
            / (np.count_nonzero(first == label) + np.count_nonzero(second == label))
        )
        for label in range(1, 6)
    }


def run_sitk(
    folder: Path, output: Path, points: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    fixed, moving = (
        sitk.ReadImage(str(folder / f"{name}.nii.gz"), sitk.sitkFloat64)
        for name in ["fixed", "moving"]
    )
    registration = sitk.ImageRegistrationMethod()
    registration.SetMetricAsMattesMutualInformation(32)
    registration.SetMetricSamplingStrategy(registration.RANDOM)
    registration.SetMetricSamplingPercentage(0.5, SEED)
    registration.SetInterpolator(sitk.sitkLinear)
    registration.SetOptimizerAsGradientDescentLineSearch(
        learningRate=1.0,
        numberOfIterations=300,
        convergenceMinimumValue=1e-6,
        convergenceWindowSize=10,
        estimateLearningRate=(
            registration.EachIteration
            if SITK_SETTINGS["estimate_learning_rate"] == "EachIteration"
            else registration.Once
        ),
        maximumStepSizeInPhysicalUnits=SITK_SETTINGS["maximum_step_size_mm"],
        lineSearchUpperLimit=SITK_SETTINGS["line_search_upper_limit"],
    )
    registration.SetOptimizerScalesFromPhysicalShift()
    registration.SetShrinkFactorsPerLevel([4, 2, 1])
    registration.SetSmoothingSigmasPerLevel([2, 1, 0])
    registration.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
    registration.SetInitialTransform(
        sitk.ReadTransform(str(folder / "initial_identity.tfm")), inPlace=False
    )
    result = registration.Execute(fixed, moving)
    sitk.WriteTransform(result, str(output / "estimated_fixed_to_moving.hdf"))
    label = sitk.ReadImage(str(folder / "moving_labels.nii.gz"))
    warped = sitk.Resample(label, fixed, result, sitk.sitkNearestNeighbor, 0)
    sitk.WriteImage(warped, str(output / "warped_labels.nii.gz"))
    sitk.WriteImage(sitk.Resample(moving, fixed, result), str(output / "warped.nii.gz"))
    return (
        transform_points(result, points),
        sitk.GetArrayFromImage(warped),
        {
            "stop_condition": registration.GetOptimizerStopConditionDescription(),
            "last_level_iterations": registration.GetOptimizerIteration(),
            "final_metric": registration.GetMetricValue(),
        },
    )


def run_ants(
    folder: Path, output: Path, points: np.ndarray
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    ants.config.set_ants_deterministic(True, seed_value=SEED)
    fixed, moving = (
        ants.image_read(str(folder / f"{name}.nii.gz"), pixeltype="double")
        for name in ["fixed", "moving"]
    )
    result = ants.registration(
        fixed=fixed,
        moving=moving,
        initial_transform=[str(folder / "initial_identity.tfm")],
        outprefix=str(output / "registration_"),
        **ANT_SETTINGS,
    )
    estimated = ants.apply_transforms_to_points(
        3,
        pd.DataFrame(points, columns=["x", "y", "z"]),
        result["fwdtransforms"],
        whichtoinvert=[False] * len(result["fwdtransforms"]),
    )
    labels = ants.image_read(str(folder / "moving_labels.nii.gz"))
    warped = ants.apply_transforms(
        fixed, labels, result["fwdtransforms"], interpolator="nearestNeighbor"
    )
    ants.image_write(warped, str(output / "warped_labels.nii.gz"))
    ants.image_write(result["warpedmovout"], str(output / "warped.nii.gz"))
    return (
        estimated[["x", "y", "z"]].to_numpy(),
        warped.numpy().transpose(2, 1, 0),
        {
            "forward_image_transforms": result["fwdtransforms"],
            "point_direction": "same list without inversion maps fixed LPS points to moving LPS points",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--sitk-bounded-step",
        action="store_true",
        help="Exploratory second recipe: estimate each iteration, 1mm step scale, line-search upper factor2",
    )
    parser.add_argument(
        "--require-success",
        action="store_true",
        help="Exit nonzero if any engine fails; preserve all study artifacts",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must not already exist; retain separate experiments")
    if args.repeats < 1:
        parser.error("repeats must be positive")
    args.output.mkdir(parents=True)
    if args.sitk_bounded_step:
        SITK_SETTINGS.update(
            estimate_learning_rate="EachIteration",
            maximum_step_size_mm=1.0,
            line_search_upper_limit=2.0,
        )
    sitk.ProcessObject.SetGlobalDefaultNumberOfThreads(1)
    study: dict[str, Any] = {
        "purpose": "synthetic rigid registration engineering comparison; NOT SPM parity or clinical validation",
        "versions": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "antspyx": ants.__version__,
            "SimpleITK": sitk.Version_VersionString(),
        },
        "seed": SEED,
        "threads": 1,
        "initialization": "identity about physical image center; no true rotation/translation supplied",
        "coordinate_contract": "all landmark points LPS mm; estimated maps fixed points to moving points",
        "settings": {"antspy": ANT_SETTINGS, "simpleitk": SITK_SETTINGS},
        "cases": [],
    }
    for name, oblique, contrast, stress in [
        ("isotropic_same", False, False, False),
        ("isotropic_contrast_reversed", False, True, False),
        ("anisotropic_oblique", True, False, False),
        ("oblique_noisy_large_motion", True, True, True),
    ]:
        folder = args.output / name
        metadata = make_case(folder, oblique=oblique, contrast=contrast, stress=stress)
        points = np.array(metadata["fixed_landmarks_lps_mm"])
        expected = np.array(metadata["expected_moving_landmarks_lps_mm"])
        fixed_image = sitk.ReadImage(str(folder / "fixed_labels.nii.gz"))
        moving_image = sitk.ReadImage(str(folder / "moving_labels.nii.gz"))
        fixed_labels = sitk.GetArrayFromImage(fixed_image)
        oracle = sitk.Resample(
            moving_image,
            fixed_image,
            sitk.ReadTransform(str(folder / "ground_truth_fixed_to_moving.tfm")),
            sitk.sitkNearestNeighbor,
            0,
        )
        case: dict[str, Any] = {
            "name": name,
            "ground_truth": metadata,
            "unregistered_tre_mean_mm": float(
                np.linalg.norm(points - expected, axis=1).mean()
            ),
            "unregistered_label_dice": dice(
                fixed_labels, sitk.GetArrayFromImage(moving_image)
            ),
            "known_transform_label_dice": dice(
                fixed_labels, sitk.GetArrayFromImage(oracle)
            ),
            "runs": [],
        }
        # Check ANTs point convention independently using the known ITK transform.
        oracle_points = ants.apply_transforms_to_points(
            3,
            pd.DataFrame(points, columns=["x", "y", "z"]),
            [str(folder / "ground_truth_fixed_to_moving.tfm")],
            whichtoinvert=[False],
        )
        np.testing.assert_allclose(
            oracle_points[["x", "y", "z"]].to_numpy(), expected, atol=1e-5
        )
        for method, runner in [("antspy", run_ants), ("simpleitk", run_sitk)]:
            for repeat in range(args.repeats):
                output = folder / f"{method}_{repeat + 1}"
                output.mkdir()
                started = time.perf_counter()
                run: dict[str, Any] = {"method": method, "repeat": repeat + 1}
                try:
                    estimated, labels, details = runner(folder, output, points)
                    errors = np.linalg.norm(estimated - expected, axis=1)
                    run.update(
                        status="completed",
                        tre_mean_mm=float(errors.mean()),
                        tre_max_mm=float(errors.max()),
                        tre_per_landmark_mm=errors.tolist(),
                        label_dice=dice(fixed_labels, labels),
                        estimated_moving_landmarks_lps_mm=estimated.tolist(),
                        details=details,
                    )
                except Exception as error:
                    run.update(
                        status="failed", error=f"{type(error).__name__}: {error}"
                    )
                run["elapsed_seconds"] = time.perf_counter() - started
                case["runs"].append(run)
                print(json.dumps({"case": name, **run}), flush=True)
        case["input_sha256"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.iterdir()
            if p.is_file()
        }
        study["cases"].append(case)
        (args.output / "results.json").write_text(json.dumps(study, indent=2) + "\n")

    if args.require_success and any(
        run["status"] != "completed" for case in study["cases"] for run in case["runs"]
    ):
        raise SystemExit("One or more registrations failed; inspect results.json")


if __name__ == "__main__":
    main()
