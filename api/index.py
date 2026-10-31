from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request

from bot import create_bot, create_dispatcher
from config import get_settings
from database import close_pool

settings = get_settings()
if not settings.webhook_secret:
    raise RuntimeError("WEBHOOK_SECRET muhit o‘zgaruvchisi belgilanmagan")
bot = create_bot(settings.bot_token)
dispatcher = create_dispatcher()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await bot.session.close()
    await close_pool()


app = FastAPI(title="Dars jadvali Telegram webhook", lifespan=lifespan)


@app.get("/")
@app.get("/api")
async def health():
    return {"status": "ok"}


@app.post("/api")
@app.post("/")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        payload = await request.json()
        update = Update.model_validate(payload, context={"bot": bot})
        await dispatcher.feed_update(bot, update)
    except Exception as exc:
        # Do not include request bodies, tokens, or database connection strings in logs.
        import logging
        logging.getLogger(__name__).exception("Webhook yangilanishini qayta ishlashda xatolik: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Update processing failed") from exc
    return {"ok": True}
