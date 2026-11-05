"""Command line interface: ``python -m armstat_trade <command>``."""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="armstat-trade", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("catalog", help="crawl site pages (all languages), build data/catalog/*.json")

    f = sub.add_parser("fetch-files", help="download xlsx/7z files listed in the catalog")
    f.add_argument("--force", action="store_true", help="re-download existing files")

    d = sub.add_parser("fetch-db", help="download the web database via Excel export")
    d.add_argument("--nid", type=int, action="append", help="148, 159, 717 (default: all)")
    d.add_argument("--lang", action="append", help="en, hy, ru (default: all)")
    d.add_argument("--mode", action="append", choices=["annual", "monthly"])
    d.add_argument("--refresh-last", type=int, default=2, help="always refetch N most recent years")
    d.add_argument("--force", action="store_true")

    sub.add_parser("tnved", help="extract Russian section/chapter names from the TN VED 2017 .doc (needs textutil or soffice)")

    b = sub.add_parser("build", help="parse raw data and (re)build the DuckDB database")
    b.add_argument("--db", help="output path (default data/armstat_trade.duckdb)")

    sub.add_parser("docs", help="regenerate docs/data_dictionary.md from the database catalog")

    a = sub.add_parser("all", help="catalog + fetch-files + fetch-db + tnved + build + docs")
    a.add_argument("--refresh-last", type=int, default=2)

    r = sub.add_parser("release", help="pack the data snapshot and publish it as a GitHub release (needs gh)")
    r.add_argument("--tag", help="release tag (default data-<collection date>)")
    r.add_argument("--pack-only", action="store_true", help="only create the assets in data/release/<tag>")

    dl = sub.add_parser("download", help="download a data snapshot from GitHub releases into data/")
    dl.add_argument("--tag", default="latest", help="release tag (default: latest)")
    dl.add_argument("--part", action="append", choices=["db", "parquet", "raw"], help="what to download (default: db)")
    dl.add_argument("--with-catalog", action="store_true", help="with raw: also overwrite data/catalog from the snapshot")

    args = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.cmd in ("release", "download"):
        from . import release

        if args.cmd == "release":
            release.pack(args.tag) if args.pack_only else release.publish(args.tag)
        else:
            release.download(args.tag, tuple(args.part or ["db"]), args.with_catalog)
        return 0

    from . import catalog, fetch_db, fetch_files

    if args.cmd in ("catalog", "all"):
        catalog.crawl()
    if args.cmd in ("fetch-files", "all"):
        fetch_files.download(force=getattr(args, "force", False))
    if args.cmd in ("fetch-db", "all"):
        kw = {"refresh_last": args.refresh_last}
        if args.cmd == "fetch-db":
            if args.nid:
                kw["nids"] = tuple(args.nid)
            if args.lang:
                kw["langs"] = tuple(args.lang)
            if args.mode:
                kw["modes"] = tuple(args.mode)
            kw["force"] = args.force
        fetch_db.fetch(**kw)
    if args.cmd in ("tnved", "all"):
        from .parsers import tnved

        tnved.run()
    if args.cmd in ("build", "all"):
        from . import build

        build.build(getattr(args, "db", None))
    if args.cmd in ("docs", "all"):
        from . import docs

        docs.write_data_dictionary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
