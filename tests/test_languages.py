import pytest

from indic_language_utils.errors import UnsupportedLanguageError
from indic_language_utils.languages import DEFAULT_LANGUAGE_REGISTRY, LanguageTag


def test_registry_has_english_and_all_scheduled_languages() -> None:
    assert len(DEFAULT_LANGUAGE_REGISTRY.definitions()) == 23


@pytest.mark.parametrize(
    ("value", "expected"),
    [("HI_in", "hi-IN"), ("hin", "hi-IN"), ("od-IN", "or-IN"), ("ori_Orya", "or-IN")],
)
def test_registry_normalizes_aliases(value: str, expected: str) -> None:
    assert str(DEFAULT_LANGUAGE_REGISTRY.normalize(value)) == expected


def test_registry_retains_explicit_script() -> None:
    assert DEFAULT_LANGUAGE_REGISTRY.normalize("ks-Arab-IN") == LanguageTag("ks", "Arab", "IN")


def test_registry_rejects_unknown_language() -> None:
    with pytest.raises(UnsupportedLanguageError):
        DEFAULT_LANGUAGE_REGISTRY.normalize("zz-IN")
