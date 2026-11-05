# Словарь данных (data dictionary)

Генерируется автоматически из каталога DuckDB командой `python -m armstat_trade docs` — не редактировать вручную.
Описания таблиц и колонок (на английском, они же хранятся в самой БД: `duckdb_tables()`, `duckdb_columns()`) задаются в `sql/schema.sql`, `sql/views.sql`, `sql/qc.sql` (`COMMENT ON`). Обзор схемы — [database.md](database.md).

## Metadata / provenance

### `meta_db_query` (table, 378 rows)

Requests made to the web database: one query (all items) per page x language x mode x year, exported through /excelopen.php.

| column | type | description |
|---|---|---|
| `nid` | INTEGER |  |
| `lang` | VARCHAR |  |
| `mode` | VARCHAR | annual (years[]=Y) or monthly (year[]=Y, monid[]=1..12) |
| `year` | INTEGER |  |
| `query_url` | VARCHAR |  |
| `export_url` | VARCHAR |  |
| `raw_file` | VARCHAR | Gzipped export stored in the repository data directory |
| `fetched_at` | TIMESTAMP |  |
| `bytes` | BIGINT |  |
| `sha256` | VARCHAR |  |
| `n_rows` | INTEGER |  |

### `meta_file` (table, 29 rows)

Files linked from the pages nid 766 / 777 / 778 (the same file id is linked from all language versions).

| column | type | description |
|---|---|---|
| `file_id` | VARCHAR | Numeric id from the URL https://armstat.am/file/doc/<file_id>.<ext> |
| `ext` | VARCHAR |  |
| `url` | VARCHAR |  |
| `nid` | INTEGER |  |
| `nomenclature_level` | INTEGER | Digits of the EAEU CN FEA (TN VED) used in the file: 2, 4 or 10 |
| `year` | INTEGER | Reference year (from link text; for hidden links – from the workbook title) |
| `hidden` | BOOLEAN | TRUE if the page links the file with an empty link text (not visible on the site; earlier editions) |
| `is_current` | BOOLEAN | TRUE for the edition currently shown on the site for its level and year |
| `title_en` | VARCHAR |  |
| `title_hy` | VARCHAR |  |
| `title_ru` | VARCHAR |  |
| `size_bytes` | BIGINT |  |
| `sha256` | VARCHAR |  |
| `downloaded_at` | TIMESTAMP |  |

### `meta_language` (table, 3 rows)

Languages of the source site. lang is ISO 639-1; site_code is the URL segment used by armstat.am (Armenian = am).

