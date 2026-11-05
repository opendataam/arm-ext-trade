# Armenia foreign trade: Armstat data in DuckDB

**English** | [Հայերեն](README.hy.md) | [Русский](README.ru.md)

Collection, normalisation and documentation of the foreign trade data of the Republic of Armenia published
in the "External trade database" section of the Statistical Committee of the Republic of Armenia (Armstat)
website: <https://armstat.am/en/?nid=160>.

The pipeline collects **everything** published in the section, **in all three languages** (English, Armenian,
Russian):

* the **web database** (query interface):
  * by partner country — annual data since 1995, monthly since 2003 (nid 159 and 717);
  * by 4-digit commodity heading of the CN of FEA (TN VED) — annual since 1995, monthly since 2007 (nid 148);
* **xlsx files** by the EAEU Commodity Nomenclature of Foreign Economic Activity (CN FEA EAEU, TN VED EAEU)
  at the 2-, 4- and 10-digit level for 2018–2025 (nid 766, 777, 778), including hidden earlier editions
  and 7z archives (among them the 2017 EAEU CN FEA document).

The result is the DuckDB database `data/armstat_trade.duckdb` with trilingual reference tables, normalised fact
tables, a lossless copy of all source cells and exports, data quality checks and documentation.

## Ready-made data: releases

