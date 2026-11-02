import logging

from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database
from .schedule import render

router = Router()
MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


@router.message(F.text == "📆 Oylik dars jadvali")
async def month_menu(message: Message):
    months = await database.available_months()
    years = sorted({y for y, _ in months}, reverse=True)
    if not years:
        return await message.answer("Hozircha faol oylik jadval kiritilmagan.")
    buttons = [[InlineKeyboardButton(text=str(y), callback_data=f"year:{y}")] for y in years]
    await message.answer("Yilni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("year:"))
async def select_year(callback: CallbackQuery):
    await callback.answer()
    try:
        year = int(callback.data.split(":")[1])
        months = {m for y, m in await database.available_months() if y == year}
        if not months:
            return await callback.message.edit_text("Bu yil uchun faol oylik jadval topilmadi.")
        buttons = [[InlineKeyboardButton(text=MONTHS[m-1], callback_data=f"month:{year}:{m}")] for m in sorted(months)]
        await callback.message.edit_text("Oyni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception as exc:
        logging.getLogger(__name__).exception("Oylar ro‘yxatini chiqarishda xatolik: %s", type(exc).__name__)
        await callback.message.answer("Oylar ro‘yxatini ochib bo‘lmadi. Keyinroq qayta urinib ko‘ring.")


@router.callback_query(F.data.startswith("month:"))
async def select_month(callback: CallbackQuery):
    await callback.answer()
    try:
        _, year, month = callback.data.split(":")
        kind, teacher, group = await database.get_selection(callback.from_user.id)
        if not kind or not (teacher if kind == "teacher" else group):
            return await callback.message.answer("Avval bosh menyudan o‘qituvchi yoki guruhni tanlang, keyin oylik jadvalni oching.")
        from datetime import date
        from calendar import monthrange
        await render(callback.message, date(int(year), int(month), 1), date(int(year), int(month), monthrange(int(year), int(month))[1]), int(year), int(month), callback.from_user.id)
    except Exception as exc:
        logging.getLogger(__name__).exception("Oylik jadvalni chiqarishda xatolik: %s", type(exc).__name__)
        await callback.message.answer("Oylik jadvalni chiqarib bo‘lmadi. Keyinroq qayta urinib ko‘ring.")
