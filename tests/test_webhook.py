def test_webhook_health_and_secret_guard(monkeypatch):
    import asyncio
    monkeypatch.setenv("BOT_TOKEN", "123456:unit-test-token")
    monkeypatch.setenv("ADMIN_IDS", "101")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-secret-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    from starlette.requests import Request
    from fastapi import HTTPException
    from api.index import app, health, telegram_webhook

    assert app
    assert asyncio.run(health()) == {"status": "ok"}
    request = Request({"type": "http", "method": "POST", "path": "/api", "headers": [], "query_string": b""})
    try:
        asyncio.run(telegram_webhook(request, "wrong"))
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Webhook should reject an invalid secret")
