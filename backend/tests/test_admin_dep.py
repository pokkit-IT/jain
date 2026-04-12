from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth.admin import get_current_admin_user
from app.config import settings
from app.models.user import User


@pytest.fixture
def admin_user():
    return User(
        id=uuid4(), email="admin@example.com", name="Admin", email_verified=True, google_sub="g1",
    )


@pytest.fixture
def normal_user():
    return User(
        id=uuid4(), email="user@example.com", name="User", email_verified=True, google_sub="g2",
    )


def test_admin_emails_parsed_from_setting():
    original = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com, other@example.com"
    try:
        assert settings.admin_emails == {"admin@example.com", "other@example.com"}
    finally:
        settings.JAIN_ADMIN_EMAILS = original


def test_admin_emails_case_insensitive():
    original = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "Admin@Example.COM"
    try:
        assert "admin@example.com" in settings.admin_emails
    finally:
        settings.JAIN_ADMIN_EMAILS = original


def test_get_current_admin_user_allows_admin(admin_user):
    original = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com"
    try:
        got = get_current_admin_user(user=admin_user)
        assert got is admin_user
    finally:
        settings.JAIN_ADMIN_EMAILS = original


def test_get_current_admin_user_rejects_non_admin(normal_user):
    original = settings.JAIN_ADMIN_EMAILS
    settings.JAIN_ADMIN_EMAILS = "admin@example.com"
    try:
        with pytest.raises(HTTPException) as exc:
            get_current_admin_user(user=normal_user)
        assert exc.value.status_code == 403
    finally:
        settings.JAIN_ADMIN_EMAILS = original
