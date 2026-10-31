from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database
from config import get_settings

router = Router()


async def choose(message: Message, kind: str, search: str = ""):
    if message.from_user.id not in get_settings().admin_ids:
        return await message.answer("O‘qituvchi jadvali siz /start da tanlagan ism bo‘yicha ko‘rsatiladi.")
    items = await database.list_entities(kind, search)
    if not items:
        return await message.answer("Mos yozuv topilmadi. Jadval kiritilganini tekshiring.")
    prefix = "teacher" if kind == "teacher" else "group"
    # Index keeps callback data short; the canonical value is reloaded from the database.
    buttons = [[InlineKeyboardButton(text=name[:60], callback_data=f"sel:{prefix}:{i}")] for i, name in enumerate(items[:35])]
    await message.answer("Ro‘yxatdan tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.message(F.text == "📚 O‘qituvchi bo‘yicha")
async def teachers(message: Message):
    await choose(message, "teacher")


@router.message(F.text == "👥 Guruh bo‘yicha")
async def groups(message: Message):
    await choose(message, "group")


@router.message(F.text == "🔎 Qidirish")
async def search_prompt(message: Message):
    if message.from_user.id not in get_settings().admin_ids:
        return await message.answer("Siz faqat /start da tanlagan o‘qituvchining jadvalini ko‘ra olasiz.")
    await message.answer("O‘qituvchi yoki guruh nomini yuboring:")


@router.callback_query(F.data.startswith("sel:"))
async def selected(callback: CallbackQuery):
    if callback.from_user.id not in get_settings().admin_ids:
        await callback.answer("Sizning jadval tanlovingiz faqat /start paytida belgilanadi.", show_alert=True)
        return
    _, kind, index = callback.data.split(":", 2)
    kind = "teacher" if kind == "teacher" else "group"
    values = await database.list_entities(kind)
    if int(index) >= len(values):
        await callback.answer("Ro‘yxat yangilangan. Qaytadan tanlang.", show_alert=True)
        return
    value = values[int(index)]
    await database.set_selection(callback.from_user.id, kind, value)
    await callback.answer("Tanlov saqlandi")
    await callback.message.answer(f"Tanlangan {('o‘qituvchi' if kind == 'teacher' else 'guruh')}: {value}\nJadvalni bugun, hafta yoki oy bo‘yicha oching.")


@router.message(F.text)
async def search_text(message: Message):
    if message.from_user.id not in get_settings().admin_ids:
        return
    query = message.text.strip()
    if len(query) < 2 or query.startswith("/"):
        return
    teachers = await database.list_entities("teacher", query)
    groups = await database.list_entities("group", query)
    entries = [("teacher", x) for x in teachers] + [("group", x) for x in groups]
    if not entries:
        return await message.answer("O‘qituvchi yoki guruh topilmadi.")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{('O‘qituvchi' if k == 'teacher' else 'Guruh')}: {v}"[:60],
                              callback_data=f"sel:{k}:{(await database.list_entities(k)).index(v)}")]
        for k, v in entries[:35]])
    await message.answer("Qidiruv natijalari:", reply_markup=keyboard)
