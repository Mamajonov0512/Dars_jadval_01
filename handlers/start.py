from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database
from config import get_settings

router = Router()
MENU = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📚 O‘qituvchi bo‘yicha"), KeyboardButton(text="👥 Guruh bo‘yicha")],
    [KeyboardButton(text="📅 Bugungi darslar"), KeyboardButton(text="🗓 Haftalik jadval")],
    [KeyboardButton(text="📆 Oylik dars jadvali"), KeyboardButton(text="🔎 Qidirish")],
    [KeyboardButton(text="ℹ️ Yordam")],
], resize_keyboard=True)
TEACHER_MENU = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📅 Bugungi darslar"), KeyboardButton(text="🗓 Haftalik jadval")],
    [KeyboardButton(text="📆 Oylik dars jadvali"), KeyboardButton(text="ℹ️ Yordam")],
], resize_keyboard=True)


async def show_teacher_choices(message: Message, offset: int = 0, edit: bool = False):
    teachers = await database.list_entities("teacher")
    if not teachers:
        return await message.answer("Hozircha o‘qituvchilar jadvali kiritilmagan. Keyinroq /start ni bosing.")
    page_size = 30
    buttons = [[InlineKeyboardButton(text=name[:60], callback_data=f"selfteacher:{i}")]
               for i, name in enumerate(teachers[offset:offset + page_size], start=offset)]
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"teacherpage:{max(0, offset-page_size)}"))
    if offset + page_size < len(teachers):
        nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"teacherpage:{offset+page_size}"))
    if nav:
        buttons.append(nav)
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "Davom etish uchun o‘z ism-familiyangizni tanlang:"
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.message(CommandStart())
async def start(message: Message):
    user = message.from_user
    is_admin = user.id in get_settings().admin_ids
    await database.upsert_user(user.id, user.full_name, user.username, is_admin)
    if is_admin:
        await message.answer("Assalomu alaykum, administrator! Menyudan kerakli bo‘limni tanlang. /admin — boshqaruv.", reply_markup=MENU)
        return
    selected_type, selected_teacher, _ = await database.get_selection(user.id)
    if selected_type == "teacher" and selected_teacher:
        await message.answer(f"Assalomu alaykum! Siz tanlagan o‘qituvchi: {selected_teacher}. Sizga faqat shu o‘qituvchining jadvali ko‘rsatiladi.", reply_markup=TEACHER_MENU)
        return
    await show_teacher_choices(message)


@router.callback_query(F.data.startswith("teacherpage:"))
async def teacher_page(callback: CallbackQuery):
    if callback.from_user.id in get_settings().admin_ids:
        return await callback.answer("Administrator umumiy menyudan foydalanadi.", show_alert=True)
    selected_type, selected_teacher, _ = await database.get_selection(callback.from_user.id)
    if selected_type == "teacher" and selected_teacher:
        return await callback.answer(f"Sizning tanlovingiz: {selected_teacher}", show_alert=True)
    await show_teacher_choices(callback.message, int(callback.data.split(":")[1]), edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("selfteacher:"))
async def choose_self_teacher(callback: CallbackQuery):
    if callback.from_user.id in get_settings().admin_ids:
        return await callback.answer("Administrator bu tanlov bilan cheklanmaydi.", show_alert=True)
    selected_type, selected_teacher, _ = await database.get_selection(callback.from_user.id)
    if selected_type == "teacher" and selected_teacher:
        return await callback.answer(f"Tanlovingiz allaqachon saqlangan: {selected_teacher}", show_alert=True)
    teachers = await database.list_entities("teacher")
    index = int(callback.data.split(":")[1])
    if index < 0 or index >= len(teachers):
        return await callback.answer("Ro‘yxat yangilangan. /start ni qayta bosing.", show_alert=True)
    name = teachers[index]
    await database.set_selection(callback.from_user.id, "teacher", name)
    await callback.message.edit_text(f"Tanlov saqlandi: {name}\nEndi bot sizga faqat shu o‘qituvchining jadvalini ko‘rsatadi.")
    await callback.message.answer("Kerakli jadval turini tanlang:", reply_markup=TEACHER_MENU)
    await callback.answer("Tanlov saqlandi")


