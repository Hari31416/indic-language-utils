from __future__ import annotations

import logging
from typing import Any, cast

import pytest

from indic_language_utils.config import Secret, Settings
from indic_language_utils.errors import ConfigurationError, LanguageUtilsError
from indic_language_utils.telemetry import StandardEventLogger


def test_secret_representation_is_redacted() -> None:
    secret = Secret("credential-value")
    assert "credential-value" not in repr(secret)
    assert secret.reveal() == "credential-value"


def test_environment_settings_and_validation() -> None:
    settings = Settings.from_env({"ILU_CACHE_ENABLED": "true", "ILU_CACHE_MAX_ENTRIES": "12"})
    assert settings.cache.enabled
    assert settings.cache.max_entries == 12
    with pytest.raises(ConfigurationError):
        Settings.from_env({"ILU_CACHE_ENABLED": "maybe"})


def test_error_string_has_only_safe_fields() -> None:
    error = LanguageUtilsError("Request failed", provider="fake", request_id="id-1")
    assert (
        str(error) == "Request failed (code=language_utils_error, provider=fake, request_id=id-1)"
    )


def test_standard_logger_drops_content_fields(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("test-safe-logger")
    with caplog.at_level(logging.INFO, logger=logger.name):
        StandardEventLogger(logger).emit("completed", {"provider": "fake", "text": "secret"})
    fields = cast(Any, caplog.records[0]).language_utils
    assert fields == {"event": "completed", "provider": "fake"}
