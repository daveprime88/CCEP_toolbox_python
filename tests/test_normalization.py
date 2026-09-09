import json
import subprocess
import sys

import numpy as np
import pytest

ants = pytest.importorskip("ants")
nib = pytest.importorskip("nibabel")
from ccep.imaging.ants_backend import segment  # noqa: E402
from ccep.imaging.deformation import full_pull_field, pull_jacobian  # noqa: E402
from ccep.imaging.normalization import normalize  # noqa: E402
from ccep.imaging.settings import RegistrationSettings  # noqa: E402
from ccep.imaging.transforms import apply_points, capture_bundle  # noqa: E402
from ccep.reference import sha256  # noqa: E402

pytestmark = pytest.mark.imaging


def save(tmp_path, name, values):
    path = tmp_path / name
    image = nib.Nifti1Image(np.asarray(values, dtype=np.float32), np.eye(4))
    image.header.set_xyzt_units("mm")
    nib.save(image, path)
    return path


def inputs(tmp_path):
    labels = np.indices((24, 24, 24))[0] // 4
    values = (labels + 1) * 30 + np.random.default_rng(1729).normal(
        0, 0.5, labels.shape
    )
    source = save(tmp_path, "image.nii.gz", values)
    mask = np.zeros(labels.shape)
    mask[2:-2, 2:-2, 2:-2] = 1
    mask = save(tmp_path, "mask.nii.gz", mask)
    priors = [
        save(tmp_path, f"prior{i}.nii.gz", np.where(labels == i, 0.95, 0.01))
        for i in range(6)
    ]
    return source, mask, priors


def test_full_normalization_executes_and_preserves_roles(tmp_path):
    source, mask, priors = inputs(tmp_path)
    output = tmp_path / "normalized"
    recipe = RegistrationSettings(
        recipe="explicit-v1",
        aff_iterations=(0,),
        aff_shrink_factors=(1,),
        aff_smoothing_sigmas=(0,),
        reg_iterations=(5, 0),
        initialization="identity",
    )
    path = normalize(source, mask, source, priors, output, settings=recipe)
    body = json.loads(path.read_text())
    assert len(body["roles"]["native_probabilities"]) == 6
    assert len(body["roles"]["normalized_probabilities"]) == 6
    assert len(body["roles"]["modulated_densities"]) == 3
    for name, digest in body["artifacts"].items():
        assert sha256(output / name) == digest
    assert body["qc"]["jacobian_min"] > 0
    mask_values = nib.load(mask).get_fdata() == 1
    posterior_sum = sum(
        nib.load(output / p).get_fdata() for p in body["roles"]["native_probabilities"]
    )
    np.testing.assert_allclose(posterior_sum[mask_values], 1, atol=1e-4)
    assert body["inputs"]["image"] == sha256(source)
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            dict(
                image=str(source),
                mask=str(mask),
                template=str(source),
                priors=list(map(str, priors)),
                registration_settings=recipe.model_dump(mode="json"),
            )
        )
    )
    invocation = subprocess.run(
        [
            sys.executable,
            "-m",
            "ccep.cli",
            "--json",
            "image-normalize",
            str(config),
            str(tmp_path / "cli-normalized"),
        ],
        capture_output=True,
        text=True,
        timeout=90,
        check=True,
    )
    envelope = json.loads(invocation.stdout)
    assert envelope["ok"] and envelope["command"] == "image-normalize"
    cli_manifest = json.loads(
        (tmp_path / "cli-normalized" / "normalization.json").read_text()
    )
    for role in [
        "native_probabilities",
        "normalized_probabilities",
        "modulated_densities",
    ]:
        for api_path, cli_path in zip(
            body["roles"][role], cli_manifest["roles"][role], strict=True
        ):
            np.testing.assert_allclose(
                nib.load(output / api_path).get_fdata(),
                nib.load(tmp_path / "cli-normalized" / cli_path).get_fdata(),
                atol=1e-6,
            )

    # Test both saved nonlinear directions on withheld native RAS contacts.
    bundle = output / body["transform_bundle"]
    points = np.array([[8.0, 9, 10], [13, 12, 14]])
    mapped = apply_points(bundle, points)
    np.testing.assert_allclose(
        apply_points(bundle, mapped, direction="fixed-to-moving"), points, atol=0.15
    )


def test_composed_affine_field_contains_full_volume_scale(tmp_path):
    source = save(tmp_path, "image.nii.gz", np.ones((10, 11, 12)))
    transform = ants.create_ants_transform(
        transform_type="AffineTransform",
        dimension=3,
        matrix=np.diag([2.0, 2, 2]),
        translation=[-3, 4, 5],
    )
    affine = tmp_path / "scale.mat"
    ants.write_transform(transform, str(affine))
    body = capture_bundle(source, source, (affine,), (affine,), tmp_path)
    manifest = tmp_path / "transforms.json"
    manifest.write_text(body.model_dump_json())
    field = full_pull_field(manifest, source, source, tmp_path / "displacement.nii.gz")
    xyz = np.indices((10, 11, 12)).transpose(1, 2, 3, 0)
    np.testing.assert_allclose(field, 2 * xyz + [3, -4, 5], atol=1e-5)
    np.testing.assert_allclose(pull_jacobian(field, np.eye(4)), 8, atol=1e-5)


@pytest.mark.parametrize("invalid", ["mask", "intensity", "prior"])
def test_invalid_segmentation_inputs_fail_before_output(tmp_path, invalid):
    source, mask, priors = inputs(tmp_path)
    if invalid == "mask":
        mask = save(tmp_path, "bad_mask.nii.gz", np.zeros((24, 24, 24)))
    elif invalid == "intensity":
        source = save(tmp_path, "bad_image.nii.gz", -np.ones((24, 24, 24)))
    else:
        priors[0] = save(tmp_path, "bad_prior.nii.gz", np.ones((24, 24, 24)) * 1.1)
    output = tmp_path / "bad_output"
    with pytest.raises(ValueError):
        segment(source, mask, priors, list("abcdef"), output)
    assert not output.exists()


def test_explicit_syn_keeps_nonidentity_prealignment(tmp_path):
    from ccep.imaging.ants_backend import register

    grid = np.indices((24, 24, 24))
    data = np.exp(-sum((grid[i] - [8, 11, 14][i]) ** 2 for i in range(3)) / 15)
    fixed = save(tmp_path, "fixed.nii.gz", data)
    moving = tmp_path / "moving.nii.gz"
    image = nib.load(fixed)
    affine = np.eye(4)
    affine[:3, 3] = [3, -2, 1]
    shifted = nib.Nifti1Image(image.get_fdata(), affine)
    shifted.header.set_xyzt_units("mm")
    nib.save(shifted, moving)
    settings = RegistrationSettings(
        recipe="explicit-v1",
        aff_iterations=(0,),
        aff_shrink_factors=(1,),
        aff_smoothing_sigmas=(0,),
        reg_iterations=(0,),
    )
    result = register(
        fixed, moving, tmp_path / "registered", transform="SyN", settings=settings
    )
    bundle = result.manifest.parent / "transforms.json"
    points = np.array([[11.0, 9, 15], [13, 8, 12]])
    np.testing.assert_allclose(
        apply_points(bundle, points), points - [3, -2, 1], atol=1e-4
    )
    field = full_pull_field(bundle, moving, fixed, tmp_path / "full.nii.gz")
    np.testing.assert_allclose(field[8, 11, 14], [11, 9, 15], atol=1e-4)
