from datetime import date

import database
from excel_handler import inspect_excel


def validate_upload(content: bytes, filename: str, year: int, month: int, max_bytes: int) -> dict:
    return inspect_excel(content, filename, year, month, max_bytes)


async def activate_staged_import(staging_id: int, admin_id: int) -> dict | None:
    staged = await database.claim_staged_import(staging_id, admin_id)
    if not staged:
        return None
    import json
    rows = json.loads(staged["rows"]) if isinstance(staged["rows"], str) else staged["rows"]
    errors = json.loads(staged["errors"]) if isinstance(staged["errors"], str) else staged["errors"]
    for row in rows:
        if row.get("lesson_date"):
            row["lesson_date"] = date.fromisoformat(row["lesson_date"])
    try:
        await database.replace_period(staged["year"], staged["month"], rows, admin_id,
                                     staged["file_name"], staged["import_type"],
                                     len(errors), staged["duplicate_count"])
        await database.mark_staged_import(staging_id, "confirmed")
    except Exception:
        await database.mark_staged_import(staging_id, "pending")
        raise
    return {"imported": len(rows), "rejected": len(errors),
            "duplicates": staged["duplicate_count"], "year": staged["year"], "month": staged["month"]}
