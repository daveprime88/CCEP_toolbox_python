import json
import shutil

import numpy as np
import pytest

ants = pytest.importorskip("ants")
nib = pytest.importorskip("nibabel")
from ccep.imaging.transforms import (  # noqa: E402
    apply_image,
    apply_points,
    capture_bundle,
    read_ants_mm,
)

pytestmark = pytest.mark.imaging


def save(tmp_path, name, data, affine=None):
    path = tmp_path / name
    image = nib.Nifti1Image(
        np.asarray(data, dtype=np.float32), np.eye(4) if affine is None else affine
    )
    image.header.set_xyzt_units("mm")
    nib.save(image, path)
    return path


def translation_bundle(tmp_path):
    values = np.zeros((18, 18, 18))
    values[8, 8, 8] = 7
    source = save(tmp_path, "source.nii.gz", values)
    transform = ants.create_ants_transform(
        transform_type="AffineTransform", dimension=3, translation=(2, -3, 1)
    )
    path = tmp_path / "affine.mat"
    ants.write_transform(transform, str(path))
    bundle = capture_bundle(source, source, (path,), (path,), tmp_path)
    manifest = tmp_path / "transforms.json"
    manifest.write_text(bundle.model_dump_json(indent=2))
    return source, manifest


def test_affine_only_inverse_points_agree_with_image_landmark(tmp_path):
    source, manifest = translation_bundle(tmp_path)
    points = np.array([[8.0, 8, 8], [3, 4, 5]])
    mapped = apply_points(manifest, points)
    np.testing.assert_allclose(mapped, points + [2, -3, -1], atol=1e-6)
    np.testing.assert_allclose(
        apply_points(manifest, mapped, direction="fixed-to-moving"), points, atol=1e-6
    )
    output = apply_image(
        manifest, source, source, tmp_path / "forward.nii.gz", labels=True
    )
    data = nib.load(output).get_fdata()
    np.testing.assert_array_equal(np.argwhere(data == 7), [mapped[0]])
    inverse = apply_image(
        manifest,
        output,
        source,
        tmp_path / "inverse.nii.gz",
        direction="fixed-to-moving",
        labels=True,
    )
    np.testing.assert_array_equal(
        nib.load(inverse).get_fdata(), nib.load(source).get_fdata()
    )


def test_portable_bundle_integrity_and_explicit_inverse(tmp_path):
    source, manifest = translation_bundle(tmp_path)
    body = json.loads(manifest.read_text())
    assert body["forward"][0]["invert"] is False
    assert body["inverse"][0]["invert"] is True
    moved = tmp_path / "copied"
    moved.mkdir()
    shutil.copy(manifest, moved)
    shutil.copy(tmp_path / "affine.mat", moved)
    np.testing.assert_allclose(
        apply_points(moved / manifest.name, np.zeros((1, 3))), [[2, -3, -1]]
    )
    with (moved / "affine.mat").open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="checksum"):
        apply_points(moved / manifest.name, np.zeros((1, 3)))
    different = save(tmp_path, "different.nii.gz", np.zeros((19, 18, 18)))
    with pytest.raises(ValueError, match="grid"):
        apply_image(manifest, different, source, tmp_path / "bad.nii.gz")
    assert not (tmp_path / "bad.nii.gz").exists()


def test_read_geometry_oblique_reflection_and_conflicting_headers(tmp_path):
    theta = 0.37
    affine = np.array(
        [
            [np.cos(theta), -np.sin(theta), 0, 9],
            [np.sin(theta), np.cos(theta), 0, -4],
            [0, 0, -2, 7],
            [0, 0, 0, 1],
        ]
    )
    source = save(tmp_path, "oblique.nii.gz", np.ones((5, 6, 7)), affine)
    assert read_ants_mm(source).shape == (5, 6, 7)
    image = nib.load(source)
    image.set_qform(np.eye(4), code=1)
    nib.save(image, source)
    with pytest.raises(ValueError, match="qform/sform"):
        read_ants_mm(source)
