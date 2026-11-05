"""Static reference data (code lists) and name normalisation used by the build."""

from __future__ import annotations

import re
import unicodedata

ARMENIAN_RE = re.compile(r"[԰-֏]")

LANGUAGES = [
    # lang, site path segment, English name, native name
    ("en", "en", "English", "English"),
    ("hy", "am", "Armenian", "Հայերեն"),
    ("ru", "ru", "Russian", "Русский"),
]

FLOWS = [
    # code, en, hy, ru, description
    ("export", "Export", "Արտահանում", "Экспорт", "Exports of goods"),
    ("import", "Import", "Ներմուծում", "Импорт",
     "Imports of goods (tables by commodity: imports by country of origin are not distinguished)"),
    ("import_origin", "Import (country of origin)", "Ներմուծում (ըստ ապրանքի ծագման երկրի)",
     "Импорт (по стране происхождения)", "Imports allocated to the country where the goods were produced"),
    ("import_consignment", "Import (country of consignment)", "Ներմուծում (ըստ արտահանող երկրի)",
     "Импорт (по стране отправления)", "Imports allocated to the country from which the goods were dispatched"),
]

MEASURES = [
    # code, unit (en), unit (hy), description
    ("weight_ton", "tonnes", "տոննա", "Net weight in metric tonnes"),
    ("quantity", "supplementary unit", "լրացուցիչ միավոր", "Quantity in the supplementary unit of the commodity (see dim_unit)"),
    ("value_usd", "US dollars", "ԱՄՆ դոլար", "Statistical value in US dollars"),
    ("value_kusd", "thousand US dollars", "հազ. ԱՄՆ դոլար", "Statistical value in thousand US dollars"),
    ("value_musd", "million US dollars", "մլն. ԱՄՆ դոլար", "Statistical value in million US dollars"),
    ("value_mln_amd", "million drams", "մլն. դրամ", "Statistical value in million Armenian drams"),
    ("share_pct", "percent", "%", "Share in the total of the flow, %"),
]

DATA_BASES = [
    ("total", "Total trade", "Ընդամենը",
     "All trade: goods declarations, statistical form of goods transfer and declarations of physical persons"),
    ("declarations", "Goods declarations and statistical form", "Ըստ ապրանքների հայտարարագրերի և վիճակագրական ձևի",
     "Trade by goods declarations and the 'Statistical form of register of goods transfer' (EAEU mutual trade)"),
    ("physical_persons", "Physical persons", "Ֆիզիկական անձինք",
     "Trade by declarations of physical persons (individuals)"),
]

COUNTRY_GROUPS = [
    # code, en, hy, Armenian heading used in the "Countries" sheet
    ("WORLD", "World (total)", "Ընդամենը", ["Ընդամենը"]),
    ("CIS", "CIS countries", "ԱՊՀ երկրներ", ["ԱՊՀ երկրներ"]),
    ("EEU", "EAEU countries", "ԵԱՏՄ երկրներ", ["ԵԱՏՄ երկրներ"]),
    ("CIS_OTHER", "Other CIS countries", "ԱՊՀ այլ երկրներ", ["ԱՊՀ այլ երկրներ"]),
    ("NON_CIS", "Non-CIS countries (rest of the world)", "Ոչ ԱՊՀ երկրներ", ["Ոչ ԱՊՀ երկրներ"]),
    ("EU", "EU countries", "ԵՄ երկրներ", ["ԵՄ երկրներ"]),
    ("OTHER", "Other countries (non-CIS, non-EU)", "Այլ երկրներ", ["Այլ երկրներ"]),
]

# BEC (Broad Economic Categories, rev.4) top-level categories, matched by English label
BEC = [
    ("1", "Food and beverages", "food"),
    ("2", "Industrial supplies not elsewhere specified", "industrial"),
    ("3", "Fuels and lubricants", "fuel"),
    ("4", "Capital goods (except transport equipment), and parts and accessories thereof", "capital"),
    ("5", "Transport equipment and parts and accessories thereof", "transport"),
    ("6", "Consumer goods not elsewhere specified", "consumer"),
    ("7", "Goods not elsewhere specified", "goods not"),
]


