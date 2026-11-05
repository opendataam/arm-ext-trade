# Contents of the published files

**English** | [Հայերեն](../hy/files.md) | [Русский](../ru/files.md)

All files are bilingual (Armenian + English) xlsx. There are three families, by the level of detail of the
CN FEA EAEU (the commodity nomenclature of foreign economic activity of the EAEU, identical to the Harmonized
System up to 6 digits). The full list of files with their identifiers is in [inventory.md](inventory.md).

In all families Excel dropped the leading zeros of codes (`101` instead of `0101`, `101210000` instead of
`0101210000`); in the database codes are padded with zeros to 2/4/10 digits.

---

## 1. Bulletin by 2-digit chapters (page nid 766)

"Foreign trade of the Republic of Armenia (by CN FEA EAEU at the 2-digit level)".
Bulletin years: 2018–2024 (+ an early 2018 edition in the archive `99516683.7z`).
It is a statistical bulletin of 16–18 sheets of different layouts. Multi-year sheets cover the last 4 years,
so the same year appears in several bulletins (with revisions) — the database keeps all editions, and the
`v_*_latest` views pick the latest bulletin for each year.

| sheet (name variants) | type in the database (`meta_sheet.sheet_type`) | contents | measures | database table |
|---|---|---|---|---|
| `Countries` | `countries` | trade by partner country and country group (Total, CIS, EAEU, other CIS, non-CIS, EU, other) for 4 years; columns: country code, alpha-2, name (hy); English group names are on the row below | exports; imports by country of consignment; imports by country of origin — thousand USD | `file_country_trade` |
| `SITC-1`, `SITC-1-<year>` | `sitc1` | by SITC section (1 digit); two tables per sheet: exports and imports | tonnes, thousand USD × 4 years | `file_sitc_trade` |
| `SITC-2`, `SITC-2-<year>` | `sitc2` | by SITC division (2 digits) | tonnes, thousand USD × 4 years | `file_sitc_trade` |
| `BEC-1`, `BEC-1-<year>` | `bec` | by Broad Economic Categories (BEC), 7 categories | million USD × 4 years | `file_bec_trade` |
| `By_Groups` | `hs2_years` | by CN FEA chapter (2 digits) and section (Roman numerals; the files contain typos like `XY`=XV, `XYIII`=XVIII) | thousand USD × 4 years | `file_hs2_trade.value_kusd` |
| `Groups_%` | `hs2_share` | the same as % of total | % × 4 years | `file_hs2_trade.share_pct` |
| `World_groups` | `hs2_partner` | CN FEA chapters, trade with the whole world, bulletin year | tonnes, million AMD, thousand USD | `file_hs2_partner_trade` (`group_code='WORLD'`) |
| `CIS_groups` | `hs2_partner` | the same with CIS countries | the same | `group_code='CIS'` |
| `EEU_groups`, `EEU_groups_countries` | `hs2_partner` | the same with EAEU countries; the `_countries` variant is followed by blocks per country | the same | `group_code='EEU'` and country blocks |
| `EEU_countries` | `hs2_partner` | blocks for each EAEU country | the same | `partner_kind='country'` |
| `OTHER CIS_groups`, `OTHER CIS_groups_countries`, `OTHER CIS_countries` | `hs2_partner` | other CIS countries (group total and/or country blocks) | the same | `group_code='CIS_OTHER'` / countries |
| `NON CIS_countries` | `hs2_partner` | CN FEA chapters, trade with non-CIS countries (total) | the same | `group_code='NON_CIS'` |
| `EU_countries` | `hs2_partner` | EU total followed by blocks per EU country | the same | `group_code='EU'` and countries |
| `Other NON CIS_countries_1/2`, `OTHER COUNTRIES_1/2`, `Other NON CIS_NON EU countries1/2` | `hs2_partner` | other countries (neither CIS nor EU): total (if any) and country blocks; sheet `_2` continues without a header | the same | `group_code='OTHER'` and countries |
| `by Commodity Groups`, `BY COMMODITY GROUPS` | `hs2_country` | each CN FEA chapter broken down by country (with country codes) | tonnes, thousand USD | `file_hs2_country_trade` |
| `Hum-Aid`, `HUM_AID` | `hum_aid` | humanitarian aid received by Armenia: CN FEA chapter × donor country | tonnes; value labelled "US $" | `file_humanitarian_aid` |

Country blocks in `hs2_partner` sheets start with a heading row like `ԻՏԱԼԻԱ - ITALY` (Armenian and English names
in capitals), followed by a "Ընդամենը" (total) row and the CN FEA chapter rows. Headings are matched to country
codes by name (`dim_country_name`) and the dictionary `reference.COUNTRY_NAME_ALIASES`; the source text is kept
in `partner_label`.

Quirks:

* In the `Countries` sheet countries are nested in group headings: Total → CIS → EAEU (list) → other CIS (list) →
  non-CIS → EU (list) → "Այլ երկրներ / Other countries" (list of countries that are neither CIS nor EU).
  The group membership of a country is stored in `file_country_trade.group_code` and is tied to the bulletin year
  (for example, the United Kingdom (826) is in the EU group in the 2018 bulletin).
