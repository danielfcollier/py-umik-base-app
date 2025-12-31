"""
Application script for recording audio to a WAV file.

This script sets up a recording pipeline that captures audio (optionally calibrated)
and writes it to disk using the IORecorder library. It treats the output path as a
directory and automatically generates a timestamped filename.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import sys
from pathlib import Path

from umik_base_app.config import AppArgs, AppConfig
from umik_base_app.core.base_app import BaseApp
from umik_base_app.core.pipeline import AudioPipeline
from umik_base_app.hardware.calibrator_adapter import HardwareCalibratorAdapter
from umik_base_app.io.recorder import IORecorder
from umik_base_app.io.recorder_adapter import IORecorderAdapter

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


class RecorderApp(BaseApp):
    """
    A concrete application for recording audio streams to a WAV file.
    Combines the IORecorder with the BaseApp threading model.
    """

    def __init__(self, app_config: AppConfig, output_dir: str):
        """
        Initializes the RecorderApp by composing the pipeline components.

        :param app_config: Validated application configuration.
        :param output_dir: Path string where recordings should be saved.
        """
        logger.debug(f"Initializing RecorderApp with output directory: {output_dir}")

        self.dir_path = self._prepare_directory(output_dir)

        self._recorder = IORecorder(
            base_path=self.dir_path,
            sample_rate=int(app_config.sample_rate),
            channels=1,
            sample_width=2,
        )
        self._recorder.open()  # Open file handle immediately

        pipeline = AudioPipeline()

        if app_config.audio_calibrator:
            logger.info("Adding Calibration Processor to pipeline.")
            calibrator_adapter = HardwareCalibratorAdapter(app_config.audio_calibrator)
            pipeline.add_transformer(calibrator_adapter)

        recorder_sink = IORecorderAdapter(self._recorder)
        pipeline.add_sink(recorder_sink)

        super().__init__(app_config=app_config, pipeline=pipeline)

    def _prepare_directory(self, path_str: str) -> Path:
        """Helper to ensure output directory exists."""
        path = Path(path_str).resolve()
        if not path.exists():
            logger.info(f"Creating output directory: {path}")
            path.mkdir(parents=True, exist_ok=True)
        return path

    def close(self):
        """Overrides close to ensure the WAV file is properly released."""
        if hasattr(self, "_recorder"):
            self._recorder.close()
            logger.info("RecorderApp resources released.")
        super().close()


def main():
    logger.info("Initializing Audio Recorder Application...")

    parser = AppArgs.get_parser()

    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default="recordings",
        help="Directory to save the recording. Default: 'recordings'",
    )

    args = parser.parse_args()

    app: RecorderApp | None = None
    try:
        config = AppArgs.validate_args(args)
        app = RecorderApp(app_config=config, output_dir=args.output_dir)
        app.run()
    except (ValueError, SystemExit) as e:
        logger.error(f"Configuration Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nUser stopped recording.")
    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if app:
            logger.info(f"Recording saved to: {app.dir_path}")
            app.close()

    logger.info("Application shutdown complete.")


if __name__ == "__main__":
    main()
