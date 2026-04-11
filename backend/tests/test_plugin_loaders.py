from pathlib import Path

from app.plugins.core.loaders import ExternalPluginLoader, InternalPluginLoader
from app.plugins.core.registry import PluginRegistry

FIXTURES = Path(__file__).parent / "fixtures" / "plugins"


def test_internal_loader_discovers_package_with_register_function(tmp_path):
    # Build a tiny plugin package on disk
    pkg = tmp_path / "demo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from app.plugins.core.types import PluginRegistration\n"
        "def register():\n"
        "    return PluginRegistration(name='demo', version='1', type='internal')\n"
    )
    # Marker so the manifest step has something to find
    (pkg / "plugin.json").write_text('{"name":"demo","version":"1","type":"internal",'
                                     '"description":"d","skills":[]}')

    registry = PluginRegistry(plugins_dir=tmp_path)
    loader = InternalPluginLoader(plugins_dir=tmp_path)
    loader.load_all(registry)

    plugin = registry.get_plugin("demo")
    assert plugin is not None
    assert plugin.manifest.name == "demo"
    assert plugin.manifest.type == "internal"


def test_external_loader_reads_existing_filesystem_path(tmp_path):
    """Stage 1 behavior: the external loader still reads a filesystem path.
    Eventually (Stage 4) it will read from the DB."""
    registry = PluginRegistry(plugins_dir=FIXTURES)
    loader = ExternalPluginLoader(plugins_dir=FIXTURES)
    loader.load_all(registry)

    names = [p.name for p in registry.list_plugins()]
    # The exact fixture set varies — at minimum, some external plugin should load.
    assert len(names) >= 1
