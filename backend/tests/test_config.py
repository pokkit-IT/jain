from app.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.LLM_PROVIDER == "anthropic"
    assert s.LLM_MODEL == "claude-sonnet-4-20250514"
    assert s.DATABASE_URL.startswith("sqlite+aiosqlite")
    assert s.PLUGINS_DIR.endswith("plugins")


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "llama3")
    s = Settings()
    assert s.LLM_PROVIDER == "ollama"
    assert s.LLM_MODEL == "llama3"


def test_deprecation_warning_when_jain_service_key_set(caplog):
    import logging
    from app.config import settings, warn_if_service_key_set

    caplog.set_level(logging.WARNING, logger="jain.config")
    original = settings.JAIN_SERVICE_KEY
    settings.JAIN_SERVICE_KEY = "some-legacy-value"
    try:
        warn_if_service_key_set(settings)
        messages = [r.message for r in caplog.records if "jain.config" in r.name]
        assert any("JAIN_SERVICE_KEY" in m and "deprecated" in m.lower() for m in messages)
    finally:
        settings.JAIN_SERVICE_KEY = original
