"""Russian names of HS sections and chapters from the TN VED EAEU 2017 document.

The page nid=778 links the EAEU commodity nomenclature (``ТНВЭД_2017.doc``
inside the 7z archive 99528903). The document is a Word 97 file; it is
converted to plain text with ``textutil`` (macOS) or LibreOffice
(``soffice --headless --convert-to txt``). Only the headings
``РАЗДЕЛ <roman>`` and ``ГРУППА <nn>`` are extracted: the 10-digit lines of
the document are hierarchical fragments ("– – прочие") spread over merged
table cells and cannot be aligned with codes reliably.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from .. import config

log = logging.getLogger(__name__)

OUT = config.DATA_DIR / "interim" / "tnved_2017.csv"


def doc_to_text(doc: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    txt = out_dir / (doc.stem + ".txt")
    if shutil.which("textutil"):
        subprocess.run(["textutil", "-convert", "txt", "-encoding", "UTF-8", "-output", str(txt), str(doc)], check=True)
    elif shutil.which("soffice"):
        subprocess.run(["soffice", "--headless", "--convert-to", "txt:Text (encoded):UTF8", "--outdir", str(out_dir), str(doc)], check=True)
    else:
        raise RuntimeError("neither textutil nor soffice is available to convert the .doc file")
    return txt


def _clean(name: str) -> str:
    name = re.split(r"\s+Примечани[яе]\s*:?", name)[0]
    name = re.sub(r"\s+", " ", name).strip(" .;:")
    return name[:1] + name[1:].lower() if name.isupper() else name


def _heading_name(txt: str, pos: int) -> str:
    """Collect the upper-case heading text that follows position ``pos``
    (it may continue on the same line and span several lines)."""
    parts = []
    for raw in txt[pos:pos + 2000].split("\n"):
        raw = raw.strip()
        if not raw:
            if parts:
                break
            continue
        line = re.split(r"\s*ГРУППА\s+\d+.*$|\s*Примечани[яе].*$", raw)[0].strip()
        letters = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", line)
        if not letters or not letters.isupper():
            break
        parts.append(line)
        if line != raw:  # the line continued with the next heading or with notes
            break
    return " ".join(parts)


def extract(txt: str) -> list[dict]:
    rows = []
    for kind, pat in (("section", r"РАЗДЕЛ\s+([IVXL]+)\b[ \t]*"), ("chapter", r"ГРУППА\s+(\d{1,2})\b[ \t]*")):
        seen = set()
        for m in re.finditer(pat, txt):
            code = m.group(1).zfill(2) if kind == "chapter" else m.group(1)
            if code in seen:
                continue
            name = _heading_name(txt, m.end())
            if not name:
                continue  # a reference in the text, not a heading
            seen.add(code)
            rows.append({"kind": kind, "code": code, "name_ru": _clean(name)})
    return rows


def run() -> Path | None:
    files = list((config.EXTRACTED_DIR / "99528903").glob("*.doc"))
    if not files:
        log.warning("TN VED document not found (run fetch-files)")
        return None
    txt_path = doc_to_text(files[0], config.DATA_DIR / "interim")
    rows = extract(txt_path.read_text(encoding="utf-8", errors="replace"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    log.info("TN VED: %d sections, %d chapters -> %s", sum(r["kind"] == "section" for r in rows),
             sum(r["kind"] == "chapter" for r in rows), OUT)
    return OUT
