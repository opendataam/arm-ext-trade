-- DuckDB schema of the Armstat foreign trade database.
-- Table prefixes:
--   meta_  provenance: site pages, files, workbooks, sheets, web database requests
--   dim_   reference dimensions (multilingual: en / hy / ru)
--   db_    facts from the web database (query interface, nid 148 / 159 / 717)
--   file_  facts from the published xlsx files (nid 766 / 777 / 778)
--   stg_   staging copies of the web database exports in every language
--   raw_   lossless dump of every non-empty xlsx cell
--   qc_    data quality checks (created by the build)
-- Comments on every table and column are stored in the database catalog
-- (see duckdb_tables() / duckdb_columns()) and rendered into docs/data_dictionary.md.

------------------------------------------------------------------------------
-- metadata / provenance
------------------------------------------------------------------------------
CREATE TABLE meta_language (
    lang        VARCHAR PRIMARY KEY,
    site_code   VARCHAR NOT NULL,
    name_en     VARCHAR,
    name_native VARCHAR
);
COMMENT ON TABLE meta_language IS 'Languages of the source site. lang is ISO 639-1; site_code is the URL segment used by armstat.am (Armenian = am).';

CREATE TABLE meta_page (
    nid        INTEGER NOT NULL,
    lang       VARCHAR NOT NULL,
    kind       VARCHAR,
    url        VARCHAR,
    title      VARCHAR,
    fetched_at TIMESTAMP,
    sha256     VARCHAR,
    PRIMARY KEY (nid, lang)
);
COMMENT ON TABLE meta_page IS 'Pages of the section "External trade database" (https://armstat.am/en/?nid=160) in every language.';
COMMENT ON COLUMN meta_page.nid IS 'Page id on armstat.am (?nid=...)';
COMMENT ON COLUMN meta_page.kind IS 'index | db_commodity | db_country | files';
COMMENT ON COLUMN meta_page.sha256 IS 'Hash of the downloaded HTML';

CREATE TABLE meta_file (
    file_id            VARCHAR PRIMARY KEY,
    ext                VARCHAR,
    url                VARCHAR,
    nid                INTEGER,
    nomenclature_level INTEGER,
    year               INTEGER,
    hidden             BOOLEAN,
    is_current         BOOLEAN,
    title_en           VARCHAR,
    title_hy           VARCHAR,
    title_ru           VARCHAR,
    size_bytes         BIGINT,
    sha256             VARCHAR,
    downloaded_at      TIMESTAMP
);
COMMENT ON TABLE meta_file IS 'Files linked from the pages nid 766 / 777 / 778 (the same file id is linked from all language versions).';
COMMENT ON COLUMN meta_file.file_id IS 'Numeric id from the URL https://armstat.am/file/doc/<file_id>.<ext>';
COMMENT ON COLUMN meta_file.nomenclature_level IS 'Digits of the EAEU CN FEA (TN VED) used in the file: 2, 4 or 10';
COMMENT ON COLUMN meta_file.year IS 'Reference year (from link text; for hidden links – from the workbook title)';
COMMENT ON COLUMN meta_file.hidden IS 'TRUE if the page links the file with an empty link text (not visible on the site; earlier editions)';
COMMENT ON COLUMN meta_file.is_current IS 'TRUE for the edition currently shown on the site for its level and year';

CREATE TABLE meta_workbook (
    workbook_id VARCHAR PRIMARY KEY,
    file_id     VARCHAR NOT NULL,
    member      VARCHAR,
    family      VARCHAR,
    year        INTEGER,
    is_current  BOOLEAN,
    n_sheets    INTEGER
);
COMMENT ON TABLE meta_workbook IS 'Parsed xlsx workbooks: a downloaded xlsx file, or an xlsx inside a 7z archive.';
COMMENT ON COLUMN meta_workbook.workbook_id IS 'file_id, or file_id/member for a workbook from an archive';
COMMENT ON COLUMN meta_workbook.family IS 'hs2 (bulletin by 2-digit chapters, nid 766), hs4 (nid 777), hs10 (nid 778)';
COMMENT ON COLUMN meta_workbook.is_current IS 'FALSE for superseded editions (hidden links / archives); use is_current to avoid double counting';

