"""Verify the five LFS assets against the frozen original-archive baseline."""

import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    folder = root / "MNI atlases"
    manifest = json.loads((folder / "manifest.json").read_text())
    baseline = json.loads(
        (root / "reference/imaging/icbm152_sym_2009a_content.json").read_text()
    )
    assert manifest["archive_sha256"] == baseline["archive_sha256"]
    assert set(manifest["assets"]) == {"t1", "t2", "gm", "wm", "csf"}
    assert len(list(folder.glob("*.nii"))) == 5
    tissue_sum = None
    for role, asset in manifest["assets"].items():
        path = folder / asset["path"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]
        ), f"{role}: hash mismatch; fetch original data with git lfs pull"
        image = nib.load(path, mmap=False)
        data = image.get_fdata()
        expected = baseline["images"][role]
        assert list(data.shape) == expected["grid"]["shape"], role
        np.testing.assert_array_equal(image.affine, expected["grid"]["affine"])
        assert np.isfinite(data).all(), role
        assert data.size == expected["voxel_count"], role
        assert np.count_nonzero(data) == expected["nonzero_voxels"], role
        assert (
            np.count_nonzero(np.abs(data) > baseline["content_threshold"])
            == expected["content_voxels"]
        ), role
        if role in {"gm", "wm", "csf"}:
            assert data.min() >= 0 and data.max() <= 1 + 1e-6, role
            tissue_sum = data.copy() if tissue_sum is None else tissue_sum + data
        print(f"{role}: hash/grid/counts pass ({expected['nonzero_voxels']:,} nonzero)")
    assert tissue_sum is not None and tissue_sum.max() <= 1 + 1e-4
    print("All five MNI assets verified; tissue probability range/sum checks pass.")


if __name__ == "__main__":
    main()
