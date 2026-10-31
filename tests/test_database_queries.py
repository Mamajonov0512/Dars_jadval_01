"""Small offline checks for application-level settings and authorization decisions."""
from config import Settings


def test_admin_check_is_exact_id_membership():
    settings = Settings("test-token", frozenset({12, 34}), "postgresql://unused", "", "", 10, "Asia/Tashkent", 8000)
    assert 12 in settings.admin_ids
    assert 123 not in settings.admin_ids


def test_environment_example_has_no_real_secret():
    from pathlib import Path
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "replace-with-real-token" in text
    assert "service_role" not in text
