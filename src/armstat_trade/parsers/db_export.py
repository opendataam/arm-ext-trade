"""Parser for the Excel export (``/excelopen.php``) of the web database.

The export is an HTML table ("Excel HTML") with a header row:

* country database (nid 159/717)::

    country | year | Time Period | export | import (countries of origin) | import (country of consignment)

* commodity database (nid 148)::

    Commodity | Codes | year | Time Period | export in tonn | export in 1000$ | import in tonn | import in 1000$

``Time Period`` is the month number (1-12) or 13 for the annual value.
Headers are translated in the hy/ru exports, so columns are taken by position.
Values are in thousand US dollars (and tonnes) with up to 5 decimals.
"""

from __future__ import annotations

import re

from lxml import html

from ..config import ANNUAL_PERIOD_CODE
from .common import text, to_num


def _cell(c) -> str:
    # cells of the export hold plain text; text_content() only for the rare nested markup
    return ((c.text if len(c) == 0 else c.text_content()) or "").strip()


def _rows(raw: str | tuple) -> tuple[list[str], list[list[str]]]:
    """Split an export into (header, data rows); accepts an already split tuple."""
    if isinstance(raw, tuple):
        return raw
    tree = html.fromstring(raw)
    rows = [[_cell(c) for c in tr if c.tag in ("td", "th")] for tr in tree.iter("tr")]
    rows = [r for r in rows if any(r)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _period(v: str) -> tuple[int, int | None]:
    try:
        p = int(float(v))
    except ValueError:
        return -1, None
    return p, (None if p == ANNUAL_PERIOD_CODE else p)


def _int(v: str) -> int:
    try:
        return int(float(v))
    except ValueError:
        return -1


def parse_country(raw: str | tuple) -> list[dict]:
    header, rows = _rows(raw)
    out = []
    for seq, r in enumerate(rows):
        if len(r) < 6:
            continue
        period, month = _period(r[2])
        out.append(
            {
                "seq": seq,
                "country_name": text(r[0]),
                "year": _int(r[1]),
                "period": period,
                "month": month,
                "export_kusd": to_num(r[3]),
                "import_origin_kusd": to_num(r[4]),
                "import_consignment_kusd": to_num(r[5]),
            }
        )
    return out


PAGE_SIZE = 25


def expected_rows(query_html: str) -> tuple[int, int]:
    """Range of the number of result rows announced by the query page.

    The result is shown in pages of 25 rows; the pager links carry
    ``offset=<page index>``. Without a pager the table rows are counted.
    """
    offsets = [int(x) for x in re.findall(r"offset=(\d+)", query_html)]
    if offsets:
        last = max(offsets)
        return PAGE_SIZE * last + 1, PAGE_SIZE * (last + 1)
    tree = html.fromstring(query_html)
    tables = tree.xpath('//table[@class="articles"]')
    n = len([tr for tr in tables[-1].xpath(".//tr") if tr.xpath("./td")]) if len(tables) > 1 else 0
    return n, n


def validate(raw: str, nid: int, mode: str, year: int, expected: tuple[int, int] | None = None) -> str | None:
    """Return an error message if the export does not belong to the query, else None.

    The export endpoint returns the *last query known to the server*, which
    may occasionally be the query of another visitor (observed in practice),
    so every export is checked against the query parameters.
    """
    header, rows = split = _rows(raw)
    ncols = 8 if nid == 148 else 6
    if header and len(header) != ncols:
        return f"expected {ncols} columns, got {len(header)}"
    parsed = parse_commodity(split) if nid == 148 else parse_country(split)
    if len(parsed) != len(rows):
        return "unparseable rows"
    if not parsed and not (expected and expected[0] == 0):
        return "empty export"  # a query for all items of a year offered by the form is never empty
    years = {r["year"] for r in parsed}
    if years - {year}:
        return f"unexpected years {sorted(years)[:5]}"
    periods = {r["period"] for r in parsed}
    allowed = {ANNUAL_PERIOD_CODE} if mode == "annual" else set(range(1, 13))
    if periods - allowed:
        return f"unexpected periods {sorted(periods)[:5]}"
    if expected and not (expected[0] <= len(parsed) <= expected[1]):
        return f"{len(parsed)} rows, the query page announced {expected[0]}-{expected[1]}"
    return None


def parse_commodity(raw: str | tuple) -> list[dict]:
    header, rows = _rows(raw)
    out = []
    for seq, r in enumerate(rows):
        if len(r) < 8:
            continue
        period, month = _period(r[3])
        out.append(
            {
                "seq": seq,
                "commodity_name": text(r[0]),
                "code_raw": r[1].strip(),
                "year": _int(r[2]),
                "period": period,
                "month": month,
                "export_ton": to_num(r[4]),
                "export_kusd": to_num(r[5]),
                "import_ton": to_num(r[6]),
                "import_kusd": to_num(r[7]),
            }
        )
    return out
