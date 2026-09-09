import numpy as np
import pytest

ants = pytest.importorskip("ants")
nib = pytest.importorskip("nibabel")
from ccep.imaging.ants_backend import register, warp_contact_sphere  # noqa: E402

pytestmark = pytest.mark.imaging


def save_mm(image, path):
    image.header.set_xyzt_units("mm")
    nib.save(image, path)


def test_ants_identity_roi_preserves_world_position(tmp_path):
    values = np.zeros((20, 20, 20), dtype=np.float32)
    values[4:16, 5:14, 6:13] = 1
    affine = np.diag([1.0, 1, 1, 1])
    affine[:3, 3] = [-10, -10, -10]
    source = tmp_path / "native.nii.gz"
    save_mm(nib.Nifti1Image(values, affine), source)
    centroid = warp_contact_sphere(
        source, source, [], np.array([0.0, 0, 0]), tmp_path / "roi"
    )
    np.testing.assert_allclose(centroid, [0, 0, 0], atol=1e-6)


def test_registration_executes_and_writes_provenance(tmp_path):
    grid = np.indices((24, 24, 24), dtype=float)
    values = np.exp(
        -sum((grid[i] - [10, 12, 14][i]) ** 2 for i in range(3)) / 20
    ).astype(np.float32)
    values += 0.4 * np.exp(
        -sum((grid[i] - [16, 8, 10][i]) ** 2 for i in range(3)) / 8
    ).astype(np.float32)
    source = tmp_path / "native.nii.gz"
    save_mm(nib.Nifti1Image(values, np.eye(4)), source)
    result = register(source, source, tmp_path / "registration")
    assert result.warped.exists() and result.manifest.exists()
    assert all(p.is_file() for p in result.forward_transforms)
    warped = nib.load(result.warped).get_fdata()
    assert np.mean(np.abs(warped - values)) < 0.02
    # Exercise the real console process so native C++ logs cannot silently break JSON.
    import json
    import subprocess
    import sys

    command = subprocess.run(
        [
            sys.executable,
            "-m",
            "ccep.cli",
            "--json",
            "image-register",
            str(source),
            str(source),
            str(tmp_path / "cli-registration"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    body = json.loads(command.stdout)
    assert body["ok"] and body["command"] == "image-register"
    np.testing.assert_array_equal(nib.load(body["data"]["warped"]).get_fdata(), warped)


def test_six_prior_segmentation_writes_probability_maps(tmp_path):
    from ccep.imaging.ants_backend import segment

    grid = np.indices((24, 24, 24))
    labels = grid[0] // 4
    rng = np.random.default_rng(51)
    values = (labels + 1) * 30 + rng.normal(0, 1, labels.shape)

    def save(name, data):
        path = tmp_path / name
        save_mm(nib.Nifti1Image(np.asarray(data, dtype=np.float32), np.eye(4)), path)
        return path

    image = save("image.nii.gz", values)
    mask = save("mask.nii.gz", np.ones(labels.shape))
    priors = [
        save(f"prior{i}.nii.gz", np.where(labels == i, 0.95, 0.01)) for i in range(6)
    ]
    segmentation, probabilities = segment(
        image, mask, priors, [f"tissue{i}" for i in range(6)], tmp_path / "segment"
    )
    assert len(probabilities) == 6
    stacked = np.stack([nib.load(p).get_fdata() for p in probabilities])
    np.testing.assert_allclose(stacked.sum(axis=0), 1, atol=1e-4)
    assert set(np.unique(nib.load(segmentation).get_fdata())) <= set(range(1, 7))
