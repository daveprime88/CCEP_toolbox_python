import json
import zipfile

import numpy as np
import pytest

nib = pytest.importorskip("nibabel")
from ccep.imaging.anatomy import (  # noqa: E402
    atlas_lookup,
    legacy_shape,
    tissue_samples,
)
from ccep.imaging.geometry import voxel_to_world  # noqa: E402
from ccep.imaging.legacy_images import apply_spm_pull, reorient_header  # noqa: E402
from ccep.imaging.settings import (  # noqa: E402
    RegistrationSettings,
    RegistrationTask,
    task_settings,
)


def save(path, values, affine=None):
    image = nib.Nifti1Image(
        np.asarray(values, dtype=np.float32), np.eye(4) if affine is None else affine
    )
    image.header.set_xyzt_units("mm")
    nib.save(image, path)
    return path


def test_legacy_shapes_preserve_duplicates_offsets_and_cloud():
    centre = np.array([10.0, 20, 30])
    normal = np.array([1.0, 0, 0])
    cylinder = legacy_shape("cylinder", centre, normal, radius_mm=10)
    assert cylinder.shape == (36, 3)
    np.testing.assert_allclose(
        cylinder[[0, 12, 24]], cylinder[[11, 23, 35]], atol=1e-14
    )
    np.testing.assert_allclose(cylinder[:, 0].min(), 9)
    cube = legacy_shape("cube", centre, normal)
    np.testing.assert_allclose(cube[-2], centre + 1)  # Historical displaced 'centre'.
    np.testing.assert_allclose(cube.min(axis=0), centre - 1)
    np.testing.assert_allclose(cube.max(axis=0), centre + 3)
    with pytest.raises(ValueError, match="captured offsets"):
        legacy_shape("cloud", centre, normal)
    points = np.array([[0.0, 0, 0], [1, 0.5, -0.5]])
    np.testing.assert_allclose(
        legacy_shape("cloud", centre, normal, captured_cloud_offsets=points),
        points + centre,
    )


def test_tissue_sampling_preserves_weight_of_duplicate_points_and_atlas_modes():
    a = np.zeros((6, 6, 6))
    a[2, 2, 2] = 0.9
    a[3, 2, 2] = 0.3
    affine = np.array([[0, -2, 0, 9], [1, 0, 0, -4], [0, 0, 3, 7], [0, 0, 0, 1.0]])
    points = voxel_to_world(np.array([[2.0, 2, 2], [2, 2, 2], [3, 2, 2]]), affine)
    result = tissue_samples([a, 1 - a, np.zeros_like(a)], affine, points)
    np.testing.assert_allclose(result["mean"], [0.7, 0.3, 0], atol=1e-7)
    assert result["sample_count"] == 3
    atlas = np.full(a.shape, 1.2)
    with pytest.raises(ValueError, match="absent"):
        atlas_lookup(atlas, affine, points[0], {0: "OUT", 2: "region"})
    legacy = atlas_lookup(
        atlas,
        affine,
        points[0],
        {0: "OUT", 2: "region"},
        mode="legacy-closest-absolute",
        native_sample_count=36,
    )
    assert legacy["index"] == 2 and legacy["legacy_frequency"] == 1 / 36
    with pytest.raises(ValueError, match="outside"):
        tissue_samples([a, a, a], affine, np.array([[999.0, 999, 999]]))


@pytest.mark.parametrize("spm_layout", [False, True])
def test_spm_absolute_field_layout_translation_labels_and_affine(tmp_path, spm_layout):
    values = np.arange(5 * 6 * 7).reshape(5, 6, 7)
    source = save(tmp_path / "source.nii.gz", values)
    target_affine = np.eye(4)
    target_affine[:3, 3] = [1, 1, 1]
    field = voxel_to_world(
        np.indices((3, 4, 5)).reshape(3, -1).T, target_affine
    ).reshape(3, 4, 5, 3)
    path = save(
        tmp_path / "y_field.nii.gz",
        field[..., None, :] if spm_layout else field,
        target_affine,
    )
    output = apply_spm_pull(source, path, tmp_path / "warped.nii.gz", labels=True)
    np.testing.assert_array_equal(nib.load(output).get_fdata(), values[1:4, 1:5, 1:6])
    np.testing.assert_array_equal(nib.load(output).affine, target_affine)


