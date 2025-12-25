"""
Main application script for the Digital Real Time Meter.

This script parses command-line arguments for configuration, sets up the
necessary audio components (device selection, calibration), initializes the
multi-threaded application framework (BaseApp), and defines the core
metric calculation logic executed by the consumer thread via the AudioPipeline.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import sys
from datetime import datetime

import numpy as np

from src.py_umik import AudioMetrics
from src.py_umik.core.base_app import BaseApp
from src.py_umik.core.config import AppArgs, AppConfig
from src.py_umik.core.interfaces import AudioSink
from src.py_umik.core.pipeline import AudioPipeline
from src.py_umik.hardware.calibrator_adapter import HardwareCalibratorAdapter
from src.py_umik.hardware.config import HardwareConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(threadName)s %(message)s")
logger = logging.getLogger(__name__)


DEFAULT_METRIC_INTERVAL_SECONDS = 3


class AudioMetricsAudioSink(AudioSink):
    """
    A sink component that accumulates audio and calculates metrics
    over a specified time interval.
    """

    def __init__(self, config: AppConfig):
        """
        Initializes the metrics sink with buffering logic.
        """
        self._config = config
        self._audio_metrics = AudioMetrics(sample_rate=config.sample_rate)

        # --- Buffering Configuration ---
        self._interval_seconds = DEFAULT_METRIC_INTERVAL_SECONDS

        if self._interval_seconds > 0:
            # Calculate how many samples we need to collect before processing
            self._target_samples = int(self._interval_seconds * config.sample_rate)
            self._accumulated_samples = 0
            self._audio_buffer = []  # List to hold numpy arrays
            logger.info(
                f"Metrics AudioSink initialized with {self._interval_seconds}s interval "
                f"({self._target_samples} samples)."
            )
        else:
            self._target_samples = 0
            logger.info("Metrics AudioSink initialized in immediate mode (per-chunk).")

    def handle_audio(self, audio_chunk: np.ndarray, timestamp: datetime) -> None:
        """
        Buffers audio chunks. When the buffer is full, calculates and logs metrics
        for the entire interval.
        """
        try:
            # 1. Immediate Mode (Legacy behavior if interval is 0)
            if self._target_samples <= 0:
                self._process_and_log(audio_chunk, timestamp)
                return

            # 2. Windowed Mode
            self._audio_buffer.append(audio_chunk)
            self._accumulated_samples += len(audio_chunk)

            # Check if we have enough data
            if self._accumulated_samples >= self._target_samples:
                # Combine all buffered chunks into one continuous array
                full_block = np.concatenate(self._audio_buffer)

                # Process the full block
                # Use the timestamp of the *end* of the block (roughly now)
                self._process_and_log(full_block, datetime.now())

                # Reset Buffer
                self._audio_buffer = []
                self._accumulated_samples = 0

        except Exception as e:
            logger.error(f"Error in AudioMetricsAudioSink: {e}", exc_info=True)

    def _process_and_log(self, audio_data: np.ndarray, timestamp: datetime):
        """
        Helper method to calculate and log metrics for a specific block of audio.
        """
        # --- Calculate Core Metrics on the aggregated block ---
        # RMS: Effective power over the whole interval
        rms_value = self._audio_metrics.rms(audio_data)

        # dBFS: Average level over the interval
        dbfs_value = self._audio_metrics.dBFS(audio_data)

        # Flux: Max spectral change detected within this interval
        flux_value = self._audio_metrics.flux(audio_data, self._config.sample_rate)

        # LUFS: Integrated loudness over this interval
        lufs_value = self._audio_metrics.lufs(audio_data)

        # --- Prepare Metrics Dictionary ---
        metrics_to_log = {
            "measured_at": timestamp,
            "interval_s": (len(audio_data) / self._config.sample_rate),
            "rms": rms_value,
            "flux": flux_value,
            "dBFS": dbfs_value,
            "LUFS": lufs_value,
        }

        # --- Calculate dBSPL (Conditionally) ---
        if self._config.audio_calibrator and self._config.sensitivity_dbfs is not None:
            dbspl_value = self._audio_metrics.dBSPL(
                dbfs_level=dbfs_value,
                sensitivity_dbfs=self._config.sensitivity_dbfs,
                reference_dbspl=self._config.reference_dbspl,
            )
            metrics_to_log["dBSPL"] = dbspl_value

        # --- Log the Metrics ---
        self._audio_metrics.show_metrics(**metrics_to_log)


class DecibelMeterApp(BaseApp):
    """
    Concrete implementation of the audio monitoring application using the AudioPipeline pattern.
    """

    def __init__(self, config: AppConfig):
        """
        Initializes the DecibelMeterApp.
        """
        logger.debug("Initializing DecibelMeterApp...")
        self._app_config: AppConfig = config

        # --- 1. The Bridge: Convert App Config to Device Config ---
        device_config = HardwareConfig(
            target_audio_device=config.audio_device,
            sample_rate=config.sample_rate,
            buffer_seconds=config.buffer_seconds,
            high_priority=True,
        )

        # --- 2. Build the AudioPipeline ---
        pipeline = AudioPipeline()

        # Add HardwareCalibrator (Processor)
        if config.audio_calibrator:
            logger.info("Adding Calibration Processor to pipeline.")
            calibrator_adapter = HardwareCalibratorAdapter(config.audio_calibrator)
            pipeline.add_transformer(calibrator_adapter)

        # Add Metrics (AudioSink)
        logger.info("Adding Audio Metrics AudioSink to pipeline.")
        metrics_sink = AudioMetricsAudioSink(config)
        pipeline.add_sink(metrics_sink)

        # --- 3. Initialize Base ---
        super().__init__(audio_config=device_config, pipeline=pipeline)
        logger.info("DecibelMeterApp initialized.")


if __name__ == "__main__":
    logger.info("Initializing Digital Real Time Meter Application...")

    try:
        args = AppArgs.get_args()
        config = AppArgs.validate_args(args)
        app = DecibelMeterApp(config)
        app.run()
    except Exception as e:
        logger.critical(f"Application failed to initialize or run: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Digital Real Time Meter Application has shut down.")
