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
