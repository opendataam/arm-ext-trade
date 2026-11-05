"""Data snapshots published as GitHub release assets.

The database and the raw data are too large and too volatile for git history,
so every data collection is published as a GitHub release of the repository:

* tag ``data-YYYY-MM-DD`` (date of the data collection), pointing to the code
  commit the database was built with;
* assets with stable names (so ``releases/latest/download/<name>`` always works):

  ===============================  ============================================
  ``armstat_trade.duckdb.xz``      the DuckDB database
  ``armstat_trade-parquet.zip``    every table and view as Parquet + data dictionary
  ``armstat_trade-raw.tar.xz``     ``raw/`` (pages, files, web database exports) and ``catalog/``
  ``SHA256SUMS``                   checksums of the assets
  ===============================  ============================================

Commands: ``release`` (pack + ``gh release create``), ``download`` (fetch,
verify checksums, unpack into ``data/``). Compression is xz (standard library),
so downloading needs no extra tools.
"""

from __future__ import annotations

import hashlib
import logging
import lzma
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

import duckdb
import requests

from . import config

log = logging.getLogger(__name__)

ASSETS = {
    "db": "armstat_trade.duckdb.xz",
    "parquet": "armstat_trade-parquet.zip",
    "raw": "armstat_trade-raw.tar.xz",
}
SUMS = "SHA256SUMS"
NOTES = "RELEASE_NOTES.md"
PARQUET_DIR = config.DATA_DIR / "parquet"


def repo() -> str:
    return os.environ.get("ARMSTAT_TRADE_REPO", config.GITHUB_REPO)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.ROOT, check=True, capture_output=True, text=True).stdout.strip()


# ---------------------------------------------------------------------------
# packing
# ---------------------------------------------------------------------------

def snapshot_date(con: duckdb.DuckDBPyConnection) -> str:
    """Date of the data collection: the last web database request."""
    d = con.execute("SELECT max(fetched_at)::DATE::VARCHAR FROM meta_db_query").fetchone()[0]
    if d is None:
        d = con.execute("SELECT max(fetched_at)::DATE::VARCHAR FROM meta_page").fetchone()[0]
    return d


def _export_parquet(con: duckdb.DuckDBPyConnection, out: Path) -> Path:
    """Every table and view as <name>.parquet (explicit COPY: EXPORT DATABASE mangles names)."""
    names = [r[0] for r in con.execute("""
        SELECT table_name FROM duckdb_tables() WHERE schema_name = 'main'
        UNION ALL
        SELECT view_name FROM duckdb_views() WHERE schema_name = 'main' AND NOT internal
        ORDER BY 1""").fetchall()]
    zpath = out / ASSETS["parquet"]
    with tempfile.TemporaryDirectory() as tmp:
        for name in names:
            dst = Path(tmp) / f"{name}.parquet"
            con.execute(f"COPY (SELECT * FROM \"{name}\") TO '{dst}' (FORMAT parquet, COMPRESSION zstd)")
        with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED) as z:  # parquet is already compressed
            for name in names:
                z.write(Path(tmp) / f"{name}.parquet", f"parquet/{name}.parquet")
            for doc in ("data_dictionary.md", "database.md"):
                p = config.ROOT / "docs" / doc
                if p.exists():
                    z.write(p, f"parquet/{doc}")
    log.info("parquet: %d tables and views -> %s", len(names), zpath)
    return zpath


