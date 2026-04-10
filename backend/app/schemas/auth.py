from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GoogleAuthRequest(BaseModel):
    id_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    picture_url: str | None = None


class GoogleAuthResponse(BaseModel):
    access_token: str
    user: UserOut
