from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.google_verify import InvalidGoogleTokenError, verify_id_token
from app.auth.jwt import sign_access_token
from app.database import get_db
from app.models.user import User
from app.schemas.auth import GoogleAuthRequest, GoogleAuthResponse, UserOut
from app.services.user_service import upsert_by_google

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/google", response_model=GoogleAuthResponse)
async def google_auth(
    req: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> GoogleAuthResponse:
    try:
        claims = verify_id_token(req.id_token)
    except InvalidGoogleTokenError:
        raise HTTPException(status_code=401, detail="invalid google token")

    if not claims.email_verified:
        raise HTTPException(status_code=401, detail="email not verified")

    user = await upsert_by_google(db, claims)
    token = sign_access_token(user)

    return GoogleAuthResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
