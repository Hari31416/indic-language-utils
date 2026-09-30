"""Speech to text models, client, and adapters."""

from .bhashini import BhashiniSTTProvider
from .client import STTClient
from .gnani import GnaniSTTProvider
from .google_speech import (
    HAVE_SPEECH_RECOGNITION,
    GoogleFreeSTTConfig,
    GoogleFreeSTTProvider,
    GoogleSpeechSTTConfig,
    GoogleSpeechSTTProvider,
)
from .helpers import get_stt_client
from .models import ProviderSTTResult, STTRequest, STTResult, STTSegment, STTWord
from .protocols import StreamingSTTProvider, STTProvider
from .sarvam import SarvamSTTProvider
from .streaming import STTStream, STTStreamEvent
from .whisper import (
    HAVE_FASTER_WHISPER,
    FasterWhisperSTTConfig,
    FasterWhisperSTTProvider,
    WhisperSTTConfig,
    WhisperSTTProvider,
)

__all__ = [
    "HAVE_FASTER_WHISPER",
    "HAVE_SPEECH_RECOGNITION",
    "BhashiniSTTProvider",
    "FasterWhisperSTTConfig",
    "FasterWhisperSTTProvider",
    "GnaniSTTProvider",
    "GoogleFreeSTTConfig",
    "GoogleFreeSTTProvider",
    "GoogleSpeechSTTConfig",
    "GoogleSpeechSTTProvider",
    "ProviderSTTResult",
    "STTClient",
    "STTProvider",
    "STTRequest",
    "STTResult",
    "STTSegment",
    "STTStream",
    "STTStreamEvent",
    "STTWord",
    "SarvamSTTProvider",
    "StreamingSTTProvider",
    "WhisperSTTConfig",
    "WhisperSTTProvider",
    "get_stt_client",
]
