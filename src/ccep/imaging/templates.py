"""Install caller-supplied McGill assets with exact identity and retained licensing."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

from ccep.imaging.provenance import snapshot_inputs, verify_unchanged
from ccep.imaging.transforms import Grid, read_ants_mm
from ccep.reference import sha256

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


class TemplateAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: Path
    sha256: str


class TemplateBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    identity: Literal["ICBM152-ext55-symmetric-2020"] = "ICBM152-ext55-symmetric-2020"
    source_url: str = (
        "https://nist.mni.mcgill.ca/icbm-152-extended-nonlinear-atlases-2020/"
    )
    archive_sha256: str
    grid: Grid
    assets: dict[str, TemplateAsset]
    tissue_priors: tuple[str, ...] = ()
    atlas_label_names: Literal["not supplied in archive"] = "not supplied in archive"


def load_template(path: Path) -> TemplateBundle:
    bundle = TemplateBundle.model_validate_json(path.read_text())
    if set(bundle.assets) != set(ASSETS):
        raise ValueError("Incomplete McGill template asset roles")
    for asset in bundle.assets.values():
        target = (path.parent / asset.path).resolve()
        if asset.path.is_absolute() or not target.is_relative_to(path.parent.resolve()):
            raise ValueError("Template path escapes the bundle")
        if sha256(target) != asset.sha256:
            raise ValueError(f"Template asset checksum differs: {asset.path}")
    return bundle


def install_icbm152(archive: Path, output: Path) -> Path:
    """Import this explicit archive format; refuse existing folders and unsafe ZIPs.

    Full assets remain outside the installed package. No download or atlas/tissue
    inference is performed. The manifest describes the supplied archive, not an
    upstream-authenticated checksum.
    """
    if output.exists():
        raise FileExistsError(output)
    snapshot = snapshot_inputs([archive])
    expected = {f"{PREFIX}/{name}" for name in ASSETS.values()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with (
        zipfile.ZipFile(archive) as source,
        tempfile.TemporaryDirectory(dir=output.parent) as temporary,
    ):
        entries = source.infolist()
        names = [item.filename for item in entries if not item.is_dir()]
        if len(names) != len(set(names)) or set(names) != expected:
            raise ValueError(
                "Archive does not match the expected McGill ext55 asset set"
            )
        if sum(item.file_size for item in entries) > 512 * 1024**2:
            raise ValueError("Template archive exceeds the supported extracted size")
        staged = Path(temporary) / "bundle"
        staged.mkdir()
        for name in names:
            with (
                source.open(name) as incoming,
                (staged / Path(name).name).open("xb") as destination,
            ):
                shutil.copyfileobj(incoming, destination)
        grid = Grid.from_image(staged / ASSETS["t1"])
        for role, filename in ASSETS.items():
            if role == "license":
                continue
            grid.check(staged / filename)
            values = read_ants_mm(staged / filename).numpy()
            if role in {"mask", "outline"} and (
                not np.isin(values, [0, 1]).all() or not values.any()
            ):
                raise ValueError(f"Template {role} must be a nonempty binary image")
            if role == "atlas" and (
                not np.equal(values, np.floor(values)).all() or (values < 0).any()
            ):
                raise ValueError("Atlas must contain nonnegative integer IDs")
        if not (staged / "COPYING").read_text().strip():
            raise ValueError("Template license is empty")
        bundle = TemplateBundle(
            archive_sha256=snapshot[archive],
            grid=grid,
            assets={
                role: TemplateAsset(
                    path=Path(filename), sha256=sha256(staged / filename)
                )
                for role, filename in ASSETS.items()
            },
        )
        (staged / "template.json").write_text(bundle.model_dump_json(indent=2) + "\n")
        verify_unchanged(snapshot)
        if output.exists():
            raise FileExistsError(output)
        staged.rename(output)
    return output / "template.json"


def template_inspect(path: Path) -> dict[str, object]:
    bundle = load_template(path)
    return json.loads(bundle.model_dump_json())
