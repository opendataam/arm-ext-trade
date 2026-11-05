"""Minimal, fast .xlsx reader based on lxml.

openpyxl is slow on sheets whose "used range" spans 16384 columns (several
Armstat files have such sheets) and in read-only mode returns formulas instead
of the cached values. This reader walks the sheet XML directly and returns
only the cells that physically exist, with the cached value and the formula
(if any).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
_M = "{%s}" % NS["m"]
_REF_RE = re.compile(r"([A-Z]+)(\d+)")


@dataclass(frozen=True)
class Cell:
    row: int  # 1-based
    col: int  # 1-based
    value: object  # str | float | bool | None
    formula: str | None = None


def col_to_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def index_to_col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _text(el) -> str:
    """Concatenate text of <t> nodes (handles rich text runs)."""
    return "".join(el.itertext())


class Workbook:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._zip = zipfile.ZipFile(self.path)
        self.shared = self._load_shared()
        self.sheets = self._load_sheets()  # list of (name, xml path, state)

    def close(self) -> None:
        self._zip.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _load_shared(self) -> list[str]:
        try:
            data = self._zip.read("xl/sharedStrings.xml")
        except KeyError:
            return []
        root = etree.fromstring(data)
        return [_text(si) for si in root.findall("m:si", NS)]

    def _load_sheets(self) -> list[tuple[str, str, str]]:
        wb = etree.fromstring(self._zip.read("xl/workbook.xml"))
        rels = etree.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
        out = []
        for s in wb.find("m:sheets", NS).findall("m:sheet", NS):
            rid = s.get("{%s}id" % NS["r"])
            target = targets[rid].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            out.append((s.get("name"), target, s.get("state") or "visible"))
        return out

    @property
    def sheet_names(self) -> list[str]:
        return [s[0] for s in self.sheets]

    def iter_cells(self, sheet_name: str):
        """Yield ``Cell`` objects of a sheet (only cells that have a value or formula)."""
        target = next(t for n, t, _ in self.sheets if n == sheet_name)
        with self._zip.open(target) as f:
            for _, row in etree.iterparse(f, tag=_M + "row"):
                for c in row.iterfind(_M + "c"):
                    cell = self._cell(c)
                    if cell is not None:
                        yield cell
                # free memory: drop the processed row and its predecessors
                row.clear()
                parent = row.getparent()
                while row.getprevious() is not None:
                    del parent[0]

    def _cell(self, c) -> Cell | None:
        """Decode one <c> element; empty (style-only) cells give None."""
        t = c.get("t")
        v = c.find(_M + "v")
        fnode = c.find(_M + "f")
        formula = fnode.text if fnode is not None and fnode.text else None
        if t == "s" and v is not None:
            value = self.shared[int(v.text)]
        elif t == "inlineStr":
            is_ = c.find(_M + "is")
            value = _text(is_) if is_ is not None else None
        elif t in ("str", "e"):
            value = v.text if v is not None else None
        elif t == "b":
            value = bool(int(v.text)) if v is not None else None
        else:
            value = float(v.text) if v is not None and v.text not in (None, "") else None
        if value is None and not formula:
            return None
        m = _REF_RE.match(c.get("r"))
        return Cell(int(m.group(2)), col_to_index(m.group(1)), value, formula)

    def grid(self, sheet_name: str, max_col: int = 60) -> list[list]:
        """Return the sheet as a dense list of rows (values only), trimmed to ``max_col`` columns."""
        cells = [c for c in self.iter_cells(sheet_name) if c.col <= max_col and c.value is not None]
        if not cells:
            return []
        nrows = max(c.row for c in cells)
        ncols = max(c.col for c in cells)
        rows = [[None] * ncols for _ in range(nrows)]
        for c in cells:
            v = c.value
            if isinstance(v, str):
                v = v.replace("\xa0", " ")
                if not v.strip():
                    continue
            rows[c.row - 1][c.col - 1] = v
        return rows
