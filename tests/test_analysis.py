import numpy as np
import pytest

from ccep.analysis import (
    FilterSettings,
    PulseTrain,
    RunConfig,
    load_result,
    process,
    resolve_config,
    save_result,
)
from ccep.io.annotations import save_annotations
from ccep.io.exports import export_table
from ccep.models import AnnotationSet


def test_processing_roundtrip_and_export(edf_file, tmp_path):
    config = RunConfig(
        recording=edf_file,
        reference="bipolar",
        channels=["A1-A2"],
        trains=[PulseTrain(name="train", frequency_hz=0.5, pulse_samples=[3000, 5000])],
        filtering=FilterSettings(enabled=False),
    )
    result = process(config)
    output = tmp_path / "result.npz"
    save_result(output, result)
    restored = load_result(output)
    assert restored.metadata == result.metadata
    for key in result.arrays:
        np.testing.assert_array_equal(restored.arrays[key], result.arrays[key])
    response = (np.arange(3010, 3111) + 1) // 2
    baseline = (np.arange(895, 996) + 1) // 2
    expected = np.float32(np.sqrt(np.mean(response**2)) / np.sqrt(np.mean(baseline**2)))
    assert result.arrays["t0_c0_rms"][0] == expected
    export_table(result, tmp_path / "results.csv")
    assert "A1-A2" in (tmp_path / "results.csv").read_text()
    with pytest.raises(FileExistsError):
        save_result(output, result)


def test_annotation_edits_change_resolved_processing(edf_file, tmp_path):
    path = tmp_path / "annotations.json"
    save_annotations(path, AnnotationSet(automatic_pulses=[3000, 5000]))
    config = RunConfig(
        recording=edf_file,
        annotations=path,
        reference="unipolar",
        channels=["A1"],
        trains=[
            PulseTrain(name="train", frequency_hz=0.5, annotation_window=(2000, 6000))
        ],
    )
    first = resolve_config(config)
    assert first.trains[0].pulse_samples == [3000, 5000]
    save_annotations(path, AnnotationSet(automatic_pulses=[4000]), overwrite=True)
    assert resolve_config(config).trains[0].pulse_samples == [4000]
    assert first.trains[0].pulse_samples == [3000, 5000]


def test_cancellation_leaves_no_result(edf_file):
    config = RunConfig(
        recording=edf_file,
        reference="unipolar",
        channels=["A1"],
        trains=[PulseTrain(name="T", frequency_hz=0.5, pulse_samples=[3000])],
    )
    with pytest.raises(InterruptedError):
        process(config, cancelled=lambda: True)
