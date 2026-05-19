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

import argparse
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
from umik_base_app.core.pipeline_context import PipelineContext
from umik_base_app.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(threadName)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


class AudioMetricsSink(AudioSink):
    """
    A sink component that accumulates audio and calculates metrics
    over a specified time interval (or per chunk if interval is 0).

    Reads calibration metadata from PipelineContext instead of AppConfig,
    enabling decoupled operation from calibration configuration.

    Calibration-aware dBSPL calculation:
    - Requires sensitivity_dbfs and reference_dbspl from context
    - Accuracy depends on calibration applied (gain-only vs full)
    - Logs calibration state for transparency
    """

    def __init__(self, sample_rate: float):
        """
        Initializes the metrics sink with buffering logic.

        :param sample_rate: Audio sample rate in Hz.
        """
        self._sample_rate = sample_rate
        self._audio_metrics = AudioMetrics(sample_rate=sample_rate)
        self._calibration_logged = False  # Log calibration state once

        # Buffering Config
        self._interval_seconds = settings.METRICS.INTERVAL_SECONDS
        self._audio_buffer: list[np.ndarray] = []
        self._accumulated_samples = 0

        if self._interval_seconds > 0:
            self._target_samples = int(self._interval_seconds * sample_rate)
            logger.info(f"Metrics Sink: Buffered Mode ({self._interval_seconds}s / {self._target_samples} samples).")
        else:
            self._target_samples = 0
            logger.info("Metrics Sink: Immediate Mode (Per-Chunk).")

    def handle(self, ctx: PipelineContext) -> None:
        """
        Buffers audio chunks. When full, calculates and logs metrics.

        :param ctx: The pipeline context containing audio and metadata.
        """
        # Log calibration state on first chunk
        if not self._calibration_logged:
            self._log_calibration_state(ctx)
            self._calibration_logged = True

        try:
            # Immediate Mode
            if self._target_samples <= 0:
                self._process_and_log(ctx.audio, ctx.timestamp, ctx)
                return

            # Windowed Mode
            self._audio_buffer.append(ctx.audio)
            self._accumulated_samples += len(ctx.audio)

            if self._accumulated_samples >= self._target_samples:
                full_block = np.concatenate(self._audio_buffer)
                self._process_and_log(full_block[: self._target_samples], datetime.now(), ctx)

                # Carry overshoot into the next window
                remainder = full_block[self._target_samples :]
                self._audio_buffer = [remainder] if len(remainder) > 0 else []
                self._accumulated_samples = len(remainder)

        except Exception as e:
            logger.error(f"Sink Error: {e}", exc_info=True)

    def _log_calibration_state(self, ctx: PipelineContext) -> None:
        """Log the calibration state for transparency."""
        if ctx.is_fully_calibrated():
            logger.info("Calibration: FULL (gain + FIR) - dBSPL accurate across frequency spectrum")
        elif ctx.is_gain_calibrated():
            logger.info("Calibration: GAIN ONLY - dBSPL accurate for broadband levels, not frequency-specific")
        elif ctx.can_calculate_dbspl():
            logger.info("Calibration: METADATA ONLY - dBSPL calculated from raw audio (less accurate)")
        else:
            logger.info("Calibration: NONE - dBSPL not available")

    def _process_and_log(self, audio_data: np.ndarray, timestamp: datetime, ctx: PipelineContext) -> None:
        """
        Calculates core metrics and calls the display method.

        dBSPL Calculation Logic:
        - If gain was applied: audio levels are sensitivity-corrected,
          dBFS directly maps to acoustic level relative to reference
        - If gain was NOT applied: need to offset dBFS by sensitivity
          to get true acoustic level

        :param audio_data: Audio samples to analyze.
        :param timestamp: Measurement timestamp.
        :param ctx: Pipeline context with calibration metadata.
        """
        dbfs = self._audio_metrics.dBFS(audio_data)

        metrics_data = {
            "measured_at": timestamp,
            "interval_s": len(audio_data) / self._sample_rate,
            "rms": self._audio_metrics.rms(audio_data),
            "flux": self._audio_metrics.flux(audio_data, self._sample_rate),
            "dBFS": dbfs,
            "LUFS": self._audio_metrics.lufs(audio_data),
        }

        # Calculate dBSPL if calibration metadata is available
        if ctx.can_calculate_dbspl():
            dbspl = self._calculate_dbspl(dbfs, ctx)
            metrics_data["dBSPL"] = dbspl

            # Add accuracy indicator based on calibration level
            if ctx.is_fully_calibrated():
                metrics_data["calibration"] = "full"
            elif ctx.is_gain_calibrated():
                metrics_data["calibration"] = "gain"
            else:
                metrics_data["calibration"] = "raw"

        self._audio_metrics.show_metrics(**metrics_data)

    def _calculate_dbspl(self, dbfs: float, ctx: PipelineContext) -> float:
        """
        Calculate dBSPL from dBFS using calibration metadata.

        The calculation depends on whether gain calibration was applied:

        - WITH gain applied: The audio has been scaled by the sensitivity
          factor. dBFS of the processed audio directly represents the
          acoustic level relative to 0 dBFS = reference_dbspl.
          Formula: dBSPL = dBFS + reference_dbspl

        - WITHOUT gain applied (raw audio with metadata): We have the
          sensitivity value but it wasn't applied to the audio.
          Formula: dBSPL = dBFS - sensitivity_dbfs + reference_dbspl

        :param dbfs: Measured dBFS level from audio.
        :param ctx: Pipeline context with calibration values.
        :return: Calculated dBSPL value.
        """
        sensitivity = ctx.sensitivity_dbfs
        reference = ctx.reference_dbspl

        if ctx.is_gain_calibrated():
            # Gain was applied - audio is sensitivity-corrected
            # The gain transformer scaled audio by 10^(sensitivity_dbfs/20)
            # So dBFS now represents: original_dbfs + sensitivity_dbfs
            # To get dBSPL: add reference (since 0 dBFS = reference_dbspl)
            #
            # Actually, looking at the gain calculation:
            # gain = 10^(sens_db/20) where sens_db is the calculated sensitivity
            # After gain: audio_level_dbfs = original_dbfs + sens_db
            #
            # For dBSPL: we need original_dbfs - sensitivity + reference
            # Since audio is already gained: dbfs = original + sensitivity
            # So: dBSPL = dbfs - sensitivity + reference... wait, that's wrong
            #
            # Let me reconsider: the gain normalizes the mic response.
            # A mic with -18 dBFS sensitivity at 94 dBSPL means:
            # At 94 dBSPL input -> mic outputs -18 dBFS
            # After gain of 10^(18/20) = ~8x, output becomes ~0 dBFS
            # So 0 dBFS (after gain) = 94 dBSPL
            # Therefore: dBSPL = dBFS + reference_dbspl
            return dbfs + reference
        else:
            # Raw audio - need full sensitivity offset
            # dBSPL = dBFS - sensitivity_dbfs + reference_dbspl
            return self._audio_metrics.dBSPL(
                dbfs_level=dbfs,
                sensitivity_dbfs=sensitivity,
                reference_dbspl=reference,
            )


