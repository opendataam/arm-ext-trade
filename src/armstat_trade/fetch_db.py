"""Step 3: download the content of the web database (query interface).

The query pages (nid=148 commodities, nid=159/717 countries) show results in
pages of 25 rows. The site also offers "Download Excel file"
(``/excelopen.php``) which returns the *complete* result of the last query of
the PHP session as an HTML table with full precision. We therefore, for every
page x language x year:

1. open a fresh session and request the query page with all items
   (``thid[]=0``) and either ``years[]=<year>`` (annual values) or
   ``year[]=<year>`` + ``monid[]=1..12`` (monthly values);
2. request ``/excelopen.php`` with the query page as ``Referer``;
3. store the export gzipped as ``data/raw/db/nid<nid>/<lang>/<mode>_<year>.xls.gz``.

A log of all requests is kept in ``data/catalog/db_queries.json``.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import time

from . import config
from .http import Client
from .parsers import db_export
from .utils import read_gz_text, read_json, sha256_bytes, utc_now, write_gz, write_json

log = logging.getLogger(__name__)

DB_NIDS = (148, 159, 717)


def query_url(lang: str, nid: int, mode: str, year: int) -> str:
    params: list[tuple[str, str | int]] = [("nid", nid), ("thid[]", 0)]
    if mode == "annual":
        params.append(("years[]", year))
    else:
        params.append(("year[]", year))
        params += [("monid[]", m) for m in range(1, 13)]
    params.append(("submit", "Search"))
    return f"{config.BASE_URL}/{config.LANGS[lang]}/?{urlencode(params)}"


def raw_path(nid: int, lang: str, mode: str, year: int):
    return config.DB_RAW_DIR / f"nid{nid}" / lang / f"{mode}_{year}.xls.gz"


def available_years(nid: int, lang: str = "en") -> dict[str, list[int]]:
    opts = read_json(config.CATALOG_DIR / "db_options" / f"{nid}_{lang}.json")
    if not opts:
        raise SystemExit("db options not found: run `armstat-trade catalog` first")
    return {
        "annual": sorted(int(o["value"]) for o in opts["years"]),
        "monthly": sorted(int(o["value"]) for o in opts["year"]),
    }


MAX_ATTEMPTS = 6


def fetch_one(client: Client, nid: int, lang: str, mode: str, year: int) -> dict:
    """Run one query and download its export; retry until the export matches the query."""
    url = query_url(lang, nid, mode, year)
    error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        client.reset()
        page = client.get(url).text  # runs the query; the server remembers it for the export
        expected = db_export.expected_rows(page)
        data = client.get(f"{config.BASE_URL}/excelopen.php", referer=url, no_delay=True).content
        error = db_export.validate(data.decode("utf-8", errors="replace"), nid, mode, year, expected)
        if error is None:
            break
        log.warning("export of %s rejected (%s), attempt %d", url, error, attempt)
        time.sleep(10 * attempt)
    else:
        raise RuntimeError(f"could not get a valid export for {url}: {error}")
    path = raw_path(nid, lang, mode, year)
    write_gz(path, data)
    return {
        "nid": nid,
        "lang": lang,
        "mode": mode,
        "year": year,
        "query_url": url,
        "export_url": f"{config.BASE_URL}/excelopen.php",
        "file": str(path.relative_to(config.ROOT)),
        "fetched_at": utc_now(),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "rows": data.count(b"<tr") - 1,
        "expected_rows": list(expected),  # range announced by the pager of the query page
    }


def fetch(
    nids: tuple[int, ...] = DB_NIDS,
    langs: tuple[str, ...] = tuple(config.LANGS),
    modes: tuple[str, ...] = ("annual", "monthly"),
    refresh_last: int = 2,
    force: bool = False,
    validate_existing: bool = True,
    client: Client | None = None,
) -> list[dict]:
    """Fetch all (nid, lang, mode, year) combinations.

    Existing files are skipped unless ``force`` or the year is among the
    ``refresh_last`` most recent years (those are still being revised), or
    the stored export fails validation (``validate_existing``).
    """
    client = client or Client()
    log_path = config.CATALOG_DIR / "db_queries.json"
    entries = {(e["nid"], e["lang"], e["mode"], e["year"]): e for e in read_json(log_path, [])}
    kept = fetched = 0
    for nid in nids:
        years = available_years(nid)
        for mode in modes:
            ys = years[mode]
            recent = set(ys[-refresh_last:]) if refresh_last else set()
            for year in ys:
                for lang in langs:
                    path = raw_path(nid, lang, mode, year)
                    if path.exists() and not force and year not in recent:
                        exp = entries.get((nid, lang, mode, year), {}).get("expected_rows")
                        err = (db_export.validate(read_gz_text(path), nid, mode, year, tuple(exp) if exp else None)
                               if validate_existing else None)
                        if err is None:
                            kept += 1
                            continue
                        log.warning("existing export %s is invalid (%s): refetching", path, err)
                    log.info("db nid=%s lang=%s %s %s", nid, lang, mode, year)
                    entries[(nid, lang, mode, year)] = fetch_one(client, nid, lang, mode, year)
                    fetched += 1
                    write_json(log_path, sorted(entries.values(), key=lambda e: (e["nid"], e["mode"], e["year"], e["lang"])))
    log.info("web database: %d exports kept (valid), %d fetched", kept, fetched)
    return list(entries.values())
