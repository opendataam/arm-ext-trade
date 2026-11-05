"""Helpers for cleaning values from Armstat tables."""

from __future__ import annotations

import re

# Symbols used in the published tables instead of numbers.
#   "-"  no trade / no data;  "X" not applicable or confidential.
NON_NUMERIC = {"-", "–", "—", "X", "x", "Х", "х", "...", "…", "`", ""}

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}
ARMENIAN_RE = re.compile(r"[԰-֏]")
CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def to_num(v) -> float | None:
    """Convert a cell value to float; symbols such as '-' or 'X' become None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s in NON_NUMERIC:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def is_num(v) -> bool:
    return to_num(v) is not None


def text(v) -> str | None:
    """Normalise whitespace of a text cell; numbers are returned as their string form."""
    if v is None:
        return None
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else str(v)
    s = re.sub(r"\s+", " ", str(v).replace("\xa0", " ")).strip()
    return s or None


def code_str(v) -> str | None:
    """Return a code cell as a string without '.0' (keeps leading zeros of text cells)."""
    if v is None:
        return None
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else None
    s = str(v).strip()
    return s or None


def pad_hs(code: str | None, width: int) -> str | None:
    """Zero-pad a commodity code (Excel drops leading zeros: 101 -> '0101')."""
    if code is None:
        return None
    c = re.sub(r"\D", "", str(code))
    if not c:
        return None
    return c.zfill(width) if len(c) <= width else c


def fix_roman(s: str | None) -> str | None:
    """Normalise HS section numbers ('XY' -> 'XV', 'XYIII' -> 'XVIII', 'I.' -> 'I')."""
    if not s:
        return None
    r = str(s).strip().rstrip(".").upper().replace("Y", "V").replace("У", "V").replace("Х", "X").replace("І", "I")
    return r if re.fullmatch(r"[IVXL]+", r) else None


def roman_to_int(r: str) -> int:
    total, prev = 0, 0
    for ch in reversed(r):
        v = _ROMAN[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def has_armenian(s: str | None) -> bool:
    return bool(s and ARMENIAN_RE.search(s))


def split_hy_en(s: str | None) -> tuple[str | None, str | None]:
    """Split bilingual labels like 'ԱՐՏԱՀԱՆՈՒՄ - EXPORT' or 'ԼԵՍՈԹՈ - LESOTHO'."""
    if not s:
        return None, None
    parts = re.split(r"\s+[-–—]\s+|\s*[-–—]\s*(?=[A-Z])", s, maxsplit=1)
    if len(parts) == 2 and has_armenian(parts[0]) and not has_armenian(parts[1]):
        return parts[0].strip(), parts[1].strip()
    if has_armenian(s):
        # Armenian text followed by Latin text without separator
        m = re.match(r"^(.*[԰-֏][^A-Za-z]*)\s+([A-Za-z].*)$", s)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return s, None
    return None, s


def year_in(s) -> int | None:
    m = re.search(r"(?<!\d)(19[89]\d|20\d\d)(?!\d)", str(s or ""))
    return int(m.group(1)) if m else None
