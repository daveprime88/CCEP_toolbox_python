"""Explicit native image sessions and contact acquisition in RAS millimetres."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ccep.imaging.geometry import contact_positions
from ccep.io.atomic import atomic_binary
from ccep.reference import sha256


class Electrode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1)
    mesial_ras_mm: tuple[float, float, float]
    lateral_ras_mm: tuple[float, float, float]
    contacts: int = Field(ge=3, le=20)

    @model_validator(mode="after")
    def finite_endpoints(self) -> Electrode:
        if not np.isfinite([self.mesial_ras_mm, self.lateral_ras_mm]).all():
            raise ValueError("Contact endpoints must be finite RAS millimetres")
        return self

    def positions(self) -> list[list[float]]:
        return contact_positions(
            np.array(self.mesial_ras_mm), np.array(self.lateral_ras_mm), self.contacts
        ).tolist()


class ImagingSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    kind: Literal["ccep-imaging-session"] = "ccep-imaging-session"
    native_image: Path
    native_sha256: str
    overlay_image: Path | None = None
    overlay_sha256: str | None = None
    coordinate_space: Literal["native RAS mm"] = "native RAS mm"
    electrodes: tuple[Electrode, ...] = ()
    legacy_source: Path | None = None
    legacy_sha256: str | None = None

    @model_validator(mode="after")
    def consistent_identities(self) -> ImagingSession:
        if (self.legacy_source is None) != (self.legacy_sha256 is None):
            raise ValueError("Legacy source and checksum must both be supplied")
        names = [e.name for e in self.electrodes]
        if len(names) != len(set(names)):
            raise ValueError("Electrode names must be unique")
        if (self.overlay_image is None) != (self.overlay_sha256 is None):
            raise ValueError("Overlay path and checksum must both be supplied")
        return self

    def verify_inputs(self) -> None:
        if self.legacy_source and sha256(self.legacy_source) != self.legacy_sha256:
            raise ValueError("Legacy electrode source differs from the saved session")
        if sha256(self.native_image) != self.native_sha256:
            raise ValueError("Native image differs from the saved session")
        if self.overlay_image and sha256(self.overlay_image) != self.overlay_sha256:
            raise ValueError("Overlay image differs from the saved session")


def load_session(path: Path) -> ImagingSession:
    session = ImagingSession.model_validate_json(path.read_text())
    session = session.model_copy(
        update=dict(
            native_image=(path.parent / session.native_image).resolve(),
            legacy_source=(
                (path.parent / session.legacy_source).resolve()
                if session.legacy_source
                else None
            ),
            overlay_image=(
                (path.parent / session.overlay_image).resolve()
                if session.overlay_image
                else None
            ),
        )
    )
    session.verify_inputs()
    return session


def save_session(path: Path, session: ImagingSession) -> None:
    session.verify_inputs()
    session = session.model_copy(
        update=dict(
            native_image=session.native_image.resolve(),
            legacy_source=(
                session.legacy_source.resolve() if session.legacy_source else None
            ),
            overlay_image=(
                session.overlay_image.resolve() if session.overlay_image else None
            ),
        )
    )
    with atomic_binary(path) as stream:
        stream.write(session.model_dump_json(indent=2).encode() + b"\n")
