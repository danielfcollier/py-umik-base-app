"""
Initialization file for the audio_streams package.

This file marks the directory as a Python package and can be used to
define package-level objects or type hints, such as the callback definition.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from .core.consumer_thread import ConsumerThread
from .core.listener_thread import ListenerThread
from .hardware.calibrator import HardwareCalibrator
from .hardware.config import HardwareConfig
from .hardware.selector import HardwareSelector
from .processing.audio_metrics import AudioMetrics

__all__ = [
    "HardwareCalibrator",
    "HardwareConfig",
    "HardwareSelector",
    "AudioMetrics",
    "ConsumerThread",
    "ListenerThread",
]