| column | type | description |
|---|---|---|
| `lang` | VARCHAR |  |
| `site_code` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_native` | VARCHAR |  |

### `meta_page` (table, 21 rows)

Pages of the section "External trade database" (https://armstat.am/en/?nid=160) in every language.

| column | type | description |
|---|---|---|
| `nid` | INTEGER | Page id on armstat.am (?nid=...) |
| `lang` | VARCHAR |  |
| `kind` | VARCHAR | index \| db_commodity \| db_country \| files |
| `url` | VARCHAR |  |
| `title` | VARCHAR |  |
| `fetched_at` | TIMESTAMP |  |
| `sha256` | VARCHAR | Hash of the downloaded HTML |

### `meta_sheet` (table, 377 rows)

Every sheet of every workbook with its detected type and the table it was loaded into.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `sheet` | VARCHAR |  |
| `sheet_index` | INTEGER |  |
| `sheet_type` | VARCHAR | Detected table type, see docs/files.md |
| `year` | INTEGER |  |
| `title` | VARCHAR |  |
| `n_cells` | INTEGER | Non-empty cells (all of them are in raw_xlsx_cell) |
| `parsed_rows` | INTEGER | Data rows loaded into target_table |
| `target_table` | VARCHAR |  |

### `meta_workbook` (table, 28 rows)

Parsed xlsx workbooks: a downloaded xlsx file, or an xlsx inside a 7z archive.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR | file_id, or file_id/member for a workbook from an archive |
| `file_id` | VARCHAR |  |
| `member` | VARCHAR |  |
| `family` | VARCHAR | hs2 (bulletin by 2-digit chapters, nid 766), hs4 (nid 777), hs10 (nid 778) |
| `year` | INTEGER |  |
| `is_current` | BOOLEAN | FALSE for superseded editions (hidden links / archives); use is_current to avoid double counting |
| `n_sheets` | INTEGER |  |

## Dimensions

### `dim_bec` (table, 7 rows)

Broad Economic Categories (top level) as used in the 2-digit bulletins; the code is assigned by matching the English label.

| column | type | description |
|---|---|---|
| `bec_code` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |

### `dim_country` (table, 254 rows)

Partner countries. Codes are ISO 3166-1 numeric as used by Armstat, plus special codes 998 (unknown country), 999 (Nagorno-Karabakh), 1111 (EU countries not specified). Names come from the web database forms (all three languages).

| column | type | description |
|---|---|---|
| `country_code` | INTEGER |  |
| `iso_alpha2` | VARCHAR | Alpha-2 code from the "Countries" sheets of the 2-digit bulletins (Armstat uses ARTH for code 999) |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR |  |
| `is_special` | BOOLEAN |  |

### `dim_country_group` (table, 7 rows)

Country groups used in the 2-digit bulletins (CIS, EAEU, EU, ...).

| column | type | description |
|---|---|---|
| `group_code` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |

### `dim_country_name` (table, 3,669 rows)

All spellings of country names seen in the sources (used to resolve names to codes).

| column | type | description |
|---|---|---|
| `country_code` | INTEGER |  |
| `lang` | VARCHAR |  |
| `name` | VARCHAR |  |
| `source` | VARCHAR |  |

### `dim_data_basis` (table, 3 rows)

Data source basis of the 4-digit tables (total / by goods declarations / by physical persons).

| column | type | description |
|---|---|---|
| `basis` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `description` | VARCHAR |  |

### `dim_flow` (table, 4 rows)

Trade flows.

| column | type | description |
|---|---|---|
| `flow` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR |  |
| `description` | VARCHAR |  |

### `dim_hs` (table, 12,526 rows)

Commodity codes of the EAEU CN FEA (TN VED EAEU): chapters (2 digits), headings (4 digits) and 10-digit subheadings, zero padded.

| column | type | description |
|---|---|---|
| `hs_code` | VARCHAR | Zero padded code (Excel dropped leading zeros in the sources: 101 -> 0101) |
| `level` | INTEGER | 2, 4 or 10 |
| `parent_code` | VARCHAR |  |
| `section` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR | Russian names: 4-digit from the web database form, 2-digit from the TN VED 2017 document; not available for 10-digit codes |

### `dim_hs_section` (table, 21 rows)

Sections (I-XXI) of the EAEU CN FEA / Harmonized System. en/hy names from the 10-digit files, ru from the TN VED 2017 document.

| column | type | description |
|---|---|---|
| `section` | VARCHAR |  |
| `section_no` | INTEGER |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR |  |

### `dim_measure` (table, 7 rows)

Measures (value columns) used in the fact tables; column names of facts are equal to these codes.

| column | type | description |
|---|---|---|
| `measure` | VARCHAR |  |
| `unit_en` | VARCHAR |  |
| `unit_hy` | VARCHAR |  |
| `description` | VARCHAR |  |

### `dim_sitc` (table, 75 rows)

SITC sections (1 digit) and divisions (2 digits) as used in the 2-digit bulletins.

| column | type | description |
|---|---|---|
| `sitc_code` | VARCHAR |  |
| `level` | INTEGER |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |

### `dim_unit` (table, 27 rows)

Supplementary units of the 10-digit tables (normalised; raw_labels lists the spellings found).

| column | type | description |
|---|---|---|
| `unit_code` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `raw_labels` | VARCHAR[] |  |

## Facts from the web database

### `db_commodity_trade` (table, 508,692 rows)

Web database "External trade by commodity (4-digit level)" (nid 148): annual values since 1995, monthly since 2007.

| column | type | description |
|---|---|---|
| `hs4_code` | VARCHAR |  |
| `year` | INTEGER |  |
| `month` | INTEGER |  |
| `period_code` | INTEGER |  |
| `flow` | VARCHAR | export \| import |
| `weight_ton` | DOUBLE |  |
| `value_kusd` | DOUBLE |  |

### `db_country_trade` (table, 123,372 rows)

Web database "External trade by country" (nid 159 until 2016, nid 717 from 2017): trade with each partner country, annual and monthly, thousand US$.

| column | type | description |
|---|---|---|
| `country_code` | INTEGER |  |
| `year` | INTEGER |  |
| `month` | INTEGER | 1-12 for monthly values, NULL for the annual value |
| `period_code` | INTEGER | Code used by the site: 1-12 = month, 13 = year |
| `flow` | VARCHAR | export \| import_origin \| import_consignment |
| `value_kusd` | DOUBLE |  |
| `source_nid` | INTEGER | Page the value was taken from (159 for years < 2017, 717 otherwise) |

## Facts from the published files

### `file_bec_trade` (table, 1,024 rows)

Sheet BEC-1 of the 2-digit bulletins: trade by Broad Economic Categories, last 4 years, million US$.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `row_type` | VARCHAR |  |
| `bec_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `value_musd` | DOUBLE |  |

