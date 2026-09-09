import h5py
import numpy as np
import pytest
from openpyxl import Workbook

from ccep.io.legacy import read_map, read_mat, write_mat
from ccep.models import Annotation
from ccep.science.annotations import stimulation_trains


def test_mat_numeric_shape_roundtrip(tmp_path):
    variables = {
        "Data": np.arange(12.0).reshape(3, 4),
        "Names": np.array(["A1", "A2"], dtype=object),
    }
    path = tmp_path / "legacy.mat"
    write_mat(path, variables)
    actual = read_mat(path)
    np.testing.assert_array_equal(actual["Data"], variables["Data"])
    assert actual["Names"].shape == (1, 2)


def test_mat73_axis_and_reference_decode(tmp_path):
    path = tmp_path / "v73.mat"
    with h5py.File(path, "w") as f:
        numeric = f.create_dataset("numeric", data=np.arange(6).reshape(3, 2))
        numeric.attrs["MATLAB_class"] = np.bytes_("double")
        cells = f.create_dataset("cell", (1, 1), dtype=h5py.ref_dtype)
        cells.attrs["MATLAB_class"] = np.bytes_("cell")
        cells[0, 0] = numeric.ref
    data = read_mat(path)
    np.testing.assert_array_equal(data["numeric"], np.arange(6).reshape(3, 2).T)
    np.testing.assert_array_equal(data["cell"][0, 0], data["numeric"])


def test_formatted_map_column_order_and_blank_rules(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Formatted"
    sheet.append([None, 3, 2, 1])
    sheet.append(["A", "OUT", "WM", None])
    path = tmp_path / "map.xlsx"
    workbook.save(path)
    assert read_map(path) == {"A1": "WM", "A2": "WM", "A3": "OUT"}
    assert read_map(path, carry_forward=False) == {"A2": "WM", "A3": "OUT"}
    with pytest.raises(ValueError, match="Worksheet"):
        read_map(path, sheet="absent")


def test_start_stop_pulse_membership_frequency_and_incomplete():
    annotations = [
        Annotation(sample=1000, text="Stim Start A2-A1 3"),
        Annotation(sample=10000, text="Stim Stop A1-A2"),
        Annotation(sample=11000, text="Stim Start B1-B2"),
    ]
    result = stimulation_trains(annotations, [1000, 2000, 4000, 6000, 10000], 1000)
    assert result[0].label == "A1-A2" and result[0].level_ma == 3
    assert (
        result[0].pulse_samples == (2000, 4000, 6000) and result[0].frequency_hz == 0.5
    )
    assert result[1].end_sample is None


def test_nested_struct_roundtrip_retains_matlab_struct_not_cell(tmp_path):
    from scipy.io import loadmat, savemat

    source, output = tmp_path / "source.mat", tmp_path / "copy.mat"
    channels = np.empty((1, 2), dtype=[("Label", object), ("RMS", object)])
    channels["Label"] = [["A1", "A2"]]
    channels["RMS"][0, 0] = np.array([[1.0], [2.0]], dtype=np.float32)
    channels["RMS"][0, 1] = np.array([[3.0], [4.0]], dtype=np.float32)
    savemat(
        source,
        {
            "StimAnnot": dict(Label="A1-A2", Uni=channels),
            "Untouched": np.array([[42.0]]),
        },
    )
    write_mat(output, read_mat(source))
    actual = loadmat(output, struct_as_record=True)["StimAnnot"]
    assert actual.dtype.names == ("Label", "Uni")
    nested = actual["Uni"][0, 0]
    assert nested.dtype.names == ("Label", "RMS") and nested.shape == (1, 2)
    assert nested["RMS"][0, 0].dtype == np.float32
    np.testing.assert_array_equal(nested["RMS"][0, 1], [[3.0], [4.0]])


def test_mat73_struct_references_write_back_as_struct(tmp_path):
    from scipy.io import loadmat

    path = tmp_path / "v73.mat"
    with h5py.File(path, "w") as f:
        refs = f.create_group("#refs#")
        number = refs.create_dataset("number", data=[[42.0]])
        number.attrs["MATLAB_class"] = np.bytes_("double")
        struct = f.create_group("DataStruct")
        struct.attrs["MATLAB_class"] = np.bytes_("struct")
        field = struct.create_dataset("Number", (1, 1), dtype=h5py.ref_dtype)
        field[0, 0] = number.ref
    data = read_mat(path)
    output = tmp_path / "v6.mat"
    write_mat(output, data)
    result = loadmat(output)["DataStruct"]
    assert result.dtype.names == ("Number",)
    assert result["Number"][0, 0][0, 0] == 42
