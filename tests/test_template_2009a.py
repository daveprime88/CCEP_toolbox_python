"""Small synthetic checks plus an opt-in count regression on the supplied archive."""

import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pytest

nib = pytest.importorskip("nibabel")
from ccep.imaging.templates import (  # noqa: E402
    ASSETS_2009A,
    DEFAULT_TEMPLATE_ID,
    PREFIX_2009A,
    check_template,
    install_icbm152,
    load_template,
)


def archive_2009a(tmp_path, *, defect=None):
    shape = (4, 5, 6)
    maps = {role: np.ones(shape) for role in ASSETS_2009A if role != "license"}
    maps["gm"] *= 0.2
    maps["gm"][2:] = 0
    maps["wm"] *= 0.5
    maps["csf"] *= 0.3
    maps["csf"][2:] = 0.5
    maps["mask"] *= 1 + 5e-8  # Header-scaling roundoff, not soft probabilities.
    maps["eye_mask"] = np.ones((2, 3, 2))
    maps["face_mask"] = np.ones((2, 2, 2)) * (1 + 5e-8)
    maps["face_mask"][0] = -1e-14
    if defect == "range":
        maps["gm"][0, 0, 0] = -0.1
    elif defect == "sum":
        maps["gm"][0, 0, 0] = 0.9
    elif defect == "coverage":
        for role in ("gm", "wm", "csf"):
            maps[role][0, 0, 0] = 0
    elif defect == "empty":
        maps["gm"][:] = 0
    archive = tmp_path / "mni_icbm152_nlin_sym_09a_nifti.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("COPYING", "Synthetic fixture license")
        for role, values in maps.items():
            affine = np.eye(4)
            if role in {"eye_mask", "face_mask"}:
                affine[:3, 3] = [-3, 2, -1]
            if role == "face_mask":
                affine[:3, :3] *= 4
            if defect == "grid" and role == "csf":
                affine[0, 3] = 2
            image = nib.Nifti1Image(values, affine)
            image.header.set_xyzt_units("mm")
            path = tmp_path / ASSETS_2009A[role]
            nib.save(image, path)
            z.write(path, f"{PREFIX_2009A}/{path.name}")
    return archive


def test_2009a_content_roles_cropped_masks_and_exact_binary_registration_mask(tmp_path):
    source = archive_2009a(tmp_path)
    manifest = install_icbm152(source, tmp_path / "installed")
    bundle = load_template(manifest)
    assert bundle.identity == DEFAULT_TEMPLATE_ID
    assert bundle.tissue_priors == ("gm", "wm", "csf")
    assert "atlas" not in bundle.assets
    report = check_template(manifest)
    assert report["passed"]
    assert report["tissue_check"]["nonzero_voxels"] == {"gm": 60, "wm": 120, "csf": 120}
    face = report["images"]["face_mask"]
    assert face["nonzero_voxels"] == 8 and face["content_voxels"] == 4
    assert face["grid"]["shape"] == [2, 2, 2]
    assert report["images"]["t1"]["grid"]["shape"] == [4, 5, 6]
    original = nib.load(manifest.parent / bundle.assets["mask"].path).get_fdata()
    derived = nib.load(manifest.parent / bundle.assets["registration_mask"].path)
    assert original.max() > 1
    assert derived.get_data_dtype() == np.dtype("uint8")
    np.testing.assert_array_equal(derived.get_fdata(), original > 0.5)
    with zipfile.ZipFile(source) as z:
        for role in ASSETS_2009A:
            name = (
                "COPYING"
                if role == "license"
                else f"{PREFIX_2009A}/{ASSETS_2009A[role]}"
            )
            assert (manifest.parent / bundle.assets[role].path).read_bytes() == z.read(
                name
            )


@pytest.mark.parametrize("defect", ["range", "sum", "coverage", "empty", "grid"])
def test_invalid_tissue_maps_are_rejected_before_publication(tmp_path, defect):
    archive = archive_2009a(tmp_path, defect=defect)
    with pytest.raises(ValueError):
        install_icbm152(archive, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_template_check_cli_detects_changed_count_baseline(tmp_path, capsys):
    from ccep.cli import run

    manifest = install_icbm152(archive_2009a(tmp_path), tmp_path / "installed")
    bundle = load_template(manifest)
    images = check_template(manifest)["images"]
    images.pop("registration_mask")
    baseline = tmp_path / "counts.json"
    expected = dict(
        identity=bundle.identity, archive_sha256=bundle.archive_sha256, images=images
    )
    baseline.write_text(json.dumps(expected))
    args = [
        "--json",
        "image-template-check",
        str(manifest),
        "--baseline",
        str(baseline),
    ]
    assert run(args) == 0
    assert json.loads(capsys.readouterr().out)["data"]["passed"]
    expected["images"]["gm"]["nonzero_voxels"] += 1
    baseline.write_text(json.dumps(expected))
    assert run(args) == 3
    body = json.loads(capsys.readouterr().out)
    assert body["diagnostics"][0]["code"] == "COMPARISON_FAILED"
    assert "gm: nonzero_voxels differs from baseline" in body["data"]["mismatches"]


def test_template_check_recomputes_stored_counts(tmp_path):
    manifest = install_icbm152(archive_2009a(tmp_path), tmp_path / "installed")
    body = json.loads(manifest.read_text())
    body["assets"]["gm"]["content"]["nonzero_voxels"] += 1
    manifest.write_text(json.dumps(body))
    assert not check_template(manifest)["passed"]


@pytest.mark.reference
def test_supplied_2009a_archive_matches_frozen_voxel_counts(tmp_path):
    archive = os.environ.get("CCEP_ICBM2009A_ZIP")
    if not archive:
        pytest.skip("Set CCEP_ICBM2009A_ZIP for the optional real-archive count check")
    baseline = (
        Path(__file__).parents[1] / "reference/imaging/icbm152_sym_2009a_content.json"
    )
    manifest = install_icbm152(Path(archive).expanduser(), tmp_path / "installed")
    report = check_template(manifest, baseline)
    assert report["passed"], report["mismatches"]
