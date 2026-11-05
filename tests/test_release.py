"""Tests of the data snapshot helpers (no network)."""

import io
import tarfile

import pytest

from armstat_trade import release


def test_asset_urls(monkeypatch):
    monkeypatch.setenv("ARMSTAT_TRADE_REPO", "org/repo")
    assert release.asset_url("SHA256SUMS") == "https://github.com/org/repo/releases/latest/download/SHA256SUMS"
    assert (release.asset_url("armstat_trade.duckdb.xz", "data-2026-11-05")
            == "https://github.com/org/repo/releases/download/data-2026-11-05/armstat_trade.duckdb.xz")


def test_parse_sums():
    text = "abc123  armstat_trade.duckdb.xz\nDEF456 *armstat_trade-raw.tar.xz\n\n"
    assert release.parse_sums(text) == {"armstat_trade.duckdb.xz": "abc123", "armstat_trade-raw.tar.xz": "def456"}


def _tar(*names: str) -> tarfile.TarFile:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for name in names:
            info = tarfile.TarInfo(name)
            info.size = 1
            t.addfile(info, io.BytesIO(b"x"))
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode="r")


def test_safe_members_selects_prefix():
    t = _tar("raw/files/a.xlsx", "catalog/files.json", "rawish/b")
    assert [m.name for m in release.safe_members(t, "raw")] == ["raw/files/a.xlsx"]
    assert [m.name for m in release.safe_members(t, "catalog")] == ["catalog/files.json"]


def test_safe_members_rejects_traversal():
    with pytest.raises(ValueError):
        release.safe_members(_tar("raw/../../etc/passwd"), "raw")
