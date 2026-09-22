from __future__ import annotations

import pytest

from indic_language_utils.errors import OutputValidationError
from indic_language_utils.translation.models import TextFormat, TranslationOptions
from indic_language_utils.translation.processing import (
    DefaultTranslationStructureProcessor,
    ProtectedContentProcessor,
    TranslationProcessorPipeline,
    prepare_text,
    restore_protected,
)

from .translation_support import PrefixProcessor


def test_markdown_reconstruction_preserves_structure_and_visible_text() -> None:
    source = (
        "# Heading\n\n  - Visit [the portal](https://example.gov/a) and use `case_id`.\n\n"
        "```py\nvalue = 1\n```\n"
    )
    prepared = prepare_text(source, TextFormat.MARKDOWN, 1_000)
    translated = tuple(
        text.replace("Heading", "शीर्षक").replace("Visit", "देखें")
        for text in (item.text for item in prepared.segments)
    )
    result = prepared.reconstruct(translated)
    assert result == source.replace("Heading", "शीर्षक").replace("Visit", "देखें")


def test_missing_or_reordered_placeholders_validation() -> None:
    with pytest.raises(OutputValidationError):
        restore_protected("missing", ("https://example.gov",))
    # Strict order rejection when allow_reordered=False
    with pytest.raises(OutputValidationError):
        restore_protected("[[ILU-P-000001]][[ILU-P-000000]]", ("one", "two"), allow_reordered=False)
    # Reordered placeholders succeed by default (natural SOV grammar)
    assert restore_protected("[[ILU-P-000001]][[ILU-P-000000]]", ("one", "two")) == "twoone"
    # Best-effort recovery prevents failure on missing placeholders
    recovered = restore_protected("missing", ("https://example.gov",), best_effort=True)
    assert "https://example.gov" in recovered


def test_segmentation_preserves_every_character() -> None:
    text = "First sentence. Second sentence is longer. Final sentence."
    prepared = prepare_text(text, TextFormat.PLAIN, 20)
    assert prepared.reconstruct(tuple(segment.text for segment in prepared.segments)) == text
    assert all(len(segment.text) <= 20 for segment in prepared.segments)


def test_blank_markdown_has_no_translatable_segments() -> None:
    prepared = prepare_text("\n\n", TextFormat.MARKDOWN, 10)
    assert not prepared.segments
    assert prepared.literals == ("\n\n",)


def test_custom_processors_are_composable_and_restore_in_reverse_order() -> None:
    pipeline = TranslationProcessorPipeline(
        DefaultTranslationStructureProcessor(),
        (ProtectedContentProcessor(), PrefixProcessor()),
    )
    options = TranslationOptions()
    prepared = pipeline.prepare("Visit https://example.gov", options)
    assert prepared.segments[0].text == "X:Visit [[ILU-P-000000]]"
    output = pipeline.reconstruct(prepared, ("X:देखें [[ILU-P-000000]]",), options)
    assert output == "देखें https://example.gov"


def test_processors_can_be_omitted_explicitly() -> None:
    pipeline = TranslationProcessorPipeline(
        DefaultTranslationStructureProcessor(),
        (),
    )
    prepared = pipeline.prepare("Visit https://example.gov", TranslationOptions())
    assert prepared.segments[0].text == "Visit https://example.gov"


def test_duplicate_processor_identity_is_rejected() -> None:
    with pytest.raises(ValueError):
        TranslationProcessorPipeline(
            DefaultTranslationStructureProcessor(),
            (PrefixProcessor(), PrefixProcessor()),
        )
