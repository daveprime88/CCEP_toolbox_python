"""Import the captured CCEP ElectrodeArray acquisition schema without guessing paths."""

from pathlib import Path

import numpy as np

from ccep.imaging.images import load_spatial_mm
from ccep.imaging.provenance import snapshot_inputs, verify_unchanged
from ccep.imaging.session import Electrode, ImagingSession, save_session
from ccep.io.legacy import read_mat


def import_electrodes(source: Path, native: Path, output: Path) -> ImagingSession:
    """Import endpoints only when every saved PosMM agrees with interpolation.

    Native image is explicit: legacy ImageFile is a filename, not sufficient
    evidence of coordinate space. Original MAT is retained with all untouched
    metadata; this is an acquisition-session adapter, not a full MAT replacement.
    """
    if output.exists():
        raise FileExistsError(output)
    hashes = snapshot_inputs([source, native])
    load_spatial_mm(native)
    values = read_mat(source).get("ElectrodeArray")
    required = {"ElectrodeName", "StartMM", "EndMM", "NumContacts", "PosMM"}
    if not isinstance(values, np.ndarray) or not required.issubset(
        values.dtype.names or ()
    ):
        raise ValueError("Expected CCEP ElectrodeArray acquisition fields")
    electrodes = []
    for item in values.ravel(order="F"):
        name = "".join(np.asarray(item["ElectrodeName"]).astype(str).ravel())
        counts = np.asarray(item["NumContacts"]).ravel()
        start = np.asarray(item["StartMM"], dtype=float).ravel()
        end = np.asarray(item["EndMM"], dtype=float).ravel()
        if counts.size != 1 or start.size != 3 or end.size != 3:
            raise ValueError("Malformed acquisition endpoints/contact count")
        count = float(counts[0])
        if not np.isfinite(count) or not count.is_integer():
            raise ValueError("Contact count must be an integer")
        electrode = Electrode(
            name=name,
            mesial_ras_mm=tuple(start),
            lateral_ras_mm=tuple(end),
            contacts=int(count),
        )
        saved = np.asarray(item["PosMM"], dtype=float)
        if saved.shape != (int(count), 3) or not np.allclose(
            saved, electrode.positions(), atol=1e-5, rtol=0
        ):
            raise ValueError(
                "Saved contact positions differ from endpoint interpolation; retain original MAT for a dedicated adapter"
            )
        electrodes.append(electrode)
    session = ImagingSession(
        native_image=native.resolve(),
        native_sha256=hashes[native],
        electrodes=tuple(electrodes),
        legacy_source=source.resolve(),
        legacy_sha256=hashes[source],
    )
    verify_unchanged(hashes)
    save_session(output, session)
    return session