### `file_country_trade` (table, 10,055 rows)

Sheet "Countries" of the 2-digit bulletins: trade by partner country and country group for the last 4 years, thousand US$.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `row_num` | INTEGER |  |
| `row_type` | VARCHAR | country \| group (aggregate of a country group, see group_code) |
| `country_code` | INTEGER |  |
| `group_code` | VARCHAR | For row_type=country: the group heading the country is listed under; for row_type=group: the group itself |
| `label_hy` | VARCHAR |  |
| `label_en` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `value_kusd` | DOUBLE |  |

### `file_hs10_aggregate` (table, 25,304 rows)

Subtotal rows of the 10-digit files: totals, sections, groups (chapters) and subgroups (headings), with their bilingual names.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `sheet` | VARCHAR |  |
| `row_num` | INTEGER |  |
| `is_annex` | BOOLEAN |  |
| `section` | VARCHAR |  |
| `level` | VARCHAR | total_with_physical_persons \| total_without_physical_persons \| section \| group \| subgroup |
| `hs_code` | VARCHAR | Derived code: 2 digits for a group, 4 digits for a subgroup (common prefix of the codes under the row) |
| `code_prefix` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `n_items` | INTEGER |  |
| `flow` | VARCHAR |  |
| `weight_ton` | DOUBLE |  |
| `value_usd` | DOUBLE |  |

### `file_hs10_trade` (table, 166,322 rows)

Files nid 778: annual trade by 10-digit EAEU CN FEA codes (quantity in supplementary unit, tonnes, US$). is_annex=TRUE rows come from the annex "Transport total" and repeat chapter 87 codes including trade of physical persons.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `sheet` | VARCHAR |  |
| `row_num` | INTEGER |  |
| `is_annex` | BOOLEAN | TRUE for the annex "Transport total" (chapter 87 incl. trade of physical persons); exclude when summing |
| `section` | VARCHAR |  |
| `hs10_code` | VARCHAR |  |
| `hs4_code` | VARCHAR |  |
| `hs2_code` | VARCHAR |  |
| `unit_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `quantity` | DOUBLE |  |
| `weight_ton` | DOUBLE |  |
| `value_usd` | DOUBLE |  |

### `file_hs2_country_trade` (table, 77,464 rows)

Sheet "by Commodity Groups" of the 2-digit bulletins: each HS chapter broken down by partner country, bulletin year.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `row_num` | INTEGER |  |
| `row_type` | VARCHAR | country \| chapter (chapter total) \| total (all chapters) |
| `hs2_code` | VARCHAR |  |
| `country_code` | INTEGER |  |
| `flow` | VARCHAR |  |
| `weight_ton` | DOUBLE |  |
| `value_kusd` | DOUBLE |  |

### `file_hs2_partner_trade` (table, 88,452 rows)

Sheets *_groups / *_countries of the 2-digit bulletins: trade by HS chapter with the world, a country group or a single country, for the bulletin year (tonnes, million AMD, thousand US$).

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `sheet` | VARCHAR |  |
| `row_num` | INTEGER |  |
| `partner_kind` | VARCHAR | group (group_code is set) \| country (country_code is set) |
| `group_code` | VARCHAR |  |
| `country_code` | INTEGER |  |
| `partner_label` | VARCHAR | Block heading as printed, e.g. "ԻՏԱԼԻԱ - ITALY" |
| `row_type` | VARCHAR | chapter \| total |
| `hs2_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `weight_ton` | DOUBLE |  |
| `value_mln_amd` | DOUBLE |  |
| `value_kusd` | DOUBLE |  |