def _notes(con, tag: str, date: str, commit: str, out: Path) -> Path:
    def table(sql: str) -> str:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        fmt = lambda v: f"{v:,}".replace(",", " ") if isinstance(v, int) else ("" if v is None else str(v))  # noqa: E731
        return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
                         + ["| " + " | ".join(fmt(v) for v in r) + " |" for r in rows])

    coverage = table("""
        SELECT источник, годы, месяцы, объём FROM (
            SELECT 0 AS ord, 'веб-база: по странам' AS источник, min(year) || '–' || max(year) AS годы,
                   min(year) FILTER (WHERE month IS NOT NULL) || '–' || max(year) AS месяцы,
                   format('{:,} строк', count(*)) AS объём
            FROM db_country_trade
            UNION ALL
            SELECT 1, 'веб-база: по товарам (4 знака)', min(year) || '–' || max(year),
                   min(year) FILTER (WHERE month IS NOT NULL) || '–' || max(year), format('{:,} строк', count(*))
            FROM db_commodity_trade
            UNION ALL
            SELECT 1 + replace(family, 'hs', '')::INT, 'файлы xlsx: ' || replace(family, 'hs', '') || '-значный уровень ТН ВЭД',
                   min(year) || '–' || max(year), NULL,
                   format('{} книг ({} текущих)', count(*), count(*) FILTER (WHERE is_current))
            FROM meta_workbook GROUP BY family
        ) ORDER BY ord""").replace(",", " ")
    last_year = con.execute("SELECT max(year) FROM db_country_trade").fetchone()[0]
    last_month = con.execute("SELECT max(month) FROM db_country_trade WHERE year = ?", [last_year]).fetchone()[0]
    qc = table("SELECT check_name AS проверка, status AS статус, n_issues AS проблем FROM qc_summary")
    assets = "\n".join(f"| `{n}` | {(out / n).stat().st_size / 1e6:.1f} МБ |" for n in ASSETS.values())
    url = f"https://github.com/{repo()}"
    text = f"""Снимок данных о внешней торговле Армении с сайта Армстата (<https://armstat.am/en/?nid=160>),
собранных {date} на трёх языках (en/hy/ru). База собрана кодом коммита [`{commit[:7]}`]({url}/commit/{commit}).

## Файлы

| файл | размер |
|---|---|
{assets}

* `armstat_trade.duckdb.xz` — база DuckDB (описание: [database.md]({url}/blob/{commit}/docs/database.md));
* `armstat_trade-parquet.zip` — все таблицы и представления в Parquet + словарь данных;
* `armstat_trade-raw.tar.xz` — исходные данные: страницы сайта, xlsx/7z, выгрузки веб-базы (`raw/`) и манифесты (`catalog/`);
* `SHA256SUMS` — контрольные суммы.

## Как использовать

```bash
git clone {url}.git && cd arm-ext-trade
make install
make download          # база -> data/armstat_trade.duckdb (проверка SHA256)
make lab               # тетрадка с примерами
```

Пересборка из исходных данных без обращения к сайту: `git checkout {tag}`, `make download-raw build`.
Вручную: `curl -LO {url}/releases/download/{tag}/armstat_trade.duckdb.xz && xz -d armstat_trade.duckdb.xz`.

## Охват

{coverage}

{last_year} год неполный (данные веб-базы — по {last_month}-й месяц); данные последних двух лет Армстат уточняет.

## Проверки качества

{qc}

Подробности: [data_quality.md]({url}/blob/{commit}/docs/data_quality.md).
"""
    path = out / NOTES
    path.write_text(text, encoding="utf-8")
    return path


