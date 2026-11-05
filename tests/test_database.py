"""Integration tests of the built database (skipped if it has not been built)."""

import duckdb
import pytest

from armstat_trade import config

pytestmark = pytest.mark.skipif(not config.DUCKDB_PATH.exists(), reason="database not built (make build)")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_core_tables_not_empty(con):
    for t in ("db_country_trade", "db_commodity_trade", "file_hs4_trade", "file_hs10_trade",
              "file_country_trade", "file_hs2_partner_trade", "dim_country", "dim_hs", "raw_xlsx_cell"):
        assert one(con, f"SELECT count(*) FROM {t}") > 0, t


def test_all_languages_present(con):
    assert one(con, "SELECT count(DISTINCT lang) FROM stg_db_commodity") == 3
    assert one(con, "SELECT count(DISTINCT lang) FROM stg_db_country") == 3
    assert one(con, "SELECT count(*) FROM dim_country WHERE name_en IS NULL OR name_hy IS NULL OR name_ru IS NULL") == 0


def test_country_db_complete(con):
    # every country row of the web database has a resolved code
    assert one(con, "SELECT count(*) FROM stg_db_country WHERE country_code IS NULL") == 0
    assert one(con, "SELECT min(year) FROM db_country_trade") == 1995


def test_primary_keys_unique(con):
    assert one(con, """SELECT count(*) FROM (SELECT country_code, year, period_code, flow, count(*) n
                       FROM db_country_trade GROUP BY ALL HAVING n > 1)""") == 0


def test_known_value(con):
    # Exports to Russia in 2024 (web database, thousand US$), checked on the site
    v = one(con, "SELECT export_kusd FROM v_db_country_annual WHERE country_code = 643 AND year = 2024")
    assert abs(v - 3182763.1) < 1


def test_qc_no_warnings_on_web_db(con):
    status = dict(con.execute("SELECT check_name, status FROM qc_summary").fetchall())
    assert status["db_country_159_vs_717"] == "OK"
    assert status["db_language_consistency"] == "OK"