### `file_hs2_trade` (table, 7,424 rows)

Sheets By_Groups and Groups_% of the 2-digit bulletins: trade by HS chapters and sections, last 4 years.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `row_type` | VARCHAR | chapter (hs_code = 2 digits) \| section (hs_code = roman numeral) \| total |
| `hs_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `value_kusd` | DOUBLE |  |
| `share_pct` | DOUBLE |  |

### `file_hs4_trade` (table, 58,442 rows)

Files nid 777: annual trade by 4-digit headings, separately for total trade, goods declarations and physical persons.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `basis` | VARCHAR | See dim_data_basis |
| `sheet` | VARCHAR |  |
| `row_num` | INTEGER |  |
| `row_type` | VARCHAR | item (a heading) or total (the total row of the sheet) |
| `hs4_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `weight_ton` | DOUBLE |  |
| `value_kusd` | DOUBLE |  |

### `file_humanitarian_aid` (table, 4,775 rows)

Sheet "Hum-Aid" of the 2-digit bulletins: humanitarian aid received by Armenia by HS chapter and donor country. The value column is labelled "US $" in the source (magnitudes suggest thousand US$, see docs).

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `row_num` | INTEGER |  |
| `row_type` | VARCHAR |  |
| `hs2_code` | VARCHAR |  |
| `country_code` | INTEGER |  |
| `weight_ton` | DOUBLE |  |
| `value_usd` | DOUBLE |  |

### `file_sitc_trade` (table, 4,896 rows)

