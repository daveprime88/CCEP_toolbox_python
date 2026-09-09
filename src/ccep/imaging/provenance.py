"""Detect inputs changing during a long imaging operation before marking it complete."""

from pathlib import Path

from ccep.reference import sha256


def snapshot_inputs(paths: list[Path]) -> dict[Path, str]:
    return {path: sha256(path) for path in paths}


def verify_unchanged(snapshot: dict[Path, str]) -> None:
    for path, digest in snapshot.items():
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(
                f"Input changed during processing; preserve partial outputs and rerun from stable inputs: {path}"
            )