class DecibelMeterApp(AudioBaseApp):
    """
    The main application class for real-time SPL measurement.

    Stitches together hardware, calibration pipeline, and metrics sink.
    """

    def __init__(self, config: AppConfig):
        logger.debug("Initializing DecibelMeterApp...")

        pipeline = AudioPipeline(sample_rate=config.sample_rate)

        pipeline.add_sink(AudioMetricsSink(sample_rate=config.sample_rate))

        super().__init__(app_config=config, pipeline=pipeline)
        logger.info("DecibelMeterApp initialized.")


def _run_tui(config: AppConfig, output_dir: str = "recordings") -> None:
    import queue

    from .real_time_meter_tui import MeterTuiApp, TuiMetricsSink, TuiRecordingSink

    metrics_queue: queue.Queue[dict] = queue.Queue(maxsize=5)
    recording_sink = TuiRecordingSink(sample_rate=config.sample_rate, output_dir=output_dir)

    pipeline = AudioPipeline(sample_rate=config.sample_rate)
    pipeline.add_sink(TuiMetricsSink(sample_rate=config.sample_rate, metrics_queue=metrics_queue))
    pipeline.add_sink(recording_sink)

    audio_app = AudioBaseApp(app_config=config, pipeline=pipeline)
    tui = MeterTuiApp(
        audio_app=audio_app,
        metrics_queue=metrics_queue,
        config=config,
        recording_sink=recording_sink,
    )
    tui.run()


def main():
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--tui", action="store_true", default=False)
    pre.add_argument("--output-dir", default="recordings")
    pre.add_argument("--log-file", default=None)
    pre.add_argument("--log-append", action="store_true", default=False)
    pre_args, remaining = pre.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining

    if pre_args.log_file:
        mode = "a" if pre_args.log_append else "w"
        fh = logging.FileHandler(pre_args.log_file, mode=mode, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(levelname)s %(threadName)s %(message)s"))
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(fh)

    logger.info("Initializing Real Time Meter...")

    args = AppArgs.get_args()
    app = None

    try:
        config = AppArgs.validate_args(args)
        if pre_args.tui:
            _run_tui(config, output_dir=pre_args.output_dir)
        else:
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
