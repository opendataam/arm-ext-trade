"""Unit tests of the parsers on small synthetic inputs (no network, no data files)."""

from armstat_trade import reference
from armstat_trade.parsers import common, db_export, files_hs2, tnved
from armstat_trade.parsers.files_hs10 import split_unit


def test_to_num_and_symbols():
    assert common.to_num("1 234,5") == 1234.5
    assert common.to_num(12.0) == 12.0
    assert common.to_num("-") is None
    assert common.to_num("X") is None
    assert common.to_num(None) is None


def test_codes():
    assert common.pad_hs("101", 4) == "0101"
    assert common.pad_hs("101210000", 10) == "0101210000"
    assert common.code_str(7.0) == "7"
    assert common.fix_roman("XY") == "XV"
    assert common.fix_roman("XYIII") == "XVIII"
    assert common.fix_roman("12") is None
    assert common.roman_to_int("XIV") == 14


def test_split_hy_en():
    assert common.split_hy_en("ԻՏԱԼԻԱ - ITALY") == ("ԻՏԱԼԻԱ", "ITALY")
    assert common.split_hy_en("ԱՆՀԱՅՏ ԵՐԿԻՐ-UNKNOW COUNTRY") == ("ԱՆՀԱՅՏ ԵՐԿԻՐ", "UNKNOW COUNTRY")
    assert common.split_hy_en("ԲԵԼԱՌՈՒՍ – BELARUS") == ("ԲԵԼԱՌՈՒՍ", "BELARUS")


def test_reference():
    assert reference.norm_name("Saint-Barthélemy") == reference.norm_name("SAINT BARTHELEMY")
    assert reference.norm_name("Йемен") == "ЙЕМЕН"  # Cyrillic letters are not stripped
    assert reference.bec_code("Fuels and lubricants") == "3"
    assert reference.bec_code("Total") is None
    assert reference.unit_code("m sq.") == "m2"
    assert reference.unit_code("piese") == "piece"
    assert split_unit("հատ/piese") == ("հատ", "piece")


COUNTRY_EXPORT = """<html><table>
<tr><td>country</td><td>year</td><td>Time Period</td><td>export</td><td>import (countries of origin)</td><td>import (country of consignment)</td></tr>
<tr><td>Afghanistan</td><td>2024</td><td>13</td><td>0</td><td>38.22102</td><td>64.34663</td></tr>
<tr><td>Albania</td><td>2024</td><td>13</td><td>188.31681</td><td>1250.72138</td><td>310.09208</td></tr>
</table></html>"""

COMMODITY_EXPORT = """<html><table>
<tr><td>Commodity</td><td>Codes</td><td>year</td><td>Time Period</td><td>export in tonn</td><td>export in 1000$</td><td>import in tonn</td><td>import in 1000$</td></tr>
<tr><td>Live swine</td><td>103</td><td>2024</td><td>9</td><td>0</td><td>0</td><td>490.07</td><td>744.93</td></tr>
</table></html>"""


def test_db_export_parse_and_validate():
    rows = db_export.parse_country(COUNTRY_EXPORT)
    assert len(rows) == 2 and rows[0]["month"] is None and rows[1]["export_kusd"] == 188.31681
    assert db_export.validate(COUNTRY_EXPORT, 717, "annual", 2024) is None
    assert db_export.validate(COUNTRY_EXPORT, 717, "annual", 2023) is not None  # wrong year
    assert db_export.validate(COUNTRY_EXPORT, 717, "monthly", 2024) is not None  # wrong period
    assert db_export.validate(COUNTRY_EXPORT, 148, "annual", 2024) is not None  # wrong table
    assert db_export.validate(COUNTRY_EXPORT, 717, "annual", 2024, (26, 50)) is not None  # wrong size
    empty = COUNTRY_EXPORT.split("<tr><td>Afghanistan")[0] + "</table></html>"
    assert db_export.validate(empty, 717, "annual", 2024) == "empty export"
    assert db_export.validate(empty, 717, "annual", 2024, (0, 0)) is None
    c = db_export.parse_commodity(COMMODITY_EXPORT)
    assert c[0]["code_raw"] == "103" and c[0]["month"] == 9
    assert db_export.validate(COMMODITY_EXPORT, 148, "monthly", 2024) is None


def test_expected_rows_from_pager():
    page = '<a href="/en/index.php?nid=717&amp;offset=1">2</a><a href="/en/index.php?nid=717&amp;offset=7">&gt;&gt;</a>'
    assert db_export.expected_rows(page) == (176, 200)


def test_analyse_header_multi_year():
    grid = [
        ["Title 2021-2024"],
        ["(հազ. ԱՄՆ դոլար, thous. US$)"],
        ["Code", None, "Country", "ԱՐՏԱՀԱՆՈՒՄ -EXPORTS", None, "ՆԵՐՄՈՒԾՈՒՄ - IMPORTS", None, None, None],
        [None, None, None, None, None, "by countries of consignment", None, "by countries of origin", None],
        [None, None, None, 2023.0, 2024.0, 2023.0, 2024.0, 2023.0, 2024.0],
        [None, None, "Ընդամենը", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    ]
    spec, first = files_hs2.analyse_header(grid, 2, files_hs2.sheet_unit(grid), 3)
    assert first == 5
    assert spec[3] == {"flow": "export", "year": 2023, "measure": "value_kusd"}
    assert spec[6] == {"flow": "import_consignment", "year": 2024, "measure": "value_kusd"}
    assert spec[8] == {"flow": "import_origin", "year": 2024, "measure": "value_kusd"}


def test_analyse_header_measures():
    grid = [
        ["Code", "Group", "ԱՐՏԱՀԱՆՈՒՄ -EXPORTS", None, None, "ՆԵՐՄՈՒԾՈՒՄ - IMPORTS", None, None],
        [None, None, "weight, ton", "mln. drams", "thous. US $", "weight, ton", "mln. drams", "thous. US $"],
        [None, "Ընդամենը", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    ]
    spec, first = files_hs2.analyse_header(grid, 0, None, 2)
    assert first == 2
    assert [spec[j]["measure"] for j in range(2, 8)] == ["weight_ton", "value_mln_amd", "value_kusd"] * 2
    assert {spec[j]["flow"] for j in range(5, 8)} == {"import"}


def test_classify_sheets():
    assert files_hs2.classify_sheet("SITC-2-2019") == "sitc2"
    assert files_hs2.classify_sheet("Groups_%") == "hs2_share"
    assert files_hs2.classify_sheet("HUM_AID") == "hum_aid"
    assert files_hs2.classify_sheet("EU_countries") == "hs2_partner"
    assert files_hs2.leading_partner("OTHER CIS_groups_countries") == "CIS_OTHER"
    assert files_hs2.leading_partner("Other NON CIS_NON EU countries1") == "OTHER"


def test_tnved_headings():
    txt = "РАЗДЕЛ V МИНЕРАЛЬНЫЕ ПРОДУКТЫ ГРУППА 25\nСОЛЬ; СЕРА\n\nПримечания:\n1. текст\nГРУППА 01\n\nЖИВЫЕ ЖИВОТНЫЕ\nПримечание:"
    rows = {(r["kind"], r["code"]): r["name_ru"] for r in tnved.extract(txt)}
    assert rows[("section", "V")] == "Минеральные продукты"
    assert rows[("chapter", "25")] == "Соль; сера"
    assert rows[("chapter", "01")] == "Живые животные"
