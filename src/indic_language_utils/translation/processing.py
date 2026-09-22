"""Composable plain-text and Markdown translation processing."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from ..errors import OutputValidationError
from ..processors import ProcessorIdentity, VersionedProcessor
from .models import TextFormat, TranslationOptions

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
    state: tuple[tuple[str, object], ...] = ()

    def with_state(self, name: str, value: object) -> Segment:
        if any(existing == name for existing, _ in self.state):
            raise ValueError(f"Processor state already exists: {name}")
        return Segment(
            self.text,
            self.prefix,
            self.suffix,
            self.protected,
            (*self.state, (name, value)),
        )

    def state_for(self, name: str) -> object:
        for existing, value in self.state:
            if existing == name:
                return value
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class PreparedText:
    segments: tuple[Segment, ...]
    literals: tuple[str, ...]

    def reconstruct(self, translated: tuple[str, ...]) -> str:
        """Reconstruct output produced by the default pipeline."""
        if len(translated) != len(self.segments):
            raise OutputValidationError("Provider returned the wrong number of translated segments")
        restored = tuple(
            restore_protected(output, segment.protected)
            for segment, output in zip(self.segments, translated, strict=True)
        )
        return self.assemble(restored)

    def assemble(self, translated: tuple[str, ...]) -> str:
        if len(translated) != len(self.segments):
            raise OutputValidationError("Provider returned the wrong number of translated segments")
        pieces: list[str] = []
        for index, (segment, output) in enumerate(zip(self.segments, translated, strict=True)):
            pieces.append(self.literals[index])
            pieces.append(segment.prefix + output + segment.suffix)
        pieces.append(self.literals[-1])
        return "".join(pieces)


@runtime_checkable
class TranslationStructureProcessor(VersionedProcessor, Protocol):
    """Split input into translatable segments and preserved structure."""

    def prepare(self, text: str, options: TranslationOptions) -> PreparedText: ...


@runtime_checkable
class TranslationSegmentProcessor(VersionedProcessor, Protocol):
    """Transform a segment before a provider call and restore its output."""

    def prepare(self, segment: Segment, options: TranslationOptions) -> Segment: ...

    def restore(self, text: str, segment: Segment, options: TranslationOptions) -> str: ...


@dataclass(frozen=True, slots=True)
class DefaultTranslationStructureProcessor:
    identity = ProcessorIdentity("translation-structure", "1")

    def prepare(self, text: str, options: TranslationOptions) -> PreparedText:
        if options.text_format is TextFormat.PLAIN:
            return self._plain(text, options.max_segment_characters)
        return self._markdown(text, options.max_segment_characters)

    def _plain(self, text: str, max_characters: int) -> PreparedText:
        chunks = _split_large(text, max_characters)
        segments = tuple(Segment(chunk) for chunk in chunks)
        return PreparedText(segments, tuple("" for _ in range(len(segments) + 1)))

    def _markdown(self, text: str, max_characters: int) -> PreparedText:
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
                    Segment(
                        chunk,
                        prefix if index == 0 else "",
                        newline if index == len(chunks) - 1 else "",
                    )
                )
                literals.append("")
        return PreparedText(tuple(segments), tuple(literals))


@dataclass(frozen=True, slots=True)
class ProtectedContentProcessor:
    identity = ProcessorIdentity("translation-protected-content", "1")

    def prepare(self, segment: Segment, options: TranslationOptions) -> Segment:
        return _protect(segment)

    def restore(self, text: str, segment: Segment, options: TranslationOptions) -> str:
        return restore_protected(text, segment.protected)


@dataclass(frozen=True, slots=True)
class UnicodeNormalizationProcessor:
    """Optional normalization processor. It is not enabled by default."""

    form: Literal["NFC", "NFD", "NFKC", "NFKD"] = "NFC"

    @property
    def identity(self) -> ProcessorIdentity:
        return ProcessorIdentity("translation-unicode-normalization", f"1-{self.form.lower()}")

    def prepare(self, segment: Segment, options: TranslationOptions) -> Segment:
        return Segment(
            unicodedata.normalize(self.form, segment.text),
            segment.prefix,
            segment.suffix,
            segment.protected,
            segment.state,
        )

    def restore(self, text: str, segment: Segment, options: TranslationOptions) -> str:
        return text


@dataclass(frozen=True, slots=True)
class TranslationProcessorPipeline:
    structure: TranslationStructureProcessor = DefaultTranslationStructureProcessor()
    segments: tuple[TranslationSegmentProcessor, ...] = (ProtectedContentProcessor(),)

    def __post_init__(self) -> None:
        names = (self.structure.identity.name, *(item.identity.name for item in self.segments))
        if len(names) != len(set(names)):
            raise ValueError("Processor names must be unique within a pipeline")

    @property
    def cache_identity(self) -> tuple[str, ...]:
        processors = (self.structure, *self.segments)
        return tuple(f"{item.identity.name}@{item.identity.version}" for item in processors)

    def prepare(self, text: str, options: TranslationOptions) -> PreparedText:
        prepared = self.structure.prepare(text, options)
        segments = prepared.segments
        for processor in self.segments:
            segments = tuple(processor.prepare(segment, options) for segment in segments)
        return PreparedText(segments, prepared.literals)

    def restore_segment(self, text: str, segment: Segment, options: TranslationOptions) -> str:
        for processor in reversed(self.segments):
            text = processor.restore(text, segment, options)
        return text

    def reconstruct(
        self, prepared: PreparedText, translated: tuple[str, ...], options: TranslationOptions
    ) -> str:
        if len(translated) != len(prepared.segments):
            raise OutputValidationError("Provider returned the wrong number of translated segments")
        restored = tuple(
            self.restore_segment(output, segment, options)
            for output, segment in zip(translated, prepared.segments, strict=True)
        )
        return prepared.assemble(restored)


DEFAULT_TRANSLATION_PROCESSORS = TranslationProcessorPipeline()


def prepare_text(text: str, text_format: TextFormat, max_characters: int) -> PreparedText:
    """Compatibility helper using the default translation processor pipeline."""
    return DEFAULT_TRANSLATION_PROCESSORS.prepare(
        text,
        TranslationOptions(text_format=text_format, max_segment_characters=max_characters),
    )


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
        _PROTECTED.sub(replace, segment.text),
        segment.prefix,
        segment.suffix,
        tuple(protected),
        segment.state,
    )


def restore_protected(text: str, protected: tuple[str, ...]) -> str:
    found = tuple(int(value) for value in _PLACEHOLDER.findall(text))
    expected = tuple(range(len(protected)))
    if found != expected:
        raise OutputValidationError("Protected placeholders are missing, duplicated, or reordered")
    for index, value in enumerate(protected):
        text = text.replace(f"[[ILU-P-{index:06d}]]", value)
    return text