CREATE TABLE meta_sheet (
    workbook_id VARCHAR NOT NULL,
    sheet       VARCHAR NOT NULL,
    sheet_index INTEGER,
    sheet_type  VARCHAR,
    year        INTEGER,
    title       VARCHAR,
    n_cells     INTEGER,
    parsed_rows INTEGER,
    target_table VARCHAR,
    PRIMARY KEY (workbook_id, sheet)
);
COMMENT ON TABLE meta_sheet IS 'Every sheet of every workbook with its detected type and the table it was loaded into.';
COMMENT ON COLUMN meta_sheet.sheet_type IS 'Detected table type, see docs/files.md';
COMMENT ON COLUMN meta_sheet.n_cells IS 'Non-empty cells (all of them are in raw_xlsx_cell)';
COMMENT ON COLUMN meta_sheet.parsed_rows IS 'Data rows loaded into target_table';

CREATE TABLE meta_db_query (
    nid        INTEGER NOT NULL,
    lang       VARCHAR NOT NULL,
    mode       VARCHAR NOT NULL,
    year       INTEGER NOT NULL,
    query_url  VARCHAR,
    export_url VARCHAR,
    raw_file   VARCHAR,
    fetched_at TIMESTAMP,
    bytes      BIGINT,
    sha256     VARCHAR,
    n_rows     INTEGER,
    PRIMARY KEY (nid, lang, mode, year)
);
COMMENT ON TABLE meta_db_query IS 'Requests made to the web database: one query (all items) per page x language x mode x year, exported through /excelopen.php.';
COMMENT ON COLUMN meta_db_query.mode IS 'annual (years[]=Y) or monthly (year[]=Y, monid[]=1..12)';
COMMENT ON COLUMN meta_db_query.raw_file IS 'Gzipped export stored in the repository data directory';

------------------------------------------------------------------------------
-- dimensions
------------------------------------------------------------------------------
CREATE TABLE dim_flow (
    flow        VARCHAR PRIMARY KEY,
    name_en     VARCHAR,
    name_hy     VARCHAR,
    name_ru     VARCHAR,
    description VARCHAR
);
COMMENT ON TABLE dim_flow IS 'Trade flows.';

CREATE TABLE dim_measure (
    measure     VARCHAR PRIMARY KEY,
    unit_en     VARCHAR,
    unit_hy     VARCHAR,
    description VARCHAR
);
COMMENT ON TABLE dim_measure IS 'Measures (value columns) used in the fact tables; column names of facts are equal to these codes.';

CREATE TABLE dim_data_basis (
    basis       VARCHAR PRIMARY KEY,
    name_en     VARCHAR,
    name_hy     VARCHAR,
    description VARCHAR
);
COMMENT ON TABLE dim_data_basis IS 'Data source basis of the 4-digit tables (total / by goods declarations / by physical persons).';

CREATE TABLE dim_country (
    country_code INTEGER PRIMARY KEY,
    iso_alpha2   VARCHAR,
    name_en      VARCHAR,
    name_hy      VARCHAR,
    name_ru      VARCHAR,
    is_special   BOOLEAN
);
COMMENT ON TABLE dim_country IS 'Partner countries. Codes are ISO 3166-1 numeric as used by Armstat, plus special codes 998 (unknown country), 999 (Nagorno-Karabakh), 1111 (EU countries not specified). Names come from the web database forms (all three languages).';
COMMENT ON COLUMN dim_country.iso_alpha2 IS 'Alpha-2 code from the "Countries" sheets of the 2-digit bulletins (Armstat uses ARTH for code 999)';

CREATE TABLE dim_country_name (
    country_code INTEGER,
    lang         VARCHAR,
    name         VARCHAR,
    source       VARCHAR
);
COMMENT ON TABLE dim_country_name IS 'All spellings of country names seen in the sources (used to resolve names to codes).';

CREATE TABLE dim_country_group (
    group_code VARCHAR PRIMARY KEY,
    name_en    VARCHAR,
    name_hy    VARCHAR
);
COMMENT ON TABLE dim_country_group IS 'Country groups used in the 2-digit bulletins (CIS, EAEU, EU, ...).';

CREATE TABLE dim_hs_section (
    section    VARCHAR PRIMARY KEY,
    section_no INTEGER,
    name_en    VARCHAR,
    name_hy    VARCHAR,
    name_ru    VARCHAR
);
COMMENT ON TABLE dim_hs_section IS 'Sections (I-XXI) of the EAEU CN FEA / Harmonized System. en/hy names from the 10-digit files, ru from the TN VED 2017 document.';