def bec_code(label_en: str | None) -> str | None:
    lo = (label_en or "").lower()
    if lo.startswith("total"):
        return None
    for code, _, key in BEC:
        if lo.startswith(key) or key in lo[:20]:
            return code
    return None


# Codes used in the published files that differ from the web database codes
COUNTRY_CODE_ALIASES = {
    "0": 998,     # "Unknown country" (web database: 998)
    "111": 1111,  # "EU countries, not specified" (web database: 1111)
}

SPECIAL_COUNTRIES = {997, 998, 999, 1111}

# Country names that are not in the current web database form but occur in the
# web database exports of earlier years or as block headings of the 2-digit
# bulletins. Verified manually (997 by querying the web database with thid[]=997).
COUNTRY_NAME_ALIASES: dict[str, int] = {
    # web database exports (historical spellings)
    "American Saoma": 16,
    "Американское Самоа": 16,
    "FYR of Macedonia": 807,
    "БЮР Македония": 807,
    "Iran, Islamic Republic of": 364,
    "Korea, DPR of": 408,
    "Корея, НДР": 408,
    "Korea, Republic of": 410,
    "Nagorno Karabagh": 999,
    "Serbia and Montenegro": 891,
    "Сербия и Черногория": 891,
    "Սերբիա և Չերնոգորիա": 891,
    "United States": 840,
    "Соединенные Штаты": 840,
    "Individual": 997,
    "Физические лица": 997,
    "Ֆիզիկական անձինք": 997,
    "Laos": 418,
    "Лаос": 418,
    "Сальвадор": 222,
    "Հանկոնգ": 344,
    # block headings of the 2-digit bulletins
    "UNITED STATES OF AMERICA": 840,
    "AMERICAN SAMOA": 16,
    "BOSNIA AND HERZEGOVINA": 70,
    "KOREA, D P RP": 408,
    "SAINT-BARTHELEMY": 652,
    "SERBIA": 688,
    "UNKNOW COUNTRY": 998,
    "AREAS NOT SPECIFIED": 998,
}

# Names for codes that exist only in the exports (not in the current form)
EXTRA_COUNTRIES = {
    997: {"en": "Individual", "hy": "Ֆիզիկական անձինք", "ru": "Физические лица"},
}


def norm_name(s: str | None) -> str:
    """Normalise a country / commodity name for matching (case, accents, punctuation, spaces)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).replace("ՈՒ", "Ու").upper()
    s = s.replace("Ё", "Е")
    # strip accents of Latin letters only (É -> E), keep Cyrillic Й etc. intact
    out: list[str] = []
    for ch in unicodedata.normalize("NFKD", s):
        if unicodedata.combining(ch) and out and out[-1].isascii():
            continue
        out.append(ch)
    s = unicodedata.normalize("NFC", "".join(out))
    s = re.sub(r"\*+", "", s)
    s = re.sub(r"[^\w]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# Units of measure of the 10-digit tables: normalised code by English label
UNIT_ALIASES = {
    "piese": "piece",
    "m sq.": "m2",
    "m.sq.": "m2",
    "m sq": "m2",
    "cbm": "m3",
    "m5": "m3",
    "1000 piece": "1000 piece",
    "1000piece": "1000 piece",
    "100piece": "100 piece",
    "1000l": "1000 l",
    "kg p2o6": "kg P2O5",
}


def unit_code(unit_en: str | None, unit_hy: str | None = None) -> str | None:
    if not unit_en and not unit_hy:
        return None
    if not unit_en:
        return unit_hy
    u = re.sub(r"\s+", " ", unit_en.replace("Օ", "O")).strip()
    key = u.lower()
    if key in UNIT_ALIASES:
        return UNIT_ALIASES[key]
    key2 = key.replace(" ", "")
    for k, v in UNIT_ALIASES.items():
        if key2 == k.replace(" ", ""):
            return v
    return u
