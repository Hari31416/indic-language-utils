from __future__ import annotations

import pytest

from indic_language_utils.errors import OutputValidationError
from indic_language_utils.translation.models import TextFormat
from indic_language_utils.translation.processing import prepare_text, restore_protected


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


def test_missing_or_reordered_placeholders_fail() -> None:
    with pytest.raises(OutputValidationError):
        restore_protected("missing", ("https://example.gov",))
    with pytest.raises(OutputValidationError):
        restore_protected("[[ILU-P-000001]][[ILU-P-000000]]", ("one", "two"))


def test_segmentation_preserves_every_character() -> None:
    text = "First sentence. Second sentence is longer. Final sentence."
    prepared = prepare_text(text, TextFormat.PLAIN, 20)
    assert prepared.reconstruct(tuple(segment.text for segment in prepared.segments)) == text
    assert all(len(segment.text) <= 20 for segment in prepared.segments)


def test_blank_markdown_has_no_translatable_segments() -> None:
    prepared = prepare_text("\n\n", TextFormat.MARKDOWN, 10)
    assert not prepared.segments
    assert prepared.literals == ("\n\n",)
