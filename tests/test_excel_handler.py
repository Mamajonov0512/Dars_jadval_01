from datetime import date
from io import BytesIO

from openpyxl import Workbook

from excel_handler import expand_recurring, inspect_excel, parse_date, parse_day


def workbook_bytes(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def test_parse_date_and_weekdays():
    assert parse_date("01.11.2026", 2026, 11) == date(2026, 11, 1)
    assert parse_date("2026-11-01", 2026, 11) == date(2026, 11, 1)
    assert parse_day("Dushanba") == 1
    assert parse_day("7") == 7


def test_excel_validation_checks_weekday_and_period_and_duplicates():
    content = workbook_bytes([
        ["Sana", "Hafta kuni", "O‘qituvchi", "Guruh", "Juftlik", "Vaqt", "Fan", "Dars turi", "Xona"],
        ["02.11.2026", "Dushanba", "Ali Valiyev", "A-101", 1, "09:00", "Matematika", "Ma’ruza", "12"],
        ["02.11.2026", "Dushanba", "Ali Valiyev", "A-101", 1, "09:00", "Matematika", "Ma’ruza", "12"],
        ["03.11.2026", "Dushanba", "Ali Valiyev", "A-101", 1, "09:00", "Matematika", "Ma’ruza", "12"],
        ["01.12.2026", "Seshanba", "Ali Valiyev", "A-101", 1, "09:00", "Fizika", "Amaliy", "12"],
    ])
    report = inspect_excel(content, "jadval.xlsx", 2026, 11, 1_000_000)
    assert report["total"] == 4
    assert len(report["rows"]) == 1
    assert report["duplicates"] == 1
    assert len(report["errors"]) == 2


def test_header_and_extension_errors():
    assert inspect_excel(workbook_bytes([["Noma’lum"], ["x"]]), "jadval.xlsx", 2026, 11, 100000)["rows"] == []
    try:
        inspect_excel(b"x", "jadval.xls", 2026, 11, 100000)
    except ValueError as exc:
        assert ".xlsx" in str(exc)
    else:
        raise AssertionError(".xls kutilganidek rad etilmadi")


def test_date_column_can_replace_weekday_column():
    content = workbook_bytes([
        ["Sana", "O‘qituvchi", "Guruh", "Juftlik", "Vaqt", "Fan"],
        ["02.11.2026", "Ali Valiyev", "A-101", 1, "09:00", "Matematika"],
    ])
    report = inspect_excel(content, "jadval.xlsx", 2026, 11, 1_000_000)
    assert len(report["rows"]) == 1
    assert report["rows"][0]["day_index"] == 1


def test_recurring_rows_expand_on_matching_weekday():
    row = {"day_index": 1, "subject": "Matematika"}
    dates = [item["lesson_date"] for item in expand_recurring([row], 2026, 11)]
    assert dates and all(d.isoweekday() == 1 and d.month == 11 for d in dates)
