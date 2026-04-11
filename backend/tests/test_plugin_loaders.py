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


def test_get_registry_runs_both_loaders(monkeypatch, tmp_path):
    """get_registry() should invoke both InternalPluginLoader.load_all
    and ExternalPluginLoader.load_all on the shared registry."""
    from app import dependencies
    from app.plugins.core.registry import PluginRegistry

    dependencies.reset_registry_for_tests()
    monkeypatch.setattr(dependencies.settings, "PLUGINS_DIR", str(tmp_path))

    internal_called = {"v": False}
    external_called = {"v": False}

    real_internal = dependencies.InternalPluginLoader
    real_external = dependencies.ExternalPluginLoader

    class SpyInternal(real_internal):
        def load_all(self, registry: PluginRegistry) -> None:
            internal_called["v"] = True
            return super().load_all(registry)

    class SpyExternal(real_external):
        def load_all(self, registry: PluginRegistry) -> None:
            external_called["v"] = True
            return super().load_all(registry)

    monkeypatch.setattr(dependencies, "InternalPluginLoader", SpyInternal)
    monkeypatch.setattr(dependencies, "ExternalPluginLoader", SpyExternal)

    dependencies.get_registry()

    assert internal_called["v"]
    assert external_called["v"]

    dependencies.reset_registry_for_tests()
