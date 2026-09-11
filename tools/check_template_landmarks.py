"""Evaluate a full template-registration run using previously withheld study points."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ccep.imaging.transforms import apply_points
from ccep.io.atomic import atomic_binary
from ccep.reference import sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path, help="Known-motion study results.json")
    parser.add_argument("registration", type=Path, help="Full template run directory")
    parser.add_argument("output", type=Path, help="New JSON report")
    args = parser.parse_args()
    study = json.loads(args.study.read_text())
    case = next(c for c in study["cases"] if c["modality"] == "t1")
    registration = json.loads((args.registration / "registration.json").read_text())
    template = json.loads((args.registration / "template_reference.json").read_text())
    if (
        registration["moving_sha256"] != case["inputs"]["moving_t1.nii.gz"]
        or study["template_bundle_sha256"] != template["manifest_sha256"]
        or registration["fixed_sha256"] != template["fixed_sha256"]
    ):
        raise ValueError("Registration inputs do not match the known-motion study")
    bundle = args.registration / "transforms.json"
    fixed, moving = np.asarray(case["fixed_points_ras_mm"]), np.asarray(
        case["moving_points_ras_mm"]
    )
    points = apply_points(bundle, moving)
    back = apply_points(bundle, points, direction="fixed-to-moving")
    error = np.linalg.norm(points - fixed, axis=1)
    report = dict(
        scope="Known rigid header motion; 1mm fixed template and 2mm moving T1. Not a patient or SPM comparison",
        recipe=registration["requested_settings"],
        fixed_sha256=registration["fixed_sha256"],
        moving_sha256=registration["moving_sha256"],
        transform_bundle_sha256=sha256(bundle),
        registration_sha256=sha256(args.registration / "registration.json"),
        study_sha256=sha256(args.study),
        point_count=len(points),
        mean_tre_mm=float(error.mean()),
        median_tre_mm=float(np.median(error)),
        maximum_tre_mm=float(error.max()),
        inverse_maximum_mm=float(np.linalg.norm(back - moving, axis=1).max()),
        fixed_points_ras_mm=fixed.tolist(),
        moving_points_ras_mm=moving.tolist(),
        recovered_points_ras_mm=points.tolist(),
    )
    with atomic_binary(args.output) as stream:
        stream.write((json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
