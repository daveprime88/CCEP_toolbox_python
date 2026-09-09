from types import SimpleNamespace

import numpy as np
import pytest

nib = pytest.importorskip("nibabel")
pytest.importorskip("PySide6")
from ccep.gui.imaging import ImagingViewer  # noqa: E402
from ccep.imaging.session import load_session, save_session  # noqa: E402

pytestmark = pytest.mark.gui


def save_mm(image, path):
    image.header.set_xyzt_units("mm")
    nib.save(image, path)


def test_native_affine_contact_acquisition_overlay_and_session(qtbot, tmp_path):
    affine = np.array([[-2.0, 0, 0, 12], [0, 3, 0, -15], [0, 0, 4, 8], [0, 0, 0, 1]])
    data = np.arange(1000, dtype=np.float32).reshape(10, 10, 10)
    path = tmp_path / "native.nii.gz"
    save_mm(nib.Nifti1Image(data, affine), path)
    viewer = ImagingViewer()
    qtbot.addWidget(viewer)
    viewer.show()
    viewer.open_image(path)
    assert viewer.current_ras() == (2, 0, 28)
    viewer.set_endpoint("mesial")
    # Click in voxel-i plane changes j and k, not i.
    viewer._click(SimpleNamespace(inaxes=viewer.axes[0], xdata=7.0, ydata=8.0))
    assert [b.value() for b in viewer.voxel_controls] == [5, 7, 8]
    viewer.set_endpoint("lateral")
    viewer.contact_count.setValue(3)
    viewer.add_electrode()
    np.testing.assert_allclose(
        viewer.session.electrodes[0].positions(), [[2, 0, 28], [2, 3, 34], [2, 6, 40]]
    )
    np.testing.assert_array_equal(viewer.axes[0].images[0].get_array(), data[5].T)
    viewer.open_overlay(path)
    np.testing.assert_array_equal(viewer.overlay_data, data)
    assert len(viewer.axes[0].images) == 2
    viewer.overlay_visible.setChecked(False)
    assert len(viewer.axes[0].images) == 1
    saved = tmp_path / "session.json"
    save_session(saved, viewer.session)
    restored = load_session(saved)
    assert restored == viewer.session
    with pytest.raises(ValueError, match="already exists"):
        viewer.add_electrode()
    viewer.electrodes.setCurrentRow(0)
    viewer.remove_electrode()
    assert not viewer.session.electrodes
    save_mm(nib.Nifti1Image(data + 1, affine), path)
    with pytest.raises(ValueError, match="differs"):
        load_session(saved)


def test_image_command_contact_export_preserves_space(tmp_path, capsys):
    import csv
    import json

    from ccep.cli import run
    from ccep.imaging.session import Electrode, ImagingSession
    from ccep.reference import sha256

    native = tmp_path / "image.nii.gz"
    save_mm(nib.Nifti1Image(np.ones((5, 5, 5)), np.eye(4)), native)
    session = ImagingSession(
        native_image=native,
        native_sha256=sha256(native),
        electrodes=(
            Electrode(
                name="A", mesial_ras_mm=(1, 2, 3), lateral_ras_mm=(3, 2, 3), contacts=3
            ),
        ),
    )
    path = tmp_path / "session.json"
    save_session(path, session)
    output = tmp_path / "contacts.csv"
    assert run(["--json", "image-contacts", str(path), str(output)]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["data"]["contacts"] == 3
    with output.open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows[1]["x_ras_mm"] == "2.0" and rows[1]["space"] == "native RAS mm"
    assert run(["--json", "image-inspect", str(native)]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["axis_codes"] == ["R", "A", "S"]


def test_unknown_spatial_units_are_not_reported_as_mm(tmp_path):
    from ccep.imaging.images import load_spatial_mm

    path = tmp_path / "unknown.nii.gz"
    nib.save(nib.Nifti1Image(np.ones((3, 3, 3)), np.eye(4)), path)
    with pytest.raises(ValueError, match="millimetre"):
        load_spatial_mm(path)
