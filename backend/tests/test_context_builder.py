from pathlib import Path

from app.plugins.registry import PluginRegistry
from app.services.context_builder import JAIN_SYSTEM_PROMPT_BASE, build_system_prompt

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def test_system_prompt_includes_base_and_skills():
    reg = PluginRegistry(plugins_dir=FIXTURES)
    reg.load_all()

    prompt = build_system_prompt(reg)
    assert JAIN_SYSTEM_PROMPT_BASE in prompt
    assert "yardsailing.find-sales" in prompt
    assert "Find yard sales" in prompt
    assert "small-talk.chat" in prompt


def test_system_prompt_empty_registry():
    reg = PluginRegistry(plugins_dir=FIXTURES / "__nonexistent__")
    reg.load_all()

    prompt = build_system_prompt(reg)
    assert JAIN_SYSTEM_PROMPT_BASE in prompt
