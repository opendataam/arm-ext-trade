-- Data quality checks, materialised as qc_* tables by the build.
-- Each check writes rows to qc_summary (check, status, details).

CREATE TABLE qc_summary (check_name VARCHAR, status VARCHAR, n_issues BIGINT, details VARCHAR);
COMMENT ON TABLE qc_summary IS 'Result of all data quality checks (OK / WARN / INFO).';

-- 1. Country database: pages 159 and 717 return the same backend data for overlapping years
CREATE TABLE qc_db_country_overlap AS
SELECT a.year, a.period_code, a.country_code,
       a.export_kusd AS export_159, b.export_kusd AS export_717,
       a.import_origin_kusd AS import_origin_159, b.import_origin_kusd AS import_origin_717,
       a.import_consignment_kusd AS import_consignment_159, b.import_consignment_kusd AS import_consignment_717
FROM stg_db_country a
JOIN stg_db_country b USING (lang, mode, year, period_code, country_code)
WHERE a.nid = 159 AND b.nid = 717 AND a.lang = 'en'
  AND (a.export_kusd IS DISTINCT FROM b.export_kusd
       OR a.import_origin_kusd IS DISTINCT FROM b.import_origin_kusd
       OR a.import_consignment_kusd IS DISTINCT FROM b.import_consignment_kusd);
COMMENT ON TABLE qc_db_country_overlap IS 'Differences between nid 159 and nid 717 for the same country / year / period (expected: none).';
INSERT INTO qc_summary
SELECT 'db_country_159_vs_717', CASE WHEN count(*) = 0 THEN 'OK' ELSE 'WARN' END, count(*),
       'rows that differ between the two country pages in overlapping years'
FROM qc_db_country_overlap;

-- 2. The three languages return the same numbers
CREATE TABLE qc_db_language_consistency AS
WITH c AS (
    SELECT 'country' AS db, nid, mode, year, lang, count(*) AS n_rows,
           round(sum(coalesce(export_kusd, 0)), 3) AS s1, round(sum(coalesce(import_origin_kusd, 0)), 3) AS s2
    FROM stg_db_country GROUP BY ALL
    UNION ALL
    SELECT 'commodity', 148, mode, year, lang, count(*),
           round(sum(coalesce(export_kusd, 0)), 3), round(sum(coalesce(import_kusd, 0)), 3)
    FROM stg_db_commodity GROUP BY ALL
)
SELECT db, nid, mode, year, count(DISTINCT lang) AS n_langs,
       count(DISTINCT n_rows) AS distinct_row_counts, count(DISTINCT s1) AS distinct_sum1, count(DISTINCT s2) AS distinct_sum2,
       list(lang || ':' || n_rows ORDER BY lang) AS rows_by_lang
FROM c GROUP BY ALL;
COMMENT ON TABLE qc_db_language_consistency IS 'Row counts and sums of the web database exports per language (expected: identical across en/hy/ru).';
INSERT INTO qc_summary
SELECT 'db_language_consistency',
       CASE WHEN count(*) FILTER (WHERE n_langs < 3 OR distinct_row_counts > 1 OR distinct_sum1 > 1 OR distinct_sum2 > 1) = 0 THEN 'OK' ELSE 'WARN' END,
       count(*) FILTER (WHERE n_langs < 3 OR distinct_row_counts > 1 OR distinct_sum1 > 1 OR distinct_sum2 > 1),
       'queries where languages differ in row count or totals'
FROM qc_db_language_consistency;

-- 3. Unresolved country names
INSERT INTO qc_summary
SELECT 'country_names_resolved', CASE WHEN count(*) = 0 THEN 'OK' ELSE 'WARN' END, count(*),
       'country labels that could not be matched to dim_country (see qc_unresolved_country)'
FROM qc_unresolved_country;
INSERT INTO qc_summary
SELECT 'db_country_rows_without_code', CASE WHEN count(*) = 0 THEN 'OK' ELSE 'WARN' END, count(*),
       'web database rows whose country name was not resolved'
FROM stg_db_country WHERE country_code IS NULL;

-- 4. Monthly sums vs annual values in the web database
CREATE TABLE qc_db_monthly_vs_annual AS
WITH m AS (
    SELECT 'country' AS db, year, flow, sum(value_kusd) AS monthly_sum, count(DISTINCT month) AS n_months
    FROM db_country_trade WHERE month IS NOT NULL GROUP BY ALL
    UNION ALL
    SELECT 'commodity', year, flow, sum(value_kusd), count(DISTINCT month)
    FROM db_commodity_trade WHERE month IS NOT NULL GROUP BY ALL
), a AS (
    SELECT 'country' AS db, year, flow, sum(value_kusd) AS annual FROM db_country_trade WHERE month IS NULL GROUP BY ALL
    UNION ALL
    SELECT 'commodity', year, flow, sum(value_kusd) FROM db_commodity_trade WHERE month IS NULL GROUP BY ALL
)
SELECT db, year, flow, n_months, round(annual, 1) AS annual_kusd, round(monthly_sum, 1) AS sum_of_months_kusd,
       round(100 * (monthly_sum - annual) / nullif(annual, 0), 3) AS diff_pct
