# Dars jadvali Telegram bot

Python 3.14 bot: aiogram 3, Supabase-hosted PostgreSQL, Excel `.xlsx` imports. The same handlers can run as a persistent polling worker or behind a Telegram webhook on Vercel. Vercel runs one request at a time per invocation; it never starts polling.

## Imkoniyatlar

- O‘qituvchi va guruh ro‘yxati, nom bo‘yicha qidirish, bugungi/haftalik/oylik jadval.
- Administrator uchun `.xlsx` tekshiruvi, xatolar va dublikatlar hisoboti, oldindan ko‘rish va alohida tasdiqlash.
- Import tasdiqlanganda yangi davr tranzaksiyada yoziladi va faollashtiriladi; avvalgi faol nusxa arxivlanadi. Xato bo‘lsa, avvalgi nusxa saqlanadi.
- Sana kiritilgan qatorlar muayyan darsni bildiradi. Sana bo‘lmagan qatorlar tanlangan oy davomida hafta kuniga ko‘ra takrorlanadigan dars deb olinadi. O‘sha sanada aniq dars bo‘lsa, takroriy qatorlar ko‘rinishda almashtiriladi.
- Import session va preview holati PostgreSQL’da saqlanadi; webhook qayta chaqirilganda ham saqlanib qoladi.
- Telegram administrator huquqi `ADMIN_IDS` bilan server tomonida tekshiriladi.
- Oddiy foydalanuvchi `/start` bosganda o‘qituvchilar ro‘yxatidan bir ismni tanlaydi; tanlov Telegram akkauntiga saqlanadi va keyingi ishga tushirishlarda o‘zgarmaydi. Unga shaxsiy jadval menyusi chiqadi, boshqa o‘qituvchi va guruhni tanlash server tomonida rad etiladi.
- O‘qituvchi tanlovi o‘zini o‘zi belgilashga asoslangan: tanlangan ism haqiqatan shu Telegram akkaunti egasi ekanini tasdiqlamaydi. Ism bo‘yicha haqiqiy tekshiruv zarur bo‘lsa, administrator beradigan kod yoki akkauntni oldindan tasdiqlash qo‘shish kerak.

## Mahalliy sozlash

1. Python 3.14 o‘rnating, virtual muhit yarating va `pip install -r requirements.txt` bajaring. Testlar uchun `pip install -r requirements-dev.txt` bajaring.
2. `.env.example` nusxasini `.env` deb saqlang. `BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_URL` qiymatlarini kiriting. Supabase pooled Postgres URL’ini `sslmode=require` bilan ishlating.
3. Supabase SQL Editor’da `supabase_schema.sql` faylini bir marta bajaring. U `public` jadvallarida RLS yoqadi, `anon` va `authenticated` rollariga to‘g‘ridan-to‘g‘ri ruxsat bermaydi. Bot server tomonida ishonchli PostgreSQL ulanishidan foydalanadi.
4. Polling rejimi uchun `python main.py` bajaring. Bitta bot tokenini polling va webhook rejimlarida bir vaqtda ishlatmang.
5. Testlar: `pytest -q`. Bot tokeni yoki haqiqiy Supabase loyihasi shart emas.

Oddiy foydalanuvchi birinchi marta `/start` bosganda o‘qituvchining ism-familiyasini tanlaydi. Tanlovdan keyin bot shu ismni Telegram akkauntiga saqlaydi. Administrator akkauntlari `ADMIN_IDS` orqali belgilanadi va umumiy menyudan foydalanishda davom etadi.

## Excel shakli

Birinchi qatorda sarlavha. Majburiy ustunlar: `Sana` yoki `Hafta kuni` ustunidan biri, `O‘qituvchi`, `Guruh`, `Juftlik`, `Vaqt`, `Fan`. Qo‘shimcha ustunlar: `Dars turi`, `Xona`, `Holat`, `Yil`, `Oy`. Sarlavhalarning inglizcha muqobillari ham taniladi. Sana `01.11.2026`, `2026-11-01`, Excel sana katagi yoki kun raqami ko‘rinishida bo‘lishi mumkin. `Holat` ustunida `Bekor` bo‘lsa, dars bekor qilingan deb saqlanadi. `.xls` qabul qilinmaydi.

