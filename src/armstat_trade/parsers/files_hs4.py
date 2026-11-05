"""Parser for "Foreign trade ... at 4-digit level" workbooks (page nid=777).

Each workbook has three sheets with the same layout::

    A code | B name (hy) | C export, ton | D export, thous. US$ | E import, ton | F import, thous. US$ | G name (en)

Sheet 1 – total trade, sheet 2 – trade by goods declarations and the
"Statistical form of register of goods transfer", sheet 3 – trade by
declarations of physical persons. The first data row is the total.
"""

from __future__ import annotations

import logging

from .common import code_str, pad_hs, text, to_num, year_in
from .xlsx_reader import Workbook

log = logging.getLogger(__name__)

MEASURES = [("export", "weight_ton"), ("export", "value_kusd"), ("import", "weight_ton"), ("import", "value_kusd")]


def sheet_basis(title: str) -> str:
    t = (title or "").lower()
    if "physical persons" in t:
        return "physical_persons"
    if "goods declarations" in t:
        return "declarations"
    return "total"


def parse(path, workbook_id: str) -> dict:
    sheets, rows = [], []
    with Workbook(path) as wb:
        for idx, name in enumerate(wb.sheet_names):
            grid = wb.grid(name, max_col=12)
            if not grid:
                continue
            title = text(grid[0][0]) or ""
            basis = sheet_basis(title)
            year = year_in(title)
            # header: row with "EXPORT" in column C, measure rows below; data starts after "US $" row
            start = next(i for i, r in enumerate(grid) if any("US" in str(v or "") for v in r[2:6]) and "ton" in str(r[2] or "").lower()) + 1
            n = 0
            for i in range(start, len(grid)):
                r = grid[i] + [None] * (7 - len(grid[i]))
                vals = [to_num(v) for v in r[2:6]]
                name_hy, name_en = text(r[1]), text(r[6])
                code = code_str(r[0])
                if not (code or name_hy or name_en):
                    continue  # stray cells (e.g. a lone 0 below the header)
                is_total = (name_en or "").lower().startswith("total") or (name_hy or "").startswith("Ընդամենը")
                row = {
                    "workbook_id": workbook_id,
                    "sheet": name,
                    "row_num": i + 1,
                    "year": year,
                    "basis": basis,
                    "row_type": "total" if is_total else "item",
                    "hs4_code": None if is_total else pad_hs(code, 4),
                    "code_raw": code,
                    "name_hy": name_hy,
                    "name_en": name_en,
                }
                for (flow, measure), v in zip(MEASURES, vals):
                    row[f"{flow}_{measure}"] = v
                rows.append(row)
                n += 1
            sheets.append({"workbook_id": workbook_id, "sheet": name, "sheet_index": idx, "title": title,
                           "sheet_type": f"hs4_{basis}", "year": year, "parsed_rows": n})
    return {"sheets": sheets, "hs4": rows}
