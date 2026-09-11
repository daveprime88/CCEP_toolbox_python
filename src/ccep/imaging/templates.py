"""Install explicit McGill assets and check their content without registration."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from ccep.imaging.images import load_spatial_mm
from ccep.imaging.provenance import snapshot_inputs, verify_unchanged
from ccep.imaging.transforms import Grid
from ccep.reference import sha256

DEFAULT_TEMPLATE_ID = "ICBM152-nonlinear-symmetric-2009a"
CONTENT_THRESHOLD = 1e-6
# Three independently quantized probability maps can sum slightly above one.
TISSUE_SUM_TOLERANCE = 1e-4
PREFIX = "icbm152_ext55_model_sym_2020"
ASSETS = {
    "t1": "mni_icbm152_t1_tal_nlin_sym_55_ext.nii",
    "t2": "mni_icbm152_t2_tal_nlin_sym_55_ext.nii",
    "pd": "mni_icbm152_pd_tal_nlin_sym_55_ext.nii",
    "mask": "mni_icbm152_t1_tal_nlin_sym_55_ext_mask.nii",
    "outline": "mni_icbm152_t1_tal_nlin_sym_55_ext_outline.nii",
    "atlas": "mni_icbm152_CerebrA_tal_nlin_sym_55_ext.nii",
    "license": "COPYING",
}
PREFIX_2009A = "mni_icbm152_nlin_sym_09a"
ASSETS_2009A = {
    **{
        role: f"mni_icbm152_{role}_tal_nlin_sym_09a.nii"
        for role in ("t1", "t2", "pd", "gm", "wm", "csf")
    },
    "t2_relaxometry": "mni_icbm152_t2_relx_tal_nlin_sym_09a.nii",
    **{
        role: f"mni_icbm152_t1_tal_nlin_sym_09a_{role}.nii"
        for role in ("mask", "eye_mask", "face_mask")
    },
    "license": "COPYING",
}
Identity = Literal["ICBM152-ext55-symmetric-2020", "ICBM152-nonlinear-symmetric-2009a"]


@dataclass(frozen=True)
class ArchiveProfile:
    identity: Identity
    members: dict[str, str]
    source_url: str
    tissue_priors: tuple[str, ...] = ()


PROFILES = (
    ArchiveProfile(
        "ICBM152-nonlinear-symmetric-2009a",
        {
            role: name if role == "license" else f"{PREFIX_2009A}/{name}"
            for role, name in ASSETS_2009A.items()
        },
        "https://nist.mni.mcgill.ca/icbm-152-nonlinear-atlases-2009/",
        ("gm", "wm", "csf"),
    ),
    ArchiveProfile(
        "ICBM152-ext55-symmetric-2020",
        {role: f"{PREFIX}/{name}" for role, name in ASSETS.items()},
        "https://nist.mni.mcgill.ca/icbm-152-extended-nonlinear-atlases-2020/",
    ),
)


class ImageContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    grid: Grid
    voxel_count: int
    nonzero_voxels: int
    content_voxels: int
    content_threshold: float = CONTENT_THRESHOLD
    minimum: float
    maximum: float


class TemplateAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: Path
    sha256: str
    content: ImageContent | None = None


class TemplateBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1, 2] = 2
    identity: Identity = "ICBM152-nonlinear-symmetric-2009a"
    source_url: str
    archive_sha256: str
    grid: Grid
    assets: dict[str, TemplateAsset]
    tissue_priors: tuple[str, ...] = ()
    tissue_check: dict[str, object] | None = None
    atlas_label_names: Literal["not supplied in archive"] = "not supplied in archive"
    mask_policy: str = "Original mask; no conversion"


def _profile(identity: Identity) -> ArchiveProfile:
    return next(profile for profile in PROFILES if profile.identity == identity)


def load_template(path: Path) -> TemplateBundle:
    bundle = TemplateBundle.model_validate_json(path.read_text())
    profile = _profile(bundle.identity)
    expected = set(profile.members)
    if bundle.identity == DEFAULT_TEMPLATE_ID:
        expected.add("registration_mask")
    if set(bundle.assets) != expected or bundle.tissue_priors != profile.tissue_priors:
        raise ValueError("Incorrect McGill template asset/tissue roles")
    for asset in bundle.assets.values():
        target = (path.parent / asset.path).resolve()
        if asset.path.is_absolute() or not target.is_relative_to(path.parent.resolve()):
            raise ValueError("Template path escapes the bundle")
        if sha256(target) != asset.sha256:
            raise ValueError(f"Template asset checksum differs: {asset.path}")
    return bundle


def _content(path: Path) -> tuple[ImageContent, np.ndarray]:
    image = load_spatial_mm(path)
    # Count decoded NIfTI intensities, including scl_slope/scl_inter. Raw stored
    # int16 values have different zero counts in these McGill assets.
    values = np.asarray(image.get_fdata(), dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f"Template contains nonfinite intensities: {path.name}")
    return (
        ImageContent(
            grid=Grid.from_image(path),
            voxel_count=int(values.size),
            nonzero_voxels=int(np.count_nonzero(values)),
            content_voxels=int(np.count_nonzero(np.abs(values) > CONTENT_THRESHOLD)),
            minimum=float(values.min()),
            maximum=float(values.max()),
        ),
        values,
    )


def _check_images(
    directory: Path, assets: dict[str, Path], priors: tuple[str, ...]
) -> tuple[dict[str, ImageContent], dict[str, object] | None]:
    grid = Grid.from_image(directory / assets["t1"])
    summaries: dict[str, ImageContent] = {}
    tissue_sum = None
    brain_mask = None
    for role, filename in assets.items():
        if role == "license":
            continue
        summary, values = _content(directory / filename)
        # McGill eye/face masks intentionally have cropped/coarser physical grids.
        if role not in {"eye_mask", "face_mask"}:
            grid.check(directory / filename)
        if summary.content_voxels == 0:
            raise ValueError(f"Template {role} has no nonzero content")
        if role in {"mask", "registration_mask", "outline", "eye_mask", "face_mask"}:
            if not np.all(
                (np.abs(values) <= CONTENT_THRESHOLD)
                | (np.abs(values - 1) <= CONTENT_THRESHOLD)
            ):
                raise ValueError(
                    f"Template {role} must be a nonempty binary mask within scaling tolerance"
                )
            if role == "mask":
                brain_mask = values > 0.5
        if role == "atlas" and (
            not np.equal(values, np.floor(values)).all() or (values < 0).any()
        ):
            raise ValueError("Atlas must contain nonnegative integer IDs")
        if role in priors:
            if (values < 0).any() or (values > 1 + CONTENT_THRESHOLD).any():
                raise ValueError(f"Tissue probability {role} lies outside [0,1]")
            tissue_sum = values.copy() if tissue_sum is None else tissue_sum + values
        summaries[role] = summary
    tissue_check: dict[str, object] | None = None
    if priors:
        assert tissue_sum is not None and brain_mask is not None
        if float(tissue_sum.max()) > 1 + TISSUE_SUM_TOLERANCE:
            raise ValueError("GM/WM/CSF sum exceeds one beyond quantization tolerance")
        uncovered = int(np.count_nonzero(tissue_sum[brain_mask] <= CONTENT_THRESHOLD))
        if uncovered:
            raise ValueError("Tissue priors leave brain-mask voxels uncovered")
        tissue_check = dict(
            classes=list(priors),
            nonzero_voxels={role: summaries[role].nonzero_voxels for role in priors},
            sum_minimum=float(tissue_sum.min()),
            sum_maximum=float(tissue_sum.max()),
            sum_excess_tolerance=TISSUE_SUM_TOLERANCE,
            uncovered_brain_mask_voxels=uncovered,
            brain_mask_sum_minimum=float(tissue_sum[brain_mask].min()),
            policy="Original GM/WM/CSF preserved; no renormalization or invented head-tissue classes",
        )
    return summaries, tissue_check


def install_icbm152(archive: Path, output: Path) -> Path:
    """Import 2009a (preferred) or historical ext55 ZIP; preserve original assets."""
    if output.exists():
        raise FileExistsError(output)
    snapshot = snapshot_inputs([archive])
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        zipfile.ZipFile(archive) as source,
        tempfile.TemporaryDirectory(dir=output.parent) as temporary,
    ):
        entries = source.infolist()
        names = [item.filename for item in entries if not item.is_dir()]
        profile = next(
            (p for p in PROFILES if set(names) == set(p.members.values())), None
        )
        if len(names) != len(set(names)) or profile is None:
            raise ValueError("Archive does not match a supported McGill asset set")
        if sum(item.file_size for item in entries) > 512 * 1024**2:
            raise ValueError("Template archive exceeds the supported extracted size")
        staged = Path(temporary) / "bundle"
        staged.mkdir()
        assets = {role: Path(name).name for role, name in profile.members.items()}
        for name in names:
            with (
                source.open(name) as incoming,
                (staged / Path(name).name).open("xb") as destination,
            ):
                shutil.copyfileobj(incoming, destination)
        paths = {role: Path(name) for role, name in assets.items()}
        summaries, tissue_check = _check_images(staged, paths, profile.tissue_priors)
        mask_policy = "Original mask; no conversion"
        if profile.identity == DEFAULT_TEMPLATE_ID:
            import nibabel as nib

            original = load_spatial_mm(staged / paths["mask"])
            binary = nib.Nifti1Image(
                (original.get_fdata() > 0.5).astype(np.uint8), original.affine
            )
            binary.header.set_xyzt_units("mm")
            paths["registration_mask"] = Path("registration_mask.nii.gz")
            nib.save(binary, staged / paths["registration_mask"])
            summaries["registration_mask"], _ = _content(
                staged / paths["registration_mask"]
            )
            mask_policy = "Original masks retained; registration_mask is uint8 (original brain mask >0.5) after verifying 0/1 within 1e-6"
        if not (staged / "COPYING").read_text().strip():
            raise ValueError("Template license is empty")
        bundle = TemplateBundle(
            identity=profile.identity,
            source_url=profile.source_url,
            archive_sha256=snapshot[archive],
            grid=summaries["t1"].grid,
            tissue_priors=profile.tissue_priors,
            tissue_check=tissue_check,
            mask_policy=mask_policy,
            assets={
                role: TemplateAsset(
                    path=filename,
                    sha256=sha256(staged / filename),
                    content=summaries.get(role),
                )
                for role, filename in paths.items()
            },
        )
        (staged / "template.json").write_text(bundle.model_dump_json(indent=2) + "\n")
        verify_unchanged(snapshot)
        if output.exists():
            raise FileExistsError(output)
        staged.rename(output)
    return output / "template.json"


def template_inspect(path: Path) -> dict[str, object]:
    return json.loads(load_template(path).model_dump_json())


def check_template(path: Path, baseline: Path | None = None) -> dict[str, object]:
    """Recompute voxel counts/ranges/grids; optionally compare a frozen count baseline."""
    snapshot = snapshot_inputs([path, *([baseline] if baseline else [])])
    bundle = load_template(path)
    summaries, tissues = _check_images(
        path.parent,
        {role: asset.path for role, asset in bundle.assets.items()},
        bundle.tissue_priors,
    )
    mismatches = []
    for role, summary in summaries.items():
        saved = bundle.assets[role].content
        if saved is not None and summary != saved:
            mismatches.append(f"{role}: stored content summary differs")
    if bundle.tissue_check is not None and tissues != bundle.tissue_check:
        mismatches.append("Stored tissue summary differs")
    if baseline is not None:
        expected = json.loads(baseline.read_text())
        if (
            expected["identity"] != bundle.identity
            or expected["archive_sha256"] != bundle.archive_sha256
        ):
            mismatches.append("Baseline template/archive identity differs")
        if expected.get("content_threshold", CONTENT_THRESHOLD) != CONTENT_THRESHOLD:
            mismatches.append("Baseline content threshold differs")
        expected_counts = expected["images"]
        original_roles = set(_profile(bundle.identity).members) - {"license"}
        if set(expected_counts) != original_roles:
            mismatches.append("Baseline must cover every original image")
        for role in original_roles & set(expected_counts):
            actual = summaries[role].model_dump(mode="json")
            for key in ("nonzero_voxels", "content_voxels", "voxel_count", "grid"):
                if expected_counts[role][key] != actual[key]:
                    mismatches.append(f"{role}: {key} differs from baseline")
    if load_template(path) != bundle:
        raise ValueError("Template changed during content checking")
    verify_unchanged(snapshot)
    return dict(
        passed=not mismatches,
        identity=bundle.identity,
        archive_sha256=bundle.archive_sha256,
        images={
            role: summary.model_dump(mode="json") for role, summary in summaries.items()
        },
        tissue_check=tissues,
        mismatches=mismatches,
        scope="Content sanity only; not registration or SPM scientific acceptance",
    )
