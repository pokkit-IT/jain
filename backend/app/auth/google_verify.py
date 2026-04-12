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

    Accepts tokens issued for either the web or iOS client ID, since the
    native iOS flow produces tokens with the iOS client ID as audience.

    Returns the extracted claims on success. Raises InvalidGoogleTokenError
    on any failure (bad signature, wrong audience, expired, malformed, etc.).
    """
    allowed_audiences = [
        cid for cid in [settings.GOOGLE_CLIENT_ID, settings.GOOGLE_IOS_CLIENT_ID] if cid
    ]
    last_error: Exception | None = None
    for audience in allowed_audiences:
        try:
            claims = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                audience,
            )
            break
        except ValueError as e:
            last_error = e
            continue
    else:
        raise InvalidGoogleTokenError(str(last_error)) from last_error

    return VerifiedGoogleClaims(
        sub=claims["sub"],
        email=claims["email"],
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name", ""),
        picture=claims.get("picture"),
    )