* The last `Այլ երկրներ` row without a code is the remainder for countries not shown separately
  (`row_type='other_countries'`).
* Imports in the sheets by CN FEA chapter (`hs2_partner`, `hs2_country`) are not split into "by country of
  origin/consignment" (`flow='import'`).
* `Hum-Aid` sheet: the value column is labelled "ԱՄՆ դոլար, US $", but the magnitudes (for example, 42,248 for
  21 tonnes of pharmaceuticals from the USA in 2024) look more like thousand USD; the values are stored as
  published, in the `value_usd` column.
* In the `Hum-Aid` sheet the CN FEA chapter code is sometimes in column A and sometimes in column B — the parser
  handles both.

## 2. Tables by 4-digit heading (page nid 777)

"Foreign trade of RA by CN FEA EAEU at the 4-digit level", years 2018–2025
(+ two hidden early editions for 2018: `99516688`, `99520258`).

Three sheets of the same layout (`Sheet1/2/3`; in the 2025 file — `Total/Max/Citizen`):

| sheet | `basis` in the database | contents |
|---|---|---|
| 1 | `total` | all trade |
| 2 | `declarations` | by goods declarations and the "Statistical form of accounting for the movement of goods" (mutual EAEU trade) |
| 3 | `physical_persons` | by declarations of physical persons |

Columns: `A` code (4 digits), `B` name (hy), `C` exports, tonnes, `D` exports, thousand USD, `E` imports, tonnes,
`F` imports, thousand USD, `G` name (en). The first data row is the total ("Ընդամենը / Total").
Some rows have no code (for example, "Animals, live, except farm animals" in the 2024 file) — it is restored from
the name.

Database table: `file_hs4_trade` (+ view `v_file_hs4_current`).

## 3. Tables by 10-digit code (page nid 778)

"Foreign trade of RA by CN FEA EAEU at the 10-digit level", years 2018–2025
(+ hidden early editions for 2018 `99516693` and 2020 `99525728`).

Sheets `I` … `XXI` are CN FEA sections (section XIX "Arms and ammunition" is absent from the files),
plus the annex `Transport total` — "Annex N1: land, air and water transport vehicles (total, including trade of
physical persons)".

Columns of all sheets: `A` name (hy) or 10-digit code, `B` unit of measurement (`հատ/piece`, `կգ/kg`…),
`C` exports — quantity, `D` exports — tonnes, `E` exports — USD, `F`–`H` the same for imports,
`I` name (en) or code.

The rows form a hierarchy:

| row | how it is recognised | `file_hs10_aggregate.level` |
|---|---|---|
| "Ընդամենը (ներառյալ ֆիզիկական անձանց…)" | total including trade of physical persons (sheet I only) | `total_with_physical_persons` |
| "Ընդամենը (առանց ֆիզիկական անձանց…)" | total without trade of physical persons | `total_without_physical_persons` |
| "I. …", "XI. …" | section total | `section` |
| a name followed by another name | chapter (2 digits) | `group` |
| a name followed by codes | heading (4 digits) | `subgroup` |
| 10-digit code | commodity | → `file_hs10_trade` |

Chapter/heading codes are not given in the file and are computed as the common prefix of the codes below the row
(`code_prefix`, `hs_code`). The files contain no Russian names of 10-digit codes.

Quantity is given in the "supplementary unit" of the commodity; the same unit is spelled in different ways
(`m sq.`/`m.sq.`/`m2`, `piese`/`piece`) — they are normalised in `dim_unit.unit_code`, and the source spellings are
listed in `dim_unit.raw_labels`.

Rows of the `Transport total` annex repeat the codes of chapter 87 of section XVII, but include trade of physical
persons, so in `file_hs10_trade` they are flagged `is_annex = TRUE` and excluded from the `v_file_hs10_current`
view.

## 4. CN FEA EAEU 2017 (archive `99528903.7z`)

`ТНВЭД_2017.doc` — Word 97, ~58 MB, the full text of the nomenclature in Russian with duty rates.
The `armstat-trade tnved` command converts the document to text (`textutil` on macOS or LibreOffice `soffice`) and
extracts the section (`РАЗДЕЛ I`…) and chapter (`ГРУППА 01`…) headings →
`data/interim/tnved_2017.csv` → `dim_hs_section.name_ru`, `dim_hs.name_ru` (level 2).
The 10-digit lines of the document are hierarchical fragments ("– – other") scattered over merged table cells;
they cannot be matched to codes reliably and are not extracted.

## 5. Lossless storage

Every non-empty cell of every sheet of all workbooks (including footnotes, headings and formulas) is written to
`raw_xlsx_cell` (≈1.75 million cells): `workbook_id, sheet, row_num, col_num, cell_ref, value_text, value_num,
formula`. This makes it possible to check any value of the structured tables against its source cell (the
structured tables store `row_num`).
