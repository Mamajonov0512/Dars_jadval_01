"""Run once after deployment to register Telegram's webhook."""
import asyncio

from bot import create_bot
from config import get_settings


async def main():
    settings = get_settings()
    if not settings.webhook_base_url or not settings.webhook_secret:
        raise RuntimeError("WEBHOOK_BASE_URL va WEBHOOK_SECRET kerak")
    bot = create_bot(settings.bot_token)
    try:
        ok = await bot.set_webhook(url=f"{settings.webhook_base_url}/api", secret_token=settings.webhook_secret,
                                  allowed_updates=["message", "callback_query"], drop_pending_updates=False)
        print("Webhook sozlandi" if ok else "Webhook sozlanmadi")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