Sheets SITC-1 / SITC-2 of the 2-digit bulletins: trade by SITC sections and divisions, last 4 years.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `sitc_level` | INTEGER |  |
| `row_type` | VARCHAR |  |
| `sitc_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `weight_ton` | DOUBLE |  |
| `value_kusd` | DOUBLE |  |

## Staging (web database exports in all languages)

### `stg_db_commodity` (table, 763,038 rows)

Rows of the commodity database exports exactly as published, for every language.

| column | type | description |
|---|---|---|
| `lang` | VARCHAR |  |
| `mode` | VARCHAR |  |
| `seq` | INTEGER |  |
| `commodity_name` | VARCHAR |  |
| `code_raw` | VARCHAR |  |
| `hs4_code` | VARCHAR |  |
| `year` | INTEGER |  |
| `period_code` | INTEGER |  |
| `export_ton` | DOUBLE |  |
| `export_kusd` | DOUBLE |  |
| `import_ton` | DOUBLE |  |
| `import_kusd` | DOUBLE |  |

### `stg_db_country` (table, 172,974 rows)

Rows of the country database exports exactly as published, for every page (159, 717) and language; country_code is resolved from the name.

| column | type | description |
|---|---|---|
| `nid` | INTEGER |  |
| `lang` | VARCHAR |  |
| `mode` | VARCHAR |  |
| `seq` | INTEGER |  |
| `country_name` | VARCHAR |  |
| `country_code` | INTEGER |  |
| `year` | INTEGER |  |
| `period_code` | INTEGER |  |
| `export_kusd` | DOUBLE |  |
| `import_origin_kusd` | DOUBLE |  |
| `import_consignment_kusd` | DOUBLE |  |

## Raw cells

### `raw_xlsx_cell` (table, 1,755,060 rows)

Lossless dump of every non-empty cell of every workbook (cached values; formula text where present).

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `sheet` | VARCHAR |  |
| `row_num` | INTEGER |  |
| `col_num` | INTEGER |  |
| `cell_ref` | VARCHAR |  |
| `value_text` | VARCHAR |  |
| `value_num` | DOUBLE |  |
| `formula` | VARCHAR |  |

## Data quality

### `qc_db_country_overlap` (table, 0 rows)

Differences between nid 159 and nid 717 for the same country / year / period (expected: none).

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `period_code` | INTEGER |  |
| `country_code` | INTEGER |  |
| `export_159` | DOUBLE |  |
| `export_717` | DOUBLE |  |
| `import_origin_159` | DOUBLE |  |
| `import_origin_717` | DOUBLE |  |
| `import_consignment_159` | DOUBLE |  |
| `import_consignment_717` | DOUBLE |  |

### `qc_db_language_consistency` (table, 126 rows)

Row counts and sums of the web database exports per language (expected: identical across en/hy/ru).

| column | type | description |
|---|---|---|
| `db` | VARCHAR |  |
| `nid` | INTEGER |  |
| `mode` | VARCHAR |  |
| `year` | INTEGER |  |
| `n_langs` | BIGINT |  |
| `distinct_row_counts` | BIGINT |  |
| `distinct_sum1` | BIGINT |  |
| `distinct_sum2` | BIGINT |  |
| `rows_by_lang` | VARCHAR[] |  |

### `qc_db_monthly_vs_annual` (table, 112 rows)

Sum of monthly values vs the annual value in the web database (differences come from revisions not carried into monthly data).

| column | type | description |
|---|---|---|
| `db` | VARCHAR |  |
| `year` | INTEGER |  |
| `flow` | VARCHAR |  |
| `n_months` | BIGINT |  |
| `annual_kusd` | DOUBLE |  |
| `sum_of_months_kusd` | DOUBLE |  |
| `diff_pct` | DOUBLE |  |

### `qc_file_totals` (table, 460 rows)

Published total rows vs the sum of the item rows (hs4: per sheet; hs10: per section).

| column | type | description |
|---|---|---|
| `family` | VARCHAR |  |
| `workbook_id` | VARCHAR |  |
| `part` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `total_row` | DOUBLE |  |
| `sum_items` | DOUBLE |  |
| `unit` | VARCHAR |  |

### `qc_file_vs_db_hs4` (table, 16 rows)

Annual totals of the 4-digit files vs the web database (differences reflect revisions after the file was published).

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `flow` | VARCHAR |  |
| `file_kusd` | DOUBLE |  |
| `db_kusd` | DOUBLE |  |
| `diff_pct` | DOUBLE |  |

### `qc_summary` (table, 10 rows)

Result of all data quality checks (OK / WARN / INFO).

| column | type | description |
|---|---|---|
| `check_name` | VARCHAR |  |
| `status` | VARCHAR |  |
| `n_issues` | BIGINT |  |
| `details` | VARCHAR |  |

### `qc_unresolved_country` (table, 0 rows)

_no description_

| column | type | description |
|---|---|---|
| `context` | VARCHAR |  |
| `label` | VARCHAR |  |

## Views

### `v_db_commodity_annual` (view, 34,197 rows)

Annual trade by 4-digit heading from the web database (tonnes, thousand US$).

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `hs4_code` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR |  |
| `section` | VARCHAR |  |
| `export_ton` | DOUBLE |  |
| `export_kusd` | DOUBLE |  |
| `import_ton` | DOUBLE |  |
| `import_kusd` | DOUBLE |  |

### `v_db_commodity_monthly` (view, 220,149 rows)

Monthly trade by 4-digit heading from the web database (tonnes, thousand US$).

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `month` | INTEGER |  |
| `period_start` | DATE |  |
| `hs4_code` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR |  |
| `export_ton` | DOUBLE |  |
| `export_kusd` | DOUBLE |  |
| `import_ton` | DOUBLE |  |
| `import_kusd` | DOUBLE |  |

### `v_db_country_annual` (view, 4,962 rows)

Annual trade by partner country from the web database, one row per country and year (thousand US$).

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `country_code` | INTEGER |  |
| `iso_alpha2` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR |  |
| `export_kusd` | DOUBLE |  |
| `import_origin_kusd` | DOUBLE |  |
| `import_consignment_kusd` | DOUBLE |  |

### `v_db_country_monthly` (view, 36,162 rows)

Monthly trade by partner country from the web database (thousand US$; monthly values, not cumulative).

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `month` | INTEGER |  |
| `period_start` | DATE |  |
| `country_code` | INTEGER |  |
| `iso_alpha2` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR |  |
| `export_kusd` | DOUBLE |  |
| `import_origin_kusd` | DOUBLE |  |
| `import_consignment_kusd` | DOUBLE |  |

### `v_file_bec_trade_latest` (view, 320 rows)

Sheet BEC-1: latest edition for every year.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `row_type` | VARCHAR |  |
| `bec_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `value_musd` | DOUBLE |  |
| `edition_year` | INTEGER |  |

