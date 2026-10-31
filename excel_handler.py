from calendar import monthrange
from datetime import date, datetime
from io import BytesIO
import re
import unicodedata

from openpyxl import load_workbook

ALIASES = {
    "date": {"sana", "date", "lesson date", "dars sanasi"},
    "day": {"kun", "hafta kuni", "weekday", "day of week", "day"},
    "teacher": {"oqituvchi", "o'qituvchi", "teacher", "ustoz"},
    "group_name": {"guruh", "group", "group name"},
    "pair_number": {"juftlik", "juftlik raqami", "pair", "pair number", "para"},
    "time_range": {"vaqt", "dars vaqti", "time", "time range"},
    "subject": {"fan", "subject", "dars"},
    "lesson_type": {"dars turi", "turi", "lesson type", "type"},
    "room": {"xona", "room", "auditoriya", "auditoriya raqami"},
    "status": {"holat", "status"},
    "year": {"yil", "year"}, "month": {"oy", "month"},
}
DAYS = {"dushanba": 1, "seshanba": 2, "chorshanba": 3, "payshanba": 4,
        "juma": 5, "shanba": 6, "yakshanba": 7}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    for apostrophe in ("ʻ", "ʼ", "‘", "’", "`", "´"):
        text = text.replace(apostrophe, "'")
    return re.sub(r"\s+", " ", text)


def parse_day(value: object) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    s = _norm(value)
    if s.isdigit() and 1 <= int(s) <= 7:
        return int(s)
    for name, index in DAYS.items():
        if s.startswith(name):
            return index
    return None


def parse_date(value: object, year: int, month: int) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    if s.isdigit() and 1 <= int(s) <= 31:
        return date(year, month, int(s))
    raise ValueError("Sana formati noto‘g‘ri (masalan, 01.11.2026)")


def inspect_excel(content: bytes, filename: str, year: int, month: int, max_bytes: int) -> dict:
    if not filename.lower().endswith(".xlsx"):
        raise ValueError("Faqat .xlsx formatidagi Excel fayli qabul qilinadi")
    if len(content) > max_bytes:
        raise ValueError(f"Fayl hajmi {max_bytes // (1024*1024)} MB dan oshmasligi kerak")
    try:
        wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("Excel faylini ochib bo‘lmadi") from exc
    ws = wb.active
    iterator = ws.iter_rows(values_only=True)
    header = next(iterator, None)
    if not header:
        return {"rows": [], "errors": ["Ustun sarlavhalari topilmadi"], "duplicates": 0, "total": 0}
    columns = {}
    for i, value in enumerate(header):
        key = _norm(value)
        for field, names in ALIASES.items():
            if key in names:
                columns[field] = i
    required = {"teacher", "group_name", "pair_number", "time_range", "subject"}
    missing = required - columns.keys()
    if "day" not in columns and "date" not in columns:
        missing.add("day yoki sana")
    if missing:
        wb.close()
        return {"rows": [], "errors": ["Majburiy ustunlar topilmadi: " + ", ".join(sorted(missing))], "duplicates": 0, "total": 0}
    rows, errors, seen = [], [], set()
    total = 0
    for line, values in enumerate(iterator, start=2):
        if not any(v is not None and str(v).strip() for v in values):
            continue
        total += 1
        try:
            cell = lambda key: values[columns[key]] if key in columns and columns[key] < len(values) else None
            lesson_date = parse_date(cell("date"), year, month)
            weekday = parse_day(cell("day")) or (lesson_date.isoweekday() if lesson_date else None)
            if weekday is None:
                raise ValueError("Hafta kuni 1–7 yoki o‘zbekcha nomda bo‘lishi kerak")
            if lesson_date and lesson_date.isoweekday() != weekday:
                raise ValueError("Sana va hafta kuni mos emas")
            if lesson_date and (lesson_date.year, lesson_date.month) != (year, month):
                raise ValueError(f"Sana tanlangan davrdan tashqarida: {lesson_date:%d.%m.%Y}")
            for key, chosen in (("year", year), ("month", month)):
                val = cell(key)
                if val is not None and int(val) != chosen:
                    raise ValueError(f"Excel ichidagi {key} tanlangan davrga mos emas")
            teacher, group, subject = (str(cell(k) or "").strip() for k in ("teacher", "group_name", "subject"))
            if not teacher or not group or not subject:
                raise ValueError("O‘qituvchi, guruh va fan bo‘sh bo‘lmasligi kerak")
            pair = int(cell("pair_number"))
            if not 1 <= pair <= 12:
                raise ValueError("Juftlik raqami 1–12 oralig‘ida bo‘lishi kerak")
            row = {"teacher": teacher, "group_name": group, "day_of_week": list(DAYS)[weekday-1].capitalize(),
                   "day_index": weekday, "lesson_date": lesson_date, "pair_number": pair,
                   "time_range": str(cell("time_range") or "Belgilanmagan").strip(),
                   "subject": subject, "lesson_type": str(cell("lesson_type") or "Ma’ruza").strip(),
                   "room": str(cell("room") or "Belgilanmagan").strip(),
                   "status": "cancelled" if _norm(cell("status")) in {"bekor", "bekor qilingan", "cancelled"} else "scheduled"}
            key = tuple(row[k] for k in ("teacher", "group_name", "day_index", "lesson_date", "pair_number", "time_range", "subject", "room"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
        except (ValueError, TypeError, OverflowError) as exc:
            errors.append(f"{line}-qator: {exc}")
    wb.close()
    return {"rows": rows, "errors": errors, "duplicates": total - len(rows) - len(errors), "total": total}


def expand_recurring(rows: list[dict], year: int, month: int) -> list[dict]:
    """Materialize recurring weekday lessons into dated month instances."""
    _, last = monthrange(year, month)
    return [dict(r, lesson_date=date(year, month, day)) for r in rows
            for day in range(1, last + 1) if date(year, month, day).isoweekday() == r["day_index"]]
