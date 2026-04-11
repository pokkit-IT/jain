import json
from pathlib import Path

from app.engine.base import ToolCall
from app.engine.tool_executor import ToolExecutor
from app.plugins.core.loaders import InternalPluginLoader
from app.plugins.core.registry import PluginRegistry


async def test_hello_plugin_end_to_end():
    """Loader discovers _hello, registry has it, tool executor dispatches
    the handler, result is the expected greeting."""
    plugins_dir = Path(__file__).parent.parent / "app" / "plugins"
    registry = PluginRegistry(plugins_dir=plugins_dir)
    InternalPluginLoader(plugins_dir=plugins_dir).load_all(registry)

    assert registry.get_plugin("_hello") is not None

    _, tool = registry.find_tool("hello_world")
    assert tool is not None
    assert tool.handler is not None

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall(id="tc1", name="hello_world", arguments={"who": "jim"}),
        user=None,
    )
    payload = json.loads(result.content)
    assert payload == {"greeting": "hi, jim"}
