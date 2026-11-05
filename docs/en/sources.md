# Data sources

**English** | [Հայերեն](../hy/sources.md) | [Русский](../ru/sources.md)

The "External trade database" section of the website of the Statistical Committee of the Republic of Armenia
(Armstat): <https://armstat.am/en/?nid=160>. The section exists in three languages; the language is set by a URL
path segment:

| language | ISO 639-1 (in the database) | URL segment | example |
|---|---|---|---|
| English | `en` | `en` | <https://armstat.am/en/?nid=160> |
| Armenian | `hy` | `am` | <https://armstat.am/am/?nid=160> |
| Russian | `ru` | `ru` | <https://armstat.am/ru/?nid=160> |

## Section structure

| nid | what it is | type | years |
|---|---|---|---|
| 160 | index page of the section | links to subpages | — |
| 148 | database by commodity (CN FEA, 4 digits) | query interface | annual 1995–2026, monthly 2007–2026 |
| 159 | database by country ("up to 2016") | query interface | annual 1995–2025, monthly 2003–2025 |
| 717 | database by country ("2017–2025") | query interface | annual and monthly 2017–2026 |
| 766 | "Foreign trade of RA by CN FEA EAEU, 2 digits" | xlsx files (+7z) | bulletins 2018–2024 |
| 777 | "Foreign trade of RA by CN FEA EAEU, 4 digits" | xlsx files | 2018–2025 |
| 778 | "Foreign trade of RA by CN FEA EAEU, 10 digits" | xlsx files (+7z with CN FEA 2017) | 2018–2025 |

CN FEA EAEU (Commodity Nomenclature of Foreign Economic Activity of the Eurasian Economic Union, Russian
abbreviation TN VED) matches the Harmonized System (HS) up to 6 digits.

The years are as of the collection date (November 2026); the current list is recomputed on every
`armstat-trade catalog` run (see `data/catalog/pages.json`, `data/catalog/files.json`, `data/catalog/db_options/`).
2026 is incomplete (data up to and including September).

## Files (nid 766 / 777 / 778)

* Links look like `https://armstat.am/file/doc/<file_id>.<ext>`.
* **The same file** is published on all three language versions of the pages — only the link texts differ.
  The xlsx files themselves are bilingual (Armenian + English). The files are therefore downloaded once, and the
  link texts in three languages are stored in `meta_file.title_en/hy/ru`.
* The pages contain **hidden links** (with empty text) — earlier editions of the files (2018 preliminary data,
  2020 for the 10-digit level). They are loaded into the database with `meta_file.hidden = TRUE`,
  `meta_workbook.is_current = FALSE`.
* The archive `99516683.7z` contains an early version of the 2018 2-digit bulletin (`2_nish_2018.xlsx`) and a PDF;
  the archive `99528903.7z` contains the 2017 CN FEA EAEU document in Russian (`ТНВЭД_2017.doc`, 58 MB), from
  which the Russian names of sections and chapters are extracted.

The contents of the files are described in detail in [files.md](files.md); the full list is in
[inventory.md](inventory.md) (generated).

## Web database (nid 148 / 159 / 717)

The interface is an HTML form submitted with GET:

| parameter | value |
|---|---|
| `nid` | 148 (commodities) / 159, 717 (countries) |
| `thid[]` | commodity code (4 digits without the leading zero, e.g. `101`) or country (ISO 3166-1 numeric); `0` — all |
| `years[]` | years for **annual** values (several allowed) |
| `year[]` + `monid[]` | years and months (1–12) for **monthly** values |
| `submit=Search` | — |

Example: `https://armstat.am/en/?nid=717&thid[]=643&years[]=2024&submit=Search`.

Quirks discovered during development:

1. **Pagination.** Results are shown 25 rows at a time (`&offset=N` is the page number).
   A monthly "all commodities" query for one year returns about 12 thousand rows (≈ 490 pages).
2. **Excel export.** The "Download Excel file" link (`/excelopen.php`) returns the **whole** result of the last
   query as one "Excel HTML" document with full precision (up to 5 decimal places; the HTML page rounds values
   to 1–2 decimals). Without a `Referer` header the server responds with `403`. The collector uses the export:
   new session → query → export.
3. **The export may return someone else's query.** The server does not keep the "last query" strictly per session:
   during the first collection 13 of 378 exports (3.4 %) contained results of other visitors' queries (another
   table, another year) or were empty.
   Every export is therefore validated (`parsers/db_export.validate`): the number of columns, the year, the period
   codes and the row count announced by the paginator of the query page. Invalid exports are requested again.
4. **Period code**: 1–12 — month, 13 — year (shown as "Year" in the HTML).
5. **Zeros and dashes.** The HTML shows zero values as "-", the export as `0`. The database stores `0`.
   In the country database for 1995–2002 imports by country of origin are zero — only imports by country of
   consignment are filled.
6. **The export has no country codes** — only names. Rows are ordered by country code, which makes it possible
   to tell apart countries with the same name (the form lists "Serbia" twice — codes 688 and 891; the Armenian and
   Russian versions list "Samoa" twice — 16 and 882). Exports for early years contain outdated names
   ("United States", "FYR of Macedonia", "Korea, DPR of", "Individual" = physical persons, code 997, etc.);
   they are mapped with the dictionary `reference.COUNTRY_NAME_ALIASES`.
7. **Pages 159 and 717 share one backend.** Both pages return data for any year, and the values are identical
   (check `qc_db_country_overlap`). The database uses nid 159 for years < 2017 and nid 717 for 2017+;
   everything else is kept in `stg_db_country`.
8. **Names in three languages.** Values are identical in all language versions (check
   `qc_db_language_consistency`); only the country/commodity names and headings differ.
   All three language versions of the exports are saved (`data/raw/db/nid<nid>/<lang>/`) and loaded into
   `stg_db_country` / `stg_db_commodity`.
9. **Historical commodity codes.** Exports for early years contain 4-digit codes that are missing from the current
   form (e.g. 0509, 4108–4111, 8520); their names are taken from the exports themselves.

## Units of measurement

| source | value | weight | quantity |
|---|---|---|---|
| web database (148, 159, 717) | thousand USD | tonnes | — |
| 4-digit files (777) | thousand USD | tonnes | — |
| 10-digit files (778) | **USD** | tonnes | in the supplementary unit (`dim_unit`) |
| 2-digit files (766) | thousand USD; million AMD; million USD (BEC); % | tonnes | — |

## Symbols in the published tables

| symbol | meaning | in the database |
|---|---|---|
| `-` | no occurrence / no data | `NULL` (source text in `raw_xlsx_cell`) |
| `X` | not applicable / confidential | `NULL` |
| `◊` after a year (e.g. `2021◊`) | not explained in the files; used for past years of multi-year tables (probably revised data) | year without the symbol |
| `*`, `**` | footnotes (footnote texts in `raw_xlsx_cell`) | — |

Important footnotes of the "Countries" sheet of the 2-digit bulletins:

* `*` — because of the specifics of mutual trade between EAEU countries and the EEC methodology, "imports by
  country of consignment" are used instead of "imports by trading country".
* `**` — data on Nagorno-Karabakh (code 999, alpha-2 `ARTH`) are not present in customs declarations and cover
  only the energy sector (source: Ministry of Energy of RA and major energy companies).
