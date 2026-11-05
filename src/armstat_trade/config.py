"""Project-wide constants: paths, source pages, languages, HTTP settings."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PAGES_DIR = RAW_DIR / "pages"          # HTML of the site pages, per language
FILES_DIR = RAW_DIR / "files"          # downloaded xlsx / 7z files
EXTRACTED_DIR = FILES_DIR / "extracted"  # content of 7z archives
DB_RAW_DIR = RAW_DIR / "db"            # Excel exports of the web database queries
CATALOG_DIR = DATA_DIR / "catalog"     # small JSON manifests (committed to git)
SQL_DIR = ROOT / "sql"
DUCKDB_PATH = DATA_DIR / "armstat_trade.duckdb"
RELEASE_DIR = DATA_DIR / "release"     # packed data snapshots (not in git)

# GitHub repository whose releases carry the data snapshots (override: env ARMSTAT_TRADE_REPO)
GITHUB_REPO = "opendataam/arm-ext-trade"

BASE_URL = "https://armstat.am"

# ISO 639-1 language code -> path segment used by armstat.am
LANGS: dict[str, str] = {"en": "en", "hy": "am", "ru": "ru"}

# Section "External trade database" and its sub pages.
INDEX_NID = 160
PAGES: dict[int, dict] = {
    160: {"kind": "index", "title": "External trade database"},
    148: {"kind": "db_commodity", "title": "External trade database by HS 4-digit commodity"},
    159: {"kind": "db_country", "title": "External trade database by country (until 2016)"},
    717: {"kind": "db_country", "title": "External trade database by country (2017+)"},
    766: {"kind": "files", "level": 2, "title": "Foreign trade by EAEU CN FEA, 2-digit level"},
    777: {"kind": "files", "level": 4, "title": "Foreign trade by EAEU CN FEA, 4-digit level"},
    778: {"kind": "files", "level": 10, "title": "Foreign trade by EAEU CN FEA, 10-digit level"},
}

# Web database: which page serves which years (the country database 159/717 is one
# backend table; 159 is used for years < 2017 and 717 for 2017+, see docs/web_database.md).
COUNTRY_DB_SPLIT_YEAR = 2017

# Period code used by the web database for annual values.
ANNUAL_PERIOD_CODE = 13

USER_AGENT = "armstat-trade-collector/0.1 (open data research; python-requests)"
HTTP_TIMEOUT = 180
HTTP_RETRIES = 4
HTTP_DELAY = 1.0  # seconds between requests (be polite)
