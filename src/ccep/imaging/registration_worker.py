"""Private process boundary for reproducible ANTs registration; no fallback engine."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from ccep.imaging.settings import RegistrationSettings

if TYPE_CHECKING:
    from ccep.imaging.ants_backend import Registration


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixed: Path
    moving: Path
    output: Path
    transform: Literal["Rigid", "Affine", "SyN"]
    seed: int = Field(ge=0, lt=2**32)
    settings: RegistrationSettings
    fixed_mask: Path | None = None
    moving_mask: Path | None = None


_ERRORS: dict[str, type[Exception]] = {
    cls.__name__: cls
    for cls in (
        ValueError,
        FileExistsError,
        FileNotFoundError,
        ImportError,
        RuntimeError,
    )
}


def run_registration(request: RegistrationRequest) -> Registration:
    from ccep.imaging.ants_backend import Registration

    if request.output.exists():
        raise FileExistsError(request.output)
    with TemporaryDirectory(prefix="ccep-registration-") as temporary:
        root = Path(temporary)
        job, response, log = (
            root / "job.json",
            root / "response.json",
            root / "native.log",
        )
        job.write_text(request.model_dump_json())
        with log.open("wb") as stream:
            process = subprocess.run(
                [sys.executable, "-m", __name__, str(job), str(response)],
                env={**os.environ, "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": "1"},
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if not response.is_file():
            # Native exceptions/crashes may bypass Python. Keep diagnostics bounded.
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 8000))
                detail = stream.read().decode(errors="replace")
            raise RuntimeError(
                f"ANTs registration worker exited {process.returncode}: {detail}"
            )
        body = json.loads(response.read_text())
        if "error" in body:
            raise _ERRORS.get(body["error"], RuntimeError)(body["message"])
        if process.returncode:
            raise RuntimeError(f"ANTs registration worker exited {process.returncode}")
        return Registration(
            warped=Path(body["warped"]),
            forward_transforms=tuple(Path(p) for p in body["forward_transforms"]),
            inverse_transforms=tuple(Path(p) for p in body["inverse_transforms"]),
            manifest=Path(body["manifest"]),
        )


def main() -> None:
    # Called only by run_registration; the environment is set before Python starts.
    from dataclasses import asdict

    from ccep.imaging.ants_backend import _register_in_process

    request_path, response = map(Path, sys.argv[1:])
    try:
        request = RegistrationRequest.model_validate_json(request_path.read_text())
        result = _register_in_process(
            request.fixed,
            request.moving,
            request.output,
            transform=request.transform,
            seed=request.seed,
            settings=request.settings,
            fixed_mask=request.fixed_mask,
            moving_mask=request.moving_mask,
        )
    except Exception as error:
        response.write_text(
            json.dumps(dict(error=type(error).__name__, message=str(error)))
        )
        raise SystemExit(1) from error
    response.write_text(json.dumps(asdict(result), default=str))


if __name__ == "__main__":
    main()
