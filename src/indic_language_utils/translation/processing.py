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
_PLACEHOLDER = re.compile(r"\[{1,2}\s*(?:ILU-P-|[^\d\[\]]*?)\s*(\d{6})\s*\]{1,2}")
_PROTECTED_INDICES = "translation-protected-indices"
_LITERAL_INDICES = "translation-literal-placeholder-indices"


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
            restore_protected(
                output,
                segment.protected,
                indices=_protected_indices(segment),
                literal_indices=_literal_indices(segment),
            )
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
        fence_char = ""
        fence_length = 0
        for line in text.splitlines(keepends=True):
            stripped = line.lstrip(" \t").rstrip("\r\n")
            fence = re.match(r"(`{3,}|~{3,})", stripped)
            if not fence_char and fence:
                fence_char = fence.group(0)[0]
                fence_length = len(fence.group(0))
                literals[-1] += line
                continue
            if fence_char:
                if (
                    fence
                    and fence.group(0)[0] == fence_char
                    and len(fence.group(0)) >= fence_length
                    and not stripped[fence.end() :].strip()
                ):
                    fence_char = ""
                    fence_length = 0
                literals[-1] += line
                continue
            if not line.strip():
                literals[-1] += line
                continue
            if line.endswith("\r\n"):
                newline = "\r\n"
            elif line.endswith(("\n", "\r")):
                newline = line[-1]
            else:
                newline = ""
            content = line[: -len(newline)] if newline else line
            match = _LIST_PREFIX.match(content)
            if match is None:
                match = _MARKDOWN_PREFIX.match(content)
            prefix = match.group("prefix") if match else ""
            body = match.group("body") if match else content
            chunks = _split_large(body, max_characters, preserve_protected=True)
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
        return restore_protected(
            text,
            segment.protected,
            indices=_protected_indices(segment),
            literal_indices=_literal_indices(segment),
            allow_reordered=options.allow_reordered_placeholders,
            best_effort=options.best_effort,
        )


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


def _split_large(text: str, limit: int, *, preserve_protected: bool = False) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    protected_spans = (
        tuple(match.span() for match in _PROTECTED.finditer(text)) if preserve_protected else ()
    )
    offset = 0
    remaining = text
    while len(remaining) > limit:
        window = remaining[: limit + 1]
        boundaries = [match.end() for match in _SENTENCE_BOUNDARY.finditer(window)]
        cut = boundaries[-1] if boundaries else max(window.rfind(" "), window.rfind("\n")) + 1
        if cut <= 0:
            cut = limit
        for start, end in protected_spans:
            if start < offset + cut < end:
                cut = start - offset if start > offset else end - offset
                break
        chunks.append(remaining[:cut])
        remaining = remaining[cut:]
        offset += cut
    if remaining:
        chunks.append(remaining)
    return chunks


def _protect(segment: Segment) -> Segment:
    protected: list[str] = []
    occupied = {int(match.group(1)) for match in _PLACEHOLDER.finditer(segment.text)}
    indices: list[int] = []
    next_index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal next_index
        while next_index in occupied:
            next_index += 1
        if next_index > 999_999:
            raise OutputValidationError("Too many protected placeholders")
        protected.append(match.group(0))
        indices.append(next_index)
        marker = f"[[ILU-P-{next_index:06d}]]"
        next_index += 1
        return marker

    return Segment(
        _PROTECTED.sub(replace, segment.text),
        segment.prefix,
        segment.suffix,
        tuple(protected),
        (
            *segment.state,
            (_PROTECTED_INDICES, tuple(indices)),
            (_LITERAL_INDICES, frozenset(occupied)),
        ),
    )


def _protected_indices(segment: Segment) -> tuple[int, ...]:
    try:
        indices = segment.state_for(_PROTECTED_INDICES)
    except KeyError:
        return tuple(range(len(segment.protected)))
    assert isinstance(indices, tuple)
    return indices


def _literal_indices(segment: Segment) -> frozenset[int]:
    try:
        indices = segment.state_for(_LITERAL_INDICES)
    except KeyError:
        return frozenset()
    assert isinstance(indices, frozenset)
    return indices


def restore_protected(
    text: str,
    protected: tuple[str, ...],
    *,
    indices: tuple[int, ...] | None = None,
    literal_indices: frozenset[int] = frozenset(),
    allow_reordered: bool = True,
    best_effort: bool = False,
) -> str:
    if not protected:
        if not best_effort and any(
            int(match.group(1)) not in literal_indices for match in _PLACEHOLDER.finditer(text)
        ):
            raise OutputValidationError(
                "Protected placeholders are missing, duplicated, or invalid"
            )
        return text
    expected_order = indices if indices is not None else tuple(range(len(protected)))
    if len(expected_order) != len(protected):
        raise ValueError("Protected indices and values must have the same length")
    replacements = dict(zip(expected_order, protected, strict=True))
    all_matches = list(_PLACEHOLDER.finditer(text))
    matches = [match for match in all_matches if int(match.group(1)) in replacements]
    found_indices = [int(m.group(1)) for m in matches]
    expected_indices = set(expected_order)

    missing_indices = expected_indices - set(found_indices)
    extra_indices = (
        {int(match.group(1)) for match in all_matches} - expected_indices - literal_indices
    )
    has_duplicates = len(found_indices) != len(set(found_indices))
    order_invalid = not allow_reordered and tuple(found_indices) != expected_order

    if (missing_indices or extra_indices or has_duplicates or order_invalid) and not best_effort:
        raise OutputValidationError("Protected placeholders are missing, duplicated, or invalid")

    for match in reversed(matches):
        idx = int(match.group(1))
        replacement = replacements[idx]
        text = text[: match.start()] + replacement + text[match.end() :]

    if best_effort and missing_indices:
        for idx in expected_order:
            if idx in missing_indices:
                text += f" {replacements[idx]}"

    return text
