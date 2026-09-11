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


def test_registration_refuses_manifest_if_source_changes_during_native_call(
    tmp_path, monkeypatch
):
    grid = np.indices((20, 20, 20))
    values = np.exp(
        -sum((grid[i] - [8, 10, 12][i]) ** 2 for i in range(3)) / 15
    ).astype(np.float32)
    fixed = tmp_path / "fixed.nii.gz"
    moving = tmp_path / "moving.nii.gz"
    save_mm(nib.Nifti1Image(values, np.eye(4)), fixed)
    save_mm(nib.Nifti1Image(values, np.eye(4)), moving)
    from ccep.imaging.ants_backend import _register_in_process

    original_registration = ants.registration

    def registration_then_edit(*args, **kwargs):
        result = original_registration(*args, **kwargs)
        save_mm(nib.Nifti1Image(values * 2, np.eye(4)), moving)
        return result

    monkeypatch.setattr(ants, "registration", registration_then_edit)
    output = tmp_path / "changed"
    with pytest.raises(ValueError, match="Input changed during processing"):
        _register_in_process(fixed, moving, output)
    assert not (output / "registration.json").exists()
    assert not (output / "transforms.json").exists()


def test_registration_masks_recorded_and_invalid_mask_rejected(tmp_path):
    grid = np.indices((24, 24, 24))
    values = np.exp(
        -sum((grid[i] - [10, 12, 14][i]) ** 2 for i in range(3)) / 20
    ).astype(np.float32)
    source = tmp_path / "source.nii.gz"
    mask = tmp_path / "mask.nii.gz"
    save_mm(nib.Nifti1Image(values, np.eye(4)), source)
    save_mm(nib.Nifti1Image((values > 0.02).astype(np.float32), np.eye(4)), mask)
    result = register(
        source, source, tmp_path / "masked", fixed_mask=mask, moving_mask=mask
    )
    import json

    assert json.loads(result.manifest.read_text())["masks"]["all_stages"]
    save_mm(nib.Nifti1Image(np.zeros_like(values), np.eye(4)), mask)
    with pytest.raises(ValueError, match="binary and nonempty"):
        register(source, source, tmp_path / "bad-mask", fixed_mask=mask)
    assert not (tmp_path / "bad-mask").exists()


def test_auto_reorientation_keeps_original_sampling(tmp_path):
    from ccep.imaging.legacy_images import auto_reorient

    grid = np.indices((24, 24, 24))
    data = np.exp(-sum((grid[i] - [9, 11, 13][i]) ** 2 for i in range(3)) / 15).astype(
        np.float32
    )
    path = tmp_path / "source.nii.gz"
    save_mm(nib.Nifti1Image(data, np.eye(4)), path)
    manifest = auto_reorient(path, path, tmp_path / "auto")
    assert manifest.is_file()
    result = nib.load(tmp_path / "auto/reoriented.nii.gz")
    np.testing.assert_array_equal(result.get_fdata(), data)
    np.testing.assert_allclose(
        result.affine[:3, :3].T @ result.affine[:3, :3], np.eye(3), atol=1e-6
    )
    np.testing.assert_array_equal(nib.load(path).affine, np.eye(4))


def test_registration_is_independent_of_prior_itk_initialization(tmp_path):
    """Notebook use after other native operations must match a fresh CLI process."""
    import json
    import os
    import subprocess
    import sys

    grid = np.indices((24, 24, 24), dtype=float)
    data = np.exp(-sum((grid[i] - [9, 11, 13][i]) ** 2 for i in range(3)) / 15)
    source = tmp_path / "source.nii.gz"
    save_mm(nib.Nifti1Image(data.astype(np.float32), np.eye(4)), source)
    script = """
import json, os, random, sys
from pathlib import Path
import ants
import numpy as np
from ccep.imaging.ants_backend import register
source, output = map(Path, sys.argv[1:])
# Force ITK to initialize before the CCEP registration boundary.
ants.smooth_image(ants.image_read(str(source)), 1)
random.seed(43)
np.random.seed(47)
previous = (random.getstate(), np.random.get_state())
previous_threads = os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"]
result = register(source, source, output)
assert random.getstate() == previous[0]
assert np.array_equal(np.random.get_state()[1], previous[1][1])
assert os.environ["ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS"] == previous_threads
print(json.dumps({"warped": str(result.warped)}))
"""
    results = []
    for threads in ("1", "4"):
        process = subprocess.run(
            [sys.executable, "-c", script, str(source), str(tmp_path / threads)],
            env={**os.environ, "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": threads},
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        results.append(nib.load(json.loads(process.stdout)["warped"]).get_fdata())
    np.testing.assert_array_equal(*results)
