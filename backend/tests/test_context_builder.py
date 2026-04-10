from pathlib import Path
from uuid import uuid4

from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.services.context_builder import JAIN_SYSTEM_PROMPT_BASE, build_system_prompt

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def test_system_prompt_includes_base_and_skills():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    prompt = build_system_prompt(reg, user=None)
    assert JAIN_SYSTEM_PROMPT_BASE in prompt
    assert "yardsailing.find-sales" in prompt
    assert "Find yard sales" in prompt
    assert "small-talk.chat" in prompt


def test_system_prompt_empty_registry():
    reg = PluginRegistry(plugins_dir=FIXTURES / "__nonexistent__")
    reg.load_all()

    prompt = build_system_prompt(reg, user=None)
    assert JAIN_SYSTEM_PROMPT_BASE in prompt


def test_system_prompt_anonymous_user_has_not_authenticated_marker():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    prompt = build_system_prompt(reg, user=None)
    assert "not authenticated" in prompt.lower()


def test_system_prompt_authenticated_user_shows_email_and_name():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    user = User(
        id=uuid4(),
        email="jim@example.com",
        name="Jim Shelly",
        email_verified=True,
        google_sub="g-jim",
    )
    prompt = build_system_prompt(reg, user=user)
    assert "jim@example.com" in prompt
    assert "Jim Shelly" in prompt
    assert "not authenticated" not in prompt.lower()
