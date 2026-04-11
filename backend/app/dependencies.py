from functools import lru_cache
from pathlib import Path

from .config import settings
from .engine.anthropic_provider import AnthropicProvider
from .engine.base import LLMProvider
from .engine.tool_executor import ToolExecutor
from .plugins.core.loaders import ExternalPluginLoader, InternalPluginLoader
from .plugins.core.registry import PluginRegistry
from .services.chat_service import ChatService


@lru_cache(maxsize=1)
def _registry_singleton() -> PluginRegistry:
    reg = PluginRegistry(plugins_dir=settings.PLUGINS_DIR)
    # Internal plugins live inside JAIN's own source tree.
    internal_dir = Path(__file__).parent / "plugins"
    InternalPluginLoader(plugins_dir=internal_dir).load_all(reg)
    # External plugins: Stage 2 still reads the jain-plugins filesystem path.
    # Stage 4 will replace this with DB-backed loading.
    ExternalPluginLoader(plugins_dir=settings.PLUGINS_DIR).load_all(reg)
    return reg


def get_registry() -> PluginRegistry:
    return _registry_singleton()


def _make_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "anthropic":
        return AnthropicProvider(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.LLM_MODEL,
        )
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")


@lru_cache(maxsize=1)
def _chat_service_singleton() -> ChatService:
    registry = get_registry()
    provider = _make_provider()
    executor = ToolExecutor(registry=registry)
    return ChatService(registry=registry, provider=provider, tool_executor=executor)


def get_chat_service() -> ChatService:
    return _chat_service_singleton()


def reset_registry_for_tests() -> None:
    """Clear the cached registry singleton. Tests only."""
    _registry_singleton.cache_clear()
    _chat_service_singleton.cache_clear()