def test_header_reorientation_preserves_pixels_original_and_collision(tmp_path):
    source = save(tmp_path / "source.nii.gz", np.arange(120).reshape(4, 5, 6))
    original = source.read_bytes()
    matrix = np.array([[0, -1, 0, 4], [1, 0, 0, 3], [0, 0, 1, 2], [0, 0, 0, 1.0]])
    output = reorient_header(source, matrix, tmp_path / "reoriented.nii.gz")
    np.testing.assert_array_equal(
        nib.load(output).get_fdata(), nib.load(source).get_fdata()
    )
    np.testing.assert_allclose(nib.load(output).affine, matrix)
    assert source.read_bytes() == original
    with pytest.raises(FileExistsError):
        reorient_header(source, matrix, output)
    matrix[0, 1] = -2
    with pytest.raises(ValueError, match="proper rigid"):
        reorient_header(source, matrix, tmp_path / "scaled.nii.gz")


def test_templates_reject_traversal_and_verify_installed_assets(tmp_path):
    pytest.importorskip("ants")
    from ccep.imaging.templates import ASSETS, PREFIX, install_icbm152, load_template

    archive = tmp_path / "template.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../escaped", "bad")
    with pytest.raises(ValueError, match="asset set"):
        install_icbm152(archive, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()
    with zipfile.ZipFile(archive, "w") as z:
        for role, name in ASSETS.items():
            if role == "license":
                z.writestr(f"{PREFIX}/{name}", "Synthetic test fixture license")
            else:
                values = np.ones((8, 9, 10))
                path = save(tmp_path / name, values)
                z.write(path, f"{PREFIX}/{name}")
    manifest = install_icbm152(archive, tmp_path / "installed")
    bundle = load_template(manifest)
    assert bundle.tissue_priors == () and bundle.grid.shape == (8, 9, 10)
    (manifest.parent / "COPYING").write_text("changed")
    with pytest.raises(ValueError, match="checksum"):
        load_template(manifest)


def test_recipes_distinguish_multimodal_and_t1_and_reject_nonfinite_schedule():
    assert task_settings(RegistrationTask.ct_to_mri).aff_metric == "mattes"
    assert task_settings(RegistrationTask.t1_to_template).syn_metric == "CC"
    with pytest.raises(ValueError):
        RegistrationSettings(aff_smoothing_sigmas=(3, 2, float("nan"), 0))


def test_sampling_cli_persists_explicit_points(tmp_path, capsys):
    from ccep.cli import run

    paths = [
        save(tmp_path / f"tissue{i}.nii.gz", np.full((4, 4, 4), value))
        for i, value in enumerate((0.2, 0.5, 0.3))
    ]
    config = tmp_path / "sample.json"
    config.write_text(
        json.dumps(
            dict(
                tissue_maps=[p.name for p in paths],
                native_points_ras_mm=[[1, 1, 1], [1, 1, 1]],
            )
        )
    )
    output = tmp_path / "result.json"
    assert run(["--json", "image-sample", str(config), str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert json.loads(output.read_text())["tissue"]["sample_count"] == 2


def test_legacy_marsbar_metric_is_explicitly_distinct():
    from ccep.imaging.geometry import marsbar_sphere, sphere

    # Rotation plus anisotropy: row norms differ from true world distance.
    affine = np.array([[0.0, -2, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    centre = voxel_to_world(np.array([[4.0, 4, 4]]), affine)[0]
    legacy = marsbar_sphere((9, 9, 9), affine, centre)
    world = sphere((9, 9, 9), affine, centre)
    assert legacy[5, 4, 4] == 0 and world[5, 4, 4] == 1
    assert legacy[4, 5, 4] == 1 and world[4, 5, 4] == 0


def test_legacy_electrode_import_retains_source_and_rejects_curved_positions(tmp_path):
    from ccep.imaging.legacy_session import import_electrodes
    from ccep.imaging.session import load_session
    from ccep.io.legacy import write_mat

    native = save(tmp_path / "native.nii.gz", np.zeros((8, 9, 10)))
    dtype = [
        (name, object)
        for name in [
            "ElectrodeName",
            "StartMM",
            "EndMM",
            "NumContacts",
            "PosMM",
            "Custom",
        ]
    ]
    electrodes = np.empty((1, 1), dtype=dtype)
    electrodes[0, 0] = (
        "A",
        np.array([[1, 2, 3]]),
        np.array([[5, 2, 3]]),
        np.array([[3]]),
        np.array([[1, 2, 3], [3, 2, 3], [5, 2, 3]]),
        "preserve",
    )
    source = tmp_path / "electrodes.mat"
    write_mat(source, dict(ElectrodeArray=electrodes))
    output = tmp_path / "session.json"
    session = import_electrodes(source, native, output)
    assert (
        session.electrodes[0].name == "A"
        and load_session(output).legacy_source == source
    )
    electrodes[0, 0]["PosMM"][1, 1] += 1
    curved = tmp_path / "curved.mat"
    write_mat(curved, dict(ElectrodeArray=electrodes))
    with pytest.raises(ValueError, match="differ from endpoint"):
        import_electrodes(curved, native, tmp_path / "curved.json")
