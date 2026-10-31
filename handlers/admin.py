import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database
from config import get_settings

router = Router()


def authorized(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


@router.message(Command("admin"))
async def admin_menu(message: Message):
    if not authorized(message.from_user.id):
        return await message.answer("Bu bo‘lim faqat administratorlar uchun.")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Oylik Excel import", callback_data="admin:import")],
        [InlineKeyboardButton(text="🗂 Jadval tarixi", callback_data="admin:history"), InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats")],
    ])
    await message.answer("Administrator boshqaruvi", reply_markup=keyboard)


@router.callback_query(F.data.startswith("admin:"))
async def admin_action(callback: CallbackQuery):
    if not authorized(callback.from_user.id):
        return await callback.answer("Bu amal faqat administratorlar uchun.", show_alert=True)
    action = callback.data.split(":", 1)[1]
    if action == "import":
        await callback.message.answer("Davrni tanlab yuboring: /import 2026-11\nTakroriy haftalik jadval: /import_weekly 2026-11")
    elif action == "history":
        await show_history(callback.message)
    elif action == "stats":
        await show_stats(callback.message)
    await callback.answer()


async def show_history(message: Message):
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id,year,month,status,source_filename FROM schedule_periods ORDER BY created_at DESC LIMIT 30")
    if not rows:
        return await message.answer("Importlar tarixi bo‘sh.")
    await message.answer("Jadvallar tarixi:\n" + "\n".join(
        f"#{r['id']} {r['year']}-{r['month']:02d} · {r['status']} · {r['source_filename'] or 'faylsiz'}" for r in rows))


async def show_stats(message: Message):
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchrow("""SELECT count(*) lessons,count(distinct teacher) teachers,count(distinct group_name) groups
          FROM schedules s JOIN schedule_periods p ON p.id=s.period_id WHERE p.status='active'""")
        latest = await conn.fetchrow("SELECT status,file_name FROM schedule_imports ORDER BY imported_at DESC LIMIT 1")
    latest_text = f"{latest['status']} · {latest['file_name']}" if latest else "yo‘q"
    await message.answer(f"Faol jadval: {result['lessons']} dars, {result['teachers']} o‘qituvchi, {result['groups']} guruh.\nOxirgi import: {latest_text}")


@router.message(Command("history"))
async def history(message: Message):
    if not authorized(message.from_user.id):
        return await message.answer("Bu amal faqat administratorlar uchun.")
    await show_history(message)


@router.message(Command("stats"))
async def stats(message: Message):
    if not authorized(message.from_user.id):
        return await message.answer("Bu amal faqat administratorlar uchun.")
    await show_stats(message)


@router.message(Command("archive"))
async def archive(message: Message):
    if not authorized(message.from_user.id):
        return await message.answer("Bu amal faqat administratorlar uchun.")
    match = re.fullmatch(r"/archive(?:@\w+)?\s+(\d+)", message.text or "")
    if not match:
        return await message.answer("Format: /archive PERIOD_ID — faol oy jadvalini arxivlash.")
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("UPDATE schedule_periods SET status='archived' WHERE id=$1 AND status='active'", int(match.group(1)))
    await message.answer("Jadval arxivlandi." if result == "UPDATE 1" else "Faol jadval topilmadi.")
