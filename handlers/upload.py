from io import BytesIO
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database
from config import get_settings
from services.import_service import validate_upload, activate_staged_import

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


@router.message(Command("import"))
@router.message(Command("import_weekly"))
async def begin_import(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("Bu amal faqat administratorlar uchun.")
    # Telegram places a command sent with an attached document in `caption`.
    command_text = message.text or message.caption or ""
    match = re.fullmatch(r"/(import|import_weekly)(?:@\w+)?\s+(\d{4})-(\d{1,2})", command_text.strip())
    if not match:
        return await message.answer("Format: /import 2026-11\nTakroriy haftalik jadval uchun: /import_weekly 2026-11")
    year, month = int(match.group(2)), int(match.group(3))
    if not 2000 <= year <= 2100 or not 1 <= month <= 12:
        return await message.answer("Yil 2000–2100, oy 1–12 oralig‘ida bo‘lishi kerak.")
    import_type = "weekly" if match.group(1) == "import_weekly" else "monthly"
    await database.save_import_session(message.from_user.id, year, month, import_type)
    if message.document:
        return await process_excel(message, {"year": year, "month": month, "import_type": import_type})
    await message.answer(f"{year}-yil {month}-oy uchun .xlsx fayl yuboring. Fayl hajmi {get_settings().max_upload_mb} MB gacha.")


@router.message(F.document)
async def receive_excel(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("Fayl yuklash faqat administratorlarga ruxsat etilgan.")
    session = await database.get_import_session(message.from_user.id)
    if not session:
        return await message.answer("Avval davrni belgilang: /import 2026-11")
    await process_excel(message, session)


async def process_excel(message: Message, session: dict):
    doc = message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".xlsx"):
        return await message.answer("Faqat .xlsx fayli qabul qilinadi. .xls qo‘llab-quvvatlanmaydi.")
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if doc.file_size and doc.file_size > max_bytes:
        return await message.answer(f"Fayl {get_settings().max_upload_mb} MB chegarasidan katta.")
    stream = BytesIO()
    await message.bot.download(doc, destination=stream)
    try:
        report = validate_upload(stream.getvalue(), doc.file_name, session["year"], session["month"], max_bytes)
    except ValueError as exc:
        return await message.answer(str(exc))
    if not report["rows"]:
        detail = "\n".join(report["errors"][:15]) or "Yaroqli qator topilmadi"
        return await message.answer(f"Import qilinadigan qator yo‘q.\n{detail}")
    stage_id = await database.stage_import(message.from_user.id, session, doc.file_name, report)
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM schedule_periods WHERE year=$1 AND month=$2 AND status='active')", session["year"], session["month"])
    details = "\n".join(report["errors"][:12]) or "Xato qator yo‘q"
    prompt = (f"Davr: {session['year']}-{session['month']:02d}\nJami: {report['total']} | Yaroqli: {len(report['rows'])} | Xato: {len(report['errors'])} | Takroriy: {report['duplicates']}\n"
              + ("⚠️ Ushbu oy uchun faol jadval bor. Tasdiqlasangiz, yangi jadval faollashib, eskisi arxivlanadi.\n" if exists else "Importni tasdiqlaysizmi?\n")
              + details)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Importni tasdiqlash", callback_data=f"import_ok:{stage_id}"),
        InlineKeyboardButton(text="Bekor qilish", callback_data=f"import_no:{stage_id}")]])
    await message.answer(prompt[:3900], reply_markup=keyboard)


@router.callback_query(F.data.startswith("import_ok:"))
async def confirm_import(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Ruxsat yo‘q", show_alert=True)
    stage_id = int(callback.data.split(":")[1])
    try:
        outcome = await activate_staged_import(stage_id, callback.from_user.id)
    except Exception:
        return await callback.answer("Import bajarilmadi; avvalgi faol jadval saqlanib qoldi.", show_alert=True)
    if not outcome:
        return await callback.answer("Import topilmadi yoki u allaqachon ishlatilgan.", show_alert=True)
    await callback.message.edit_text(f"✅ Import yakunlandi. Kiritildi: {outcome['imported']} | Rad etildi: {outcome['rejected']} | Takroriy: {outcome['duplicates']}\nFaol davr: {outcome['year']}-{outcome['month']:02d}.")
    await callback.answer()


@router.callback_query(F.data.startswith("import_no:"))
async def cancel_import(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Ruxsat yo‘q", show_alert=True)
    await database.mark_staged_import(int(callback.data.split(":")[1]), "cancelled")
    await callback.message.edit_text("Import bekor qilindi. Faol jadval o‘zgarmadi.")
    await callback.answer()
