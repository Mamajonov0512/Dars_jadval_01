from dataclasses import dataclass
import os
import re

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    database_url: str
    webhook_base_url: str
    webhook_secret: str
    max_upload_mb: int
    timezone: str
    port: int


def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "")
    admin_ids = frozenset(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())
    if not token:
        raise RuntimeError("BOT_TOKEN muhit o‘zgaruvchisi belgilanmagan")
    if not admin_ids:
        raise RuntimeError("ADMIN_IDS da kamida bitta administrator ID bo‘lishi kerak")
    webhook_url = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
    webhook_secret = os.getenv("WEBHOOK_SECRET", "")
    if webhook_url and not webhook_url.startswith("https://"):
        raise RuntimeError("WEBHOOK_BASE_URL HTTPS manzil bo‘lishi kerak")
    if webhook_secret and not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", webhook_secret):
        raise RuntimeError("WEBHOOK_SECRET faqat 1–256 ta harf, raqam, _ yoki - belgilaridan iborat bo‘lishi kerak")
    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "10"))
    if max_upload_mb < 1:
        raise RuntimeError("MAX_UPLOAD_MB kamida 1 bo‘lishi kerak")
    return Settings(token, admin_ids, os.getenv("DATABASE_URL", ""), webhook_url,
                    webhook_secret, max_upload_mb, os.getenv("TIMEZONE", "Asia/Tashkent"),
                    int(os.getenv("PORT", "8000")))
