"""
Main application script for the Digital Decibel Meter.

This script parses command-line arguments for configuration, sets up the
necessary audio components (device selection, calibration), initializes the
multi-threaded application framework (BaseAudioApp), and defines the core
metric calculation logic executed by the consumer thread via the AudioPipeline.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import sys
from datetime import datetime

import numpy as np

from src import AudioMetrics
from src.audio_app_config import AudioAppArgs, AudioAppConfig
from src.base_audio_app import BaseAudioApp
from src.library.audio_device.calibrator_adapter import AudioDeviceCalibratorAdapter
from src.library.audio_device.config import AudioDeviceConfig
from src.library.audio_pipeline import AudioPipeline
from src.library.interfaces import AudioSink

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(threadName)s %(message)s")
logger = logging.getLogger(__name__)


class AudioMetricsSink(AudioSink):
    """
    A sink component that calculates and logs audio metrics for the pipeline.
    """

    def __init__(self, config: AudioAppConfig):
        """
        Initializes the metrics sink.

        :param config: Application configuration containing sample rate and
                       calibration sensitivity values.
        """
        self._config = config
        self._audio_metrics = AudioMetrics(sample_rate=config.sample_rate)

    def handle_audio(self, audio_chunk: np.ndarray, timestamp: datetime) -> None:
        """
        Calculates and logs metrics for the received audio chunk.

        Note: The 'audio_chunk' received here has already been processed (calibrated)
        by the pipeline if a calibrator was configured.
        """
        try:
            # --- Calculate Core Metrics ---
            rms_value = self._audio_metrics.rms(audio_chunk)
            dbfs_value = self._audio_metrics.dBFS(audio_chunk)
            flux_value = self._audio_metrics.flux(audio_chunk, self._config.sample_rate)
            lufs_value = self._audio_metrics.lufs(audio_chunk)

            # --- Prepare Metrics Dictionary for Logging ---
            metrics_to_log = {
                "measured_at": timestamp,
                "rms": rms_value,
                "flux": flux_value,
                "dBFS": dbfs_value,
                "LUFS_M": lufs_value,
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

        except Exception as e:
            logger.error(
                f"Error calculating metrics for chunk captured around {timestamp}: {e}",
                exc_info=True,
            )


class DecibelMeterApp(BaseAudioApp):
    """
    Concrete implementation of the audio monitoring application using the Pipeline pattern.
    """

    def __init__(self, config: AudioAppConfig):
        """
        Initializes the DecibelMeterApp.
        """
        logger.debug("Initializing DecibelMeterApp...")
        self._app_config: AudioAppConfig = config

        # --- 1. The Bridge: Convert App Config to Device Config ---
        device_config = AudioDeviceConfig(
            target_audio_device=config.audio_device,
            sample_rate=config.sample_rate,
            buffer_seconds=config.buffer_seconds,
            high_priority=True,
        )

        # --- 2. Build the Pipeline ---
        pipeline = AudioPipeline()

        # Add Calibrator (Processor)
        if config.audio_calibrator:
            logger.info("Adding Calibration Processor to pipeline.")
            calibrator_adapter = AudioDeviceCalibratorAdapter(config.audio_calibrator)
            pipeline.add_processor(calibrator_adapter)

        # Add Metrics (Sink)
        logger.info("Adding Audio Metrics Sink to pipeline.")
        metrics_sink = AudioMetricsSink(config)
        pipeline.add_sink(metrics_sink)

        # --- 3. Initialize Base ---
        super().__init__(audio_config=device_config, pipeline=pipeline)
        logger.info("DecibelMeterApp initialized.")


if __name__ == "__main__":
    logger.info("Initializing Digital Decibel Meter Application...")

    try:
        args = AudioAppArgs.get_args()
        config = AudioAppArgs.validate_args(args)
        app = DecibelMeterApp(config)
        app.run()
    except Exception as e:
        logger.critical(f"Application failed to initialize or run: {e}", exc_info=True)
        sys.exit(1)

    logger.info("Digital Decibel Meter Application has shut down.")
