# Data quality

**English** | [Հայերեն](../hy/data_quality.md) | [Русский](../ru/data_quality.md)

The checks run on every build (`sql/qc.sql`) and are stored in the database. Summary:

```sql
SELECT * FROM qc_summary;
```

## Results of the latest build (5 November 2026)

| check | status | meaning |
|---|---|---|
| `db_country_159_vs_717` | OK, 0 differences | pages 159 and 717 return identical values for the overlapping years (2017–2026) |
| `db_language_consistency` | OK, 0 | the en/hy/ru exports match in row counts and sums for all 126 requests |
| `country_names_resolved`, `db_country_rows_without_code` | OK, 0 | all country names in all exports and in all country block headings of the files are matched to codes |
| `db_monthly_vs_annual` | 0 differences | the sum of the months equals the annual value exactly (countries 2003–2025, commodities 2007–2025) |
| `file_vs_db_hs4` | 0 differences > 0.5 % | annual totals of the 4-digit files match the web database (max. 0.002 %) |
| `file_totals_vs_items` | 2 | a published section total ≠ the sum of its rows (see below) |
| `hs_codes_in_dim` | OK | all codes of the fact tables are present in `dim_hs` |
| `hs4_rows_without_code` | OK | empty codes in the 4-digit files are restored from the names |
| `partner_rows_without_country` | OK | all country blocks of the 2-digit bulletins are matched |

## Quirks and issues of the sources

### Web database

1. **The Excel export may return the result of someone else's query.** During the first full collection 13 of
   378 exports (3.4 %) contained data of another table or another year, or were empty. Exports are validated
   against the query parameters and the row count from the paginator; invalid ones are requested again (see
   [sources.md](sources.md)).
2. **Imports by country of origin are zero in 1995–2002** — for these years the country database has only
   imports by country of consignment. Since 2003 both measures are filled (their world totals are equal).
3. **Monthly data:** by country — since 2003, by commodity — since 2007; 2026 — January–September.
4. **Outdated country names** in the exports of early years and **duplicate names** in the form (Serbia 688/891,
   Samoa 16/882 in hy/ru, "Saoma" — a typo in en for code 16) are resolved, see `dim_country_name`.
5. **Code 997 "Individual" (physical persons)** is present in the 1996–1998 exports but missing from the form.
6. **Historical 4-digit codes** (22 codes, e.g. 0509, 4108–4111, 8520, 9203) exist only in the exports of early
   years.

### Files

1. **The rows of the 10-digit sections are trade without physical persons.** The sum of the 10-digit rows of the
   sections equals the "Total (without trade of physical persons)"; the "including" total is larger by the trade
   of physical persons (in 2019 imports were 5,063 vs 5,529 million USD). Trade of physical persons by 10-digit
   code is given only for transport (the "Transport total" annex, chapter 87).
2. **Section VII in the 2025 file**: the section export total is 51.2 million USD, while the sum of its rows is
   19.8 million USD (for chapters 39 and 40 the totals match the rows) — probably an error in the total row of the
   source. Because of it, the sum of the 10-digit export rows for 2025 is 0.38 % lower than the published total.
3. **Section XVIII in the 2024 file**: imports by rows exceed the section total by 1.7 million USD.
4. **`Countries` sheet of the 2023–2024 bulletins**: imports (by consignment) of the "non-CIS" group for 2022 and
   2023 are identical (5,620,130.104 thousand USD) — the 2022 value is repeated for 2023. In the same 2023 bulletin
   imports by origin are 8,146,184.9; the data are stored as published.
5. **Revisions.** The same year is published in several bulletins (4-year series) and in early editions;
   the values may differ (for example, the preliminary 2018 data in `99516688`, `99520258`, `99516683.7z`).
   Use `meta_workbook.is_current` and the `v_*_latest` views.
6. **Typos in the sources** (not corrected in the text, but handled by the parsers): Roman section numbers
   (`XY`, `XYIII`), units (`piese`, `m5` instead of `m3`, `kgP2O6`), names ("UNKNOW COUNTRY", "Saoma",
   "EEU contries"), the Karabakh code `ARTH` instead of an alpha-2 code.
7. **`Hum-Aid` sheet** — labelled "US $", but the magnitudes suggest thousand USD (see [files.md](files.md)).
8. **Section XIX** (arms and ammunition) is absent from the 10-digit files.
9. **Formulas.** The workbooks contain 44 formulas (mostly totals); the database holds the cached values,
   the formula text is in `raw_xlsx_cell.formula`.

## How to check a value against the source

```sql
-- a fact value → its source cell
SELECT f.*, c.cell_ref, c.value_text
FROM file_hs4_trade f
JOIN raw_xlsx_cell c ON c.workbook_id = f.workbook_id AND c.sheet = f.sheet AND c.row_num = f.row_num
WHERE f.hs4_code = '2208' AND f.year = 2024 AND f.basis = 'total' AND f.flow = 'export';

-- a web database export row in all languages
SELECT lang, country_name, export_kusd FROM stg_db_country
WHERE nid = 717 AND mode = 'annual' AND year = 2024 AND country_code = 643;
```
