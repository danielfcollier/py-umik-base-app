"""
Application script for recording audio to a WAV file.

This script sets up a recording pipeline that captures audio (optionally calibrated)
and writes it to disk using the RecorderSink library. It treats the output path as a
directory and automatically generates a timestamped filename.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import sys
from pathlib import Path

from umik_base_app import AppArgs, AppConfig, AudioBaseApp, AudioPipeline
from umik_base_app.sinks.recorder_adapter import RecorderSinkAdapter
from umik_base_app.sinks.recorder_sink import RecorderSink
from umik_base_app.transformers.calibrator_adapter import CalibratorAdapter

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


class RecorderApp(AudioBaseApp):
    """
    A concrete application for recording audio streams to a WAV file.
    Combines the RecorderSink with the AudioBaseApp threading model.
    """

    def __init__(self, app_config: AppConfig, output_dir: str):
        """
        Initializes the RecorderApp by composing the pipeline components.
        """
        self.output_path = Path(output_dir).resolve()
        self.output_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Initializing RecorderApp with output directory: {self.output_path}")

        self._recorder = RecorderSink(
            base_path=self.output_path,
            sample_rate=int(app_config.sample_rate),
            channels=1,
            sample_width=2,
        )
        self._recorder.open()

        pipeline = AudioPipeline()

        if app_config.audio_calibrator:
            logger.info("Adding Calibration Processor to pipeline.")
            pipeline.add_transformer(CalibratorAdapter(app_config.audio_calibrator))

        pipeline.add_sink(RecorderSinkAdapter(self._recorder))

        super().__init__(app_config=app_config, pipeline=pipeline)

    def close(self):
        """Overrides close to ensure the WAV file is properly released."""
        if hasattr(self, "_recorder"):
            self._recorder.close()
            logger.info("RecorderApp resources released.")
        super().close()


def main():
    logger.info("Initializing Audio Recorder Application...")

    parser = AppArgs.get_parser()
    parser.add_argument("-o", "--output-dir", default="recordings", help="Directory to save the recording.")
    args = parser.parse_args()

    app = None
    try:
        config = AppArgs.validate_args(args)
        app = RecorderApp(config, args.output_dir)
        app.run()
    except KeyboardInterrupt:
        logger.info("\nUser stopped recording.")
    except Exception as e:
        logger.critical(f"Application failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if app:
            app.close()
            logger.info(f"Recording saved to: {app.output_path}")

    logger.info("Application shutdown complete.")


if __name__ == "__main__":
    main()
