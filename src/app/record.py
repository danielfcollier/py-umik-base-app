"""
Application script for recording audio to a WAV file.

This script sets up a recording pipeline that captures audio (optionally calibrated)
and writes it to disk using the Recorder library. It treats the output path as a
directory and automatically generates a timestamped filename.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import sys
from pathlib import Path

from src.audio_app_config import AudioAppArgs, AudioAppConfig
from src.base_audio_app import BaseAudioApp
from src.library.audio_device.calibrator_adapter import AudioDeviceCalibratorAdapter
from src.library.audio_device.config import AudioDeviceConfig
from src.library.audio_pipeline import AudioPipeline
from src.library.audio_streams.recorder import AudioStreamsRecorder
from src.library.audio_streams.recorder_adapter import AudioStreamsRecorderAdapter

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


class RecorderApp(BaseAudioApp):
    """
    A concrete application for recording audio streams to a WAV file.
    """

    def __init__(self, app_config: AudioAppConfig, output_dir: str):
        """
        Initializes the RecorderApp by composing the pipeline components.
        Checks and creates the output directory if it does not exist, then
        generates a unique filename based on the current timestamp.
        """
        logger.debug(f"Initializing RecorderApp with output directory: {output_dir}")

        # --- 0. Directory & Filename Setup ---
        dir_path = Path(output_dir).resolve()

        # Create the folder if it doesn't exist
        if not dir_path.exists():
            logger.info(f"Output directory does not exist. Creating: {dir_path}")
            dir_path.mkdir(parents=True, exist_ok=True)

        self.dir_path = dir_path

        # --- 1. Configuration Bridge ---
        device_config = AudioDeviceConfig(
            target_audio_device=app_config.audio_device,
            sample_rate=app_config.sample_rate,
            buffer_seconds=app_config.buffer_seconds,
            high_priority=True,
        )

        # --- 2. Instantiate Library (Manager) ---
        self._recorder = AudioStreamsRecorder(
            base_path=self.dir_path,
            sample_rate=int(device_config.sample_rate),
            channels=1,
            sample_width=2,
        )

        # Open the file resource immediately
        self._recorder.open()

        # --- 3. Instantiate the Adapter (The Sink) ---
        recorder_sink = AudioStreamsRecorderAdapter(self._recorder)

        # --- 4. Build the Pipeline ---
        pipeline = AudioPipeline()

        if app_config.audio_calibrator:
            logger.info("Adding Calibration Processor to pipeline.")
            calibrator_adapter = AudioDeviceCalibratorAdapter(app_config.audio_calibrator)
            pipeline.add_processor(calibrator_adapter)

        pipeline.add_sink(recorder_sink)

        # --- 5. Initialize Base Application ---
        super().__init__(audio_config=device_config, pipeline=pipeline)

    def close(self):
        """Overrides close to ensure the WAV file is properly closed."""
        if hasattr(self, "_recorder"):
            self._recorder.close()
            logger.info("RecorderApp resources have been released.")

        super().close()


if __name__ == "__main__":
    logger.info("Initializing Audio Recorder Application...")

    parser = AudioAppArgs.get_parser()

    # Updated argument to reflect directory input
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default="recordings",
        help="Directory to save the recording. Default: recordings",
    )
    args = parser.parse_args()

    app: RecorderApp | None = None
    try:
        config = AudioAppArgs.validate_args(args)
        app = RecorderApp(app_config=config, output_dir=args.output_dir)
        app.run()
    except (ValueError, SystemExit) as e:
        logger.error(f"Configuration or Device Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)

    # Log the final file path for the user
    if app:
        logger.info(f"Recording saved to: {app.dir_path}")
    logger.info("Audio Recorder Application has shut down.")
