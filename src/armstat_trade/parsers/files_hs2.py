"""Parser for "Foreign trade ... at 2-digit level" workbooks (page nid=766).

These workbooks are a bilingual (hy/en) statistical bulletin with 16-18
sheets of different shape. All of them are "header block + data rows" tables,
so a generic header analyser (:func:`analyse_header`) detects for every value
column its flow (export / import / import by origin / import by consignment),
year and measure (ton, thous. US$, mln. AMD, mln. US$, US$, %). Sheet-specific
code then interprets the label columns of the rows.

Sheet types (``classify_sheet``):

* ``countries``        – trade by partner country, 4 years, value in thous. US$;
* ``sitc1`` / ``sitc2``  – by SITC sections / divisions, 4 years, ton and thous. US$;
* ``bec``              – by BEC categories, 4 years, mln. US$;
* ``hs2_years``        – by HS chapters (2-digit) and sections, 4 years, thous. US$;
* ``hs2_share``        – the same as % structure;
* ``hs2_partner``      – HS chapters x partner (world, country group or country
  blocks), file year, ton / mln. AMD / thous. US$;
* ``hs2_country``      – HS chapters x countries (with country codes), ton and thous. US$;
* ``hum_aid``          – humanitarian aid received, HS chapter x country.
"""

from __future__ import annotations

import logging
import re

from .common import code_str, has_armenian, is_num, split_hy_en, text, to_num
from .xlsx_reader import Workbook

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# sheet classification
# ---------------------------------------------------------------------------

def classify_sheet(name: str) -> str:
    n = re.sub(r"[\s_-]+", " ", name.strip().lower())
    if n == "countries":
        return "countries"
    if n.startswith("sitc 1"):
        return "sitc1"
    if n.startswith("sitc 2"):
        return "sitc2"
    if n.startswith("bec"):
        return "bec"
    if n == "by groups":
        return "hs2_years"
    if n.startswith("groups %"):
        return "hs2_share"
    if n == "by commodity groups":
        return "hs2_country"
    if n.startswith("hum"):
        return "hum_aid"
    return "hs2_partner"


def leading_partner(sheet_name: str) -> str | None:
    """Country group of the rows before the first country block of a partner sheet."""
    n = re.sub(r"[\s_-]+", " ", sheet_name.strip().lower())
    if n.startswith("world"):
        return "WORLD"
    if n.startswith("cis"):
        return "CIS"
    if n.startswith("eeu"):
        return "EEU"
    if n.startswith("other cis"):
        return "CIS_OTHER"
    if n.startswith("non cis"):
        return "NON_CIS"
    if n.startswith("eu"):
        return "EU"
    if n.startswith("other"):
        return "OTHER"  # non-CIS, non-EU countries
    return None


# ---------------------------------------------------------------------------
# generic header analysis
# ---------------------------------------------------------------------------

def _flow_of(s: str) -> str | None:
    u = s.upper()
    if "EXPORT" in u:
        return "export"
    if "IMPORT" in u:
        return "import"
    return None


def _subflow_of(s: str) -> str | None:
    lo = s.lower()
    if "consignment" in lo:
        return "import_consignment"
    if "origin" in lo:
        return "import_origin"
    return None


def _measure_of(s: str) -> str | None:
    lo = s.lower()
    if "%" in lo and "us" not in lo:
        return "share_pct"
    if "ton" in lo:
        return "weight_ton"
    if "quantity" in lo:
        return "quantity"
    if "dram" in lo:
        return "value_mln_amd"
    if "mln" in lo and "us" in lo:
        return "value_musd"
    if "thous" in lo and "us" in lo:
        return "value_kusd"
    if "us $" in lo or "us$" in lo:
        return "value_usd"
    return None


def _is_year(v) -> int | None:
    if isinstance(v, float) and v.is_integer() and 1990 <= v <= 2035:
        return int(v)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*((?:19|20)\d\d)\s*[^\d\s]?\s*", v)  # '2021◊'
        if m:
            return int(m.group(1))
    return None


def sheet_unit(grid: list[list]) -> str | None:
    """Unit note in the first rows, e.g. '(հազ. ԱՄՆ դոլար, thous. US$)'."""
    for r in grid[:6]:
        for v in r:
            s = text(v)
            if s and s.startswith("(") and len(s) < 60:
                m = _measure_of(s)
                if m:
                    return m
    return None


