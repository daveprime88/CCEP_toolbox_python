"""Publish complete files while preserving prior outputs on serialization failure."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


@contextmanager
def atomic_binary(path: Path, *, overwrite: bool = False) -> Iterator[BinaryIO]:
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    staged = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(staged, path)
        else:
            # A hard link is an atomic no-replace publish on the same filesystem.
            # Unlike checking existence then rename, it preserves concurrent outputs.
            os.link(staged, path)
    finally:
        staged.unlink(missing_ok=True)