### `v_file_country_trade_latest` (view, 3,117 rows)

Sheet "Countries": for every year the values of the most recent bulletin containing that year.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `row_num` | INTEGER |  |
| `row_type` | VARCHAR |  |
| `country_code` | INTEGER |  |
| `group_code` | VARCHAR |  |
| `label_hy` | VARCHAR |  |
| `label_en` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `value_kusd` | DOUBLE |  |
| `edition_year` | INTEGER |  |

### `v_file_hs10_current` (view, 129,028 rows)

10-digit trade from the current edition of each year (sections only, the transport annex is excluded to avoid double counting).

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `hs10_code` | VARCHAR |  |
| `hs4_code` | VARCHAR |  |
| `hs4_name_en` | VARCHAR |  |
| `hs4_name_hy` | VARCHAR |  |
| `hs4_name_ru` | VARCHAR |  |
| `hs2_code` | VARCHAR |  |
| `section` | VARCHAR |  |
| `unit_code` | VARCHAR |  |
| `unit_en` | VARCHAR |  |
| `unit_hy` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `quantity` | DOUBLE |  |
| `weight_ton` | DOUBLE |  |
| `value_usd` | DOUBLE |  |
| `workbook_id` | VARCHAR |  |

### `v_file_hs2_partner_current` (view, 75,268 rows)

Trade by HS chapter and partner (world, group or country) from the current 2-digit bulletins.

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `partner_kind` | VARCHAR |  |
| `group_code` | VARCHAR |  |
| `group_name_en` | VARCHAR |  |
| `country_code` | INTEGER |  |
| `country_name_en` | VARCHAR |  |
| `country_name_hy` | VARCHAR |  |
| `country_name_ru` | VARCHAR |  |
| `hs2_code` | VARCHAR |  |
| `hs2_name_en` | VARCHAR |  |
| `hs2_name_hy` | VARCHAR |  |
| `hs2_name_ru` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `weight_ton` | DOUBLE |  |
| `value_mln_amd` | DOUBLE |  |
| `value_kusd` | DOUBLE |  |
| `workbook_id` | VARCHAR |  |
| `sheet` | VARCHAR |  |

### `v_file_hs2_trade_latest` (view, 2,320 rows)

Sheets By_Groups / Groups_%: latest edition for every year.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `row_type` | VARCHAR |  |
| `hs_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `value_kusd` | DOUBLE |  |
| `share_pct` | DOUBLE |  |
| `edition_year` | INTEGER |  |

### `v_file_hs4_current` (view, 46,930 rows)

4-digit trade from the current edition of each year, by data basis (total / declarations / physical persons).

| column | type | description |
|---|---|---|
| `year` | INTEGER |  |
| `basis` | VARCHAR |  |
| `hs4_code` | VARCHAR |  |
| `name_en` | VARCHAR |  |
| `name_hy` | VARCHAR |  |
| `name_ru` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `weight_ton` | DOUBLE |  |
| `value_kusd` | DOUBLE |  |
| `workbook_id` | VARCHAR |  |

### `v_file_sitc_trade_latest` (view, 1,532 rows)

Sheets SITC-1 / SITC-2: latest edition for every year.

| column | type | description |
|---|---|---|
| `workbook_id` | VARCHAR |  |
| `year` | INTEGER |  |
| `sitc_level` | INTEGER |  |
| `row_type` | VARCHAR |  |
| `sitc_code` | VARCHAR |  |
| `flow` | VARCHAR |  |
| `weight_ton` | DOUBLE |  |
| `value_kusd` | DOUBLE |  |
| `edition_year` | INTEGER |  |

### `v_sources` (view, 407 rows)

Every source file and web database request used to build the database.

| column | type | description |
|---|---|---|
| `source_kind` | VARCHAR |  |
| `source_id` | VARCHAR |  |
| `nid` | INTEGER |  |
| `nomenclature_level` | INTEGER |  |
| `year` | INTEGER |  |
| `is_current` | BOOLEAN |  |
| `title_en` | VARCHAR |  |
| `url` | VARCHAR |  |

