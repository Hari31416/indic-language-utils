from __future__ import annotations

from pathlib import Path

import pytest

from indic_language_utils.config import ProviderSettings, Settings
from indic_language_utils.errors import ConfigurationError
from indic_language_utils.providers import CapabilityId
from indic_language_utils.providers.factories import (
    ProviderFactoryRegistry,
    configured_provider_factories,
    default_provider_factories,
)
from indic_language_utils.translation import get_translation_client

from .translation_support import FakeTranslationProvider


class FakeEntryPoint:
    def __init__(self, name: str, builder: object) -> None:
        self.name = name
        self.builder = builder
        self.loads = 0

    def load(self) -> object:
        self.loads += 1
        if isinstance(self.builder, Exception):
            raise self.builder
        return self.builder


def test_default_factories_are_indexed_by_capability_and_provider() -> None:
    factories = default_provider_factories()

    assert factories.get(CapabilityId.TRANSLATION, "bhashini") is not None
    assert factories.get(CapabilityId.TEXT_TO_SPEECH, "bhashini") is not None
    assert factories.get(CapabilityId.TRANSLATION, "missing") is None
    assert [
        factory.provider_id for factory in factories.for_capability(CapabilityId.TRANSLATION)
    ] == [
        "bhashini",
        "sarvam",
        "googletrans",
    ]


def test_registry_builds_in_registration_order() -> None:
    factories = ProviderFactoryRegistry()
    first = FakeTranslationProvider("first")
    second = FakeTranslationProvider("second")
    factories.register(CapabilityId.TRANSLATION, "first", lambda settings, env: first)
    factories.register(CapabilityId.TRANSLATION, "second", lambda settings, env: second)

    assert factories.build(CapabilityId.TRANSLATION, Settings(), {}) == (first, second)


def test_registry_rejects_duplicate_and_mismatched_factories() -> None:
    factories = ProviderFactoryRegistry()
    factories.register(
        CapabilityId.TRANSLATION, "expected", lambda settings, env: FakeTranslationProvider("wrong")
    )

    with pytest.raises(ConfigurationError, match="invalid adapter"):
        factories.build(CapabilityId.TRANSLATION, Settings(), {})
    with pytest.raises(ConfigurationError, match="registration is invalid"):
        factories.register(CapabilityId.TRANSLATION, "expected", lambda settings, env: None)


def test_configured_entry_point_is_loaded_and_routed(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FakeTranslationProvider("plugin")
    selected = FakeEntryPoint("plugin", lambda settings, env: provider)
    unselected = FakeEntryPoint("unused", ImportError("should not import"))
    groups: list[str] = []

    def entry_points(*, group: str) -> tuple[FakeEntryPoint, ...]:
        groups.append(group)
        return selected, unselected

    monkeypatch.setattr(
        "indic_language_utils.providers.factories.metadata.entry_points", entry_points
    )
    settings = Settings(routes={"translation": ("plugin",)})

    client = get_translation_client(settings, env={})

    assert client.router.registry.get("plugin") is provider
    assert groups == ["indic_language_utils.providers.translation"]
    assert selected.loads == 1
    assert unselected.loads == 0


def test_unconfigured_entry_points_are_not_scanned(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*, group: str) -> None:
        raise AssertionError(group)

    monkeypatch.setattr(
        "indic_language_utils.providers.factories.metadata.entry_points", unexpected
    )
    factories = configured_provider_factories(CapabilityId.TRANSLATION, Settings())
    assert factories.get(CapabilityId.TRANSLATION, "bhashini") is not None


@pytest.mark.parametrize(
    ("builder", "message"),
    [
        (ImportError("broken import"), "could not be loaded"),
        (object(), "not callable"),
        (lambda settings, env: None, "returned no adapter"),
        (lambda settings, env: FakeTranslationProvider("wrong"), "invalid adapter"),
    ],
)
def test_selected_plugin_errors_name_the_provider(
    monkeypatch: pytest.MonkeyPatch, builder: object, message: str
) -> None:
    entry_point = FakeEntryPoint("plugin", builder)
    monkeypatch.setattr(
        "indic_language_utils.providers.factories.metadata.entry_points",
        lambda *, group: (entry_point,),
    )

    with pytest.raises(ConfigurationError, match=message):
        get_translation_client(Settings(routes={"translation": ("plugin",)}), env={})


def test_explicit_providers_skip_entry_point_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    entry_point = FakeEntryPoint("plugin", ImportError("should not import"))
    monkeypatch.setattr(
        "indic_language_utils.providers.factories.metadata.entry_points",
        lambda *, group: (entry_point,),
    )
    explicit = FakeTranslationProvider("explicit")

    client = get_translation_client(providers=[explicit], env={})

    assert client.router.registry.get("explicit") is explicit
    assert entry_point.loads == 0


def test_application_can_register_a_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "indic_language_utils.providers.factories.metadata.entry_points",
        lambda *, group: (),
    )
    factories = default_provider_factories()
    provider = FakeTranslationProvider("application")
    factories.register(CapabilityId.TRANSLATION, "application", lambda settings, env: provider)

    client = get_translation_client(
        Settings(routes={"translation": ("application",)}),
        provider_factories=factories,
        env={},
    )

    assert client.router.registry.get("application") is provider


def test_provider_settings_select_plugin_and_reach_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FakeTranslationProvider("configured")
    received: list[object] = []

    def build(settings: Settings, env: object) -> FakeTranslationProvider:
        received.append(settings.providers["configured"].options["region"])
        return provider

    entry_point = FakeEntryPoint("configured", build)
    monkeypatch.setattr(
        "indic_language_utils.providers.factories.metadata.entry_points",
        lambda *, group: (entry_point,),
    )
    settings = Settings(providers={"configured": ProviderSettings(options={"region": "south"})})

    client = get_translation_client(settings, env={})

    assert client.router.registry.get("configured") is provider
    assert received == ["south"]


def test_plugin_builder_failure_names_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(settings: Settings, env: object) -> None:
        raise RuntimeError("builder failed")

    monkeypatch.setattr(
        "indic_language_utils.providers.factories.metadata.entry_points",
        lambda *, group: (FakeEntryPoint("broken", broken),),
    )

    with pytest.raises(ConfigurationError, match="broken"):
        get_translation_client(Settings(routes={"translation": ("broken",)}), env={})


def test_plugin_cannot_reuse_builtin_factory_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "indic_language_utils.providers.factories.metadata.entry_points",
        lambda *, group: (FakeEntryPoint("bhashini", lambda settings, env: None),),
    )

    with pytest.raises(ConfigurationError, match="registration is invalid"):
        get_translation_client(Settings(routes={"translation": ("bhashini",)}), env={})


def test_installed_entry_point_is_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sample_ilu_plugin.py").write_text(
        "from tests.translation_support import FakeTranslationProvider\n"
        "def build(settings, env):\n"
        "    return FakeTranslationProvider('installed_plugin')\n"
    )
    dist_info = tmp_path / "sample_ilu_plugin-0.1.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Name: sample-ilu-plugin\nVersion: 0.1\n")
    (dist_info / "entry_points.txt").write_text(
        "[indic_language_utils.providers.translation]\ninstalled_plugin = sample_ilu_plugin:build\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    client = get_translation_client(Settings(routes={"translation": ("installed_plugin",)}), env={})

    assert client.router.registry.get("installed_plugin").identity.provider == "installed_plugin"