CREATE TABLE dim_hs (
    hs_code     VARCHAR PRIMARY KEY,
    level       INTEGER,
    parent_code VARCHAR,
    section     VARCHAR,
    name_en     VARCHAR,
    name_hy     VARCHAR,
    name_ru     VARCHAR
);
COMMENT ON TABLE dim_hs IS 'Commodity codes of the EAEU CN FEA (TN VED EAEU): chapters (2 digits), headings (4 digits) and 10-digit subheadings, zero padded.';
COMMENT ON COLUMN dim_hs.hs_code IS 'Zero padded code (Excel dropped leading zeros in the sources: 101 -> 0101)';
COMMENT ON COLUMN dim_hs.level IS '2, 4 or 10';
COMMENT ON COLUMN dim_hs.name_ru IS 'Russian names: 4-digit from the web database form, 2-digit from the TN VED 2017 document; not available for 10-digit codes';

CREATE TABLE dim_sitc (
    sitc_code VARCHAR PRIMARY KEY,
    level     INTEGER,
    name_en   VARCHAR,
    name_hy   VARCHAR
);
COMMENT ON TABLE dim_sitc IS 'SITC sections (1 digit) and divisions (2 digits) as used in the 2-digit bulletins.';

CREATE TABLE dim_bec (
    bec_code VARCHAR PRIMARY KEY,
    name_en  VARCHAR,
    name_hy  VARCHAR
);
COMMENT ON TABLE dim_bec IS 'Broad Economic Categories (top level) as used in the 2-digit bulletins; the code is assigned by matching the English label.';

CREATE TABLE dim_unit (
    unit_code  VARCHAR PRIMARY KEY,
    name_en    VARCHAR,
    name_hy    VARCHAR,
    raw_labels VARCHAR[]
);
COMMENT ON TABLE dim_unit IS 'Supplementary units of the 10-digit tables (normalised; raw_labels lists the spellings found).';

------------------------------------------------------------------------------
-- web database facts
------------------------------------------------------------------------------
CREATE TABLE db_country_trade (
    country_code INTEGER NOT NULL,
    year         INTEGER NOT NULL,
    month        INTEGER,
    period_code  INTEGER NOT NULL,
    flow         VARCHAR NOT NULL,
    value_kusd   DOUBLE,
    source_nid   INTEGER,
    PRIMARY KEY (country_code, year, period_code, flow)
);
COMMENT ON TABLE db_country_trade IS 'Web database "External trade by country" (nid 159 until 2016, nid 717 from 2017): trade with each partner country, annual and monthly, thousand US$.';
COMMENT ON COLUMN db_country_trade.month IS '1-12 for monthly values, NULL for the annual value';
COMMENT ON COLUMN db_country_trade.period_code IS 'Code used by the site: 1-12 = month, 13 = year';
COMMENT ON COLUMN db_country_trade.flow IS 'export | import_origin | import_consignment';
COMMENT ON COLUMN db_country_trade.source_nid IS 'Page the value was taken from (159 for years < 2017, 717 otherwise)';

CREATE TABLE db_commodity_trade (
    hs4_code    VARCHAR NOT NULL,
    year        INTEGER NOT NULL,
    month       INTEGER,
    period_code INTEGER NOT NULL,
    flow        VARCHAR NOT NULL,
    weight_ton  DOUBLE,
    value_kusd  DOUBLE,
    PRIMARY KEY (hs4_code, year, period_code, flow)
);
COMMENT ON TABLE db_commodity_trade IS 'Web database "External trade by commodity (4-digit level)" (nid 148): annual values since 1995, monthly since 2007.';
COMMENT ON COLUMN db_commodity_trade.flow IS 'export | import';

CREATE TABLE stg_db_country (
    nid          INTEGER,
    lang         VARCHAR,
    mode         VARCHAR,
    seq          INTEGER,
    country_name VARCHAR,
    country_code INTEGER,
    year         INTEGER,
    period_code  INTEGER,
    export_kusd  DOUBLE,
    import_origin_kusd      DOUBLE,
    import_consignment_kusd DOUBLE
);
COMMENT ON TABLE stg_db_country IS 'Rows of the country database exports exactly as published, for every page (159, 717) and language; country_code is resolved from the name.';

