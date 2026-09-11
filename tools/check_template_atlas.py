"""Check CerebrA transport for a saved benchmark_ants_template known-motion run.

The ground truth is the original label array with the known motion applied only
to its header. This is an engineering check, not SPM/patient outcome acceptance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import nibabel as nib
import numpy as np

from ccep.imaging.transforms import apply_image
from ccep.reference import sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("output", type=Path, help="New output directory")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory")
    root = args.study
    expected_path, moving = root / "atlas_2mm.nii.gz", root / "moving_t1.nii.gz"
    bundle = root / "t1/transforms.json"
    args.output.mkdir(parents=True)
    output = args.output / "atlas_in_moving_t1.nii.gz"
    apply_image(
        bundle,
        expected_path,
        moving,
        output,
        direction="fixed-to-moving",
        labels=True,
    )
    expected, actual = (
        nib.load(expected_path).get_fdata(),
        nib.load(output).get_fdata(),
    )
    selected = (actual != 0) | (expected != 0)
    labels = np.unique(expected)
    if not set(np.unique(actual)) <= set(labels):
        raise ValueError("Label interpolation introduced new IDs")
    if not selected.any():
        raise ValueError("No foreground atlas labels to compare")
    report = dict(
        scope=__doc__,
        expected_ids=labels.tolist(),
        output_ids=np.unique(actual).tolist(),
        foreground_union_voxels=int(selected.sum()),
        mismatches=int((actual[selected] != expected[selected]).sum()),
        foreground_agreement=float(np.mean(actual[selected] == expected[selected])),
        macro_region_dice=float(
            np.mean(
                [
                    2
                    * np.sum((actual == i) & (expected == i))
                    / (np.sum(actual == i) + np.sum(expected == i))
                    for i in labels
                    if i != 0
                ]
            )
        ),
        interpolation="genericLabel",
        direction="fixed-to-moving",
        output_sha256=sha256(output),
        transform_bundle_sha256=sha256(bundle),
        template_atlas_sha256=sha256(expected_path),
    )
    (args.output / "atlas_transport.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
