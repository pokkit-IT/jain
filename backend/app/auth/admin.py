from fastapi import Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.config import settings
from app.models.user import User


def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    """Require that the authenticated user's email is in JAIN_ADMIN_EMAILS.

    Raises 403 for non-admins, propagates 401 from get_current_user for
    anonymous callers.
    """
    if user.email.lower() not in settings.admin_emails:
        raise HTTPException(status_code=403, detail="admin only")
    return user
