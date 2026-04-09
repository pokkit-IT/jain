from functools import lru_cache

from .config import settings
from .engine.anthropic_provider import AnthropicProvider
from .engine.base import LLMProvider
from .engine.tool_executor import ToolExecutor
from .plugins.registry import PluginRegistry
from .services.chat_service import ChatService


@lru_cache(maxsize=1)
def _registry_singleton() -> PluginRegistry:
    reg = PluginRegistry(plugins_dir=settings.PLUGINS_DIR)
    reg.load_all()
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
