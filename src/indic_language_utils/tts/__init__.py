"""Text to speech models, client, and Bhashini adapter."""

from .bhashini import BhashiniTTSProvider
from .client import TTSClient
from .edge_tts import HAVE_EDGE_TTS, EdgeTTSConfig, EdgeTTSProvider
from .helpers import get_tts_client
from .models import ProviderTTSResult, TTSOptions, TTSRequest, TTSResult
from .protocols import TTSProvider
from .sarvam import SarvamTTSProvider

__all__ = [
    "HAVE_EDGE_TTS",
    "BhashiniTTSProvider",
    "EdgeTTSConfig",
    "EdgeTTSProvider",
    "ProviderTTSResult",
    "SarvamTTSProvider",
    "TTSClient",
    "TTSOptions",
    "TTSProvider",
    "TTSRequest",
    "TTSResult",
    "get_tts_client",
]
