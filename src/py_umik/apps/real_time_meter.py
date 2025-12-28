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

from py_umik.core.base_app import BaseApp
from py_umik.core.config import AppArgs, AppConfig
from py_umik.core.interfaces import AudioSink
from py_umik.core.pipeline import AudioPipeline
from py_umik.hardware.calibrator_adapter import HardwareCalibratorAdapter
from py_umik.hardware.config import HardwareConfig
from py_umik.processing.audio_metrics import AudioMetrics
from py_umik.settings import get_settings

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
        self._interval_seconds = settings.METRICS.INTERVAL_SECONDS if hasattr(settings, "METRICS") else 3
        # Fallback if settings structure changed, typically defined in settings.py as DEFAULT_METRIC_INTERVAL_SECONDS
        if hasattr(settings, "DEFAULT_METRIC_INTERVAL_SECONDS"):
            self._interval_seconds = settings.DEFAULT_METRIC_INTERVAL_SECONDS

        if self._interval_seconds > 0:
            self._target_samples = int(self._interval_seconds * config.sample_rate)
            self._accumulated_samples = 0
            self._audio_buffer: list[np.ndarray] = []
            logger.info(f"Metrics Sink: Buffered Mode ({self._interval_seconds}s / {self._target_samples} samples).")
        else:
            self._target_samples = 0
            logger.info("Metrics Sink: Immediate Mode (Per-Chunk).")

    def handle_audio(self, audio_chunk: np.ndarray, timestamp: datetime) -> None:
        """
        Buffers audio chunks. When full, calculates and logs metrics.
        """
        try:
            # 1. Immediate Mode
            if self._target_samples <= 0:
                self._process_and_log(audio_chunk, timestamp)
                return

            # 2. Windowed Mode
            self._audio_buffer.append(audio_chunk)
            self._accumulated_samples += len(audio_chunk)

            if self._accumulated_samples >= self._target_samples:
                # Combine & Process
                full_block = np.concatenate(self._audio_buffer)
                self._process_and_log(full_block, datetime.now())

                # Reset
                self._audio_buffer = []
                self._accumulated_samples = 0

        except Exception as e:
            logger.error(f"Sink Error: {e}", exc_info=True)

    def _process_and_log(self, audio_data: np.ndarray, timestamp: datetime):
        """Calculates core metrics and calls the display method."""

        # Calculate Base Metrics
        rms = self._audio_metrics.rms(audio_data)
        dbfs = self._audio_metrics.dBFS(audio_data)
        flux = self._audio_metrics.flux(audio_data, self._config.sample_rate)
        lufs = self._audio_metrics.lufs(audio_data)

        metrics_data = {
            "measured_at": timestamp,
            "interval_s": (len(audio_data) / self._config.sample_rate),
            "rms": rms,
            "flux": flux,
            "dBFS": dbfs,
            "LUFS": lufs,
        }

        # Calculate dBSPL (if calibrated)
        if self._config.audio_calibrator and self._config.sensitivity_dbfs is not None:
            dbspl = self._audio_metrics.dBSPL(
                dbfs_level=dbfs,
                sensitivity_dbfs=self._config.sensitivity_dbfs,
                reference_dbspl=self._config.reference_dbspl,
            )
            metrics_data["dBSPL"] = dbspl

        self._audio_metrics.show_metrics(**metrics_data)


class DecibelMeterApp(BaseApp):
    """
    The main application class that stitches together hardware, pipeline, and sink.
    """

    def __init__(self, config: AppConfig):
        logger.debug("Initializing DecibelMeterApp...")

        device_config = HardwareConfig(
            target_audio_device=config.audio_device,
            sample_rate=config.sample_rate,
            buffer_seconds=config.buffer_seconds,
            high_priority=True,
        )

        pipeline = AudioPipeline()

        if config.audio_calibrator:
            logger.info("Adding Calibration Processor to pipeline.")
            adapter = HardwareCalibratorAdapter(config.audio_calibrator)
            pipeline.add_transformer(adapter)

        metrics_sink = AudioMetricsAudioSink(config)
        pipeline.add_sink(metrics_sink)

        super().__init__(audio_config=device_config, pipeline=pipeline)
        logger.info("DecibelMeterApp initialized.")


def main():
    logger.info("Initializing Real Time Meter...")

    args = AppArgs.get_args()

    app: DecibelMeterApp | None = None
    try:
        config = AppArgs.validate_args(args)
        app = DecibelMeterApp(config)
        app.run()
    except (ValueError, SystemExit) as e:
        logger.error(f"Configuration Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nMeter stopped by user.")
    except Exception as e:
        logger.critical(f"Unexpected Error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if app:
            app.close()

    logger.info("Application shutdown complete.")


if __name__ == "__main__":
    main()
