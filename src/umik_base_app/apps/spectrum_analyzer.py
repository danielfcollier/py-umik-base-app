import logging
import os
import sys
import tempfile
import threading
import webbrowser

from pathlib import Path

import numpy as np

from umik_base_app import AppArgs, AppConfig, AudioBaseApp, AudioPipeline
from umik_base_app.core.operational_mode import OperationalMode
from umik_base_app.core.pipeline_context import PipelineContext
from umik_base_app.settings import get_settings
from umik_base_app.sinks.recorder_sink import RecorderSink
from umik_base_app.sinks.websocket_sink import WebSocketSink
from umik_base_app.transformers.calibrator_adapter import CalibratorAdapter
from umik_base_app.transformers.calibrator_transformer import CalibratorTransformer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(threadName)s %(message)s")
logger = logging.getLogger(__name__)

import umik_base_app.sinks.websocket_sink as _ws_mod
_ws_mod._app_instance = None


class RawRecordingTransformer:
    """Pass-through transformer that captures raw (pre-calibration) audio into RecorderSink.

    Pinned at the front of the processor chain so recordings are never affected
    by the sensitivity gain (+18 dB) applied by CalibratorAdapter for dBSPL display.
    """

    def __init__(self, recorder: RecorderSink):
        self._recorder = recorder

    def process(self, ctx: PipelineContext) -> PipelineContext:
        if self._recorder._is_open:
            int16 = (np.clip(ctx.audio.flatten(), -1.0, 1.0) * 32767).astype(np.int16)
            self._recorder.write(int16.tobytes())
        return ctx


class SpectrumAnalyzerApp(AudioBaseApp):
    _instance = None

    def __init__(self, config: AppConfig, ws_port: int = 8767):
        import umik_base_app.sinks.websocket_sink as _ws_mod
        _ws_mod._app_instance = self
        self._config = config
        logger.info(f"App instance registered in websocket_sink module")

        self._ws_sink = WebSocketSink(
            sample_rate=config.sample_rate,
            chunk_size=int(config.sample_rate * config.buffer_seconds),
            ws_port=ws_port,
        )

        self._recorder = RecorderSink(
            base_path=Path("recordings"),
            sample_rate=int(config.sample_rate),
        )
        self._recording_transformer = RawRecordingTransformer(self._recorder)

        pipeline = AudioPipeline(sample_rate=config.sample_rate)
        pipeline.add_sink(self._ws_sink)

        super().__init__(app_config=config, pipeline=pipeline)
        # Prepend after super() so we stay ahead of any CLI calibrator it injects.
        self._pipeline.prepend_transformer(self._recording_transformer)
        self._ws_sink.start()
        self._listener = None
        self._hw_config = None
        logger.info(f"SpectrumAnalyzerApp initialized. WebSocket on port {ws_port}")

    def _setup_threads(self):
        from umik_base_app.hardware_config import HardwareConfig
        from umik_base_app.listener_thread import ListenerThread
        from umik_base_app.consumer_thread import ConsumerThread
        from umik_base_app.settings import get_settings as _get_settings

        settings = _get_settings()
        mode = self._config.run_mode

        if mode in (OperationalMode.MONOLITHIC, OperationalMode.PRODUCER):
            if not self._config.audio_device:
                logger.error("Cannot start Listener: No audio device configured.")
                return

            self._hw_config = HardwareConfig(
                target_audio_device=self._config.audio_device,
                sample_rate=self._config.sample_rate,
                buffer_seconds=self._config.buffer_seconds,
            )

            logger.info("Starting Audio Listener (Producer)...")
            self._listener = ListenerThread(
                audio_device_config=self._hw_config,
                transport=self._transport,
                stop_event=self._stop_event,
            )
            self._threads.append(
                threading.Thread(target=self._thread_guard(self._listener.run), name="ListenerThread", daemon=True)
            )

        if mode in (OperationalMode.MONOLITHIC, OperationalMode.CONSUMER):
            logger.info("Starting Audio Consumer (Processor)...")
            consumer = ConsumerThread(
                transport=self._transport,
                stop_event=self._stop_event,
                pipeline=self._pipeline,
                consumer_queue_timeout_seconds=settings.CONSUMER_QUEUE_TIMEOUT_SECONDS,
            )
            self._threads.append(
                threading.Thread(target=self._thread_guard(consumer.run), name="ConsumerThread", daemon=True)
            )

    def close(self):
        self._recorder.close()
        super().close()

    def start_recording(self) -> str:
        self._recorder.open()
        logger.info(f"Recording started: {self._recorder.current_file}")
        return self._recorder.current_file

    def stop_recording(self) -> str:
        saved = self._recorder.current_file
        self._recorder.close()
        logger.info(f"Recording stopped: {saved}")
        return saved

    def load_calibration(self, content: str) -> bool:
        settings = get_settings()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            cal_path = f.name

        try:
            calibrator = CalibratorTransformer(
                calibration_file_path=cal_path,
                sample_rate=self._config.sample_rate,
                num_taps=settings.AUDIO.NUM_TAPS,
                nominal_sensitivity_dbfs=settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS,
                reference_dbspl=settings.HARDWARE.REFERENCE_DBSPL,
            )
            adapter = CalibratorAdapter(
                calibrator=calibrator,
                sensitivity_dbfs=calibrator.sensitivity_dbfs,
                reference_dbspl=calibrator.reference_dbspl,
            )
            self._pipeline._processors = [self._recording_transformer, adapter]
            logger.info("Calibration loaded from web UI")
            return True
        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            return False
        finally:
            os.unlink(cal_path)

    def switch_device(self, device_id: int) -> bool:
        try:
            import sounddevice as sd

            device_info = sd.query_devices(device_id)
            if device_info["max_input_channels"] <= 0:
                logger.error(f"Device {device_id} has no input channels")
                return False

            self._config.audio_device.id = device_id
            self._config.audio_device.name = device_info["name"]
            self._config.audio_device.native_rate = device_info["default_samplerate"]

            self._hw_config.id = device_id

            if self._listener:
                self._listener.restart_event.set()

            self._pipeline._processors = [self._recording_transformer]
            self._ws_sink.notify_calibration_cleared()
            logger.info(f"Switched to device {device_id}: {device_info['name']}")
            return True
        except Exception as e:
            logger.error(f"Failed to switch device: {e}")
            return False


def main():
    logger.info("Initializing Spectrum Analyzer...")

    parser = AppArgs.get_parser()
    parser.add_argument("--port", type=int, default=8767, help="WebSocket/HTTP port (default: 8767)")
    parser.add_argument("--no-open", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    app = None
    try:
        _settings = get_settings()
        user_buffer = float(args.buffer_seconds)
        spectrum_buffer = user_buffer if user_buffer != _settings.AUDIO.BUFFER_SECONDS else 0.1
        args.buffer_seconds = 3.0  # pass LUFS validation silently
        config = AppArgs.validate_args(args)
        config.buffer_seconds = spectrum_buffer
        logger.info(f"Spectrum analyzer buffer: {spectrum_buffer}s")
        app = SpectrumAnalyzerApp(config, ws_port=args.port)
        if not args.no_open:
            url = f"http://localhost:{args.port}"
            logger.info(f"Opening browser: {url}")
            webbrowser.open(url)
        app.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    except Exception as e:
        logger.critical(f"Application failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if app:
            app.close()
    logger.info("Application shutdown complete.")


if __name__ == "__main__":
    main()
