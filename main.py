import asyncio

from bot import create_bot, create_dispatcher
from config import get_settings
from database import close_pool


async def main() -> None:
    settings = get_settings()
    bot = create_bot(settings.bot_token)
    dp = create_dispatcher()
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
