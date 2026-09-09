import json

import numpy as np
import pytest

from ccep.analysis import load_config, load_result, process
from ccep.cli import run


def invoke(capsys, *args):
    status = run(["--json", *map(str, args)])
    captured = capsys.readouterr()
    body = json.loads(captured.out)
    assert body["exit_code"] == status and body["ok"] == (status == 0)
    return status, body


def test_cli_complete_workflow_matches_api(edf_file, tmp_path, capsys):
    config = tmp_path / "run config.json"
    config.write_text(
        json.dumps(
            dict(
                schema_version=1,
                recording=edf_file.name,
                reference="bipolar",
                channels=["A1-A2"],
                trains=[
                    dict(name="test", frequency_hz=0.5, pulse_samples=[3000, 5000])
                ],
                filtering={"enabled": False},
            )
        )
    )
    assert invoke(capsys, "inspect", edf_file)[0] == 0
    assert invoke(capsys, "validate", config)[0] == 0
    output = tmp_path / "analysis result.npz"
    assert invoke(capsys, "process", config, output)[0] == 0
    expected = process(load_config(config))
    actual = load_result(output)
    for key in expected.arrays:
        np.testing.assert_array_equal(actual.arrays[key], expected.arrays[key])
    table = tmp_path / "report.csv"
    assert invoke(capsys, "export", output, table)[0] == 0
    assert table.exists()
    status, body = invoke(capsys, "process", config, output)
    assert status == 2 and body["diagnostics"][0]["code"] == "OUTPUT_EXISTS"


@pytest.mark.parametrize(
    "args,code",
    [
        (["inspect", "does not exist.edf"], "INPUT_NOT_FOUND"),
        (["unknown-command"], "CLI_USAGE"),
        (["process"], "CLI_USAGE"),
        (["inspect", "--unknown"], "CLI_USAGE"),
    ],
)
def test_json_failure_contract(capsys, args, code):
    status, body = invoke(capsys, *args)
    assert status == 2 and body["diagnostics"][0]["code"] == code


def test_comparison_uses_per_array_units_and_exact_sample_indexes(
    edf_file, tmp_path, capsys
):
    from ccep.analysis import FilterSettings, PulseTrain, RunConfig, save_result

    result = process(
        RunConfig(
            recording=edf_file,
            reference="unipolar",
            channels=["A1"],
            trains=[PulseTrain(name="T", frequency_hz=0.5, pulse_samples=[3000])],
            filtering=FilterSettings(enabled=False),
        )
    )
    # Synthetic category arrays exercise exact comparisons independently of numeric tolerances.
    result.arrays["t0_score_valid"] = np.array([1.0])
    result.arrays["t0_score_rms_mean_qv"] = np.array([4.0])
    expected = tmp_path / "expected.npz"
    save_result(expected, result)
    tolerance = tmp_path / "limits.json"
    limits = {
        key: dict(
            absolute=100,
            relative=0,
            unit="uV" if key.endswith("_erp") else "dimensionless",
            rationale="Synthetic command contract, not scientific acceptance",
        )
        for key in result.arrays
        if not key.endswith(("_offsets", "_source_indexes"))
    }
    tolerance.write_text(json.dumps({"arrays": limits}))
    assert invoke(capsys, "compare", expected, expected, tolerance)[0] == 0
    result.arrays["t0_c0_source_indexes"][0, 0] += 1
    result.arrays["t0_score_valid"][0] = 0
    actual = tmp_path / "actual.npz"
    save_result(actual, result)
    status, body = invoke(capsys, "compare", actual, expected, tolerance)
    assert status == 3 and body["data"]["comparisons"]["t0_c0_source_indexes"][
        "first_mismatch"
    ] == [0, 0]
    assert not body["data"]["comparisons"]["t0_score_valid"]["passed"]
    limits["t0_c0_erp"]["unit"] = "dimensionless"
    tolerance.write_text(json.dumps({"arrays": limits}))
    assert invoke(capsys, "compare", actual, expected, tolerance)[0] == 2
