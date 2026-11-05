-- Convenience views (wide layout, names joined). Created after the tables are loaded.

-- Web database: trade by country, wide by flow ---------------------------------
CREATE VIEW v_db_country_annual AS
SELECT t.year, t.country_code, c.iso_alpha2, c.name_en, c.name_hy, c.name_ru,
       max(value_kusd) FILTER (WHERE flow = 'export')             AS export_kusd,
       max(value_kusd) FILTER (WHERE flow = 'import_origin')      AS import_origin_kusd,
       max(value_kusd) FILTER (WHERE flow = 'import_consignment') AS import_consignment_kusd
FROM db_country_trade t LEFT JOIN dim_country c USING (country_code)
WHERE t.month IS NULL
GROUP BY ALL;
COMMENT ON VIEW v_db_country_annual IS 'Annual trade by partner country from the web database, one row per country and year (thousand US$).';

CREATE VIEW v_db_country_monthly AS
SELECT t.year, t.month, make_date(t.year, t.month, 1) AS period_start, t.country_code, c.iso_alpha2,
       c.name_en, c.name_hy, c.name_ru,
       max(value_kusd) FILTER (WHERE flow = 'export')             AS export_kusd,
       max(value_kusd) FILTER (WHERE flow = 'import_origin')      AS import_origin_kusd,
       max(value_kusd) FILTER (WHERE flow = 'import_consignment') AS import_consignment_kusd
FROM db_country_trade t LEFT JOIN dim_country c USING (country_code)
WHERE t.month IS NOT NULL
GROUP BY ALL;
COMMENT ON VIEW v_db_country_monthly IS 'Monthly trade by partner country from the web database (thousand US$; monthly values, not cumulative).';

-- Web database: trade by 4-digit commodity, wide by flow --------------------------
CREATE VIEW v_db_commodity_annual AS
SELECT t.year, t.hs4_code, h.name_en, h.name_hy, h.name_ru, h.section,
       max(weight_ton) FILTER (WHERE flow = 'export') AS export_ton,
       max(value_kusd) FILTER (WHERE flow = 'export') AS export_kusd,
       max(weight_ton) FILTER (WHERE flow = 'import') AS import_ton,
       max(value_kusd) FILTER (WHERE flow = 'import') AS import_kusd
FROM db_commodity_trade t LEFT JOIN dim_hs h ON h.hs_code = t.hs4_code
WHERE t.month IS NULL
GROUP BY ALL;
COMMENT ON VIEW v_db_commodity_annual IS 'Annual trade by 4-digit heading from the web database (tonnes, thousand US$).';

CREATE VIEW v_db_commodity_monthly AS
SELECT t.year, t.month, make_date(t.year, t.month, 1) AS period_start, t.hs4_code, h.name_en, h.name_hy, h.name_ru,
       max(weight_ton) FILTER (WHERE flow = 'export') AS export_ton,
       max(value_kusd) FILTER (WHERE flow = 'export') AS export_kusd,
       max(weight_ton) FILTER (WHERE flow = 'import') AS import_ton,
       max(value_kusd) FILTER (WHERE flow = 'import') AS import_kusd
FROM db_commodity_trade t LEFT JOIN dim_hs h ON h.hs_code = t.hs4_code
WHERE t.month IS NOT NULL
GROUP BY ALL;
COMMENT ON VIEW v_db_commodity_monthly IS 'Monthly trade by 4-digit heading from the web database (tonnes, thousand US$).';

-- Files: current editions -------------------------------------------------------
CREATE VIEW v_file_hs10_current AS
SELECT t.year, t.hs10_code, t.hs4_code, h4.name_en AS hs4_name_en, h4.name_hy AS hs4_name_hy, h4.name_ru AS hs4_name_ru,
       t.hs2_code, t.section, t.unit_code, u.name_en AS unit_en, u.name_hy AS unit_hy, t.flow,
       t.quantity, t.weight_ton, t.value_usd, t.workbook_id
FROM file_hs10_trade t
JOIN meta_workbook w USING (workbook_id)
LEFT JOIN dim_hs h4 ON h4.hs_code = t.hs4_code
LEFT JOIN dim_unit u USING (unit_code)
WHERE w.is_current AND NOT t.is_annex;
COMMENT ON VIEW v_file_hs10_current IS '10-digit trade from the current edition of each year (sections only, the transport annex is excluded to avoid double counting).';

