"""
Application script for recording audio to a WAV file.

This script sets up a recording pipeline that captures audio (optionally calibrated)
and writes it to disk using the Recorder library. It ensures the destination
folder exists before starting the recording.

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

    def __init__(self, app_config: AudioAppConfig, output_file: str):
        """
        Initializes the RecorderApp by composing the pipeline components.
        Checks and creates the output directory if it does not exist.
        """
        logger.debug(f"Initializing RecorderApp with output: {output_file}")

        # --- 0. Directory Setup ---
        path_obj = Path(output_file)

        # Check if the path is just a filename (no parents)
        if len(path_obj.parts) == 1:
            output_path = Path("recordings") / path_obj
        else:
            output_path = path_obj

        # Resolve to absolute path
        output_path = output_path.resolve()

        # Determine target directory
        if output_path.suffix:
            # It's a file path (e.g., recordings/rec.wav) -> ensure parent dir exists
            target_dir = output_path.parent
        else:
            # It's a directory path -> ensure it exists
            target_dir = output_path

        # Create the folder if it doesn't exist
        if not target_dir.exists():
            logger.info(f"Output directory does not exist. Creating: {target_dir}")
            target_dir.mkdir(parents=True, exist_ok=True)

        # --- 1. Configuration Bridge ---
        device_config = AudioDeviceConfig(
            target_audio_device=app_config.audio_device,
            sample_rate=app_config.sample_rate,
            buffer_seconds=app_config.buffer_seconds,
            high_priority=True,
        )

        # --- 2. Instantiate Library (Manager) ---
        self._recorder = AudioStreamsRecorder(
            base_path=output_path,
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
        self.output_file = str(output_path)

    def close(self):
        """Overrides close to ensure the WAV file is properly closed."""
        if hasattr(self, "_recorder"):
            self._recorder.close()
            logger.info("RecorderApp resources have been released.")

        super().close()


if __name__ == "__main__":
    logger.info("Initializing Audio Recorder Application...")

    parser = AudioAppArgs.get_parser()
    
    # Updated default to include the folder explicitly
    parser.add_argument(
        "-o",
        "--output-file",
        type=str,
        default="recordings/recording.wav",
        help="Path to the output WAV file (or directory). Default: recordings/recording.wav",
    )
    args = parser.parse_args()

    app: RecorderApp | None = None
    try:
        config = AudioAppArgs.validate_args(args)
        app = RecorderApp(app_config=config, output_file=args.output_file)
        app.run()
    except (ValueError, SystemExit) as e:
        logger.error(f"Configuration or Device Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
        
    # Log the final resolved path used by the app
    final_path = app.output_file if app else args.output_file
    logger.info(f"Recording saved to: {final_path}")
    logger.info("Audio Recorder Application has shut down.")