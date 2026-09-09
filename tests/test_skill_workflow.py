"""Execute the playbook's documented commands as installed subprocess entry points."""

import json
import subprocess
import sys
from pathlib import Path


def test_documented_demo_commands_and_failure(tmp_path):
    root = Path(__file__).resolve().parents[1]
    demo = tmp_path / "demo with spaces"
    subprocess.run(
        [sys.executable, str(root / "tools/make_demo.py"), str(demo)], check=True
    )
    commands = [
        ["inspect", "recording.edf", "--annotations", "annotations.json"],
        ["validate", "config.json"],
        ["process", "config.json", "result.npz"],
        ["export", "result.npz", "report.csv"],
    ]
    for args in commands:
        result = subprocess.run(
            [sys.executable, "-m", "ccep.cli", "--json", *args],
            cwd=demo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        envelope = json.loads(result.stdout)
        assert envelope["ok"] and envelope["schema_version"] == 1
    assert (demo / "report.csv").read_text().count("A1-A2") == 6
    missing = subprocess.run(
        [sys.executable, "-m", "ccep.cli", "--json", "validate", "absent.json"],
        cwd=demo,
        capture_output=True,
        text=True,
    )
    assert missing.returncode == 2
    assert json.loads(missing.stdout)["diagnostics"][0]["code"] == "INPUT_NOT_FOUND"


def test_skill_install_preserves_source_and_refuses_overwrite(tmp_path, capsys):
    from ccep.cli import run

    assert run(["--json", "install-skill", str(tmp_path)]) == 0
    envelope = json.loads(capsys.readouterr().out)
    path = Path(envelope["data"]["path"]) / "SKILL.md"
    assert path.is_file()
    original = path.read_bytes()
    assert run(["--json", "install-skill", str(tmp_path)]) == 2
    assert (
        json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "OUTPUT_EXISTS"
    )
    assert path.read_bytes() == original