The database and the raw data are not stored in git (the database exceeds GitHub's 100 MB file limit, and the
history would grow with every rebuild). Each collection run is published as a repository **release**
([Releases](https://github.com/opendataam/arm-ext-trade/releases)) tagged `data-YYYY-MM-DD` — the collection
date; the tag points to the code commit the database was built with.

| release asset | contents | size* |
|---|---|---|
| `armstat_trade.duckdb.xz` | DuckDB database | ~25 MB (124 MB uncompressed) |
| `armstat_trade-parquet.zip` | all tables and views as Parquet + data dictionary | ~40 MB |
| `armstat_trade-raw.tar.xz` | raw data: site pages, xlsx/7z, web database exports (`raw/`) and manifests (`catalog/`) | ~46 MB |
| `SHA256SUMS` | checksums | |

\* for the 2026-11-05 snapshot.

```bash
make install
make download            # latest release: database -> data/armstat_trade.duckdb (SHA256 verified)
make lab                 # notebook with examples
```

Other options: `make download-parquet` (Parquet → `data/parquet/`), `make download-raw` (raw data →
`data/raw/`, then `make build` rebuilds the database without touching the website), a specific snapshot —
`make download TAG=data-2026-11-05`. Without Python:
`curl -LO https://github.com/opendataam/arm-ext-trade/releases/latest/download/armstat_trade.duckdb.xz && xz -d armstat_trade.duckdb.xz`.

To rebuild a snapshot exactly, check out its tag (`git checkout data-2026-11-05`): the manifests in
`data/catalog/` must match the snapshot's raw data (or use
`python -m armstat_trade download --part raw --with-catalog`).

Publishing a new snapshot (maintainers): collect the data (`make all`), commit and push the manifest changes,
then run `make release`. The archives and `RELEASE_NOTES.md` are created in `data/release/<tag>/` and uploaded
with `gh release create` (requires `gh` and write access; `make release-pack` only packs).

## Quick start: build everything yourself

```bash
make install   # creates .venv and installs the package with the dev + notebook extras (via uv if available; Python ≥ 3.10)
make all       # catalog → fetch-files → fetch-db → tnved → build → docs  (~40–60 minutes, mostly downloading)
```

All `make` targets use `.venv/bin/python` automatically once the environment exists (a system-wide
`pip install` is blocked in Homebrew/Debian Python, PEP 668). Another interpreter: `make build PY=python3`.

Or step by step (in the activated environment: `source .venv/bin/activate`):

```bash
python -m armstat_trade catalog       # section pages in en/hy/ru → data/catalog/*.json
python -m armstat_trade fetch-files   # xlsx/7z → data/raw/files (+ 7z extraction)
python -m armstat_trade fetch-db      # web database via the Excel export → data/raw/db (≈ 380 requests)
python -m armstat_trade tnved         # Russian section/chapter names from CN FEA 2017 (needs textutil or soffice)
python -m armstat_trade build         # → data/armstat_trade.duckdb
python -m armstat_trade docs          # → docs/data_dictionary.md, docs/{en,hy,ru}/inventory.md
```

7z extraction needs `7zz`/`7z` (e.g. `brew install sevenzip`) or the `py7zr` package
(`.venv/bin/python -m pip install '.[7z]'` or `uv pip install --python .venv/bin/python '.[7z]'`).
A repeated `fetch-db` run downloads only what is missing and always refreshes the last two years
(`--refresh-last N`); it also re-validates exports already on disk and re-requests invalid ones.

Example query:

```bash
duckdb data/armstat_trade.duckdb -c "
  SELECT year, round(sum(export_kusd)/1e3) AS export_musd, round(sum(import_origin_kusd)/1e3) AS import_musd
  FROM v_db_country_annual GROUP BY year ORDER BY year"
```

## Jupyter notebook with examples

[`docs/examples.ipynb`](docs/examples.ipynb) contains example queries, source comparisons and charts (the text
of the notebook is in Russian). It is stored with its outputs, so it can be read directly on GitHub.
To work with it interactively:

1. Install the environment (creates `.venv` with JupyterLab, matplotlib and a Python kernel):

   ```bash
   make install
   ```

2. Make sure the database exists: `data/armstat_trade.duckdb` (download it with `make download`, or build it:
   `make all` the first time, `make build` when the raw data is already on disk).

3. Start JupyterLab with the notebook:

   ```bash
   make lab
   ```

   A browser opens with the notebook (`http://localhost:8888/lab/tree/docs/examples.ipynb`); the file browser
   shows the whole repository. Server settings are in
   [`scripts/jupyter_lab_config.py`](scripts/jupyter_lab_config.py): a project-local JupyterLab workspace in
   `.jupyter/` (tabs of other projects are not restored) and kernel connections over unix sockets instead of TCP.
   The same without `make`:

   ```bash
   source .venv/bin/activate
   jupyter trust docs/examples.ipynb
   jupyter lab --config scripts/jupyter_lab_config.py docs/examples.ipynb
   ```

   `jupyter trust` marks the notebook as trusted for your user: its outputs were not produced in your browser,
   and without it JupyterLab reports `Notebook ... is not trusted` and hides HTML/JS outputs (PNG charts and
   tables are shown either way).

4. Check the kernel in the top right corner: **Python 3 (ipykernel)** is the kernel from `.venv`
   (`.venv/bin/jupyter kernelspec list` shows a path inside `.venv`).

5. Run the cells: **Run → Run All Cells**, or one by one with `Shift+Enter`. The first cell finds the repository
   root (by `pyproject.toml`) and opens the database read-only, so Jupyter can be started from any folder of the
   repository.

6. To stop, press `Ctrl+C` in the terminal running `make lab` and confirm with `y`.

**VS Code:** open `docs/examples.ipynb`, click **Select Kernel → Python Environments** and choose
`.venv/bin/python` (the Jupyter extension is required).

Good to know:

* If another process holds the database open **for writing** (for example `duckdb data/armstat_trade.duckdb`
  without `-readonly`), the notebook cannot connect — close that process.
* After rebuilding the database (`make build`), restart the kernel (**Kernel → Restart Kernel**): an open
  connection keeps seeing the old file.
* Before committing, refresh the stored outputs with one clean in-order run of all cells: `make notebook`
  (no browser; executes the notebook and writes the outputs to the file).

## Repository layout

```
├── README.md                  this file (English); README.hy.md — Armenian, README.ru.md — Russian
├── Makefile                   pipeline commands
├── pyproject.toml             armstat_trade package (CLI: armstat-trade)
├── src/armstat_trade/
│   ├── config.py              paths, section pages, languages, HTTP settings
│   ├── http.py                HTTP client: retries, pauses between requests, sessions
│   ├── catalog.py             step 1: crawl pages in 3 languages, list files and form options
│   ├── fetch_files.py         step 2: download files, extract 7z, sha256
│   ├── fetch_db.py            step 3: web database export (query → /excelopen.php → validation)
│   ├── build.py               step 4: parse and build DuckDB
│   ├── docs.py                generate the data dictionary and the source inventory
│   ├── release.py             data snapshots in GitHub Releases: pack, publish, download
│   ├── reference.py           static reference data and mapping dictionaries
│   ├── cli.py, __main__.py    command line
│   └── parsers/
│       ├── pages.py           page HTML: file links, form options
│       ├── db_export.py       web database exports + check that they match the query
│       ├── xlsx_reader.py     fast streaming xlsx reader (cached values + formulas)
│       ├── files_hs2.py       2-digit bulletins (generic table header analysis)
│       ├── files_hs4.py       4-digit heading tables
│       ├── files_hs10.py      10-digit code tables (section/chapter/heading hierarchy)
│       ├── tnved.py           CN FEA 2017 headings (.doc)
│       └── common.py          value and code cleaning
├── sql/
│   ├── schema.sql             tables + COMMENT ON (descriptions are stored in the database itself)
│   ├── views.sql              views
│   └── qc.sql                 data quality checks
├── data/
│   ├── catalog/               manifests (in git): pages.json, files.json, db_queries.json, db_options/
│   ├── interim/               tnved_2017.csv (in git)
│   ├── raw/                   downloaded pages, files, exports (not in git; in releases)
│   ├── release/               packed and downloaded snapshots (not in git)
│   └── armstat_trade.duckdb   result (not in git; in releases)
├── docs/
│   ├── en/, hy/, ru/          documentation in English, Armenian and Russian
│   ├── data_dictionary.md     all tables and columns (generated)
│   └── examples.ipynb         Jupyter notebook with examples
├── scripts/
│   ├── run_notebook.py        execute the notebook and save outputs (make notebook)
│   └── jupyter_lab_config.py  JupyterLab settings for make lab
└── tests/                     tests of the parsers and of the built database
```

## Documentation

The documentation is available in English ([docs/en](docs/en)), Armenian ([docs/hy](docs/hy)) and Russian
([docs/ru](docs/ru)).

| document | contents |
|---|---|
| [sources.md](docs/en/sources.md) | the website section, pages, languages, how the web database works and its quirks, units and symbols |
| [files.md](docs/en/files.md) | contents of the files: sheets, columns, hierarchies, quirks |
| [database.md](docs/en/database.md) | database design: principles, schema (ER), tables, views, example queries |
| [data_dictionary.md](docs/data_dictionary.md) | all tables and columns (generated) |
| [inventory.md](docs/en/inventory.md) | list of files and web database requests (generated) |
| [data_quality.md](docs/en/data_quality.md) | data quality checks and known issues of the sources |
| [examples.ipynb](docs/examples.ipynb) | Jupyter notebook: example queries, source comparisons and charts (interactive: `make lab`, see above) |
| [maintenance.md](docs/en/maintenance.md) | maintenance: updates, new years, changes on the website |

## Main tables

| table / view | contents |
|---|---|
| `v_db_country_annual`, `v_db_country_monthly` | trade by country (exports, imports by country of origin and by country of consignment), thousand USD |
| `v_db_commodity_annual`, `v_db_commodity_monthly` | trade by 4-digit CN FEA heading, tonnes and thousand USD |
| `v_file_hs10_current` | 10-digit codes: quantity, tonnes, USD (2018–2025) |
| `v_file_hs4_current` | 4-digit headings by data basis (total / declarations / physical persons) |
| `v_file_hs2_partner_current` | CN FEA chapters × country / country group: tonnes, million AMD, thousand USD |
| `file_country_trade`, `file_sitc_trade`, `file_bec_trade`, `file_hs2_trade` | multi-year bulletin tables (all editions; `v_*_latest` — the latest one) |
| `dim_country`, `dim_hs`, `dim_hs_section`, … | reference tables with names in en / hy / ru |
| `raw_xlsx_cell`, `stg_db_*` | lossless source data |

## Caveats

* Units are those of the source and are part of the column name (`value_kusd` — thousand USD, `value_usd` — USD, …).
* Total rows (`row_type = 'total'`, `'chapter'`, `'group'`, …) are stored together with detail rows — filter them.
* Files are publications as of their release date; the web database contains later revisions. Values for the same
  year may differ between sources (see `qc_file_vs_db_hs4`).
* 2026 is incomplete.

## Source

Data: Statistical Committee of the Republic of Armenia, <https://armstat.am>. A licence for the repository code
has not been chosen yet.
