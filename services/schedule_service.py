from calendar import monthrange
from datetime import date, timedelta

import database


async def today_schedule(user_id: int, day: date):
    kind, teacher, group = await database.get_selection(user_id)
    value = teacher if kind == "teacher" else group
    if not value:
        return None, []
    return value, await database.fetch_schedules(kind=kind, value=value, start=day, end=day,
                                                period_year=day.year, period_month=day.month)


async def three_day_schedule(user_id: int, first_day: date):
    last_day = first_day + timedelta(days=2)
    kind, teacher, group = await database.get_selection(user_id)
    value = teacher if kind == "teacher" else group
    if not value:
        return None, []
    return value, await database.fetch_schedules(kind=kind, value=value, start=first_day, end=last_day)


async def all_day_schedule(day: date):
    return "Barcha darslar", await database.fetch_schedules(start=day, end=day)


async def weekly_schedule(user_id: int, day: date):
    monday = day - timedelta(days=day.weekday())
    sunday = monday + timedelta(days=6)
    kind, teacher, group = await database.get_selection(user_id)
    value = teacher if kind == "teacher" else group
    if not value:
        return value, []
    return value, await database.fetch_schedules(kind=kind, value=value, start=monday, end=sunday)


async def monthly_schedule(user_id: int, year: int, month: int):
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    kind, teacher, group = await database.get_selection(user_id)
    value = teacher if kind == "teacher" else group
    if not value:
        return value, []
    return value, await database.fetch_schedules(kind=kind, value=value, start=first, end=last,
                                                period_year=year, period_month=month)
