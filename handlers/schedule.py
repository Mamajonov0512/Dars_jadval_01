from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import get_settings
from services import schedule_service
import database

router = Router()
UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]


async def render(message: Message, start, end, year=None, month=None, user_id=None):
    uid = user_id or message.from_user.id
    if year is not None and month is not None and start != end:
        scope, key = "month", f"{year:04d}-{month:02d}"
        value, rows = await schedule_service.monthly_schedule(uid, year, month)
    elif start == end:
        scope, key = "day", start.isoformat()
        value, rows = await schedule_service.today_schedule(uid, start)
    elif (end - start).days == 2:
        scope, key = "three", start.isoformat()
        value, rows = await schedule_service.three_day_schedule(uid, start)
    else:
        scope, key = "week", start.isoformat()
        value, rows = await schedule_service.weekly_schedule(uid, start)
    if not value:
        return await message.answer("Avval o‘qituvchi yoki guruhni tanlang.")
    if not rows:
        return await message.answer("Tanlangan davr uchun dars jadvali topilmadi.")
    kind, _, _ = await database.get_selection(uid)
    await send_page(message, value, rows, scope, key, 0, kind=kind)


def page_text(value, rows, offset, scope, kind):
    title = {"day": "📅 BUGUNGI DARSLAR", "week": "🗓 HAFTALIK DARSLAR",
             "three": "📆 3 KUNLIK DARSLAR", "month": "📆 OYLIK DARSLAR",
             "all": "📆 ERTANGI BARCHA DARSLAR"}.get(scope, "📚 DARSLAR")
    if kind == "teacher":
        who = f"👨‍🏫 {value}"
    elif kind == "group":
        who = f"👥 Guruh: {value}"
    else:
        who = "🏫 Barcha guruhlar va o‘qituvchilar"
    lines = [title, who, ""]
    previous_date = None
    for r in rows[offset:offset + 8]:
        d = r["display_date"]
        if d != previous_date:
            if previous_date is not None:
                lines.extend(["━━━━━━━━", ""])
            lines.extend([f"📆 {d:%d.%m.%Y} | {UZ[d.weekday()]}", ""])
            previous_date = d
        else:
            lines.append("────────")
        subject_line = f"📚 {r['subject']} | {r['lesson_type']}"
        if r["status"] == "cancelled":
            subject_line += " | Bekor qilingan"
        if kind == "teacher":
            context_lines = [f"👥 Guruh: {r['group_name']}"]
        elif kind == "group":
            context_lines = [f"🎓 O‘qituvchi: {r['teacher']}"]
        else:
            context_lines = [f"🎓 O‘qituvchi: {r['teacher']}",
                             f"👥 Guruh: {r['group_name']}"]
        lines.extend([f"🕘 {r['pair_number'] or '—'}-Juftlik | {r['time_range']}",
                      *context_lines,
                      subject_line,
                      f"📍 Xona: {r['room']}"])
    lines.append(f"📊 Jami darslar: {len(rows)} ta")
    if offset > 0 or offset + 8 < len(rows):
        lines.append(f"📄 Ko‘rsatilmoqda: {offset + 1}–{min(offset + 8, len(rows))}/{len(rows)}")
    return "\n".join(lines)


def page_keyboard(scope, key, offset, total):
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"sch:{scope}:{max(0,offset-8)}:{key}"))
    if offset + 8 < total:
        buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"sch:{scope}:{offset+8}:{key}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None


async def send_page(message, value, rows, scope, key, offset, edit=False, kind=None):
    text = page_text(value, rows, offset, scope, kind)
    markup = page_keyboard(scope, key, offset, len(rows))
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("sch:"))
async def paginate(callback: CallbackQuery):
    _, scope, raw_offset, key = callback.data.split(":", 3)
    offset = int(raw_offset)
    if scope == "all":
        if callback.from_user.id not in get_settings().admin_ids:
            await callback.answer("Bu ro‘yxat faqat administratorlar uchun.", show_alert=True)
            return
        day = datetime.fromisoformat(key).date()
        value, rows = await schedule_service.all_day_schedule(day)
        kind = "all"
    elif scope == "month":
        year, month = (int(x) for x in key.split("-"))
        value, rows = await schedule_service.monthly_schedule(callback.from_user.id, year, month)
        kind, _, _ = await database.get_selection(callback.from_user.id)
    elif scope == "day":
        day = datetime.fromisoformat(key).date()
        value, rows = await schedule_service.today_schedule(callback.from_user.id, day)
        kind, _, _ = await database.get_selection(callback.from_user.id)
    elif scope == "three":
        day = datetime.fromisoformat(key).date()
        value, rows = await schedule_service.three_day_schedule(callback.from_user.id, day)
        kind, _, _ = await database.get_selection(callback.from_user.id)
    else:
        day = datetime.fromisoformat(key).date()
        value, rows = await schedule_service.weekly_schedule(callback.from_user.id, day)
        kind, _, _ = await database.get_selection(callback.from_user.id)
    if not value or not rows:
        await callback.answer("Jadval topilmadi", show_alert=True)
        return
    await send_page(callback.message, value, rows, scope, key,
                    min(offset, max(0, len(rows)-1)), edit=True, kind=kind)
    await callback.answer()


@router.message(F.text == "📅 Bugungi darslar")
async def today(message: Message):
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    await render(message, today, today, today.year, today.month)


@router.message(F.text == "📆 3 kunlik jadval")
async def three_day(message: Message):
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    await render(message, today, today + timedelta(days=2))


@router.message(F.text == "📆 Ertangi barcha darslar")
async def tomorrow_all(message: Message):
    if message.from_user.id not in get_settings().admin_ids:
        return await message.answer("Bu ro‘yxat faqat administratorlar uchun.")
    await show_tomorrow_all(message)


async def show_tomorrow_all(message: Message):
    tomorrow = datetime.now(ZoneInfo(get_settings().timezone)).date() + timedelta(days=1)
    value, rows = await schedule_service.all_day_schedule(tomorrow)
    if not rows:
        return await message.answer("Ertangi kunga dars topilmadi.")
    await send_page(message, value, rows, "all", tomorrow.isoformat(), 0, kind="all")


@router.message(F.text == "🗓 Haftalik jadval")
async def weekly(message: Message):
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    # Active month periods for each month intersecting the week are queried separately.
    await render(message, monday, sunday)


@router.message(F.text == "ℹ️ Yordam")
async def help_message(message: Message):
    await message.answer("O‘qituvchi jadvalini tanlab, bugungi, 3 kunlik, haftalik yoki oylik jadvalni ko‘ring. Qidirish uchun nom yuboring. Administratorlar /admin buyrug‘idan foydalanadi.")
