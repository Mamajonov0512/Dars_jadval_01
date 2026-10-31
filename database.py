"""Supabase hosted PostgreSQL access via asyncpg (server-only DATABASE_URL)."""
from datetime import date
import json
from typing import Any

import asyncpg

from config import get_settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = get_settings().database_url
        if not dsn:
            raise RuntimeError("DATABASE_URL belgilanmagan")
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, command_timeout=20,
                                          max_inactive_connection_lifetime=30)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def upsert_user(user_id: int, full_name: str, username: str | None, is_admin: bool) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO users(user_id,full_name,username,is_admin)
            VALUES($1,$2,$3,$4) ON CONFLICT(user_id) DO UPDATE SET
            full_name=EXCLUDED.full_name, username=EXCLUDED.username, is_admin=EXCLUDED.is_admin""",
                           user_id, full_name, username, is_admin)


async def set_selection(user_id: int, kind: str, value: str) -> None:
    column = "selected_teacher" if kind == "teacher" else "selected_group"
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE users SET selected_type=$2,{column}=$3 WHERE user_id=$1", user_id, kind, value)


async def get_selection(user_id: int) -> tuple[str | None, str | None, str | None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT selected_type,selected_teacher,selected_group FROM users WHERE user_id=$1", user_id)
    return tuple(row) if row else (None, None, None)


async def list_entities(kind: str, search: str = "") -> list[str]:
    field = "teacher" if kind == "teacher" else "group_name"
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"SELECT DISTINCT {field} FROM schedules s JOIN schedule_periods p ON p.id=s.period_id WHERE p.status='active' AND s.status='scheduled' AND {field} ILIKE $1 ORDER BY {field} LIMIT 200", f"%{search}%")
    return [r[0] for r in rows]


async def available_months() -> list[tuple[int, int]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT year,month FROM schedule_periods WHERE status='active' ORDER BY year DESC,month DESC")
    return [(r['year'], r['month']) for r in rows]


async def fetch_schedules(*, kind: str | None = None, value: str | None = None,
                          start: date | None = None, end: date | None = None,
                          period_year: int | None = None, period_month: int | None = None) -> list[dict[str, Any]]:
    pool = await get_pool()
    where = ["p.status='active'"]
    args: list[Any] = []
    def param(v: Any) -> str:
        args.append(v)
        return f"${len(args)}"
    if kind and value:
        field = "s.teacher" if kind == "teacher" else "s.group_name"
        where.append(f"{field} ILIKE {param(value)}")
    if period_year is not None and period_month is not None:
        where.append(f"p.year={param(period_year)} AND p.month={param(period_month)}")
    if start:
        where.append(f"d.display_date >= {param(start)}")
    if end:
        where.append(f"d.display_date <= {param(end)}")
    sql = f"""SELECT s.*, d.display_date
        FROM schedules s JOIN schedule_periods p ON p.id=s.period_id
        CROSS JOIN LATERAL (
          SELECT s.lesson_date AS display_date WHERE s.lesson_date IS NOT NULL
          UNION ALL
          SELECT dates.day::date FROM generate_series(make_date(p.year,p.month,1),
            (make_date(p.year,p.month,1) + interval '1 month - 1 day')::date, interval '1 day') AS dates(day)
          WHERE s.lesson_date IS NULL AND extract(isodow FROM dates.day)::int=s.day_index
        ) d
        WHERE {' AND '.join(where)} ORDER BY d.display_date,s.pair_number NULLS LAST,s.time_range"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
    # A dated monthly schedule replaces weekly rows for each date it covers.
    dated = {r['display_date'] for r in rows if r['lesson_date'] is not None}
    return [dict(r) for r in rows if r['lesson_date'] is not None or r['display_date'] not in dated]


