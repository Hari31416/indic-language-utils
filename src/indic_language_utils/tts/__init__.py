"""Text to speech models, client, and Bhashini adapter."""

from .bhashini import BhashiniTTSProvider
from .cache import TTSCacheEntry, TTSCacheEntryCodec, create_tts_cache
from .client import TTSClient
from .edge_tts import HAVE_EDGE_TTS, EdgeTTSConfig, EdgeTTSProvider
from .helpers import get_tts_client
from .models import ProviderTTSResult, TTSOptions, TTSRequest, TTSResult
from .navana import NavanaTTSProvider
from .protocols import StreamingTTSProvider, TTSProvider
from .sarvam import SarvamTTSProvider
from .streaming import TTSStream, TTSStreamEvent

__all__ = [
    "HAVE_EDGE_TTS",
    "BhashiniTTSProvider",
    "EdgeTTSConfig",
    "EdgeTTSProvider",
    "NavanaTTSProvider",
    "ProviderTTSResult",
    "SarvamTTSProvider",
    "StreamingTTSProvider",
    "TTSCacheEntry",
    "TTSCacheEntryCodec",
    "TTSClient",
    "TTSOptions",
    "TTSProvider",
    "TTSRequest",
    "TTSResult",
    "TTSStream",
    "TTSStreamEvent",
    "create_tts_cache",
    "get_tts_client",
]
