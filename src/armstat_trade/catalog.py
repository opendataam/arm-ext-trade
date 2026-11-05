"""Step 1: crawl the "External trade database" section in all languages.

Saves page HTML to ``data/raw/pages/<lang>/nid<nid>.html`` and writes the
catalog manifests to ``data/catalog``:

* ``pages.json``      – every page x language with its title;
* ``files.json``      – every distinct downloadable file with the link texts in all languages;
* ``db_options/<nid>_<lang>.json`` – options of the web database query forms
  (countries / commodities with codes, available years and months).
"""

from __future__ import annotations

import logging

from . import config
from .http import Client
from .parsers.pages import parse_form_options, parse_page
from .utils import read_json, sha256_bytes, utc_now, write_json

log = logging.getLogger(__name__)


def page_url(lang: str, nid: int) -> str:
    return f"{config.BASE_URL}/{config.LANGS[lang]}/?nid={nid}"


def crawl(client: Client | None = None) -> dict:
    client = client or Client()
    pages, files = [], {}
    for nid, meta in config.PAGES.items():
        for lang in config.LANGS:
            url = page_url(lang, nid)
            log.info("page %s", url)
            raw = client.get(url).content
            path = config.PAGES_DIR / lang / f"nid{nid}.html"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            text = raw.decode("utf-8", errors="replace")
            parsed = parse_page(text, url)
            pages.append(
                {
                    "nid": nid,
                    "lang": lang,
                    "kind": meta["kind"],
                    "url": url,
                    "title": parsed["title"],
                    "fetched_at": utc_now(),
                    "sha256": sha256_bytes(raw),
                    "subpages": sorted({p["nid"] for p in parsed["subpages"]}),
                }
            )
            for f in parsed["files"]:
                rec = files.setdefault(
                    f["file_id"],
                    {
                        "file_id": f["file_id"],
                        "ext": f["ext"],
                        "url": f"{config.BASE_URL}/file/doc/{f['file_id']}.{f['ext']}",
                        "nid": nid,
                        "level": meta.get("level"),
                        "year": None,
                        "hidden": True,
                        "titles": {},
                    },
                )
                if f["link_text"]:
                    rec["hidden"] = False
                    rec["titles"].setdefault(lang, f["link_text"])
                    rec["year"] = rec["year"] or f["year"]
            if meta["kind"].startswith("db_"):
                write_json(config.CATALOG_DIR / "db_options" / f"{nid}_{lang}.json", parse_form_options(text))
    write_json(config.CATALOG_DIR / "pages.json", pages)
    old = {f["file_id"]: f for f in read_json(config.CATALOG_DIR / "files.json", [])}
    out = []
    for fid, rec in sorted(files.items()):
        # keep download info from previous runs
        for k in ("sha256", "size", "downloaded_at", "members"):
            if k in old.get(fid, {}):
                rec[k] = old[fid][k]
        out.append(rec)
    write_json(config.CATALOG_DIR / "files.json", out)
    log.info("catalog: %d pages, %d files", len(pages), len(out))
    return {"pages": pages, "files": out}
