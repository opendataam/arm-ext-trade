"""Checks of the multilingual documentation: every document exists in all languages, relative links resolve."""

import re
from pathlib import Path

import duckdb
import pytest

from armstat_trade import config, docs

ROOT = config.ROOT
LANGS = ("en", "hy", "ru")
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _markdown_files():
    docs = [p for p in sorted((ROOT / "docs").rglob("*.md")) if not any(s.startswith(".") for s in p.parts)]
    return [ROOT / "README.md", ROOT / "README.hy.md", ROOT / "README.ru.md", *docs]


def test_every_document_in_every_language():
    names = {lang: {p.name for p in (ROOT / "docs" / lang).glob("*.md")} for lang in LANGS}
    assert names["en"], "docs/en is empty"
    for lang in LANGS:
        assert names[lang] == names["en"], lang
    for readme in ("README.md", "README.hy.md", "README.ru.md"):
        assert (ROOT / readme).exists(), readme


@pytest.mark.parametrize("path", _markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(path: Path):
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    broken = []
    for target in LINK.findall(text):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue
        if not (path.parent / target.split("#")[0]).exists():
            broken.append(target)
    assert not broken, broken


@pytest.mark.skipif(not config.DUCKDB_PATH.exists(), reason="database not built (make build)")
def test_inventory_in_every_language(tmp_path):
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    try:
        docs.write_inventory(con, tmp_path)
    finally:
        con.close()
    titles = {lang: (tmp_path / lang / "inventory.md").read_text(encoding="utf-8").splitlines()[0] for lang in LANGS}
    assert titles == {"en": "# Source inventory", "hy": "# Աղբյուրների ցանկ", "ru": "# Перечень источников"}
