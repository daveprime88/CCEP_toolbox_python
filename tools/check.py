"""Cross-platform development checks; execute from the repository root."""

import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS", "1")
for command in (
    ["ruff", "check", "."],
    ["black", "--check", "."],
    ["pyright", "--pythonpath", sys.executable],
    ["pytest"],
):
    subprocess.run([sys.executable, "-m", *command], check=True)
