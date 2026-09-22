"""Stable, content-safe exceptions used by providers and clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass(eq=False)
class LanguageUtilsError(Exception):
    """Base exception with safe fields suitable for logs and telemetry."""

    message: str
    provider: str | None = None
    capability: str | None = None
    request_id: str | None = None
    details: Mapping[str, str | int | float | bool | None] | None = None

    code: ClassVar[str] = "language_utils_error"

    def __str__(self) -> str:
        fields = [f"code={self.code}"]
        for name in ("provider", "capability", "request_id"):
            value = getattr(self, name)
            if value is not None:
                fields.append(f"{name}={value}")
        return f"{self.message} ({', '.join(fields)})"

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "capability": self.capability,
            "request_id": self.request_id,
        }
        if self.details:
            result["details"] = dict(self.details)
        return result


class InvalidInputError(LanguageUtilsError):
    code = "invalid_input"


class UnsupportedCapabilityError(LanguageUtilsError):
    code = "unsupported_capability"


class UnsupportedLanguageError(LanguageUtilsError):
    code = "unsupported_language"


class UnsupportedLanguagePairError(LanguageUtilsError):
    code = "unsupported_language_pair"


class MissingOptionalDependencyError(LanguageUtilsError):
    code = "missing_optional_dependency"


class AuthenticationError(LanguageUtilsError):
    code = "authentication"


class PermissionDeniedError(LanguageUtilsError):
    code = "permission"


@dataclass(eq=False)
class RateLimitError(LanguageUtilsError):
    retry_after: float | None = None
    code: ClassVar[str] = "rate_limit"


class ProviderTimeoutError(LanguageUtilsError):
    code = "timeout"


class TransientProviderError(LanguageUtilsError):
    code = "transient_provider"


class MalformedProviderResponseError(LanguageUtilsError):
    code = "malformed_provider_response"


class OutputValidationError(LanguageUtilsError):
    code = "output_validation"


class ConfigurationError(LanguageUtilsError):
    code = "configuration"