def analyse_header(grid: list[list], start: int, default_measure: str | None, label_cols: int) -> tuple[dict, int]:
    """Analyse header rows starting at ``start`` (the row containing EXPORT/IMPORT).

    Returns ``(colspec, first_data_row)`` where ``colspec`` maps a 0-based column
    index to ``{"flow", "year", "measure"}``.
    """
    ncols = max(len(r) for r in grid)
    # 1. find the first data row: the first row after `start` with a number that is not a year
    first = start + 1
    while first < len(grid):
        r = grid[first]
        if any(is_num(v) and _is_year(v) is None for j, v in enumerate(r) if j >= label_cols and v is not None):
            break
        first += 1
    header = [grid[k] + [None] * (ncols - len(grid[k])) for k in range(start, first)]
    # 2. the table width is the last column that has any header text
    width = max((j for r in header for j, v in enumerate(r) if j >= label_cols and v is not None), default=-1) + 1
    flow: list[str | None] = [None] * width
    year: list[int | None] = [None] * width
    measure: list[str | None] = [None] * width
    for r in header:
        cur_flow = cur_sub = cur_year = None
        for j in range(label_cols, width):
            v, s = r[j], text(r[j])
            if s is None:  # empty cell (part of a merged range): forward fill
                if cur_sub and flow[j] in (None, "import"):
                    flow[j] = cur_sub
                elif cur_flow and flow[j] is None:
                    flow[j] = cur_flow
                if cur_year and year[j] is None:
                    year[j] = cur_year
                continue
            if f := _flow_of(s):
                cur_flow, cur_sub = f, None
                flow[j] = f
            elif sf := _subflow_of(s):
                cur_sub = sf
                flow[j] = sf
            elif y := _is_year(v):
                cur_year = y
                year[j] = y
            elif m := _measure_of(s):
                measure[j] = m  # measures are per column, no fill
            else:  # other text (e.g. the header of the English name column) stops the fill
                cur_flow = cur_sub = cur_year = None
    spec = {}
    for j in range(label_cols, width):
        if flow[j] is None or (year[j] is None and measure[j] is None):
            continue
        m = measure[j] or default_measure
        if m is None:
            continue
        spec[j] = {"flow": flow[j], "year": year[j], "measure": m}
    return spec, first


def _find_header_rows(grid: list[list]) -> list[int]:
    """Rows that start a table (contain EXPORT or IMPORT and are followed by headers)."""
    out = []
    for i, r in enumerate(grid):
        if any(_flow_of(text(v) or "") for v in r if isinstance(v, str)):
            if not out or i > out[-1] + 3:
                out.append(i)
    return out


# ---------------------------------------------------------------------------
# helpers for label columns
# ---------------------------------------------------------------------------

def _labels(r: list, value_cols: set[int]) -> list[tuple[int, object]]:
    return [(j, v) for j, v in enumerate(r) if j not in value_cols and v is not None]


def _values(r: list, spec: dict) -> list[dict]:
    out = []
    for j, s in spec.items():
        raw = r[j] if j < len(r) else None
        if raw is None:
            continue
        out.append({**s, "col": j + 1, "value": to_num(raw), "value_raw": text(raw)})
    return out


def _is_header_like(r: list) -> bool:
    joined = " ".join(str(v) for v in r if isinstance(v, str))
    return bool(re.search(r"\bCode\b|EXPORT|IMPORT|weight, ton", joined))


# ---------------------------------------------------------------------------
# sheet parsers – each returns a list of "observations" (one per value cell)
# ---------------------------------------------------------------------------

def _obs(base: dict, values: list[dict]) -> list[dict]:
    return [{**base, **v} for v in values]


