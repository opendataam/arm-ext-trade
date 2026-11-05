"""Generate docs/data_dictionary.md (from the comments stored in the DuckDB catalog) and docs/<lang>/inventory.md."""

from __future__ import annotations

import logging

import duckdb

from . import config

log = logging.getLogger(__name__)

PREFIX_TITLES = [
    ("meta_", "Metadata / provenance"),
    ("dim_", "Dimensions"),
    ("db_", "Facts from the web database"),
    ("file_", "Facts from the published files"),
    ("stg_", "Staging (web database exports in all languages)"),
    ("raw_", "Raw cells"),
    ("qc_", "Data quality"),
    ("v_", "Views"),
]


def _md(s) -> str:
    return "" if s is None else str(s).replace("|", "\\|").replace("\n", " ")


INVENTORY_TEXT = {
    "en": {
        "title": "Source inventory",
        "intro": "Generated automatically (`python -m armstat_trade docs`) from the tables `meta_file`, `meta_workbook`, "
                 "`meta_db_query` — do not edit by hand.",
        "files": "Files",
        "file_cols": ["file_id", "nid", "level", "year", "current edition", "hidden", "sheets", "size, KB",
                      "title (en)"],
        "yes": "yes", "no": "no",
        "queries": "Web database requests",
        "query_cols": ["nid", "mode", "languages", "years", "requests", "rows (en)"],
    },
    "hy": {
        "title": "Աղբյուրների ցանկ",
        "intro": "Ստեղծվում է ավտոմատ (`python -m armstat_trade docs`) `meta_file`, `meta_workbook`, `meta_db_query` "
                 "աղյուսակներից․ ձեռքով մի խմբագրեք։",
        "files": "Ֆայլեր",
        "file_cols": ["file_id", "nid", "մակարդակ", "տարի", "ընթացիկ խմբագրություն", "թաքնված", "թերթեր",
                      "չափ, ԿԲ", "անվանում (hy)"],
        "yes": "այո", "no": "ոչ",
        "queries": "Հարցումներ վեբ տվյալների բազային",
        "query_cols": ["nid", "ռեժիմ", "լեզուներ", "տարիներ", "հարցումներ", "տողեր (en)"],
    },
    "ru": {
        "title": "Перечень источников",
        "intro": "Генерируется автоматически (`python -m armstat_trade docs`) из таблиц `meta_file`, `meta_workbook`, "
                 "`meta_db_query` — не редактировать вручную.",
        "files": "Файлы",
        "file_cols": ["file_id", "nid", "уровень", "год", "текущая редакция", "скрыт", "листов", "размер, КБ",
                      "название (ru)"],
        "yes": "да", "no": "нет",
        "queries": "Запросы к веб-базе данных",
        "query_cols": ["nid", "режим", "языки", "годы", "запросов", "строк (en)"],
    },
}


def _row(cells) -> str:
    return "| " + " | ".join(cells) + " |"


def write_inventory(con, docs_dir) -> None:
    """docs/<lang>/inventory.md: every file and a summary of the web database requests, in each language."""
    files = con.execute("""
        SELECT f.file_id || '.' || f.ext, f.nid, f.nomenclature_level, f.year, f.is_current, f.hidden,
               (SELECT sum(n_sheets) FROM meta_workbook w WHERE w.file_id = f.file_id),
               round(f.size_bytes / 1024), f.title_en, f.title_hy, f.title_ru
        FROM meta_file f ORDER BY f.nid, f.year, f.file_id""").fetchall()
    queries = con.execute("""
        SELECT nid, mode, string_agg(DISTINCT lang, ', ' ORDER BY lang), min(year) || '–' || max(year), count(*),
               sum(n_rows) FILTER (WHERE lang = 'en')
        FROM meta_db_query GROUP BY nid, mode ORDER BY nid, mode""").fetchall()
    for lang, tx in INVENTORY_TEXT.items():
        lines = [f"# {tx['title']}", "", tx["intro"], "", f"## {tx['files']}", "",
                 _row(tx["file_cols"]), "|" + "---|" * len(tx["file_cols"])]
        for fid, nid, lvl, year, cur, hidden, nsh, kb, *titles in files:
            title = dict(zip(("en", "hy", "ru"), titles))[lang] or ""
            lines.append(_row([f"[{fid}](https://armstat.am/file/doc/{fid})", str(nid), str(lvl or ""),
                               str(year or ""), tx["yes"] if cur else tx["no"], tx["yes"] if hidden else "",
                               str(nsh or ""), f"{kb:,.0f}", _md(title)]))
        lines += ["", f"## {tx['queries']}", "", _row(tx["query_cols"]), "|" + "---|" * len(tx["query_cols"])]
        lines += [_row(_md(x) for x in r) for r in queries]
        out = docs_dir / lang / "inventory.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_data_dictionary(db_path=None, out=None) -> None:
    db_path = db_path or config.DUCKDB_PATH
    out = out or (config.ROOT / "docs" / "data_dictionary.md")
    con = duckdb.connect(str(db_path), read_only=True)
    objects = con.execute("""
        SELECT table_name, 'table' AS kind, comment, estimated_size AS n FROM duckdb_tables() WHERE schema_name = 'main'
        UNION ALL
        SELECT view_name, 'view', comment, NULL FROM duckdb_views() WHERE schema_name = 'main' AND NOT internal
        ORDER BY 1
    """).fetchall()
    cols = con.execute("""
        SELECT table_name, column_name, data_type, comment, column_index
        FROM duckdb_columns() WHERE schema_name = 'main' ORDER BY table_name, column_index
    """).fetchall()
    by_table: dict[str, list] = {}
    for t, c, typ, com, _ in cols:
        by_table.setdefault(t, []).append((c, typ, com))
    lines = [
        "# Data dictionary",
        "",
        "Generated automatically from the DuckDB catalog by `python -m armstat_trade docs` — do not edit by hand.",
        ("The descriptions of tables and columns are also stored in the database itself (`duckdb_tables()`, "
         "`duckdb_columns()`) and are defined in `sql/schema.sql`, `sql/views.sql`, `sql/qc.sql` (`COMMENT ON`). "
         "Schema overview: [database.md](en/database.md) ([hy](hy/database.md), [ru](ru/database.md))."),
        "",
    ]
    for prefix, title in PREFIX_TITLES:
        group = [o for o in objects if o[0].startswith(prefix)]
        if not group:
            continue
        lines += [f"## {title}", ""]
        for name, kind, comment, n in group:
            rows = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            lines += [f"### `{name}` ({kind}, {rows:,} rows)", "", _md(comment) or "_no description_", "",
                      "| column | type | description |", "|---|---|---|"]
            for c, typ, com in by_table.get(name, []):
                lines.append(f"| `{c}` | {typ} | {_md(com)} |")
            lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_inventory(con, out.parent)
    con.close()
    log.info("written %s and %s/*/inventory.md", out, out.parent)
