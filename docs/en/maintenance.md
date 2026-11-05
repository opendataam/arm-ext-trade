# Maintenance

**English** | [Հայերեն](../hy/maintenance.md) | [Русский](../ru/maintenance.md)

## Regular update

On a new machine, first restore the raw data of the latest snapshot so that you do not download everything again
(`fetch-db` will then fetch only what is missing plus the last two years):

```bash
make install download-raw
```

Then:

```bash
make catalog fetch-files fetch-db build docs notebook test
git add -A && git commit -m "data: update to $(date +%F)" && git push
make release            # a new data-<collection date> release with the database, Parquet and raw data
```

* `catalog` crawls the pages in three languages again. New files and new years in the web database forms are
  picked up automatically (`data/catalog/files.json`, `data/catalog/db_options/*.json`).
  Manifest changes show up in `git diff` — a convenient way to notice that something changed on the website.
* `fetch-files` downloads only missing files (`--force` downloads all of them again). Hashes are in `files.json`.
* `fetch-db` fetches missing years and **always** re-requests the last two years (`--refresh-last 2`), because the
  current and the previous year are revised. Exports already on disk are re-validated; invalid ones are requested
  again. It can be narrowed down: `--nid 148 --lang en --mode annual`.
* `build` recreates the whole database (about 5 minutes).
* After the build, check `SELECT * FROM qc_summary` (see [data_quality.md](data_quality.md)) and run `make test`.
* `release` requires a clean working tree and a pushed `HEAD` (the release tag is put on that commit), as well as
  `gh` with write access to `opendataam/arm-ext-trade`. The default tag is `data-<date of the latest web database
  request>`; if such a release already exists, set another one: `python -m armstat_trade release --tag ...`.
  The release description (coverage, quality checks) is generated automatically (`RELEASE_NOTES.md`).

Recommended frequency: monthly (monthly data are published with a lag of ~1–2 months; annual CN FEA files appear
during the following year).

## What to do if…

**A new file with an unknown layout appears.** The family is determined by the page (`FAMILY_BY_NID` in
`build.py`). All cells end up in `raw_xlsx_cell` in any case. If a 2-digit bulletin gets a sheet with a new name,
it is classified in `files_hs2.classify_sheet` (default — `hs2_partner`); add a rule and a sheet type if needed.

**Country names are not resolved** (`qc_unresolved_country`, `partner_rows_without_country`).
Add the spelling to `reference.COUNTRY_NAME_ALIASES` (key — the name as in the source, value — the country code).
The code can be checked with a web database query for a specific `thid[]`.

**Web database exports are rejected** (`export ... rejected` in the log). The server sometimes returns the result of
someone else's query; the collector retries up to 6 times with a pause. If the error persists, check the query page
manually (its URL is in the log): the form parameters or the export format may have changed (the columns are
checked in `parsers/db_export.validate`).

**The website layout changed.** Page content is looked up in `div#center`, file links by the pattern
`/file/doc/<id>.<ext>`, form options by `select[name="thid[]"]` etc. (`parsers/pages.py`).

**No `textutil` (Linux).** Install LibreOffice (`soffice`), or use the committed `data/interim/tnved_2017.csv` —
the `tnved` step can be skipped.

## How the code is organised

| module | responsibility | input → output |
|---|---|---|
| `catalog.py` | crawl the pages | website → `data/raw/pages/`, `data/catalog/` |
| `fetch_files.py` | download files | `files.json` → `data/raw/files/` |
| `fetch_db.py` | export the web database | `db_options` → `data/raw/db/`, `db_queries.json` |
| `parsers/*` | parse formats, no side effects | bytes/files → lists of dicts |
| `build.py` | reference tables, code resolution, loading into DuckDB | `data/raw` + `data/catalog` → `.duckdb` |
| `sql/*.sql` | schema, views, checks | — |
| `docs.py` | generated documentation | `.duckdb` → `docs/data_dictionary.md`, `docs/{en,hy,ru}/inventory.md` |
| `release.py` | data snapshots in GitHub Releases | `.duckdb`, `data/raw`, `data/catalog` → `data/release/<tag>/` → release |

Principle: the downloaders only download and save data "as is"; all interpretation happens in the parsers and in
`build.py`, so any parsing error can be fixed and the database rebuilt without downloading again.

## Documentation languages

The documentation is kept in three languages: `docs/en/` (primary), `docs/hy/` and `docs/ru/`; the README likewise:
`README.md`, `README.hy.md`, `README.ru.md`. When changing a document, update all three versions. The data
dictionary (`docs/data_dictionary.md`) is generated in English from the `COMMENT ON` descriptions; the source
inventories `docs/<lang>/inventory.md` are generated in each language by `make docs`.

## Adding a new table

1. Describe the table and its columns in `sql/schema.sql` (with `COMMENT ON`).
2. Add parsing to the corresponding parser and loading to `build.py` (`insert(con, "<table>", rows)`).
3. If needed, add a view to `sql/views.sql` and a check to `sql/qc.sql`.
4. `make build docs test`.
