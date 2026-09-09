"""Read legacy MATLAB containers and Excel maps without inventing missing metadata."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from openpyxl import load_workbook
from scipy.io import loadmat, savemat

from ccep.io.atomic import atomic_binary


def read_mat(path: Path) -> dict[str, Any]:
    """MAT v4/v5/v6/v7 plus numeric/char/cell/struct MATLAB 7.3 HDF5 data.

    Returned arrays preserve MATLAB axis order. MATLAB objects/function handles
    require dedicated adapters and are rejected in the HDF5 path.
    """
    if not h5py.is_hdf5(path):
        return {
            k: v
            for k, v in loadmat(path, struct_as_record=True, squeeze_me=False).items()
            if not k.startswith("__")
        }
    with h5py.File(path, "r") as file:

        def decode(node: Any, stack: frozenset[str] = frozenset()) -> Any:
            if node.name in stack:
                raise ValueError("Cyclic MATLAB references are unsupported")
            stack = stack | {node.name}
            kind = node.attrs.get("MATLAB_class", b"")
            kind = kind.decode() if isinstance(kind, bytes) else str(kind)
            if kind not in {
                "",
                "struct",
                "cell",
                "char",
                "logical",
                "double",
                "single",
                "int8",
                "int16",
                "int32",
                "int64",
                "uint8",
                "uint16",
                "uint32",
                "uint64",
            }:
                raise ValueError(f"MATLAB class {kind!r} needs a dedicated adapter")
            if isinstance(node, h5py.Group):
                if kind != "struct":
                    raise ValueError(f"Unsupported MATLAB HDF5 group: {node.name}")
                fields = {name: decode(value, stack) for name, value in node.items()}
                if not fields:
                    raise ValueError(
                        "Empty MATLAB structs need explicit dimension metadata"
                    )
                shapes = {value.shape for value in fields.values()}
                if len(shapes) != 1:
                    raise ValueError("MATLAB struct field dimensions disagree")
                shape = shapes.pop()
                result = np.empty(shape, dtype=[(name, object) for name in fields])
                for name, values in fields.items():
                    result[name] = values
                return result
            values = node[()]
            if node.attrs.get("MATLAB_empty", 0):
                shape = tuple(int(n) for n in values)
                return np.empty(shape)
            if h5py.check_dtype(ref=node.dtype):
                result = np.empty(values.shape, dtype=object)
                for index in np.ndindex(values.shape):
                    result[index] = (
                        decode(file[values[index]], stack)
                        if values[index]
                        else np.array([])
                    )
                return result.T
            if getattr(values.dtype, "fields", None):
                if set(values.dtype.fields) == {"real", "imag"}:
                    values = values["real"] + 1j * values["imag"]
                else:
                    raise ValueError("Unsupported MATLAB compound data")
            values = values.T
            if kind == "char":
                return np.asarray([chr(int(v)) for v in values.ravel()]).reshape(
                    values.shape
                )
            return values.astype(bool) if kind == "logical" else values

        return {name: decode(value) for name, value in file.items() if name != "#refs#"}


def write_mat(path: Path, variables: dict[str, Any]) -> None:
    """Write a MATLAB v5/v6-compatible file while preserving arrays/field names."""
    with atomic_binary(path) as stream:
        savemat(stream, variables, long_field_names=True, do_compression=False)


def read_map(
    path: Path, *, sheet: str = "Formatted", carry_forward: bool = True
) -> dict[str, str]:
    """Read the legacy descending-contact worksheet layout.

    CCEPMapImport carries anatomical text across blank cells before reversing
    columns. Load_Patient_Map skips blanks instead. Choose that behavior explicitly;
    this function does not silently substitute a worksheet or fill unknown labels.
    """
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet not in workbook.sheetnames:
            raise ValueError(
                f"Worksheet {sheet!r} not found; choose one of {workbook.sheetnames}"
            )
        rows = list(workbook[sheet].iter_rows(values_only=True))
    finally:
        workbook.close()
    result: dict[str, str] = {}
    for row in rows:
        if not row or not isinstance(row[0], str) or not row[0].strip():
            continue
        electrode = row[0].replace("’", "'").strip()
        if not re.fullmatch(r"[A-Za-z]{1,2}2?'?", electrode):
            raise ValueError(f"Unrecognized electrode row label: {electrode}")
        labels: list[str | None] = []
        previous = electrode  # CCEPMapImport starts filling from the row label.
        for value in row[1:]:
            if value is not None and value != "":
                previous = str(value)
                labels.append(previous)
            else:
                labels.append(previous if carry_forward else None)
        for number, anatomy in enumerate(reversed(labels), 1):
            if anatomy is None:
                continue
            label = f"{electrode}{number}"
            if label in result:
                raise ValueError(f"Duplicate anatomical map contact: {label}")
            result[label] = anatomy
    if not result:
        raise ValueError("No contact rows found in map")
    return result