async def _replace_period_transaction(year: int, month: int, rows: list[dict[str, Any]], admin_id: int,
                                     filename: str, import_type: str, error_rows: int,
                                     duplicate_rows: int) -> int:
    """Insert validated version and activate atomically; previous active version is retained."""
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock($1)", year * 100 + month)
        imp = await conn.fetchrow("""INSERT INTO schedule_imports(file_name,admin_id,import_type,year,month,status,total_rows,success_rows,error_rows,duplicate_rows)
            VALUES($1,$2,$3,$4,$5,'processing',$6,0,$7,$8) RETURNING id""", filename, admin_id, import_type, year, month, len(rows), error_rows, duplicate_rows)
        period = await conn.fetchrow("""INSERT INTO schedule_periods(year,month,status,source_filename,uploaded_by)
            VALUES($1,$2,'draft',$3,$4) RETURNING id""", year, month, filename, admin_id)
        for r in rows:
            await conn.execute("""INSERT INTO schedules(period_id,teacher,group_name,day_of_week,day_index,lesson_date,pair_number,time_range,subject,lesson_type,room,status)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""", period['id'], r['teacher'], r['group_name'], r['day_of_week'], r['day_index'], r.get('lesson_date'), r.get('pair_number'), r['time_range'], r['subject'], r['lesson_type'], r['room'], r.get('status','scheduled'))
        await conn.execute("UPDATE schedule_periods SET status='archived' WHERE year=$1 AND month=$2 AND status='active'", year, month)
        await conn.execute("UPDATE schedule_periods SET status='active',activated_at=now() WHERE id=$1", period['id'])
        await conn.execute("UPDATE schedule_imports SET status='completed',success_rows=$2 WHERE id=$1", imp['id'], len(rows))
        return period['id']


async def replace_period(year: int, month: int, rows: list[dict[str, Any]], admin_id: int,
                        filename: str, import_type: str = "monthly", error_rows: int = 0,
                        duplicate_rows: int = 0) -> int:
    try:
        return await _replace_period_transaction(year, month, rows, admin_id, filename, import_type, error_rows, duplicate_rows)
    except Exception:
        # Preserve the failed attempt in the import history after the replacement transaction rolls back.
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""INSERT INTO schedule_imports(file_name,admin_id,import_type,year,month,status,total_rows,success_rows,error_rows,duplicate_rows)
                    VALUES($1,$2,$3,$4,$5,'failed',$6,0,$7,$8)""", filename, admin_id, import_type,
                    year, month, len(rows), error_rows, duplicate_rows)
        except Exception:
            pass
        raise


async def save_import_session(admin_id: int, year: int, month: int, import_type: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO schedule_import_sessions(admin_id,year,month,import_type)
            VALUES($1,$2,$3,$4) ON CONFLICT(admin_id) DO UPDATE SET year=EXCLUDED.year,
            month=EXCLUDED.month,import_type=EXCLUDED.import_type,created_at=now()""", admin_id, year, month, import_type)


async def get_import_session(admin_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT year,month,import_type FROM schedule_import_sessions WHERE admin_id=$1", admin_id)
    return dict(row) if row else None


async def stage_import(admin_id: int, session: dict, filename: str, report: dict) -> int:
    pool = await get_pool()
    serializable = [{**r, "lesson_date": r["lesson_date"].isoformat() if r.get("lesson_date") else None} for r in report["rows"]]
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""INSERT INTO schedule_import_staging(admin_id,year,month,import_type,file_name,rows,errors,duplicate_count,total_rows)
            VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8,$9) RETURNING id""",
            admin_id, session["year"], session["month"], session["import_type"], filename,
            json.dumps(serializable, ensure_ascii=False), json.dumps(report["errors"], ensure_ascii=False), report["duplicates"], report["total"])
    return row["id"]


async def claim_staged_import(staging_id: int, admin_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("UPDATE schedule_import_staging SET status='processing' WHERE id=$1 AND admin_id=$2 AND status='pending' RETURNING *", staging_id, admin_id)
    return dict(row) if row else None


async def mark_staged_import(staging_id: int, status: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE schedule_import_staging SET status=$2 WHERE id=$1 AND status IN ('pending','processing')", staging_id, status)
