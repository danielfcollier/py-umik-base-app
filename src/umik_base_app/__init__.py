"""
Initialization file for the audio_streams package.

This file marks the directory as a Python package and can be used to
define package-level objects or type hints, such as the callback definition.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import importlib.util
import os
import sys

_vendor_dir = os.path.join(os.path.dirname(__file__), "vendor")
if os.path.isdir(_vendor_dir) and _vendor_dir not in sys.path:
    # Only use vendored packages when they aren't already available (i.e. installed .deb,
    # not a dev venv). Avoids loading C-extensions compiled for the wrong Python version.
    if importlib.util.find_spec("numpy") is None:
        sys.path.insert(0, _vendor_dir)

from importlib.metadata import PackageNotFoundError, version

from .app_args import AppArgs
from .app_config import AppConfig
from .audio_base_app import AudioBaseApp
from .audio_pipeline import AudioPipeline
from .calibration_config import CalibrationConfig
from .core.audio_metrics import AudioMetrics
from .core.operational_mode import OperationalMode
from .core.pipeline_context import PipelineContext
from .create_transport import QueueInMemoryTransport, ZmqConsumerTransport, ZmqProducerTransport
from .hardware_config import HardwareConfig
from .sinks.sinks_protocol import AudioSink
from .transformers.transformers_protocol import AudioTransformer

__all__ = [
    "AppArgs",
    "AppConfig",
    "AudioBaseApp",
    "AudioMetrics",
    "AudioPipeline",
    "AudioSink",
    "AudioTransformer",
    "CalibrationConfig",
    "HardwareConfig",
    "OperationalMode",
    "PipelineContext",
    "QueueInMemoryTransport",
    "ZmqConsumerTransport",
    "ZmqProducerTransport",
]

try:
    __version__ = version("umik-base-app")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "unknown"