CREATE VIEW v_file_hs4_current AS
SELECT t.year, t.basis, t.hs4_code, h.name_en, h.name_hy, h.name_ru, t.flow, t.weight_ton, t.value_kusd, t.workbook_id
FROM file_hs4_trade t
JOIN meta_workbook w USING (workbook_id)
LEFT JOIN dim_hs h ON h.hs_code = t.hs4_code
WHERE w.is_current AND t.row_type = 'item';
COMMENT ON VIEW v_file_hs4_current IS '4-digit trade from the current edition of each year, by data basis (total / declarations / physical persons).';

CREATE VIEW v_file_hs2_partner_current AS
SELECT t.year, t.partner_kind, t.group_code, g.name_en AS group_name_en, t.country_code, c.name_en AS country_name_en,
       c.name_hy AS country_name_hy, c.name_ru AS country_name_ru, t.hs2_code, h.name_en AS hs2_name_en, h.name_hy AS hs2_name_hy,
       h.name_ru AS hs2_name_ru, t.flow, t.weight_ton, t.value_mln_amd, t.value_kusd, t.workbook_id, t.sheet
FROM file_hs2_partner_trade t
JOIN meta_workbook w USING (workbook_id)
LEFT JOIN dim_country_group g USING (group_code)
LEFT JOIN dim_country c USING (country_code)
LEFT JOIN dim_hs h ON h.hs_code = t.hs2_code
WHERE w.is_current AND t.row_type = 'chapter';
COMMENT ON VIEW v_file_hs2_partner_current IS 'Trade by HS chapter and partner (world, group or country) from the current 2-digit bulletins.';

-- Files: multi-year tables, latest available edition of every year ----------------
-- The 2-digit bulletins repeat the last 4 years; later bulletins contain revised data.
CREATE VIEW v_file_country_trade_latest AS
SELECT t.* EXCLUDE (rn) FROM (
    SELECT t.*, w.year AS edition_year,
           dense_rank() OVER (PARTITION BY t.year ORDER BY w.year DESC, t.workbook_id DESC) AS rn
    FROM file_country_trade t JOIN meta_workbook w USING (workbook_id)
    WHERE w.is_current
) t WHERE rn = 1;
COMMENT ON VIEW v_file_country_trade_latest IS 'Sheet "Countries": for every year the values of the most recent bulletin containing that year.';

CREATE VIEW v_file_hs2_trade_latest AS
SELECT t.* EXCLUDE (rn) FROM (
    SELECT t.*, w.year AS edition_year,
           dense_rank() OVER (PARTITION BY t.year ORDER BY w.year DESC, t.workbook_id DESC) AS rn
    FROM file_hs2_trade t JOIN meta_workbook w USING (workbook_id)
    WHERE w.is_current
) t WHERE rn = 1;
COMMENT ON VIEW v_file_hs2_trade_latest IS 'Sheets By_Groups / Groups_%: latest edition for every year.';

CREATE VIEW v_file_sitc_trade_latest AS
SELECT t.* EXCLUDE (rn) FROM (
    SELECT t.*, w.year AS edition_year,
           dense_rank() OVER (PARTITION BY t.year ORDER BY w.year DESC, t.workbook_id DESC) AS rn
    FROM file_sitc_trade t JOIN meta_workbook w USING (workbook_id)
    WHERE w.is_current
) t WHERE rn = 1;
COMMENT ON VIEW v_file_sitc_trade_latest IS 'Sheets SITC-1 / SITC-2: latest edition for every year.';

CREATE VIEW v_file_bec_trade_latest AS
SELECT t.* EXCLUDE (rn) FROM (
    SELECT t.*, w.year AS edition_year,
           dense_rank() OVER (PARTITION BY t.year ORDER BY w.year DESC, t.workbook_id DESC) AS rn
    FROM file_bec_trade t JOIN meta_workbook w USING (workbook_id)
    WHERE w.is_current
) t WHERE rn = 1;
COMMENT ON VIEW v_file_bec_trade_latest IS 'Sheet BEC-1: latest edition for every year.';

-- Catalogue of everything that was loaded ----------------------------------------
CREATE VIEW v_sources AS
SELECT 'file' AS source_kind, f.file_id AS source_id, f.nid, f.nomenclature_level, f.year, f.is_current,
       coalesce(f.title_en, '(hidden link)') AS title_en, f.url
FROM meta_file f
UNION ALL
SELECT 'web_db', q.nid || '/' || q.lang || '/' || q.mode || '/' || q.year, q.nid, NULL, q.year, TRUE,
       q.mode || ' query, all items', q.query_url
FROM meta_db_query q;
COMMENT ON VIEW v_sources IS 'Every source file and web database request used to build the database.';
