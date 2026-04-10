from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.auth import GoogleAuthRequest, GoogleAuthResponse, UserOut


def test_google_auth_request_requires_id_token():
    req = GoogleAuthRequest(id_token="eyJ.fake.token")
    assert req.id_token == "eyJ.fake.token"


def test_google_auth_request_rejects_missing_id_token():
    with pytest.raises(ValidationError):
        GoogleAuthRequest.model_validate({})


def test_user_out_serializes():
    uid = uuid4()
    out = UserOut(
        id=uid,
        email="jim@example.com",
        name="Jim",
        picture_url="https://x.jpg",
    )
    dumped = out.model_dump()
    assert dumped["id"] == uid
    assert dumped["email"] == "jim@example.com"
    assert dumped["picture_url"] == "https://x.jpg"


def test_user_out_allows_null_picture():
    out = UserOut(id=uuid4(), email="a@b.c", name="A", picture_url=None)
    assert out.picture_url is None


def test_google_auth_response_shape():
    resp = GoogleAuthResponse(
        access_token="jwt-here",
        user=UserOut(id=uuid4(), email="a@b.c", name="A", picture_url=None),
    )
    assert resp.access_token == "jwt-here"
    assert resp.user.email == "a@b.c"
