"""Validated native-space inputs and explicit N4 parameters for the ANTs candidate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ccep.imaging.transforms import Grid, read_ants_mm

N4_SETTINGS = dict(
    rescale_intensities=False,
    shrink_factor=4,
    convergence=dict(iters=[50, 50, 50, 50], tol=1e-7),
    spline_param=None,
)
SPM_TISSUES = (
    "gray_matter",
    "white_matter",
    "csf",
    "bone",
    "soft_tissue",
    "background",
)


def masked_image(image: Path, mask: Path) -> tuple[Any, Any]:
    Grid.from_image(image).check(mask)
    original, mask_image = read_ants_mm(image), read_ants_mm(mask)
    mask_values = mask_image.numpy()
    if not np.isin(mask_values, [0, 1]).all() or not mask_values.any():
        raise ValueError("N4/Atropos mask must be binary and nonempty")
    if np.any(original.numpy()[mask_values == 1] <= 0):
        raise ValueError(
            "N4/Atropos require positive MRI intensities inside the mask; do not apply to CT HU"
        )
    return original, mask_image


def validate_priors(image: Path, mask_image: Any, priors: list[Path]) -> list[Any]:
    grid = Grid.from_image(image)
    images = []
    for path in priors:
        grid.check(path)
        images.append(read_ants_mm(path))
    values = np.stack([p.numpy() for p in images])
    selected = values[:, mask_image.numpy() == 1]
    if (values < 0).any() or (values > 1).any():
        raise ValueError("Tissue priors must be finite probabilities in [0,1]")
    if not np.allclose(selected.sum(axis=0), 1, atol=1e-4, rtol=0):
        raise ValueError("Tissue priors must sum to one inside the mask")
    if (selected.sum(axis=1) <= 0).any():
        raise ValueError("Every tissue class needs prior support inside the mask")
    return images


def correct_bias(image: Path, mask: Path, output: Path) -> Path:
    """N4 on explicitly positive MRI data; retain original intensity input."""
    from ccep.imaging.ants_backend import _REGISTRATION_LOCK, _ants

    if output.exists():
        raise FileExistsError(output)
    original, mask_image = masked_image(image, mask)
    with _REGISTRATION_LOCK:
        corrected = _ants().n4_bias_field_correction(
            original, mask=mask_image, **N4_SETTINGS
        )
    if not np.isfinite(corrected.numpy()).all():
        raise ValueError("N4 returned nonfinite intensities")
    output.parent.mkdir(parents=True, exist_ok=True)
    _ants().image_write(corrected, str(output))
    return output


def registration_mask(image: Path, mask: Path) -> Any:
    """Metric masks do not impose N4's positivity requirement on CT/MRI data."""
    Grid.from_image(image).check(mask)
    result = read_ants_mm(mask)
    values = result.numpy()
    if not np.isin(values, [0, 1]).all() or not values.any():
        raise ValueError("Registration mask must be binary and nonempty")
    return result
