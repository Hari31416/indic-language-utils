"""Speech to text models, client, and adapters."""

from .bhashini import BhashiniSTTProvider
from .client import STTClient
from .google_speech import (
    HAVE_SPEECH_RECOGNITION,
    GoogleFreeSTTConfig,
    GoogleFreeSTTProvider,
    GoogleSpeechSTTConfig,
    GoogleSpeechSTTProvider,
)
from .helpers import get_stt_client
from .models import ProviderSTTResult, STTRequest, STTResult
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
    "GoogleFreeSTTConfig",
    "GoogleFreeSTTProvider",
    "GoogleSpeechSTTConfig",
    "GoogleSpeechSTTProvider",
    "ProviderSTTResult",
    "STTClient",
    "STTProvider",
    "STTRequest",
    "STTResult",
    "STTStream",
    "STTStreamEvent",
    "SarvamSTTProvider",
    "StreamingSTTProvider",
    "WhisperSTTConfig",
    "WhisperSTTProvider",
    "get_stt_client",
]
