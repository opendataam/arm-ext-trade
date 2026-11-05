"""JupyterLab settings for this repository (used by `make lab`).

Run: jupyter lab --config scripts/jupyter_lab_config.py docs/examples.ipynb

* the server root is the repository, so the file browser shows all of it;
* the Lab workspace (open tabs, layout) is kept in .jupyter/workspaces of this
  repository instead of the shared ~/.jupyter/lab/workspaces, so tabs of other
  projects are not restored here;
* kernels talk over unix sockets instead of TCP (no ipykernel warning about
  unencrypted TCP traffic);
* the websocket ping timeout is aligned with the ping interval (jupyter-server
  defaults otherwise make tornado print a warning on every kernel connection).
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

c = get_config()  # noqa: F821 - provided by Jupyter when it loads this file

c.ServerApp.root_dir = str(ROOT)
c.LabApp.workspaces_dir = str(ROOT / ".jupyter" / "workspaces")
c.ServerApp.tornado_settings = {"ws_ping_timeout": 30000}  # ms, equal to the default ping interval
if sys.platform != "win32":
    c.KernelManager.transport = "ipc"
    c.KernelManager.ip = str(Path(tempfile.mkdtemp(prefix="jupyter-kernel-")) / "kernel")
