from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config import settings


class InvalidGoogleTokenError(Exception):
    """Raised when a Google ID token fails verification."""


@dataclass(frozen=True)
class VerifiedGoogleClaims:
    sub: str
    email: str
    email_verified: bool
    name: str
    picture: str | None


def verify_id_token(id_token_str: str) -> VerifiedGoogleClaims:
    """Verify a Google ID token against Google's public keys.

    Returns the extracted claims on success. Raises InvalidGoogleTokenError
    on any failure (bad signature, wrong audience, expired, malformed, etc.).
    """
    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        raise InvalidGoogleTokenError(str(e)) from e

    return VerifiedGoogleClaims(
        sub=claims["sub"],
        email=claims["email"],
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name", ""),
        picture=claims.get("picture"),
    )
