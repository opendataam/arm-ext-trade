"""Parse armstat.am HTML pages: title, file links and query form options."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from lxml import html

FILE_RE = re.compile(r"/file/doc/(\d+)\.(\w+)$")
YEAR_RE = re.compile(r"(?<!\d)(19\d\d|20\d\d)(?!\d)")


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _content(tree: html.HtmlElement) -> html.HtmlElement:
    """Return the central content block (the page also contains a huge menu)."""
    nodes = tree.xpath('//div[@id="center"]')
    return nodes[0] if nodes else tree


def parse_page(raw: str, page_url: str) -> dict:
    """Extract title, links to files and links to sub pages from a page."""
    tree = html.fromstring(raw)
    center = _content(tree)
    h1 = center.xpath(".//h1")
    title = _norm(h1[0].text_content()) if h1 else ""
    files, subpages = [], []
    for a in center.xpath(".//a[@href]"):
        href = a.get("href")
        absolute = urljoin(page_url, href)
        text = _norm(a.text_content())
        m = FILE_RE.search(absolute)
        if m:
            years = YEAR_RE.findall(text)
            files.append(
                {
                    "file_id": m.group(1),
                    "ext": m.group(2).lower(),
                    "url": absolute,
                    "link_text": text,
                    "hidden": text == "",
                    "year": int(years[0]) if years else None,
                }
            )
            continue
        m = re.search(r"[?&]nid=(\d+)", href)
        if m and not a.xpath('ancestor::div[@id="centers"]'):  # skip breadcrumbs
            subpages.append({"nid": int(m.group(1)), "url": absolute, "link_text": text})
    return {"title": title, "files": files, "subpages": subpages}


def parse_form_options(raw: str) -> dict[str, list[dict]]:
    """Return the options of the query form selects (thid[], years[], year[], monid[]).

    Commented-out options (``<!-- <option ...> -->``) are ignored by lxml.
    """
    tree = html.fromstring(raw)
    out: dict[str, list[dict]] = {}
    for name in ("thid", "years", "year", "monid"):
        opts = []
        for o in tree.xpath(f'//select[@name="{name}[]"]/option'):
            value = o.get("value")
            if value is None or value == "0":  # "- all -"
                continue
            opts.append({"value": value, "label": _norm(o.text_content())})
        out[name] = opts
    return out
