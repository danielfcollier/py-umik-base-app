"""
Initialization file for the audio_streams package.

This file marks the directory as a Python package and can be used to
define package-level objects or type hints, such as the callback definition.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from importlib.metadata import PackageNotFoundError, version

from .core.consumer_thread import ConsumerThread
from .core.listener_thread import ListenerThread
from .hardwares.calibrator import HardwareCalibrator
from .hardwares.config import HardwareConfig
from .hardwares.selector import HardwareSelector
from .sinks.audio_metrics import AudioMetrics

__all__ = [
    "HardwareCalibrator",
    "HardwareConfig",
    "HardwareSelector",
    "AudioMetrics",
    "ConsumerThread",
    "ListenerThread",
]


try:
    __version__ = version("umik-base-app")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "unknown"
