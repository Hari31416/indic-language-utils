"""Text language detection capability models, contracts, clients, and adapters."""

from .bhashini_detect import BhashiniDetectionProvider
from .cache import DetectionResultCodec, create_detection_cache
from .client import DetectionClient
from .fasttext import (
    FastTextDetectionConfig,
    FastTextDetectionProvider,
    detect_script,
)
from .helpers import (
    detect,
    detect_batch,
    detect_batch_sync,
    detect_sync,
    get_detection_client,
    get_sync_detection_client,
)
from .models import (
    DetectionOptions,
    DetectionProviderMetadata,
    DetectionRequest,
    DetectionResult,
    LanguageCandidate,
    ProviderDetectionResult,
)
from .protocols import DetectionProvider
from .sarvam_detect import SarvamDetectionProvider
from .sync import SyncDetectionClient

__all__ = [
    "BhashiniDetectionProvider",
    "DetectionClient",
    "DetectionOptions",
    "DetectionProvider",
    "DetectionProviderMetadata",
    "DetectionRequest",
    "DetectionResult",
    "DetectionResultCodec",
    "FastTextDetectionConfig",
    "FastTextDetectionProvider",
    "LanguageCandidate",
    "ProviderDetectionResult",
    "SarvamDetectionProvider",
    "SyncDetectionClient",
    "create_detection_cache",
    "detect",
    "detect_batch",
    "detect_batch_sync",
    "detect_script",
    "detect_sync",
    "get_detection_client",
    "get_sync_detection_client",
]
