from dataclasses import dataclass

# NOTE: google.auth.transport.requests requires the `requests` package, which
# is not installed (Task 1 deps did not pull it in, and this task forbids new
# installs). google.auth.transport._http_client is the stdlib-only transport
# shipped with google-auth and is used here instead. Swap to
# `google.auth.transport.requests` if `requests` is added to deps later.
from google.auth.transport import _http_client as google_transport
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
            google_transport.Request(),
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
