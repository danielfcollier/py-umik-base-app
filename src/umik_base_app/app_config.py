"""
Defines classes and functions for parsing command-line arguments and setting up
the configuration for the audio monitoring application.

This module handles argument validation, device selection logic based on arguments,
and initialization of the calibration process if specified via command line
or environment variable.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging

from .hardwares.selector import HardwareSelector
from .settings import get_settings
from .transformers.calibrator_transformer import CalibratorTransformer

settings = get_settings()

logger = logging.getLogger(__name__)


class AppConfig:
    """
    Holds the validated and processed configuration settings for the audio application.
    """

    def __init__(
        self,
        audio_device: HardwareSelector | None,
        sample_rate: float,
        buffer_seconds: float,
        run_mode: str,
        zmq_host: str | None = None,
        zmq_port: int | None = None,
    ):
        """
        Initializes the configuration object.

        :param audio_device: The selected HardwareSelector instance (None if Consumer).
        :param sample_rate: The final sample rate to be used (native or default).
        :param buffer_seconds: The validated and adjusted buffer duration in seconds.
        :param run_mode: The topology mode ('monolithic', 'producer', 'consumer').
        :param zmq_host: The ZMQ hostname (if applicable).
        :param zmq_port: The ZMQ port (if applicable).
        """
        self.audio_device: HardwareSelector | None = audio_device
        self.sample_rate: float = sample_rate
        self.buffer_seconds: float = buffer_seconds

        self.run_mode = run_mode  # "monolithic", "producer", "consumer"
        self.zmq_host = zmq_host
        self.zmq_port = zmq_port

        self.audio_calibrator: CalibratorTransformer | None = None
        self.sensitivity_dbfs: float | None = None
        self.reference_dbspl: float | None = None
        self.num_taps: int | None = None