CREATE TABLE stg_db_commodity (
    lang           VARCHAR,
    mode           VARCHAR,
    seq            INTEGER,
    commodity_name VARCHAR,
    code_raw       VARCHAR,
    hs4_code       VARCHAR,
    year           INTEGER,
    period_code    INTEGER,
    export_ton     DOUBLE,
    export_kusd    DOUBLE,
    import_ton     DOUBLE,
    import_kusd    DOUBLE
);
COMMENT ON TABLE stg_db_commodity IS 'Rows of the commodity database exports exactly as published, for every language.';

------------------------------------------------------------------------------
-- file facts
------------------------------------------------------------------------------
CREATE TABLE file_hs4_trade (
    workbook_id VARCHAR NOT NULL,
    year        INTEGER,
    basis       VARCHAR,
    sheet       VARCHAR,
    row_num     INTEGER,
    row_type    VARCHAR,
    hs4_code    VARCHAR,
    flow        VARCHAR,
    weight_ton  DOUBLE,
    value_kusd  DOUBLE
);
COMMENT ON TABLE file_hs4_trade IS 'Files nid 777: annual trade by 4-digit headings, separately for total trade, goods declarations and physical persons.';
COMMENT ON COLUMN file_hs4_trade.row_type IS 'item (a heading) or total (the total row of the sheet)';
COMMENT ON COLUMN file_hs4_trade.basis IS 'See dim_data_basis';

CREATE TABLE file_hs10_trade (
    workbook_id VARCHAR NOT NULL,
    year        INTEGER,
    sheet       VARCHAR,
    row_num     INTEGER,
    is_annex    BOOLEAN,
    section     VARCHAR,
    hs10_code   VARCHAR,
    hs4_code    VARCHAR,
    hs2_code    VARCHAR,
    unit_code   VARCHAR,
    flow        VARCHAR,
    quantity    DOUBLE,
    weight_ton  DOUBLE,
    value_usd   DOUBLE
);
COMMENT ON TABLE file_hs10_trade IS 'Files nid 778: annual trade by 10-digit EAEU CN FEA codes (quantity in supplementary unit, tonnes, US$). is_annex=TRUE rows come from the annex "Transport total" and repeat chapter 87 codes including trade of physical persons.';
COMMENT ON COLUMN file_hs10_trade.is_annex IS 'TRUE for the annex "Transport total" (chapter 87 incl. trade of physical persons); exclude when summing';

CREATE TABLE file_hs10_aggregate (
    workbook_id VARCHAR NOT NULL,
    year        INTEGER,
    sheet       VARCHAR,
    row_num     INTEGER,
    is_annex    BOOLEAN,
    section     VARCHAR,
    level       VARCHAR,
    hs_code     VARCHAR,
    code_prefix VARCHAR,
    name_hy     VARCHAR,
    name_en     VARCHAR,
    n_items     INTEGER,
    flow        VARCHAR,
    weight_ton  DOUBLE,
    value_usd   DOUBLE
);
COMMENT ON TABLE file_hs10_aggregate IS 'Subtotal rows of the 10-digit files: totals, sections, groups (chapters) and subgroups (headings), with their bilingual names.';
COMMENT ON COLUMN file_hs10_aggregate.level IS 'total_with_physical_persons | total_without_physical_persons | section | group | subgroup';
COMMENT ON COLUMN file_hs10_aggregate.hs_code IS 'Derived code: 2 digits for a group, 4 digits for a subgroup (common prefix of the codes under the row)';

CREATE TABLE file_country_trade (
    workbook_id VARCHAR NOT NULL,
    year        INTEGER,
    row_num     INTEGER,
    row_type    VARCHAR,
    country_code INTEGER,
    group_code  VARCHAR,
    label_hy    VARCHAR,
    label_en    VARCHAR,
    flow        VARCHAR,
    value_kusd  DOUBLE
);
COMMENT ON TABLE file_country_trade IS 'Sheet "Countries" of the 2-digit bulletins: trade by partner country and country group for the last 4 years, thousand US$.';
COMMENT ON COLUMN file_country_trade.row_type IS 'country | group (aggregate of a country group, see group_code)';
COMMENT ON COLUMN file_country_trade.group_code IS 'For row_type=country: the group heading the country is listed under; for row_type=group: the group itself';

