# Processor composition

Processors are explicit inputs to a capability client. Each capability defines protocols for its own data rather than forcing text and audio through one generic model. All processors share `ProcessorIdentity`, which contains a stable name and version.

Changing a processor name, version, selection, or order changes the translation cache key. Increment the version whenever a behavior change can alter provider input or reconstructed output.

## Translation pipeline

A `TranslationProcessorPipeline` contains one structure processor and an ordered tuple of segment processors.

The structure processor splits the input into translatable segments while retaining syntax and whitespace for reconstruction. Segment processors then prepare every segment in tuple order. After translation, they restore each segment in reverse order. A processor that adds a wrapper after placeholder protection therefore removes its wrapper before placeholder restoration.

The default pipeline is equivalent to:

```python
processors = TranslationProcessorPipeline(
    structure=DefaultTranslationStructureProcessor(),
    segments=(ProtectedContentProcessor(),),
)
```

Pass a different pipeline to the client:

```python
processors = TranslationProcessorPipeline(
    structure=DefaultTranslationStructureProcessor(),
    segments=(
        UnicodeNormalizationProcessor("NFC"),
        ProtectedContentProcessor(),
    ),
)

client = TranslationClient(router, processors=processors)
```

Use an empty segment tuple only when the provider may receive URLs, inline code, and Markdown markers without protection:

```python
processors = TranslationProcessorPipeline(
    structure=DefaultTranslationStructureProcessor(),
    segments=(),
)
```

## Custom segment processor

A custom segment processor implements `prepare()` and `restore()`. It must have a unique, versioned identity. Store reconstruction data with `Segment.with_state()` rather than in mutable processor instance fields. This keeps concurrent calls independent.

```python
from dataclasses import dataclass

from indic_language_utils import ProcessorIdentity, Segment, TranslationOptions
from indic_language_utils.errors import OutputValidationError


@dataclass(frozen=True)
class WrapperProcessor:
    identity = ProcessorIdentity("application-wrapper", "1")

    def prepare(self, segment: Segment, options: TranslationOptions) -> Segment:
        wrapped = Segment(
            text=f"<value>{segment.text}</value>",
            prefix=segment.prefix,
            suffix=segment.suffix,
            protected=segment.protected,
            state=segment.state,
        )
        return wrapped.with_state(self.identity.name, ("<value>", "</value>"))

    def restore(self, text: str, segment: Segment, options: TranslationOptions) -> str:
        opening, closing = segment.state_for(self.identity.name)
        if not text.startswith(opening) or not text.endswith(closing):
            raise OutputValidationError("Provider did not preserve the application wrapper")
        return text[len(opening) : -len(closing)]
```

Custom restoration must fail when required structure is missing or reordered. Returning the source segment as a fallback would hide provider corruption.

## Custom structure processor

A structure processor implements `TranslationStructureProcessor.prepare()` and returns `PreparedText`. Its `literals` tuple must contain one more item than its `segments` tuple. Literal item zero precedes segment zero, and the final literal follows the final segment. `PreparedText.assemble()` validates the translated segment count before reconstruction.

Future language and speech capabilities should define their own processor protocols using `VersionedProcessor`. They can reuse identity and cache-version rules without inheriting translation's `Segment`, `PreparedText`, or `TranslationOptions` types.