Oylik aniq sanali fayl uchun administrator Telegram’da `/import 2026-11` yuboradi, Excel’ni biriktiradi, hisobotni tekshiradi va **Importni tasdiqlash** tugmasini bosadi. Takroriy haftalik fayl uchun `/import_weekly 2026-11` ishlatiladi.

## Vercel webhook orqali deploy

1. Loyiha papkasini GitHub repozitoriyasiga joylang va Vercel’da shu repozitoriyani import qiling. Python runtime hozir FastAPI/ASGI ilovasini `api/index.py` dagi `app` orqali aniqlaydi.
2. Vercel Project → Settings → Environment Variables’da `BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_URL`, `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET`, `MAX_UPLOAD_MB`, `TIMEZONE` kiriting. `WEBHOOK_BASE_URL` Vercel HTTPS domeni bo‘lsin. `WEBHOOK_SECRET` Telegram talablariga mos 1–256 belgili `[A-Za-z0-9_-]` random qiymat bo‘lsin.
3. Deploy qiling. Health endpoint: `https://<domen>/`.
4. Lokal `.env` fayliga Vercel’dagi ayni webhook sozlamalarini kiriting va bir marta `python set_webhook.py` bajaring. Skript Telegram `setWebhook` API’sini chaqiradi; muvaffaqiyat xabarini ko‘ring. Webhook manzili `https://<domen>/api`.
5. Telegram botga `/start` yuborib tekshiring. `getWebhookInfo` Telegram Bot API orqali webhook URL va oxirgi xato tafsilotlarini beradi. Vercel loglaridan runtime xatolarni ko‘ring.

Vercel funksiyasi faqat so‘rov kelganda ishlaydi, shu sababli u doimiy polling jarayoniga mos emas. Polling kerak bo‘lsa, Railway, Render worker, Fly.io yoki VPS’da `python main.py` buyrug‘i bilan doimiy worker ishga tushiring. Bitta bot tokenini webhook va polling rejimlarida bir vaqtda ishlatmang.

## Deploy’dan oldin tekshiriladigan narsalar

- Avval Supabase’da schema SQL’ni bajaring; bu repozitoriydagi kod tashqi loyihaga o‘zi ulanmaydi.
- `.env` ni GitHub’ga yubormang. Faqat `.env.example` kuzatiladi.
- Import fayli Telegram orqali yuboriladi; bot fayl nomi, kengaytmasi va maksimal hajmini tekshiradi.
- Ma’lumotlar bazasida `service_role` API key kerak emas: ilova server-only `DATABASE_URL` orqali ulanadi. Bu ulanish ma’lumotini hech qachon brauzerga yoki logga chiqarmang.

## Vercel muhit o‘zgaruvchilari

| O‘zgaruvchi | Maqsad |
| --- | --- |
| `BOT_TOKEN` | Telegram bot tokeni |
| `ADMIN_IDS` | Vergul bilan ajratilgan Telegram raqamli ID’lari |
| `DATABASE_URL` | Supabase PostgreSQL pooled connection URL |
| `WEBHOOK_BASE_URL` | Deploy qilingan HTTPS domeni |
| `WEBHOOK_SECRET` | Telegram webhook so‘rovi maxfiy sarlavhasi |
| `MAX_UPLOAD_MB` | Excel faylining eng katta hajmi |
| `TIMEZONE` | Odatda `Asia/Tashkent` |

## Hozirgi qamrov va sozlash

`supabase_schema.sql` ni Supabase’da qo‘llash va muhit o‘zgaruvchilarini hostingga kiritish kerak. Bu papkada Supabase loyihasi, bot tokeni yoki Vercel deployment ma’lumotlari berilmagan, shuning uchun haqiqiy baza, Telegram API yoki deploy holatini tekshirish imkoni yo‘q.
