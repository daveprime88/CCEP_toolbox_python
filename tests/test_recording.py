import numpy as np
import pytest
from scipy.io import loadmat, savemat

from ccep.io.annotations import load_annotations, save_annotations
from ccep.io.edf import EDF
from ccep.models import Annotation, AnnotationSet
from ccep.montage import bipolar, contact


def test_edf_calibration_window_and_annotation(edf_file):
    recording = EDF(edf_file)
    a = recording.read("A1", 995, 1005)
    np.testing.assert_array_equal(a.samples, np.arange(995, 1005))
    assert a.sampling_hz == 1000 and a.unit == "uV"
    b = recording.read("A2", 995, 1005)
    np.testing.assert_array_equal(
        bipolar(a, b, "A1-A2").samples, np.arange(995, 1005) - np.arange(995, 1005) // 2
    )
    assert recording.annotations(1000) == [
        Annotation(sample=2500, text="Stim start", duration_seconds=0.1)
    ]
    with pytest.raises(ValueError, match="outside"):
        recording.read("A1", -1, 2)


def test_truncated_record_rejected(edf_file):
    edf_file.write_bytes(edf_file.read_bytes()[:-1])
    with pytest.raises(ValueError, match="record count"):
        EDF(edf_file)


def test_annotations_preserve_unknown_mat_fields(tmp_path):
    path = tmp_path / "legacy.mat"
    savemat(
        path,
        {
            "Annotations": {
                "Times": 1001,
                "Time": 1001,
                "Comment": "old",
                "VendorValue": 42,
            },
            "PulseTimes": [501, 1501],
            "Unrelated": np.array([4, 5]),
        },
    )
    data = load_annotations(path)
    data.annotations[0] = Annotation(sample=1000, text="revised")
    output = tmp_path / "edited.mat"
    save_annotations(output, data)
    raw = loadmat(output, simplify_cells=True)
    assert raw["Annotations"]["VendorValue"] == 42
    assert raw["Annotations"]["Comment"] == "revised"
    np.testing.assert_array_equal(raw["Unrelated"], [4, 5])
    assert load_annotations(output).pulses == [500, 1500]
    with pytest.raises(FileExistsError):
        save_annotations(output, data)


def test_empty_and_json_annotations(tmp_path):
    for suffix in (".mat", ".json"):
        path = tmp_path / f"empty{suffix}"
        save_annotations(path, AnnotationSet())
        assert load_annotations(path).annotations == []
    assert contact("A21") == ("A2", 1)
    assert contact("A'3") == ("A'", 3)
    assert contact("DC1") == ("Other", 0)


def test_annotation_duration_survives_mat(tmp_path):
    data = AnnotationSet(
        [Annotation(sample=100, text="timed event", duration_seconds=0.25)]
    )
    path = tmp_path / "annotation.mat"
    save_annotations(path, data)
    assert load_annotations(path).annotations == data.annotations


def test_atomic_failure_preserves_existing_file(tmp_path):
    from ccep.io.atomic import atomic_binary

    path = tmp_path / "precious.mat"
    path.write_bytes(b"original")
    with pytest.raises(RuntimeError):
        with atomic_binary(path, overwrite=True) as stream:
            stream.write(b"incomplete")
            raise RuntimeError("serialization failed")
    assert path.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [path]