def pack(tag: str | None = None) -> Path:
    """Pack the database, Parquet export and raw data into data/release/<tag>/."""
    if not config.DUCKDB_PATH.exists():
        raise SystemExit("database not found: run `make build` (or `make download`) first")
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    date = snapshot_date(con)
    tag = tag or f"data-{date}"
    out = config.RELEASE_DIR / tag
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    db_xz = out / ASSETS["db"]
    with open(config.DUCKDB_PATH, "rb") as src, lzma.open(db_xz, "wb", preset=6) as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
    log.info("database -> %s", db_xz)

    _export_parquet(con, out)

    raw_xz = out / ASSETS["raw"]
    with tarfile.open(raw_xz, "w:xz", preset=6) as t:
        t.add(config.RAW_DIR, arcname="raw")
        t.add(config.CATALOG_DIR, arcname="catalog")
    log.info("raw data -> %s", raw_xz)

    (out / SUMS).write_text("".join(f"{sha256(out / n)}  {n}\n" for n in ASSETS.values()), encoding="utf-8")
    try:
        commit = _git("rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    _notes(con, tag, date, commit, out)
    con.close()
    log.info("release %s packed in %s", tag, out)
    return out


# ---------------------------------------------------------------------------
# publishing
# ---------------------------------------------------------------------------

def publish(tag: str | None = None) -> str:
    """Pack (if needed) and create the GitHub release with ``gh``.

    The working tree must be clean and HEAD pushed: the tag points to HEAD, so
    the release documents exactly the code the database was built with.
    """
    if _git("status", "--porcelain"):
        raise SystemExit("working tree is not clean: commit the changes before publishing a release")
    if not _git("branch", "-r", "--contains", "HEAD"):
        raise SystemExit("HEAD is not pushed: run `git push` before publishing a release")
    if not shutil.which("gh"):
        raise SystemExit("the GitHub CLI `gh` is required to publish a release")
    out = pack(tag)
    tag = out.name
    files = [str(out / n) for n in (*ASSETS.values(), SUMS)]
    date = tag.removeprefix("data-")
    subprocess.run(["gh", "release", "create", tag, *files, "--repo", repo(), "--target", _git("rev-parse", "HEAD"),
                    "--title", f"Данные на {date}", "--notes-file", str(out / NOTES)], check=True)
    log.info("published release %s to %s", tag, repo())
    return tag


# ---------------------------------------------------------------------------
# downloading
# ---------------------------------------------------------------------------

def asset_url(name: str, tag: str = "latest") -> str:
    base = f"https://github.com/{repo()}/releases"
    return f"{base}/latest/download/{name}" if tag == "latest" else f"{base}/download/{tag}/{name}"


def parse_sums(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[1].lstrip("*")] = parts[0].lower()
    return out


def _fetch(session: requests.Session, url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        tmp = dst.with_suffix(dst.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.replace(dst)


def safe_members(t: tarfile.TarFile, prefix: str) -> list[tarfile.TarInfo]:
    """Members under ``prefix/`` that are plain files/dirs with safe relative paths."""
    out = []
    for m in t.getmembers():
        name = m.name
        if not (name == prefix or name.startswith(prefix + "/")):
            continue
        if name.startswith("/") or ".." in Path(name).parts or not (m.isfile() or m.isdir()):
            raise ValueError(f"unsafe archive member: {name}")
        out.append(m)
    return out


def download(tag: str = "latest", parts: tuple[str, ...] = ("db",), with_catalog: bool = False) -> None:
    """Download release assets, verify SHA256 and unpack them into data/."""
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT
    cache = config.RELEASE_DIR / "download"
    cache.mkdir(parents=True, exist_ok=True)
    sums = session.get(asset_url(SUMS, tag), timeout=60)
    sums.raise_for_status()
    expected = parse_sums(sums.text)
    for part in parts:
        name = ASSETS[part]
        path = cache / name
        log.info("download %s", asset_url(name, tag))
        _fetch(session, asset_url(name, tag), path)
        digest = sha256(path)
        if digest != expected.get(name):
            path.unlink()
            raise SystemExit(f"checksum mismatch for {name}: got {digest}, expected {expected.get(name)}")
        if part == "db":
            tmp = config.DUCKDB_PATH.with_name(config.DUCKDB_PATH.name + ".download")
            with lzma.open(path) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            tmp.replace(config.DUCKDB_PATH)
            log.info("database -> %s", config.DUCKDB_PATH)
        elif part == "parquet":
            if PARQUET_DIR.exists():
                shutil.rmtree(PARQUET_DIR)
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    target = (config.DATA_DIR / info.filename).resolve()
                    if not str(target).startswith(str(config.DATA_DIR.resolve()) + os.sep):
                        raise ValueError(f"unsafe archive member: {info.filename}")
                z.extractall(config.DATA_DIR)
            log.info("parquet -> %s", PARQUET_DIR)
        elif part == "raw":
            with tarfile.open(path, "r:xz") as t:
                members = safe_members(t, "raw") + (safe_members(t, "catalog") if with_catalog else [])
                try:
                    t.extractall(config.DATA_DIR, members=members, filter="data")
                except TypeError:  # Python without tarfile extraction filters
                    t.extractall(config.DATA_DIR, members=members)
            log.info("raw data -> %s%s", config.RAW_DIR, " (+ catalog)" if with_catalog else "")