def parse_sheet(grid: list[list], sheet: str, file_year: int | None) -> tuple[str, list[dict], dict]:
    stype = classify_sheet(sheet)
    unit = sheet_unit(grid)
    title = " ".join(t for t in (text(v) for r in grid[:3] for v in r) if t and not t.startswith("("))[:500]
    # single-year sheets carry the year in the title; continuation sheets have no title
    has_title = bool(re.search(r"ԱՌԵՎՏ|TRADE|ՕԳՆՈՒԹ|AID", title))
    years = [int(y) for y in re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", title)] if has_title else []
    year = max(years) if years else file_year
    label_cols = {"countries": 3, "sitc1": 2, "sitc2": 2, "bec": 1, "hs2_years": 2, "hs2_share": 2,
                  "hs2_partner": 2, "hs2_country": 4, "hum_aid": 5}[stype]
    if stype == "hum_aid":
        # The column of "Country code" defines the label width
        for r in grid[:6]:
            for j, v in enumerate(r):
                if isinstance(v, str) and "Country code" in v:
                    label_cols = j + 1
    obs: list[dict] = []
    headers = _find_header_rows(grid)
    partner_kind, partner = ("group", leading_partner(sheet)) if stype == "hs2_partner" else (None, None)
    hs2_ctx = None  # current HS chapter for hs2_country / hum_aid
    for t_idx, h in enumerate(headers):
        spec, first = analyse_header(grid, h, unit, label_cols)
        if not spec:
            continue
        end = headers[t_idx + 1] if t_idx + 1 < len(headers) else len(grid)
        vcols = set(spec)
        prev = None
        for i in range(first, end):
            r = grid[i]
            if not any(v is not None for v in r):
                continue
            vals = _values(r, spec)
            labels = _labels(r, vcols)
            numeric_vals = [v for v in vals if v["value"] is not None or v["value_raw"] in ("-", "X", "x")]
            if not numeric_vals:
                # label-only row: block header, English name of previous row, footnote
                s = " ".join(text(v) for _, v in labels if text(v))
                if not s or _is_header_like(r):
                    continue
                if stype == "hs2_partner" and not s.startswith("*"):
                    hy, en = split_hy_en(s)
                    partner_kind, partner = "country", s
                elif stype == "countries" and prev is not None and not has_armenian(s) and not s.startswith("*"):
                    prev["label_en"] = s
                    for o in prev["_obs"]:
                        o["label_en"] = s
                continue
            base = {"sheet": sheet, "sheet_type": stype, "row_num": i + 1, "year_of_file": year}
            lab_texts = [text(v) for _, v in labels if isinstance(v, str) and text(v)]
            lab_nums = [(j, v) for j, v in labels if not isinstance(v, str) or re.fullmatch(r"\s*\d+\s*", v)]
            if stype == "countries":
                code = code_str(r[0]) if r and r[0] is not None else None
                alpha2 = text(r[1]) if len(r) > 1 and isinstance(r[1], str) else None
                base.update({"code": code, "alpha2": alpha2, "label_hy": text(r[2]) if len(r) > 2 else None,
                             "label_en": None})
            elif stype in ("sitc1", "sitc2", "hs2_years", "hs2_share", "hs2_partner"):
                code = code_str(r[0]) if r and r[0] is not None else None
                hy = text(r[1]) if len(r) > 1 else None
                en = next((t for t in lab_texts if not has_armenian(t) and t != code), None) if len(lab_texts) > 1 else None
                base.update({"code": code, "label_hy": hy, "label_en": en})
                if stype == "hs2_partner":
                    base.update({"partner_kind": partner_kind, "partner": partner})
            elif stype == "bec":
                hy = next((t for t in lab_texts if has_armenian(t)), None)
                en = next((t for t in lab_texts if not has_armenian(t)), None)
                base.update({"code": None, "label_hy": hy, "label_en": en})
            elif stype in ("hs2_country", "hum_aid"):
                # country rows carry a country code in the last label column
                cc = r[label_cols - 1] if len(r) >= label_cols else None
                names = [t for t in lab_texts if has_armenian(t) or re.search(r"[A-Za-z]", t)]
                if cc is not None and is_num(cc) and names:
                    base.update({"code": hs2_ctx, "label_hy": None, "country_code": code_str(cc),
                                 "country_name_hy": names[-1]})
                else:
                    small = [code_str(v) for _, v in lab_nums if code_str(v)]
                    hs2_ctx = small[0] if small else None
                    base.update({"code": hs2_ctx, "label_hy": names[0] if names else None,
                                 "country_code": None, "country_name_hy": None})
            row_obs = _obs(base, vals)
            obs.extend(row_obs)
            prev = {"_obs": row_obs}
    meta = {"sheet_type": stype, "title": title, "year": year, "unit": unit, "tables": len(headers)}
    return stype, obs, meta


def parse(path, workbook_id: str) -> dict:
    sheets, obs = [], []
    with Workbook(path) as wb:
        file_year = None
        for idx, name in enumerate(wb.sheet_names):
            grid = wb.grid(name, max_col=40)
            if not grid:
                continue
            if file_year is None:  # publication year = last year in the title of the first sheet
                ys = re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", " ".join(str(v) for r in grid[:3] for v in r if v))
                file_year = max(int(y) for y in ys) if ys else None
            stype, o, meta = parse_sheet(grid, name, file_year)
            for x in o:
                x["workbook_id"] = workbook_id
            obs.extend(o)
            sheets.append({"workbook_id": workbook_id, "sheet": name, "sheet_index": idx, "title": meta["title"],
                           "sheet_type": stype, "year": meta["year"], "parsed_rows": len({x["row_num"] for x in o})})
    return {"sheets": sheets, "hs2_obs": obs}
