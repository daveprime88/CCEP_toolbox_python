"""Render physically resampled template-study overlays for visual review."""

import argparse
from pathlib import Path

import numpy as np

from ccep.imaging.ants_backend import _ants


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists")
    import matplotlib.pyplot as plt

    ants = _ants()
    fixed = ants.image_read(str(args.study / "t1_2mm.nii.gz"))
    rows = []
    for modality in ("t1", "t2"):
        moving = ants.image_read(str(args.study / f"moving_{modality}.nii.gz"))
        before = ants.resample_image_to_target(moving, fixed, interp_type="linear")
        after = ants.image_read(str(args.study / modality / "moving_in_fixed.nii.gz"))
        rows.append((before.numpy(), after.numpy()))
    data = fixed.numpy()
    index = int(round((0 - fixed.origin[2]) / fixed.spacing[2]))
    fig, axes = plt.subplots(
        2, 3, figsize=(12, 8), facecolor="white", constrained_layout=True
    )
    fixed_slice = data[:, :, index].T
    for row, (before, after) in enumerate(rows):
        for col, values in enumerate((data, before, after)):
            axis = axes[row, col]
            axis.imshow(
                values[:, :, index].T,
                cmap="gray",
                origin="lower",
                vmin=0,
                vmax=np.percentile(values, 99),
            )
            if col:
                axis.contour(
                    fixed_slice,
                    levels=[45, 75, 105],
                    colors=["#e9bd4f"],
                    linewidths=0.4,
                    alpha=0.75,
                )
            axis.set_title(
                [
                    "Fixed T1",
                    "Before: physical-grid resample",
                    "After: registered image",
                ][col]
            )
            axis.set_xticks([])
            axis.set_yticks([])
            if col == 0:
                axis.set_ylabel("Moving T1" if row == 0 else "Moving T2")
    fig.suptitle(
        "ICBM152 ext55 known-motion checks at z=0 mm\nGold contours: fixed T1; template-derived inputs, not SPM or patient validation"
    )
    fig.savefig(args.output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
