"""Step 4: parse the raw data and build the DuckDB database.

The database is rebuilt from scratch on every run (into a temporary file that
replaces ``data/armstat_trade.duckdb`` at the end), so the build is
deterministic and only depends on ``data/raw`` and ``data/catalog``.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path

import duckdb
import pandas as pd

from . import config, reference
from .fetch_db import raw_path
from .parsers import db_export, files_hs2, files_hs4, files_hs10
from .parsers.common import code_str, fix_roman, pad_hs, roman_to_int, split_hy_en
from .parsers.xlsx_reader import Workbook, index_to_col
from .utils import read_gz_text, read_json

log = logging.getLogger(__name__)

FAMILY_BY_NID = {766: "hs2", 777: "hs4", 778: "hs10"}
TOTAL_HY = "Ընդամենը"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def insert(con: duckdb.DuckDBPyConnection, table: str, records: list[dict] | pd.DataFrame) -> int:
    df = records if isinstance(records, pd.DataFrame) else pd.DataFrame.from_records(records)
    if df.empty:
        log.warning("table %s: nothing to insert", table)
        return 0
    cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    df = df[[c for c in df.columns if c in cols]]
    con.register("_df", df)
    con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _df")
    con.unregister("_df")
    log.info("table %-26s +%d rows", table, len(df))
    return len(df)


def is_total(*labels) -> bool:
    for s in labels:
        s = (s or "").strip()
        if s.startswith(TOTAL_HY) or s.lower().startswith("total"):
            return True
    return False


# ---------------------------------------------------------------------------
# countries
# ---------------------------------------------------------------------------

class CountryResolver:
    """Resolve country names / codes found in the sources to dim_country codes."""

    def __init__(self) -> None:
        self.names: dict[int, dict[str, str]] = defaultdict(dict)  # code -> lang -> name
        self.alpha2: dict[int, str] = {}
        self.index: dict[str, set[int]] = defaultdict(set)
        self.variants: set[tuple[int, str, str, str]] = set()
        self.aliases: dict[str, int] = {}  # normalised name -> code (reference.COUNTRY_NAME_ALIASES)
        self.unresolved: list[dict] = []

    def alias(self, *names: str | None) -> int | None:
        for n in names:
            code = self.aliases.get(reference.norm_name(n))
            if code is not None:
                return code
        return None

    def add(self, code: int, lang: str, name: str | None, source: str, primary: bool = False) -> None:
        if not name:
            return
        name = re.sub(r"\*+$", "", name).strip()
        if primary or lang not in self.names[code]:
            self.names[code].setdefault(lang, name)
        self.index[reference.norm_name(name)].add(code)
        self.variants.add((code, lang, name, source))

    def known(self, code: int) -> bool:
        return code in self.names

    def code_from_raw(self, raw) -> int | None:
        c = code_str(raw)
        if c is None or not re.fullmatch(r"\d+", c):
            return None
        if c in reference.COUNTRY_CODE_ALIASES:
            return reference.COUNTRY_CODE_ALIASES[c]
        return int(c)

    def by_name(self, *names: str | None) -> int | None:
        for n in names:
            key = reference.norm_name(n)
            if not key:
                continue
            codes = self.index.get(key)
            if codes and len(codes) == 1:
                return next(iter(codes))
        return None

    def resolve_label(self, label: str, context: str) -> int | None:
        """Resolve a block heading like 'ԻՏԱԼԻԱ - ITALY'."""
        hy, en = split_hy_en(label)
        code = self.alias(en, hy, label)
        if code is None:
            code = self.by_name(hy, en, label)
        if code is None:
            # try progressively shorter English prefixes ('LIBYAN ARAB JAMA' is cut)
            for n in (en, hy):
                key = reference.norm_name(n)
                if len(key) >= 5:
                    cands = {c for k, cs in self.index.items() if k.startswith(key) or key.startswith(k) and len(k) >= 5 for c in cs}
                    if len(cands) == 1:
                        code = cands.pop()
                        break
        if code is None:
            self.unresolved.append({"context": context, "label": label})
        return code


def load_country_options() -> CountryResolver:
    res = CountryResolver()
    for lang in config.LANGS:
        opts = read_json(config.CATALOG_DIR / "db_options" / f"159_{lang}.json", {"thid": []})
        for o in opts["thid"]:
            res.add(int(o["value"]), lang, o["label"], "web database form (nid 159/717)", primary=True)
    for code, names in reference.EXTRA_COUNTRIES.items():
        for lang, name in names.items():
            res.add(code, lang, name, "reference.EXTRA_COUNTRIES", primary=True)
    for name, code in reference.COUNTRY_NAME_ALIASES.items():
        res.aliases[reference.norm_name(name)] = code
    return res


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------

def load_meta(con) -> list[dict]:
    insert(con, "meta_language", [dict(zip(["lang", "site_code", "name_en", "name_native"], row)) for row in reference.LANGUAGES])
    pages = read_json(config.CATALOG_DIR / "pages.json", [])
    insert(con, "meta_page", [{k: p.get(k) for k in ("nid", "lang", "kind", "url", "title", "fetched_at", "sha256")} for p in pages])
    files = read_json(config.CATALOG_DIR / "files.json", [])
    return files


def workbooks(files: list[dict]) -> list[dict]:
    out = []
    for f in files:
        family = FAMILY_BY_NID.get(f["nid"])
        if f["ext"] == "xlsx":
            out.append({"workbook_id": f["file_id"], "file_id": f["file_id"], "member": None, "family": family,
                        "path": config.FILES_DIR / f"{f['file_id']}.xlsx", "is_current": not f["hidden"]})
        for m in f.get("members") or []:
            if m.lower().endswith(".xlsx"):
                out.append({"workbook_id": f"{f['file_id']}/{m}", "file_id": f["file_id"], "member": m, "family": family,
                            "path": config.EXTRACTED_DIR / f["file_id"] / m, "is_current": False})
    return out


# ---------------------------------------------------------------------------
# web database
# ---------------------------------------------------------------------------

def load_web_db(con, countries: CountryResolver) -> None:
    queries = read_json(config.CATALOG_DIR / "db_queries.json", [])
    insert(con, "meta_db_query", [{**{k: q[k] for k in ("nid", "lang", "mode", "year", "query_url", "export_url", "fetched_at", "bytes", "sha256")},
                                   "raw_file": q["file"], "n_rows": q["rows"]} for q in queries])
    stg_c, stg_h = [], []
    for q in queries:
        path = raw_path(q["nid"], q["lang"], q["mode"], q["year"])
        if not path.exists():
            log.warning("missing %s", path)
            continue
        raw = read_gz_text(path)
        if q["nid"] in (159, 717):
            prev = 0
            for r in db_export.parse_country(raw):
                key = reference.norm_name(r["country_name"])
                cands = sorted(countries.index.get(key, set()))
                # the export is ordered by country code: disambiguate duplicate names (Serbia, Samoa)
                code = next((c for c in cands if c > prev), cands[0] if cands else None) if len(cands) > 1 else (cands[0] if cands else None)
                if code is None:
                    code = countries.alias(r["country_name"])
                    if code is not None:
                        countries.add(code, q["lang"], r["country_name"], f"web database export nid={q['nid']} (historical name)")
                if code is None:
                    countries.unresolved.append({"context": f"db nid={q['nid']} {q['lang']}", "label": r["country_name"]})
                else:
                    prev = code
                stg_c.append({"nid": q["nid"], "lang": q["lang"], "mode": q["mode"], "seq": r["seq"],
                              "country_name": r["country_name"], "country_code": code, "year": r["year"],
                              "period_code": r["period"], "export_kusd": r["export_kusd"],
                              "import_origin_kusd": r["import_origin_kusd"], "import_consignment_kusd": r["import_consignment_kusd"]})
        else:
            for r in db_export.parse_commodity(raw):
                stg_h.append({"lang": q["lang"], "mode": q["mode"], "seq": r["seq"], "commodity_name": r["commodity_name"],
                              "code_raw": r["code_raw"], "hs4_code": pad_hs(r["code_raw"], 4), "year": r["year"],
                              "period_code": r["period"], "export_ton": r["export_ton"], "export_kusd": r["export_kusd"],
                              "import_ton": r["import_ton"], "import_kusd": r["import_kusd"]})
    insert(con, "stg_db_country", stg_c)
    insert(con, "stg_db_commodity", stg_h)
    split = config.COUNTRY_DB_SPLIT_YEAR
    con.execute(f"""
        INSERT INTO db_country_trade
        SELECT country_code, year, CASE WHEN period_code = 13 THEN NULL ELSE period_code END, period_code,
               flow, value, nid
        FROM (
            SELECT * FROM stg_db_country
            WHERE lang = 'en' AND country_code IS NOT NULL
              AND ((nid = 159 AND year < {split}) OR (nid = 717 AND year >= {split}))
        ) UNPIVOT (value FOR flow IN (export_kusd AS 'export', import_origin_kusd AS 'import_origin',
                                      import_consignment_kusd AS 'import_consignment'))
    """)
    con.execute("""
        INSERT INTO db_commodity_trade
        SELECT hs4_code, year, CASE WHEN period_code = 13 THEN NULL ELSE period_code END, period_code, 'export', export_ton, export_kusd
        FROM stg_db_commodity WHERE lang = 'en'
        UNION ALL
        SELECT hs4_code, year, CASE WHEN period_code = 13 THEN NULL ELSE period_code END, period_code, 'import', import_ton, import_kusd
        FROM stg_db_commodity WHERE lang = 'en'
    """)


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------

def _pivot(obs: list[dict], keys: list[str], measures: list[str]) -> list[dict]:
    """Group observations (one per value cell) into rows with one column per measure."""
    out: dict[tuple, dict] = {}
    for o in obs:
        k = tuple(o.get(x) for x in keys)
        rec = out.setdefault(k, {x: o.get(x) for x in keys})
        if o["measure"] in measures:
            rec[o["measure"]] = o["value"]
    return list(out.values())


def countries_rows(obs, countries: CountryResolver, wid: str) -> list[dict]:
    group_by_heading = {reference.norm_name(h): g for g, _, _, hs in reference.COUNTRY_GROUPS for h in hs}
    rows = sorted({x["row_num"]: x for x in obs}.values(), key=lambda x: x["row_num"])
    last_country_row = max((x["row_num"] for x in rows if countries.code_from_raw(x.get("code")) is not None), default=0)
    info, group, prev_code = {}, None, 0
    for x in rows:
        code = countries.code_from_raw(x.get("code"))
        label = re.sub(r"\*+$", "", x.get("label_hy") or "").strip()
        if code is None:
            g = group_by_heading.get(reference.norm_name(label))
            if label.startswith(TOTAL_HY):
                g = "WORLD"
            if g == "OTHER" and x["row_num"] > last_country_row:
                # "Other countries" after the last country = residual of countries not listed
                info[x["row_num"]] = {"row_type": "other_countries", "group_code": None, "country_code": None}
                group = None
            else:
                info[x["row_num"]] = {"row_type": "group", "group_code": g, "country_code": None}
                group, prev_code = g, 0
            continue
        if group == "EU" and code < prev_code:  # the EU list is over; the following countries are non-CIS, non-EU
            group = "OTHER"
        prev_code = code
        info[x["row_num"]] = {"row_type": "country", "group_code": group, "country_code": code}
        countries.add(code, "hy", label, f"file {wid} Countries")
        if x.get("alpha2"):
            countries.alpha2.setdefault(code, x["alpha2"])
    out = []
    for o in obs:
        i = info[o["row_num"]]
        out.append({"workbook_id": wid, "year": o["year"], "row_num": o["row_num"], **i,
                    "label_hy": o.get("label_hy"), "label_en": o.get("label_en"), "flow": o["flow"], "value_kusd": o["value"]})
    return out


def hs2_rows(obs: list[dict], countries: CountryResolver, wid: str) -> dict[str, list[dict]]:
    by_type = defaultdict(list)
    for o in obs:
        o["year"] = o["year"] or o["year_of_file"]
        by_type[o["sheet_type"]].append(o)
    res: dict[str, list[dict]] = defaultdict(list)
    # Countries
    for sheet in {o["sheet"] for o in by_type["countries"]}:
        res["file_country_trade"] += countries_rows([o for o in by_type["countries"] if o["sheet"] == sheet], countries, wid)
    # SITC
    for st, level in (("sitc1", 1), ("sitc2", 2)):
        for r in _pivot(by_type[st], ["row_num", "code", "label_hy", "label_en", "flow", "year"], ["weight_ton", "value_kusd"]):
            tot = r["code"] is None and is_total(r["label_hy"], r["label_en"])
            res["file_sitc_trade"].append({"workbook_id": wid, "year": r["year"], "sitc_level": level,
                                           "row_type": "total" if tot else "item",
                                           "sitc_code": None if tot else (r["code"] if level == 1 else pad_hs(r["code"], 2)),
                                           "flow": r["flow"], "weight_ton": r.get("weight_ton"), "value_kusd": r.get("value_kusd"),
                                           "_label_hy": r["label_hy"], "_label_en": r["label_en"]})
    # BEC
    for o in by_type["bec"]:
        tot = is_total(o["label_hy"], o["label_en"])
        res["file_bec_trade"].append({"workbook_id": wid, "year": o["year"], "row_type": "total" if tot else "item",
                                      "bec_code": None if tot else reference.bec_code(o["label_en"]),
                                      "flow": o["flow"], "value_musd": o["value"],
                                      "_label_hy": o["label_hy"], "_label_en": o["label_en"]})
    # HS chapters x years (value and share)
    merged: dict[tuple, dict] = {}
    for st, measure in (("hs2_years", "value_kusd"), ("hs2_share", "share_pct")):
        for o in by_type[st]:
            code = o["code"]
            roman = fix_roman(code) if code and not code.isdigit() else None
            if code and code.isdigit():
                row_type, hs = "chapter", pad_hs(code, 2)
            elif roman:
                row_type, hs = "section", roman
            else:
                row_type, hs = "total", None
            k = (row_type, hs, o["flow"], o["year"])
            rec = merged.setdefault(k, {"workbook_id": wid, "year": o["year"], "row_type": row_type, "hs_code": hs,
                                        "flow": o["flow"], "_label_hy": o["label_hy"]})
            rec[measure] = o["value"]
    res["file_hs2_trade"] = list(merged.values())
    # HS chapters x partner
    for r in _pivot(by_type["hs2_partner"], ["sheet", "row_num", "partner_kind", "partner", "code", "label_hy", "flow", "year"],
                    ["weight_ton", "value_mln_amd", "value_kusd"]):
        country = None
        group = None
        if r["partner_kind"] == "country":
            country = countries.resolve_label(r["partner"], f"{wid} {r['sheet']}")
        else:
            group = r["partner"]
        tot = r["code"] is None
        res["file_hs2_partner_trade"].append({"workbook_id": wid, "year": r["year"], "sheet": r["sheet"], "row_num": r["row_num"],
                                              "partner_kind": r["partner_kind"], "group_code": group, "country_code": country,
                                              "partner_label": r["partner"] if r["partner_kind"] == "country" else None,
                                              "row_type": "total" if tot else "chapter", "hs2_code": None if tot else pad_hs(r["code"], 2),
                                              "flow": r["flow"], "weight_ton": r.get("weight_ton"),
                                              "value_mln_amd": r.get("value_mln_amd"), "value_kusd": r.get("value_kusd")})
    # HS chapters x countries / humanitarian aid
    for st, table, measures in (("hs2_country", "file_hs2_country_trade", ["weight_ton", "value_kusd"]),
                                ("hum_aid", "file_humanitarian_aid", ["weight_ton", "value_usd"])):
        for r in _pivot(by_type[st], ["row_num", "code", "label_hy", "country_code", "country_name_hy", "flow", "year"], measures):
            cc = countries.code_from_raw(r["country_code"]) if r["country_code"] is not None else None
            if cc is not None:
                countries.add(cc, "hy", r["country_name_hy"], f"file {wid} {st}")
                row_type = "country"
            elif r["code"]:
                row_type = "chapter"
            else:
                row_type = "total"
            rec = {"workbook_id": wid, "year": r["year"], "row_num": r["row_num"], "row_type": row_type,
                   "hs2_code": pad_hs(r["code"], 2) if r["code"] else None, "country_code": cc, "flow": r["flow"]}
            for m in measures:
                rec[m] = r.get(m)
            res[table].append(rec)
    return res


def load_files(con, files: list[dict], countries: CountryResolver) -> dict:
    wbs = workbooks(files)
    tables: dict[str, list[dict]] = defaultdict(list)
    sheets_meta, wb_meta, cells = [], [], []
    target = {"hs4": "file_hs4_trade", "hs10_section": "file_hs10_trade", "hs10_annex": "file_hs10_trade",
              "countries": "file_country_trade", "sitc1": "file_sitc_trade", "sitc2": "file_sitc_trade",
              "bec": "file_bec_trade", "hs2_years": "file_hs2_trade", "hs2_share": "file_hs2_trade",
              "hs2_partner": "file_hs2_partner_trade", "hs2_country": "file_hs2_country_trade",
              "hum_aid": "file_humanitarian_aid"}
    for wb in wbs:
        wid, path, family = wb["workbook_id"], wb["path"], wb["family"]
        log.info("workbook %s (%s)", wid, family)
        # 1. lossless cell dump
        n_cells = {}
        with Workbook(path) as x:
            for s in x.sheet_names:
                n = 0
                for c in x.iter_cells(s):
                    n += 1
                    cells.append({"workbook_id": wid, "sheet": s, "row_num": c.row, "col_num": c.col,
                                  "cell_ref": f"{index_to_col(c.col)}{c.row}",
                                  "value_text": c.value if isinstance(c.value, str) else (None if c.value is None else str(c.value)),
                                  "value_num": c.value if isinstance(c.value, float) else None,
                                  "formula": c.formula})
                n_cells[s] = n
        # 2. structured parse
        if family == "hs4":
            p = files_hs4.parse(path, wid)
            for r in p["hs4"]:
                for flow in ("export", "import"):
                    tables["file_hs4_trade"].append({k: r[k] for k in ("workbook_id", "year", "basis", "sheet", "row_num", "row_type", "hs4_code")}
                                                    | {"flow": flow, "weight_ton": r[f"{flow}_weight_ton"], "value_kusd": r[f"{flow}_value_kusd"],
                                                       "_name_hy": r["name_hy"], "_name_en": r["name_en"], "_code_raw": r["code_raw"]})
        elif family == "hs10":
            p = files_hs10.parse(path, wid)
            for r in p["hs10"]:
                for flow in ("export", "import"):
                    tables["file_hs10_trade"].append({k: r[k] for k in ("workbook_id", "year", "sheet", "row_num", "is_annex", "section",
                                                                        "hs10_code", "hs4_code", "hs2_code")}
                                                     | {"unit_code": reference.unit_code(r["unit_en"], r["unit_hy"]), "flow": flow,
                                                        "quantity": r[f"{flow}_quantity"], "weight_ton": r[f"{flow}_weight_ton"],
                                                        "value_usd": r[f"{flow}_value_usd"], "_unit_hy": r["unit_hy"],
                                                        "_unit_en": r["unit_en"], "_unit_raw": r["unit_raw"]})
            for g in p["hs10_groups"]:
                for flow in ("export", "import"):
                    tables["file_hs10_aggregate"].append({k: g[k] for k in ("workbook_id", "year", "sheet", "row_num", "is_annex", "section", "level",
                                                                            "hs_code", "code_prefix", "name_hy", "name_en", "n_items")}
                                                         | {"flow": flow, "weight_ton": g[f"{flow}_weight_ton"], "value_usd": g[f"{flow}_value_usd"]})
        else:
            p = files_hs2.parse(path, wid)
            for t, rows in hs2_rows(p["hs2_obs"], countries, wid).items():
                tables[t] += rows
        years = [s["year"] for s in p["sheets"] if s["year"]]
        wb_year = max(years) if years else None
        for s in p["sheets"]:
            st = s["sheet_type"]
            sheets_meta.append({**{k: s[k] for k in ("workbook_id", "sheet", "sheet_index", "sheet_type", "year", "title", "parsed_rows")},
                                "n_cells": n_cells.get(s["sheet"]), "target_table": target.get("hs4" if st.startswith("hs4") else st)})
        for s, n in n_cells.items():  # sheets without parsed content
            if not any(m["workbook_id"] == wid and m["sheet"] == s for m in sheets_meta):
                sheets_meta.append({"workbook_id": wid, "sheet": s, "n_cells": n, "parsed_rows": 0})
        wb_meta.append({"workbook_id": wid, "file_id": wb["file_id"], "member": wb["member"], "family": family,
                        "year": wb_year, "is_current": wb["is_current"], "n_sheets": len(n_cells)})
    fill_missing_hs4(tables["file_hs4_trade"])
    insert(con, "meta_workbook", wb_meta)
    insert(con, "meta_sheet", sheets_meta)
    insert(con, "raw_xlsx_cell", cells)
    return {"tables": tables, "workbooks": wb_meta}


def fill_missing_hs4(rows: list[dict]) -> None:
    """Some item rows of the 4-digit files have an empty code cell; restore it by name."""
    by_name: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        if r["hs4_code"]:
            for n in (r["_name_en"], r["_name_hy"]):
                if n:
                    by_name[reference.norm_name(n)].add(r["hs4_code"])
    for r in rows:
        if r["row_type"] == "item" and not r["hs4_code"]:
            for n in (r["_name_en"], r["_name_hy"]):
                codes = by_name.get(reference.norm_name(n))
                if codes and len(codes) == 1:
                    r["hs4_code"] = next(iter(codes))
                    break


# ---------------------------------------------------------------------------
# dimensions
# ---------------------------------------------------------------------------

def build_dims(con, tables: dict, countries: CountryResolver, wb_meta: list[dict], tnved: dict | None) -> None:
    current = {w["workbook_id"]: (w["is_current"], w["year"] or 0) for w in wb_meta}

    def rank(wid):  # prefer current editions and recent years for labels
        cur, year = current.get(wid, (False, 0))
        return (cur, year)

    insert(con, "dim_flow", [dict(zip(["flow", "name_en", "name_hy", "name_ru", "description"], f)) for f in reference.FLOWS])
    insert(con, "dim_measure", [dict(zip(["measure", "unit_en", "unit_hy", "description"], m)) for m in reference.MEASURES])
    insert(con, "dim_data_basis", [dict(zip(["basis", "name_en", "name_hy", "description"], b)) for b in reference.DATA_BASES])
    insert(con, "dim_country_group", [{"group_code": g, "name_en": en, "name_hy": hy} for g, en, hy, _ in reference.COUNTRY_GROUPS])

    # countries
    rows = []
    for code, names in sorted(countries.names.items()):
        rows.append({"country_code": code, "iso_alpha2": countries.alpha2.get(code), "name_en": names.get("en"),
                     "name_hy": names.get("hy"), "name_ru": names.get("ru"), "is_special": code in reference.SPECIAL_COUNTRIES})
    insert(con, "dim_country", rows)
    insert(con, "dim_country_name", [{"country_code": c, "lang": lg, "name": n, "source": s} for c, lg, n, s in sorted(countries.variants)])

    # HS: 4-digit names from the web database form (3 languages)
    hs: dict[str, dict] = {}
    for lang in config.LANGS:
        opts = read_json(config.CATALOG_DIR / "db_options" / f"148_{lang}.json", {"thid": []})
        for o in opts["thid"]:
            m = re.match(r"^\s*(\d+)\s+(.*)$", o["label"])
            name = m.group(2).strip() if m else o["label"]
            code = pad_hs(o["value"], 4)
            hs.setdefault(code, {"hs_code": code, "level": 4})[f"name_{lang}"] = name
    # headings of earlier years that are no longer in the form: names from the exports (latest year)
    for code, lang, name in con.execute(
        "SELECT hs4_code, lang, arg_max(commodity_name, year) FROM stg_db_commodity GROUP BY ALL ORDER BY 1, 2"
    ).fetchall():
        hs.setdefault(code, {"hs_code": code, "level": 4}).setdefault(f"name_{lang}", name)
    # names from files (hy/en), latest current workbook wins, only fill gaps
    for r in sorted(tables["file_hs4_trade"], key=lambda r: rank(r["workbook_id"]), reverse=True):
        if r["row_type"] == "item" and r["hs4_code"]:
            d = hs.setdefault(r["hs4_code"], {"hs_code": r["hs4_code"], "level": 4})
            d.setdefault("name_hy", r["_name_hy"])
            d.setdefault("name_en", r["_name_en"])
    agg = sorted(tables["file_hs10_aggregate"], key=lambda r: rank(r["workbook_id"]), reverse=True)
    sections: dict[str, dict] = {}
    for g in agg:
        if g["level"] == "group" and g["hs_code"]:
            d = hs.setdefault(g["hs_code"], {"hs_code": g["hs_code"], "level": 2})
            d.setdefault("name_en", g["name_en"])
            d.setdefault("name_hy", g["name_hy"])
        elif g["level"] == "subgroup" and g["hs_code"]:
            d = hs.setdefault(g["hs_code"], {"hs_code": g["hs_code"], "level": 4})
            d.setdefault("name_en", g["name_en"])
            d.setdefault("name_hy", g["name_hy"])
        elif g["level"] == "section" and g["section"] and not g["is_annex"]:
            s = sections.setdefault(g["section"], {"section": g["section"], "section_no": roman_to_int(g["section"])})
            s.setdefault("name_hy", re.sub(r"^[IVXLY]+\s*\.\s*", "", g["name_hy"] or "") or None)
            s.setdefault("name_en", re.sub(r"^[IVXLY]+\s*\.\s*", "", g["name_en"] or "") or None)
    for r in sorted(tables["file_hs2_trade"], key=lambda r: rank(r["workbook_id"]), reverse=True):
        if r["row_type"] == "chapter":
            d = hs.setdefault(r["hs_code"], {"hs_code": r["hs_code"], "level": 2})
            d.setdefault("name_hy", r["_label_hy"])
        elif r["row_type"] == "section":
            s = sections.setdefault(r["hs_code"], {"section": r["hs_code"], "section_no": roman_to_int(r["hs_code"])})
            s.setdefault("name_hy", r["_label_hy"])
    # 10-digit codes and the chapter -> section map
    chapter_section = {}
    for r in tables["file_hs10_trade"]:
        hs.setdefault(r["hs10_code"], {"hs_code": r["hs10_code"], "level": 10})
        if r["section"] and not r["is_annex"]:
            chapter_section.setdefault(r["hs2_code"], r["section"])
    if tnved:
        for code, name in tnved.get("chapter", {}).items():
            hs.setdefault(code, {"hs_code": code, "level": 2}).setdefault("name_ru", name)
        for sec, name in tnved.get("section", {}).items():
            sections.setdefault(sec, {"section": sec, "section_no": roman_to_int(sec)})["name_ru"] = name
    for code, d in hs.items():
        d["parent_code"] = {2: None, 4: code[:2], 10: code[:4]}[d["level"]]
        d["section"] = chapter_section.get(code[:2])
    insert(con, "dim_hs", sorted(hs.values(), key=lambda d: d["hs_code"]))
    insert(con, "dim_hs_section", sorted(sections.values(), key=lambda s: s["section_no"]))

    # SITC / BEC
    sitc, bec = {}, {}
    for r in sorted(tables["file_sitc_trade"], key=lambda r: rank(r["workbook_id"]), reverse=True):
        if r["row_type"] == "item" and r["sitc_code"] is not None:
            d = sitc.setdefault(r["sitc_code"], {"sitc_code": r["sitc_code"], "level": r["sitc_level"]})
            d.setdefault("name_hy", r["_label_hy"])
            d.setdefault("name_en", r["_label_en"])
    for r in sorted(tables["file_bec_trade"], key=lambda r: rank(r["workbook_id"]), reverse=True):
        if r["bec_code"]:
            d = bec.setdefault(r["bec_code"], {"bec_code": r["bec_code"]})
            d.setdefault("name_hy", r["_label_hy"])
            d.setdefault("name_en", r["_label_en"])
    insert(con, "dim_sitc", sorted(sitc.values(), key=lambda d: (d["level"], d["sitc_code"])))
    insert(con, "dim_bec", sorted(bec.values(), key=lambda d: d["bec_code"]))

    # units
    units: dict[str, dict] = {}
    for r in tables["file_hs10_trade"]:
        if r["unit_code"]:
            u = units.setdefault(r["unit_code"], {"unit_code": r["unit_code"], "name_en": r["_unit_en"], "name_hy": r["_unit_hy"], "raw": set()})
            if r["_unit_raw"]:
                u["raw"].add(r["_unit_raw"])
    insert(con, "dim_unit", [{**{k: v for k, v in u.items() if k != "raw"}, "raw_labels": sorted(u["raw"])} for u in units.values()])


# ---------------------------------------------------------------------------
# TN VED (Russian names) – optional
# ---------------------------------------------------------------------------

def load_tnved() -> dict | None:
    """Russian section / chapter names extracted by ``armstat-trade tnved`` (optional)."""
    from .parsers.tnved import OUT

    if not OUT.exists():
        log.warning("%s not found: Russian chapter names are skipped (run `tnved`)", OUT)
        return None
    df = pd.read_csv(OUT, dtype=str)
    return {kind: dict(zip(g["code"], g["name_ru"])) for kind, g in df.groupby("kind")}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build(db_path: str | None = None) -> Path:
    out = Path(db_path) if db_path else config.DUCKDB_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".building.duckdb")
    if tmp.exists():
        tmp.unlink()
    con = duckdb.connect(str(tmp))
    con.execute((config.SQL_DIR / "schema.sql").read_text(encoding="utf-8"))

    files = load_meta(con)
    countries = load_country_options()
    loaded = load_files(con, files, countries)
    tables, wb_meta = loaded["tables"], loaded["workbooks"]

    # meta_file (year of hidden files from the parsed workbook)
    wb_year = {w["file_id"]: w["year"] for w in wb_meta if w["year"]}
    insert(con, "meta_file", [{"file_id": f["file_id"], "ext": f["ext"], "url": f["url"], "nid": f["nid"],
                               "nomenclature_level": f.get("level"), "year": f.get("year") or wb_year.get(f["file_id"]),
                               "hidden": f["hidden"], "is_current": not f["hidden"] and f["ext"] == "xlsx",
                               "title_en": f["titles"].get("en"), "title_hy": f["titles"].get("hy"), "title_ru": f["titles"].get("ru"),
                               "size_bytes": f.get("size"), "sha256": f.get("sha256"), "downloaded_at": f.get("downloaded_at")}
                              for f in files])

    load_web_db(con, countries)
    build_dims(con, tables, countries, wb_meta, load_tnved())
    for t, rows in tables.items():
        insert(con, t, [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])

    # unresolved labels for the QC report
    con.execute("CREATE TABLE qc_unresolved_country AS SELECT * FROM (SELECT NULL::VARCHAR AS context, NULL::VARCHAR AS label) WHERE false")
    if countries.unresolved:
        insert(con, "qc_unresolved_country", pd.DataFrame(countries.unresolved).drop_duplicates())
    con.execute((config.SQL_DIR / "views.sql").read_text(encoding="utf-8"))
    con.execute((config.SQL_DIR / "qc.sql").read_text(encoding="utf-8"))
    con.execute("CHECKPOINT")
    con.close()
    tmp.replace(out)
    log.info("database written to %s", out)
    return out
