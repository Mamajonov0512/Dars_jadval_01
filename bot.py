from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from handlers import start, admin, selection, schedule, monthly_schedule, upload


def create_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties())


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_routers(start.router, admin.router, monthly_schedule.router, schedule.router, selection.router, upload.router)
    return dp
