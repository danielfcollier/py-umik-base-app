"""
Main application script for the Digital Real Time Meter.

This script parses command-line arguments for configuration, sets up the
necessary audio components (device selection, calibration), initializes the
multi-threaded application framework (AudioBaseApp), and defines the core
metric calculation logic executed by the consumer thread via the AudioPipeline.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

import numpy as np

from umik_base_app import (
    AppArgs,
    AppConfig,
    AudioBaseApp,
    AudioMetrics,
    AudioPipeline,
    AudioSink,
)
from umik_base_app.settings import get_settings
from umik_base_app.transformers.calibrator_adapter import CalibratorAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(threadName)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


class AudioMetricsAudioSink(AudioSink):
    """
    A sink component that accumulates audio and calculates metrics
    over a specified time interval (or per chunk if interval is 0).
    """

    def __init__(self, config: AppConfig):
        """
        Initializes the metrics sink with buffering logic.
        """
        self._config = config
        self._audio_metrics = AudioMetrics(sample_rate=config.sample_rate)

        # Buffering Config
        self._interval_seconds = settings.METRICS.INTERVAL_SECONDS
        self._audio_buffer: list[np.ndarray] = []
        self._accumulated_samples = 0

        if self._interval_seconds > 0:
            self._target_samples = int(self._interval_seconds * config.sample_rate)
            logger.info(f"Metrics Sink: Buffered Mode ({self._interval_seconds}s / {self._target_samples} samples).")
        else:
            self._target_samples = 0
            logger.info("Metrics Sink: Immediate Mode (Per-Chunk).")

    def handle_audio(self, audio_chunk: np.ndarray, timestamp: datetime) -> None:
        """
        Buffers audio chunks. When full, calculates and logs metrics.
        """
        try:
            # Immediate Mode
            if self._target_samples <= 0:
                self._process_and_log(audio_chunk, timestamp)
                return

            # Windowed Mode
            self._audio_buffer.append(audio_chunk)
            self._accumulated_samples += len(audio_chunk)

            if self._accumulated_samples >= self._target_samples:
                full_block = np.concatenate(self._audio_buffer)
                self._process_and_log(full_block, datetime.now())

                # Reset buffer
                self._audio_buffer = []
                self._accumulated_samples = 0

        except Exception as e:
            logger.error(f"Sink Error: {e}", exc_info=True)

    def _process_and_log(self, audio_data: np.ndarray, timestamp: datetime):
        """Calculates core metrics and calls the display method."""
        metrics_data = {
            "measured_at": timestamp,
            "interval_s": (len(audio_data) / self._config.sample_rate),
            "rms": self._audio_metrics.rms(audio_data),
            "flux": self._audio_metrics.flux(audio_data, self._config.sample_rate),
            "dBFS": self._audio_metrics.dBFS(audio_data),
            "LUFS": self._audio_metrics.lufs(audio_data),
        }

        # Calculate dBSPL (if calibrated)
        if self._config.audio_calibrator and self._config.sensitivity_dbfs is not None:
            metrics_data["dBSPL"] = self._audio_metrics.dBSPL(
                dbfs_level=metrics_data["dBFS"],
                sensitivity_dbfs=self._config.sensitivity_dbfs,
                reference_dbspl=self._config.reference_dbspl,
            )

        self._audio_metrics.show_metrics(**metrics_data)


class DecibelMeterApp(AudioBaseApp):
    """
    The main application class that stitches together hardware, pipeline, and sink.
    """

    def __init__(self, config: AppConfig):
        logger.debug("Initializing DecibelMeterApp...")

        pipeline = AudioPipeline()

        if config.audio_calibrator:
            logger.info("Adding Calibration Processor to pipeline.")
            pipeline.add_transformer(CalibratorAdapter(config.audio_calibrator))

        pipeline.add_sink(AudioMetricsAudioSink(config))

        super().__init__(app_config=config, pipeline=pipeline)
        logger.info("DecibelMeterApp initialized.")


def main():
    logger.info("Initializing Real Time Meter...")

    args = AppArgs.get_args()
    app = None

    try:
        config = AppArgs.validate_args(args)
        app = DecibelMeterApp(config)
        app.run()
    except KeyboardInterrupt:
        logger.info("\nMeter stopped by user.")
    except Exception as e:
        logger.critical(f"Application failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if app:
            app.close()

    logger.info("Application shutdown complete.")


if __name__ == "__main__":
    main()
