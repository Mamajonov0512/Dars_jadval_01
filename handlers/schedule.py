from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import get_settings
from services import schedule_service

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
    else:
        scope, key = "week", start.isoformat()
        value, rows = await schedule_service.weekly_schedule(uid, start)
    if not value:
        return await message.answer("Avval o‘qituvchi yoki guruhni tanlang.")
    if not rows:
        return await message.answer("Tanlangan davr uchun dars jadvali topilmadi.")
    await send_page(message, value, rows, scope, key, 0)


def page_text(value, rows, offset):
    lines = [f"📚 {value} · {offset + 1}–{min(offset + 8, len(rows))}/{len(rows)}"]
    for r in rows[offset:offset + 8]:
        d = r["display_date"]
        label = f"❌ Bekor qilingan: {r['subject']}" if r["status"] == "cancelled" else r["subject"]
        lines.append(f"\n{d:%d.%m.%Y} — {UZ[d.weekday()]} | {r['pair_number'] or '—'}-juftlik ({r['time_range']})\n{label} · {r['lesson_type']}\nGuruh: {r['group_name']} · Xona: {r['room']}\nO‘qituvchi: {r['teacher']}")
    return "\n".join(lines)


def page_keyboard(scope, key, offset, total):
    buttons = []
    if offset > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"sch:{scope}:{max(0,offset-8)}:{key}"))
    if offset + 8 < total:
        buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"sch:{scope}:{offset+8}:{key}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None


async def send_page(message, value, rows, scope, key, offset, edit=False):
    text = page_text(value, rows, offset)
    markup = page_keyboard(scope, key, offset, len(rows))
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("sch:"))
async def paginate(callback: CallbackQuery):
    _, scope, raw_offset, key = callback.data.split(":", 3)
    offset = int(raw_offset)
    if scope == "month":
        year, month = (int(x) for x in key.split("-"))
        value, rows = await schedule_service.monthly_schedule(callback.from_user.id, year, month)
    elif scope == "day":
        day = datetime.fromisoformat(key).date()
        value, rows = await schedule_service.today_schedule(callback.from_user.id, day)
    else:
        day = datetime.fromisoformat(key).date()
        value, rows = await schedule_service.weekly_schedule(callback.from_user.id, day)
    if not value or not rows:
        await callback.answer("Jadval topilmadi", show_alert=True)
        return
    await send_page(callback.message, value, rows, scope, key, min(offset, max(0, len(rows)-1)), edit=True)
    await callback.answer()


@router.message(F.text == "📅 Bugungi darslar")
async def today(message: Message):
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    await render(message, today, today, today.year, today.month)


@router.message(F.text == "🗓 Haftalik jadval")
async def weekly(message: Message):
    today = datetime.now(ZoneInfo(get_settings().timezone)).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    # Active month periods for each month intersecting the week are queried separately.
    await render(message, monday, sunday)


@router.message(F.text == "ℹ️ Yordam")
async def help_message(message: Message):
    await message.answer("O‘qituvchi yoki guruhni tanlab, bugungi, haftalik yoki oylik jadvalni ko‘ring. Qidirish uchun nom yuboring. Administratorlar /admin buyrug‘idan foydalanadi.")