CREATE TABLE file_sitc_trade (
    workbook_id VARCHAR NOT NULL,
    year        INTEGER,
    sitc_level  INTEGER,
    row_type    VARCHAR,
    sitc_code   VARCHAR,
    flow        VARCHAR,
    weight_ton  DOUBLE,
    value_kusd  DOUBLE
);
COMMENT ON TABLE file_sitc_trade IS 'Sheets SITC-1 / SITC-2 of the 2-digit bulletins: trade by SITC sections and divisions, last 4 years.';

CREATE TABLE file_bec_trade (
    workbook_id VARCHAR NOT NULL,
    year        INTEGER,
    row_type    VARCHAR,
    bec_code    VARCHAR,
    flow        VARCHAR,
    value_musd  DOUBLE
);
COMMENT ON TABLE file_bec_trade IS 'Sheet BEC-1 of the 2-digit bulletins: trade by Broad Economic Categories, last 4 years, million US$.';

CREATE TABLE file_hs2_trade (
    workbook_id VARCHAR NOT NULL,
    year        INTEGER,
    row_type    VARCHAR,
    hs_code     VARCHAR,
    flow        VARCHAR,
    value_kusd  DOUBLE,
    share_pct   DOUBLE
);
COMMENT ON TABLE file_hs2_trade IS 'Sheets By_Groups and Groups_% of the 2-digit bulletins: trade by HS chapters and sections, last 4 years.';
COMMENT ON COLUMN file_hs2_trade.row_type IS 'chapter (hs_code = 2 digits) | section (hs_code = roman numeral) | total';

CREATE TABLE file_hs2_partner_trade (
    workbook_id   VARCHAR NOT NULL,
    year          INTEGER,
    sheet         VARCHAR,
    row_num       INTEGER,
    partner_kind  VARCHAR,
    group_code    VARCHAR,
    country_code  INTEGER,
    partner_label VARCHAR,
    row_type      VARCHAR,
    hs2_code      VARCHAR,
    flow          VARCHAR,
    weight_ton    DOUBLE,
    value_mln_amd DOUBLE,
    value_kusd    DOUBLE
);
COMMENT ON TABLE file_hs2_partner_trade IS 'Sheets *_groups / *_countries of the 2-digit bulletins: trade by HS chapter with the world, a country group or a single country, for the bulletin year (tonnes, million AMD, thousand US$).';
COMMENT ON COLUMN file_hs2_partner_trade.partner_kind IS 'group (group_code is set) | country (country_code is set)';
COMMENT ON COLUMN file_hs2_partner_trade.partner_label IS 'Block heading as printed, e.g. "ԻՏԱԼԻԱ - ITALY"';
COMMENT ON COLUMN file_hs2_partner_trade.row_type IS 'chapter | total';

CREATE TABLE file_hs2_country_trade (
    workbook_id  VARCHAR NOT NULL,
    year         INTEGER,
    row_num      INTEGER,
    row_type     VARCHAR,
    hs2_code     VARCHAR,
    country_code INTEGER,
    flow         VARCHAR,
    weight_ton   DOUBLE,
    value_kusd   DOUBLE
);
COMMENT ON TABLE file_hs2_country_trade IS 'Sheet "by Commodity Groups" of the 2-digit bulletins: each HS chapter broken down by partner country, bulletin year.';
COMMENT ON COLUMN file_hs2_country_trade.row_type IS 'country | chapter (chapter total) | total (all chapters)';

CREATE TABLE file_humanitarian_aid (
    workbook_id  VARCHAR NOT NULL,
    year         INTEGER,
    row_num      INTEGER,
    row_type     VARCHAR,
    hs2_code     VARCHAR,
    country_code INTEGER,
    weight_ton   DOUBLE,
    value_usd    DOUBLE
);
COMMENT ON TABLE file_humanitarian_aid IS 'Sheet "Hum-Aid" of the 2-digit bulletins: humanitarian aid received by Armenia by HS chapter and donor country. The value column is labelled "US $" in the source (magnitudes suggest thousand US$, see docs).';

CREATE TABLE raw_xlsx_cell (
    workbook_id VARCHAR NOT NULL,
    sheet       VARCHAR NOT NULL,
    row_num     INTEGER NOT NULL,
    col_num     INTEGER NOT NULL,
    cell_ref    VARCHAR,
    value_text  VARCHAR,
    value_num   DOUBLE,
    formula     VARCHAR
);
COMMENT ON TABLE raw_xlsx_cell IS 'Lossless dump of every non-empty cell of every workbook (cached values; formula text where present).';
