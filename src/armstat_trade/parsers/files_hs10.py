"""Parser for "Foreign trade ... at 10-digit level" workbooks (page nid=778).

One sheet per HS section (I ... XXI, without XIX) plus the annex "Transport total"
(chapter 87 including trade of physical persons).
Layout of every sheet::

    A name (hy) or 10-digit code | B unit | C export quantity | D export ton | E export US$
    | F import quantity | G import ton | H import US$ | I name (en) or code

Rows are a hierarchy: section total (``I. ...``) -> group (HS 2-digit chapter)
-> subgroup (HS 4-digit heading) -> 10-digit commodity rows. The hierarchy
level of a label row is derived from what follows it: a label directly
followed by code rows is a subgroup, a label followed by another label is a
group. The code of a label row is the common prefix of its commodity codes.
"""

from __future__ import annotations

import logging
import re

from .common import fix_roman, has_armenian, text, to_num, year_in
from .xlsx_reader import Workbook

log = logging.getLogger(__name__)

CODE_RE = re.compile(r"^\d{8,10}$")
VALUE_COLS = [("export", "quantity"), ("export", "weight_ton"), ("export", "value_usd"),
              ("import", "quantity"), ("import", "weight_ton"), ("import", "value_usd")]


def _code(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float):
        if not v.is_integer():
            return None
        s = str(int(v))
    else:
        s = re.sub(r"\s", "", str(v))
    return s.zfill(10) if CODE_RE.match(s) else None


def split_unit(u: str | None) -> tuple[str | None, str | None]:
    """'հատ/piece' -> ('հատ', 'piece')."""
    if not u:
        return None, None
    parts = [p.strip() for p in u.split("/", 1)]
    if len(parts) == 2 and has_armenian(parts[0]):
        en = parts[1].replace("piese", "piece")
        return parts[0], en
    return (u, None) if has_armenian(u) else (None, u)


def _common_prefix(codes: list[str]) -> str:
    if not codes:
        return ""
    p = codes[0]
    for c in codes[1:]:
        while not c.startswith(p):
            p = p[:-1]
    return p


def parse(path, workbook_id: str) -> dict:
    sheets, items, groups = [], [], []
    year = None
    with Workbook(path) as wb:
        for idx, name in enumerate(wb.sheet_names):
            grid = wb.grid(name, max_col=12)
            if not grid:
                continue
            # only the first sheet has a title ("... TRADE OF THE REPUBLIC OF ARMENIA for 2025")
            title_rows = [t for t in (text(c) for r in grid[:3] for c in r) if t and re.search(r"ԱՌԵՎՏ|TRADE|Annex|Հավելված", t)]
            year = year_in(" ".join(t for t in title_rows if "TRADE" in t or "ԱՌԵՎՏ" in t)) or year
            annex = name.strip().lower().startswith("transport")
            section = None if annex else fix_roman(name)
            start = next(i for i, r in enumerate(grid) if "quantity" in str(r[2] if len(r) > 2 else "").lower()) + 1
            # first pass: classify rows
            parsed = []
            for i in range(start, len(grid)):
                r = grid[i] + [None] * (9 - len(grid[i]))
                vals = [to_num(v) for v in r[2:8]]
                code = _code(r[0])
                label_hy = None if code else text(r[0])
                label_en = text(r[8])
                if code is None and not label_hy and all(v is None for v in vals):
                    continue
                parsed.append((i + 1, code, label_hy, label_en, text(r[1]), vals))
            # second pass: hierarchy
            label_stack: list[dict] = []
            for k, (row_num, code, hy, en, unit, vals) in enumerate(parsed):
                if code:
                    unit_hy, unit_en = split_unit(unit)
                    rec = {"workbook_id": workbook_id, "sheet": name, "row_num": row_num, "year": year,
                           "is_annex": annex, "section": section, "hs10_code": code, "hs4_code": code[:4],
                           "hs2_code": code[:2], "unit_raw": unit, "unit_hy": unit_hy, "unit_en": unit_en}
                    for (flow, measure), v in zip(VALUE_COLS, vals):
                        rec[f"{flow}_{measure}"] = v
                    items.append(rec)
                    for g in label_stack:
                        g["codes"].append(code)
                    continue
                # label row
                low_hy, low_en = (hy or ""), (en or "").lower()
                g = {"workbook_id": workbook_id, "sheet": name, "row_num": row_num, "year": year,
                     "is_annex": annex, "section": section, "name_hy": hy, "name_en": en, "codes": [],
                     "export_weight_ton": vals[1], "export_value_usd": vals[2],
                     "import_weight_ton": vals[4], "import_value_usd": vals[5]}
                if low_hy.startswith("Ընդամենը") or low_en.startswith("total ("):
                    g["level"] = "total_with_physical_persons" if ("ներառյալ" in low_hy or "including" in low_en) else "total_without_physical_persons"
                    groups.append(g)
                    continue
                if not annex and re.match(r"^[IVXLY]+\s*\.", hy or en or ""):
                    g["level"] = "section"
                    label_stack = [g]
                    groups.append(g)
                    continue
                # group or subgroup: decided by the next row
                nxt = parsed[k + 1] if k + 1 < len(parsed) else None
                g["level"] = "subgroup" if (nxt and nxt[1]) else "group"
                if g["level"] == "group":
                    label_stack = [x for x in label_stack if x["level"] == "section"] + [g]
                else:
                    label_stack = [x for x in label_stack if x["level"] in ("section", "group")] + [g]
                groups.append(g)
            sheets.append({"workbook_id": workbook_id, "sheet": name, "sheet_index": idx,
                           "title": " / ".join(title_rows[:2]), "sheet_type": "hs10_annex" if annex else "hs10_section",
                           "year": year, "parsed_rows": len(parsed)})
    for g in groups:
        codes = g.pop("codes")
        prefix = _common_prefix(codes)
        g["n_items"] = len(codes)
        g["code_prefix"] = prefix or None
        if g["level"] == "subgroup":
            g["hs_code"] = prefix[:4] if len(prefix) >= 4 else None
        elif g["level"] == "group":
            g["hs_code"] = prefix[:2] if len(prefix) >= 2 else None
        else:
            g["hs_code"] = None
    for it in items:
        it["year"] = it["year"] or year
    for g in groups:
        g["year"] = g["year"] or year
    return {"sheets": sheets, "hs10": items, "hs10_groups": groups}
