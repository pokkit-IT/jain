from app.plugins.nutrition.tools import TOOLS, set_macro_targets_handler


def test_set_macro_targets_tool_is_auth_required():
    t = next(t for t in TOOLS if t.name == "set_macro_targets")
    assert t.auth_required is True
    assert t.handler is set_macro_targets_handler


async def test_set_targets_rejects_missing_user(session_and_user):
    session, _ = session_and_user
    result = await set_macro_targets_handler({"calorie_target": 1800}, user=None, db=session)
    assert result["status"] == "error"


async def test_set_targets_updates_only_given_fields(session_and_user):
    session, user = session_and_user

    r1 = await set_macro_targets_handler(
        {"protein_g": 180, "tone_mode": "ruthless-mentor"},
        user=user, db=session,
    )
    assert r1["status"] == "ok"
    assert r1["data"]["protein_g"] == 180
    assert r1["data"]["tone_mode"] == "ruthless-mentor"
    assert r1["data"]["calorie_target"] == 2000

    r2 = await set_macro_targets_handler(
        {"calorie_target": 1800}, user=user, db=session,
    )
    assert r2["data"]["calorie_target"] == 1800
    assert r2["data"]["protein_g"] == 180


async def test_set_targets_returns_full_profile(session_and_user):
    session, user = session_and_user
    r = await set_macro_targets_handler(
        {"calorie_target": 1500}, user=user, db=session,
    )
    data = r["data"]
    assert set(data.keys()) >= {
        "user_id", "calorie_target", "protein_g", "carbs_g", "fat_g",
        "fiber_g", "tone_mode", "goals",
    }
