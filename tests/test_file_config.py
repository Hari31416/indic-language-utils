from __future__ import annotations

from pathlib import Path

import pytest

from indic_language_utils.config import Settings, discover_config_files
from indic_language_utils.errors import ConfigurationError
from indic_language_utils.providers.bhashini import BhashiniConfig


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_toml_loading_and_standard_precedence(tmp_path: Path) -> None:
    xdg = tmp_path / "xdg"
    project = tmp_path / "project"
    nested = project / "src" / "package"
    nested.mkdir(parents=True)
    write(
        xdg / "indic-language-utils" / "config.toml",
        """
        [cache]
        enabled = true
        backend = "memory"
        ttl_seconds = 100
        namespace = "user"

        [telemetry]
        logging_enabled = false
        """,
    )
    write(
        project / ".indic-language-utils.toml",
        """
        [cache]
        backend = "sqlite"
        ttl_seconds = 200
        path = "/tmp/project-cache.sqlite3"

        [providers.bhashini]
        endpoint = "https://project.example/inference"
        translation_service_id = "project-service"
        timeout_seconds = 15

        [providers.bhashini.translation_service_ids]
        "hi-IN" = "hindi-service"

        [routes]
        translation = ["bhashini"]
        """,
    )
    explicit = write(
        tmp_path / "selected.toml",
        """
        [cache]
        ttl_seconds = 300
        max_entries = 9000
        """,
    )
    settings = Settings.load(
        explicit,
        env={
            "XDG_CONFIG_HOME": str(xdg),
            "ILU_CACHE_TTL_SECONDS": "400",
        },
        overrides={"cache": {"ttl_seconds": 500}},
        start_dir=nested,
    )
    assert settings.cache.enabled
    assert settings.cache.backend == "sqlite"
    assert settings.cache.namespace == "user"
    assert settings.cache.max_entries == 9000
    assert settings.cache.ttl_seconds == 500
    assert not settings.telemetry.logging_enabled
    assert settings.providers["bhashini"].endpoint == "https://project.example/inference"
    assert settings.providers["bhashini"].translation_service_id == "project-service"
    assert settings.providers["bhashini"].translation_service_ids == {"hi-IN": "hindi-service"}
    assert settings.routes["translation"] == ("bhashini",)


def test_environment_can_select_an_explicit_config_file(tmp_path: Path) -> None:
    selected = write(
        tmp_path / "selected.toml",
        """
        [retry]
        max_attempts = 7
        """,
    )
    settings = Settings.load(
        env={
            "XDG_CONFIG_HOME": str(tmp_path / "empty-xdg"),
            "ILU_CONFIG_FILE": str(selected),
        },
        start_dir=tmp_path / "empty-project",
    )
    assert settings.retry.max_attempts == 7


def test_provider_options_merge_and_preserve_nested_values(tmp_path: Path) -> None:
    config = write(
        tmp_path / "provider.toml",
        """
        [providers.example.options]
        region = "south"
        enabled = true
        models = ["small", "large"]

        [providers.example.options.request]
        beam_width = 4
        """,
    )

    settings = Settings.load(
        config,
        env={"XDG_CONFIG_HOME": str(tmp_path / "no-user-config")},
        overrides={"providers": {"example": {"options": {"region": "north"}}}},
        start_dir=tmp_path,
    )

    assert settings.providers["example"].options == {
        "region": "north",
        "enabled": True,
        "models": ["small", "large"],
        "request": {"beam_width": 4},
    }


@pytest.mark.parametrize(
    "options",
    [
        {"api_key": "secret"},
        {"request": {"token": "secret"}},
        {"nested": [{"password": "secret"}]},
        {"invalid": object()},
        {"": "empty key"},
    ],
)
def test_provider_options_reject_secrets_and_invalid_shapes(options: object) -> None:
    with pytest.raises(ConfigurationError):
        Settings.load(
            env={},
            overrides={"providers": {"example": {"options": options}}},
        )


def test_missing_explicit_file_and_invalid_environment_fail(tmp_path: Path) -> None:
    env = {"XDG_CONFIG_HOME": str(tmp_path / "empty-xdg")}
    start_dir = tmp_path / "empty-project"
    with pytest.raises(ConfigurationError, match="does not exist"):
        Settings.load(tmp_path / "missing.toml", env=env, start_dir=start_dir)
    with pytest.raises(ConfigurationError, match="Environment settings are invalid"):
        Settings.load(env={**env, "ILU_CACHE_MAX_ENTRIES": "many"}, start_dir=start_dir)


def test_project_discovery_uses_nearest_file(tmp_path: Path) -> None:
    outer = write(tmp_path / ".indic-language-utils.toml", "[cache]\nnamespace = 'outer'\n")
    inner_dir = tmp_path / "inner"
    inner = write(inner_dir / ".indic-language-utils.toml", "[cache]\nnamespace = 'inner'\n")
    nested = inner_dir / "src"
    nested.mkdir()
    files = discover_config_files(
        {"XDG_CONFIG_HOME": str(tmp_path / "empty-xdg")}, start_dir=nested
    )
    assert inner.resolve() in files
    assert outer.resolve() not in files


@pytest.mark.parametrize("field", ["api_key", "credential", "access_token", "password"])
def test_secrets_are_rejected_in_toml(tmp_path: Path, field: str) -> None:
    config = write(
        tmp_path / "config.toml",
        f"[providers.bhashini]\nendpoint = 'https://example.test'\n{field} = 'secret'\n",
    )
    with pytest.raises(ConfigurationError, match="Secrets are not allowed"):
        Settings.load(
            config,
            env={"XDG_CONFIG_HOME": str(tmp_path / "empty-xdg")},
            start_dir=tmp_path / "empty-project",
        )


def test_unknown_and_malformed_config_fail_strictly(tmp_path: Path) -> None:
    unknown = write(tmp_path / "unknown.toml", "[cache]\nmade_up = true\n")
    with pytest.raises(ConfigurationError, match="Unknown configuration field"):
        Settings.load(
            unknown,
            env={"XDG_CONFIG_HOME": str(tmp_path / "empty-xdg")},
            start_dir=tmp_path / "empty-project",
        )
    malformed = write(tmp_path / "malformed.toml", "[cache\n")
    with pytest.raises(ConfigurationError, match="could not be read or parsed"):
        Settings.load(
            malformed,
            env={"XDG_CONFIG_HOME": str(tmp_path / "empty-xdg")},
            start_dir=tmp_path / "empty-project",
        )


def test_bhashini_combines_file_settings_with_environment_secret(tmp_path: Path) -> None:
    config = write(
        tmp_path / "config.toml",
        """
        [providers.bhashini]
        endpoint = "https://file.example/inference"
        translation_service_id = "file-service"
        timeout_seconds = 11
        max_concurrency = 4

        [retry]
        max_attempts = 5
        """,
    )
    settings = Settings.load(
        config,
        env={"XDG_CONFIG_HOME": str(tmp_path / "empty-xdg")},
        start_dir=tmp_path / "empty-project",
    )
    bhashini = BhashiniConfig.from_settings(
        settings,
        {
            "BHASHINI_API_KEY": "environment-secret",
            "BHASHINI_TRANSLATION_SERVICE_ID": "environment-service",
        },
    )
    assert bhashini.endpoint == "https://file.example/inference"
    assert bhashini.translation_service_id == "environment-service"
    assert bhashini.api_key.reveal() == "environment-secret"
    assert bhashini.timeout_seconds == 11
    assert bhashini.max_concurrency == 4
    assert bhashini.retry_policy.max_attempts == 5
