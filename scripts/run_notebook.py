"""Execute a Jupyter notebook in place and save its outputs (used by `make notebook`).

* The kernel talks over IPC (unix sockets) instead of TCP where the platform
  allows it, so ipykernel does not warn about unencrypted TCP traffic.
* No per-cell timestamps are stored and the kernelspec display name is the one
  JupyterLab writes, so re-running or re-saving the notebook without data
  changes leaves no git diff.
* The result is signed (trusted) for the current user, so JupyterLab does not
  report "Notebook ... is not trusted".

Usage: python scripts/run_notebook.py [docs/examples.ipynb]
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import nbformat
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient
from nbformat.sign import NotebookNotary
from traitlets.config import Config

KERNEL = "python3"


def run(path: Path) -> None:
    nb = nbformat.read(path, as_version=4)
    config = Config()
    if sys.platform != "win32":
        config.KernelManager.transport = "ipc"
        config.KernelManager.ip = str(Path(tempfile.mkdtemp(prefix="nbkernel-")) / "kernel")
    started = time.monotonic()
    NotebookClient(nb, config=config, timeout=600, kernel_name=KERNEL, record_timing=False,
                   resources={"metadata": {"path": str(path.parent)}}).execute()
    for cell in nb.cells:  # drop timestamps left by earlier runs
        cell.metadata.pop("execution", None)
    spec = KernelSpecManager().get_kernel_spec(KERNEL)
    nb.metadata["kernelspec"] = {"display_name": spec.display_name, "language": spec.language, "name": KERNEL}
    NotebookNotary().sign(nb)
    nbformat.write(nb, path)
    n = sum(c.cell_type == "code" for c in nb.cells)
    print(f"{path}: {n} code cells executed in {time.monotonic() - started:.0f} s, outputs saved, notebook trusted")


if __name__ == "__main__":
    run(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/examples.ipynb"))
