import numpy as np
import pytest

from ccep.imaging.deformation import (
    modulated_density,
    pull_jacobian,
    spm_one_based_affine,
)
from ccep.imaging.geometry import voxel_to_world


def world_grid(shape, affine):
    return voxel_to_world(np.indices(shape).reshape(3, -1).T, affine).reshape(*shape, 3)


def test_full_jacobian_oblique_anisotropic_and_signed_fold():
    affine = np.array([[0, -2, 0.2, 7], [1.5, 0, 0, -8], [0, 0, 3, 9], [0, 0, 0, 1]])
    field = world_grid((5, 6, 7), affine)
    np.testing.assert_allclose(pull_jacobian(field, affine), 1, atol=1e-12)
    for scale in (0.5, 2):
        np.testing.assert_allclose(
            pull_jacobian(field * scale + [4, 3, 2], affine), scale**3, atol=1e-12
        )
    field[..., 0] *= -1
    np.testing.assert_allclose(pull_jacobian(field, affine), -1, atol=1e-12)
    with pytest.raises(ValueError, match="Nonpositive"):
        modulated_density(np.ones((5, 6, 7)), affine, field, affine)


def test_density_preserves_analytic_mass_includes_affine_scaling():
    # Periodic smooth tissue over one integer domain: samples on both grids have
    # exactly the same analytic mean, with no cropped nonzero support.
    native_affine = np.eye(4)
    shape = (16, 16, 16)
    x = np.indices(shape)[0]
    probability = 0.5 + 0.25 * np.cos(2 * np.pi * x / 16)
    target_affine = np.diag([0.5, 0.5, 0.5, 1])
    pull = world_grid(shape, target_affine) * 2
    density, jacobian = modulated_density(
        probability, native_affine, pull, target_affine
    )
    np.testing.assert_allclose(jacobian, 8)
    assert density.max() > 1  # A density must not be clipped like a probability.
    assert density.sum() * abs(np.linalg.det(target_affine[:3, :3])) == pytest.approx(
        probability.sum()
    )


def test_spm_matrix_conversion_does_not_change_world_location():
    spm = np.array([[2, 0, 0, -20], [0, -3, 0, 30], [0, 0, 4, 8], [0, 0, 0, 1]])
    coordinates = np.array([[1, 1, 1], [4, 5, 6]], dtype=float)
    np.testing.assert_allclose(
        voxel_to_world(coordinates - 1, spm_one_based_affine(spm)),
        voxel_to_world(coordinates, spm),
    )
