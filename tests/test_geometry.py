import numpy as np
import pytest

from ccep.imaging.geometry import (
    contact_positions,
    ras_lps,
    sample_nearest,
    sphere,
    spm_pull_resample,
    voxel_to_world,
    warped_roi_centroid,
    world_to_voxel,
)


def test_oblique_geometry_and_lps_roundtrip():
    affine = np.array(
        [[0, -2, 0, 10], [1, 0, 0, -4], [0, 0, 3, 6], [0, 0, 0, 1]], dtype=float
    )
    voxel = np.array([[2.0, 3.0, 4.0]])
    world = voxel_to_world(voxel, affine)
    np.testing.assert_array_equal(world, [[4, -2, 18]])
    np.testing.assert_allclose(world_to_voxel(world, affine), voxel)
    np.testing.assert_array_equal(ras_lps(ras_lps(world)), world)
    contacts = contact_positions(np.array([0.0, 0, 0]), np.array([0.0, 0, 10]), 3)
    np.testing.assert_array_equal(contacts, [[0, 0, 0], [0, 0, 5], [0, 0, 10]])


def test_sphere_centroid_tissue_bounds_and_pull_field():
    image = sphere((11, 11, 11), np.eye(4), np.array([5.0, 5, 5]))
    np.testing.assert_array_equal(warped_roi_centroid(image, np.eye(4)), [5, 5, 5])
    sampled = sample_nearest(image, np.eye(4), np.array([[5.0, 5, 5], [0, 0, 0]]))
    np.testing.assert_array_equal(sampled, [1, 0])
    with pytest.raises(ValueError, match="outside"):
        sample_nearest(image, np.eye(4), np.array([[-1.0, 0, 0]]))
    field = np.moveaxis(np.indices(image.shape, dtype=float), 0, -1)
    np.testing.assert_array_equal(spm_pull_resample(image, np.eye(4), field), image)
    image *= 0.97
    np.testing.assert_array_equal(warped_roi_centroid(image, np.eye(4)), [5, 5, 5])
    with pytest.raises(ValueError, match="threshold"):
        warped_roi_centroid(image * 0.5, np.eye(4))
