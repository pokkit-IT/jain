from unittest.mock import patch

import pytest

from app.auth.google_verify import (
    InvalidGoogleTokenError,
    VerifiedGoogleClaims,
    verify_id_token,
)


def test_verify_valid_token_returns_dataclass():
    fake_claims = {
        "sub": "google-user-123",
        "email": "jim@example.com",
        "email_verified": True,
        "name": "Jim Shelly",
        "picture": "https://lh3.googleusercontent.com/jim",
    }
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = fake_claims
        result = verify_id_token("fake-id-token")

    assert isinstance(result, VerifiedGoogleClaims)
    assert result.sub == "google-user-123"
    assert result.email == "jim@example.com"
    assert result.email_verified is True
    assert result.name == "Jim Shelly"
    assert result.picture == "https://lh3.googleusercontent.com/jim"


def test_verify_invalid_token_raises():
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.side_effect = ValueError("Wrong audience")
        with pytest.raises(InvalidGoogleTokenError):
            verify_id_token("fake-id-token")


def test_verify_missing_email_verified_defaults_false():
    fake_claims = {
        "sub": "google-user-123",
        "email": "jim@example.com",
        "name": "Jim Shelly",
    }
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = fake_claims
        result = verify_id_token("fake-id-token")

    assert result.email_verified is False


def test_verify_missing_picture_is_none():
    fake_claims = {
        "sub": "google-user-123",
        "email": "jim@example.com",
        "email_verified": True,
        "name": "Jim",
    }
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = fake_claims
        result = verify_id_token("fake-id-token")

    assert result.picture is None


def test_verify_passes_client_id_to_google():
    from app.config import settings

    fake_claims = {
        "sub": "x",
        "email": "x@y.z",
        "email_verified": True,
        "name": "x",
    }
    with patch("app.auth.google_verify.google_id_token.verify_oauth2_token") as mock_verify:
        mock_verify.return_value = fake_claims
        verify_id_token("token-str")

    args, kwargs = mock_verify.call_args
    # Called as verify_oauth2_token(token, request, client_id)
    assert args[0] == "token-str"
    assert args[2] == settings.GOOGLE_CLIENT_ID