FROM a JOIN m USING (db, year, flow)
ORDER BY db, flow, year;
COMMENT ON TABLE qc_db_monthly_vs_annual IS 'Sum of monthly values vs the annual value in the web database (differences come from revisions not carried into monthly data).';
INSERT INTO qc_summary
SELECT 'db_monthly_vs_annual', 'INFO', count(*) FILTER (WHERE n_months = 12 AND abs(diff_pct) > 1),
       'complete years where the sum of months differs from the annual value by more than 1%'
FROM qc_db_monthly_vs_annual;

-- 5. Totals of the files vs the sum of their items
CREATE TABLE qc_file_totals AS
SELECT 'hs4' AS family, t.workbook_id, t.basis AS part, t.flow,
       max(t.value_kusd) FILTER (WHERE row_type = 'total') AS total_row,
       sum(t.value_kusd) FILTER (WHERE row_type = 'item') AS sum_items,
       'thousand US$' AS unit
FROM file_hs4_trade t GROUP BY ALL
UNION ALL
SELECT 'hs10', a.workbook_id, a.section, a.flow, a.value_usd, s.sum_items, 'US$'
FROM file_hs10_aggregate a
JOIN (SELECT workbook_id, section, flow, sum(value_usd) AS sum_items FROM file_hs10_trade WHERE NOT is_annex GROUP BY ALL) s
  USING (workbook_id, section, flow)
WHERE a.level = 'section' AND NOT a.is_annex;
COMMENT ON TABLE qc_file_totals IS 'Published total rows vs the sum of the item rows (hs4: per sheet; hs10: per section).';
INSERT INTO qc_summary
SELECT 'file_totals_vs_items', 'INFO', count(*) FILTER (WHERE abs(total_row - sum_items) > greatest(1, 0.001 * abs(total_row))),
       'sheets/sections where the published total differs from the sum of items by more than 0.1%'
FROM qc_file_totals;

-- 6. Files vs web database: annual 4-digit totals (current editions, basis = total)
CREATE TABLE qc_file_vs_db_hs4 AS
WITH f AS (
    SELECT year, flow, sum(value_kusd) AS file_kusd FROM v_file_hs4_current WHERE basis = 'total' GROUP BY ALL
), d AS (
    SELECT year, flow, sum(value_kusd) AS db_kusd FROM db_commodity_trade WHERE month IS NULL GROUP BY ALL
)
SELECT year, flow, round(file_kusd, 1) AS file_kusd, round(db_kusd, 1) AS db_kusd,
       round(100 * (file_kusd - db_kusd) / nullif(db_kusd, 0), 3) AS diff_pct
FROM f JOIN d USING (year, flow) ORDER BY year, flow;
COMMENT ON TABLE qc_file_vs_db_hs4 IS 'Annual totals of the 4-digit files vs the web database (differences reflect revisions after the file was published).';
INSERT INTO qc_summary
SELECT 'file_vs_db_hs4', 'INFO', count(*) FILTER (WHERE abs(diff_pct) > 0.5),
       'years/flows where 4-digit files and the web database differ by more than 0.5%'
FROM qc_file_vs_db_hs4;

-- 7. Rows of the parsed fact tables without a code in the dimension
INSERT INTO qc_summary
SELECT 'hs_codes_in_dim', CASE WHEN count(*) = 0 THEN 'OK' ELSE 'WARN' END, count(*),
       'distinct hs codes in fact tables missing from dim_hs'
FROM (
    SELECT hs4_code AS c FROM db_commodity_trade UNION SELECT hs4_code FROM file_hs4_trade
    UNION SELECT hs10_code FROM file_hs10_trade UNION SELECT hs2_code FROM file_hs2_partner_trade
) x WHERE c IS NOT NULL AND c NOT IN (SELECT hs_code FROM dim_hs);
INSERT INTO qc_summary
SELECT 'hs4_rows_without_code', CASE WHEN count(*) = 0 THEN 'OK' ELSE 'WARN' END, count(*),
       'item rows of the 4-digit files with an empty code cell'
FROM file_hs4_trade WHERE row_type = 'item' AND hs4_code IS NULL;
INSERT INTO qc_summary
SELECT 'partner_rows_without_country', CASE WHEN count(*) = 0 THEN 'OK' ELSE 'WARN' END, count(*),
       'rows of country blocks in the 2-digit bulletins without a resolved country code'
FROM file_hs2_partner_trade WHERE partner_kind = 'country' AND country_code IS NULL;
