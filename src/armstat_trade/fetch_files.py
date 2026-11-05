"""Step 2: download the files listed in ``data/catalog/files.json``.

Files go to ``data/raw/files/<file_id>.<ext>``; 7z archives are unpacked into
``data/raw/files/extracted/<file_id>/`` (needs the ``7zz``/``7z`` CLI or the
``py7zr`` package).
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from . import config
from .http import Client
from .utils import read_json, sha256_file, utc_now, write_json

log = logging.getLogger(__name__)


def _extract_7z(archive, dest) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    exe = shutil.which("7zz") or shutil.which("7z") or shutil.which("7za")
    if exe:
        subprocess.run([exe, "x", "-y", f"-o{dest}", str(archive)], check=True, capture_output=True)
    else:
        import py7zr  # optional dependency

        with py7zr.SevenZipFile(archive) as z:
            z.extractall(dest)
    return sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())


def download(force: bool = False, client: Client | None = None) -> list[dict]:
    client = client or Client()
    catalog_path = config.CATALOG_DIR / "files.json"
    files = read_json(catalog_path, [])
    if not files:
        raise SystemExit("data/catalog/files.json is empty: run `armstat-trade catalog` first")
    for rec in files:
        path = config.FILES_DIR / f"{rec['file_id']}.{rec['ext']}"
        if force or not path.exists():
            log.info("download %s", rec["url"])
            r = client.get(rec["url"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            rec["downloaded_at"] = utc_now()
        rec["size"] = path.stat().st_size
        rec["sha256"] = sha256_file(path)
        if rec["ext"] == "7z":
            rec["members"] = _extract_7z(path, config.EXTRACTED_DIR / rec["file_id"])
    write_json(catalog_path, files)
    return files
