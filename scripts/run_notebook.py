"""Execute a Jupyter notebook in place and save its outputs (used by `make notebook`).

The kernel talks over IPC (unix sockets) instead of TCP where the platform
allows it, so ipykernel does not warn about unencrypted TCP traffic.

Usage: python scripts/run_notebook.py [docs/examples.ipynb]
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from traitlets.config import Config


def run(path: Path) -> None:
    nb = nbformat.read(path, as_version=4)
    config = Config()
    if sys.platform != "win32":
        config.KernelManager.transport = "ipc"
        config.KernelManager.ip = str(Path(tempfile.mkdtemp(prefix="nbkernel-")) / "kernel")
    started = time.monotonic()
    # record_timing=False: no per-cell timestamps, so a re-run without data changes gives no git diff
    NotebookClient(nb, config=config, timeout=600, kernel_name="python3", record_timing=False,
                   resources={"metadata": {"path": str(path.parent)}}).execute()
    for cell in nb.cells:  # drop timestamps left by earlier runs
        cell.metadata.pop("execution", None)
    nbformat.write(nb, path)
    n = sum(c.cell_type == "code" for c in nb.cells)
    print(f"{path}: {n} code cells executed in {time.monotonic() - started:.0f} s, outputs saved")


if __name__ == "__main__":
    run(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/examples.ipynb"))
