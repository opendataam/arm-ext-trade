"""Generate docs/data_dictionary.md from the comments stored in the DuckDB catalog."""

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


def write_inventory(con, out) -> None:
    """docs/inventory.md: every file and a summary of the web database requests."""
    lines = ["# Перечень источников", "",
             "Генерируется автоматически (`python -m armstat_trade docs`) из таблиц `meta_file`, `meta_workbook`, "
             "`meta_db_query`.", "", "## Файлы", "",
             "| file_id | nid | уровень | год | текущая редакция | скрыт | листов | размер, КБ | название (ru) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in con.execute("""
        SELECT f.file_id || '.' || f.ext, f.nid, f.nomenclature_level, f.year, f.is_current, f.hidden,
               (SELECT sum(n_sheets) FROM meta_workbook w WHERE w.file_id = f.file_id),
               round(f.size_bytes / 1024), coalesce(f.title_ru, '')
        FROM meta_file f ORDER BY f.nid, f.year, f.file_id""").fetchall():
        fid, nid, lvl, year, cur, hidden, nsh, kb, title = r
        url = f"https://armstat.am/file/doc/{fid}"
        lines.append(f"| [{fid}]({url}) | {nid} | {lvl or ''} | {year or ''} | {'да' if cur else 'нет'} | "
                     f"{'да' if hidden else ''} | {nsh or ''} | {kb:,.0f} | {_md(title)} |")
    lines += ["", "## Запросы к веб-базе данных", "",
              "| nid | режим | языки | годы | запросов | строк (en) |", "|---|---|---|---|---|---|"]
    for r in con.execute("""
        SELECT nid, mode, string_agg(DISTINCT lang, ', ' ORDER BY lang), min(year) || '–' || max(year), count(*),
               sum(n_rows) FILTER (WHERE lang = 'en')
        FROM meta_db_query GROUP BY nid, mode ORDER BY nid, mode""").fetchall():
        lines.append("| " + " | ".join(_md(x) for x in r) + " |")
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
        "# Словарь данных (data dictionary)",
        "",
        "Генерируется автоматически из каталога DuckDB командой `python -m armstat_trade docs` — не редактировать вручную.",
        "Описания таблиц и колонок (на английском, они же хранятся в самой БД: `duckdb_tables()`, `duckdb_columns()`) "
        "задаются в `sql/schema.sql`, `sql/views.sql`, `sql/qc.sql` (`COMMENT ON`). Обзор схемы — [database.md](database.md).",
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
    write_inventory(con, out.parent / "inventory.md")
    con.close()
    log.info("written %s and inventory.md", out)
