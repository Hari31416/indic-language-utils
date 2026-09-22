"""Plain-text segmentation and Markdown-safe reconstruction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..errors import OutputValidationError
from .models import TextFormat

PREPROCESSOR_POLICY_VERSION = "translation-pre-v1"
POSTPROCESSOR_POLICY_VERSION = "translation-post-v1"

_PROTECTED = re.compile(
    r"```.*?```|`[^`\n]+`|(?<=\]\()[^)]+(?=\))|https?://[^\s)>]+|[*_~]{1,3}",
    re.DOTALL,
)
_LIST_PREFIX = re.compile(r"^(?P<prefix>[ \t]*(?:[-+*]|\d+[.)]|>)[ \t]+)(?P<body>.*)$")
_MARKDOWN_PREFIX = re.compile(r"^(?P<prefix>[ \t]*(?:#{1,6}[ \t]+)?)(?P<body>.*)$")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।॥])\s+")
_PLACEHOLDER = re.compile(r"\[\[ILU-P-(\d{6})\]\]")


@dataclass(frozen=True, slots=True)
class Segment:
    text: str
    prefix: str = ""
    suffix: str = ""
    protected: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedText:
    segments: tuple[Segment, ...]
    literals: tuple[str, ...]

    def reconstruct(self, translated: tuple[str, ...]) -> str:
        if len(translated) != len(self.segments):
            raise OutputValidationError("Provider returned the wrong number of translated segments")
        pieces: list[str] = []
        for index, (segment, output) in enumerate(zip(self.segments, translated, strict=True)):
            pieces.append(self.literals[index])
            pieces.append(
                segment.prefix + restore_protected(output, segment.protected) + segment.suffix
            )
        pieces.append(self.literals[-1])
        return "".join(pieces)


def prepare_text(text: str, text_format: TextFormat, max_characters: int) -> PreparedText:
    if text_format is TextFormat.PLAIN:
        chunks = _split_large(text, max_characters)
        plain_segments = tuple(_protect(Segment(chunk)) for chunk in chunks)
        return PreparedText(plain_segments, tuple("" for _ in range(len(plain_segments) + 1)))

    segments: list[Segment] = []
    literals: list[str] = [""]
    in_fence = False
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            literals[-1] += line
            continue
        if in_fence or not line.strip():
            literals[-1] += line
            continue
        newline = "\n" if line.endswith("\n") else ""
        content = line[:-1] if newline else line
        match = _LIST_PREFIX.match(content)
        if match is None:
            match = _MARKDOWN_PREFIX.match(content)
        prefix = match.group("prefix") if match else ""
        body = match.group("body") if match else content
        chunks = _split_large(body, max_characters)
        for index, chunk in enumerate(chunks):
            segments.append(
                _protect(
                    Segment(
                        chunk,
                        prefix if index == 0 else "",
                        newline if index == len(chunks) - 1 else "",
                    )
                )
            )
            literals.append("")
    return PreparedText(tuple(segments), tuple(literals))


def _split_large(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[: limit + 1]
        boundaries = [match.end() for match in _SENTENCE_BOUNDARY.finditer(window)]
        cut = boundaries[-1] if boundaries else max(window.rfind(" "), window.rfind("\n")) + 1
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
    if remaining:
        chunks.append(remaining)
    return chunks


def _protect(segment: Segment) -> Segment:
    protected: list[str] = []

    def replace(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"[[ILU-P-{len(protected) - 1:06d}]]"

    return Segment(
        _PROTECTED.sub(replace, segment.text), segment.prefix, segment.suffix, tuple(protected)
    )


def restore_protected(text: str, protected: tuple[str, ...]) -> str:
    found = tuple(int(value) for value in _PLACEHOLDER.findall(text))
    expected = tuple(range(len(protected)))
    if found != expected:
        raise OutputValidationError("Protected placeholders are missing, duplicated, or reordered")
    for index, value in enumerate(protected):
        text = text.replace(f"[[ILU-P-{index:06d}]]", value)
    return text
