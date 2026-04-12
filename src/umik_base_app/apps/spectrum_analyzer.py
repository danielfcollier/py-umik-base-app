import logging
import os
import sys
import tempfile
import threading
import webbrowser

from umik_base_app import AppArgs, AppConfig, AudioBaseApp, AudioPipeline
from umik_base_app.settings import get_settings
from umik_base_app.sinks.websocket_sink import WebSocketSink
from umik_base_app.transformers.calibrator_adapter import CalibratorAdapter
from umik_base_app.transformers.calibrator_transformer import CalibratorTransformer

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(threadName)s %(message)s")
logger = logging.getLogger(__name__)


class SpectrumAnalyzerApp(AudioBaseApp):
    _instance = None

    def __init__(self, config: AppConfig, ws_port: int = 8767):
        SpectrumAnalyzerApp._instance = self
        self._config = config

        self._ws_sink = WebSocketSink(
            sample_rate=config.sample_rate,
            chunk_size=int(config.sample_rate * config.buffer_seconds),
            ws_port=ws_port,
        )

        pipeline = AudioPipeline()
        if config.audio_calibrator:
            pipeline.add_transformer(CalibratorAdapter(config.audio_calibrator))
        pipeline.add_sink(self._ws_sink)

        super().__init__(app_config=config, pipeline=pipeline)
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

        if mode in ["monolithic", "producer"]:
            if not self._config.audio_device:
                logger.error("Cannot start Listener: No audio device configured.")
                return

            self._hw_config = HardwareConfig(
                target_audio_device=self._config.audio_device,
                sample_rate=self._config.sample_rate,
                buffer_seconds=self._config.buffer_seconds,
                high_priority=settings.AUDIO.HIGH_PRIORITY,
            )

            logger.info("Starting Audio Listener (Producer)...")
            self._listener = ListenerThread(
                audio_device_config=self._hw_config,
                transport=self._transport,
                stop_event=self._stop_event,
            )
            self._threads.append(
                threading.Thread(target=self._thread_guard(self._listener.run), name="ListenerThread")
            )

        if mode in ["monolithic", "consumer"]:
            logger.info("Starting Audio Consumer (Processor)...")
            consumer = ConsumerThread(
                transport=self._transport,
                stop_event=self._stop_event,
                pipeline=self._pipeline,
                consumer_queue_timeout_seconds=settings.CONSUMER_QUEUE_TIMEOUT_SECONDS,
            )
            self._threads.append(
                threading.Thread(target=self._thread_guard(consumer.run), name="ConsumerThread")
            )

    def close(self):
        super().close()

    def load_calibration(self, content: str) -> bool:
        settings = get_settings()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            cal_path = f.name

        try:
            calibrator = CalibratorTransformer(
                calibration_file_path=cal_path,
                sample_rate=self._config.sample_rate,
                num_taps=self._config.num_taps or settings.AUDIO.NUM_TAPS,
                nominal_sensitivity_dbfs=settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS,
                reference_dbspl=settings.HARDWARE.REFERENCE_DBSPL,
            )
            adapter = CalibratorAdapter(calibrator)
            self._pipeline._processors = [adapter]
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
        config = AppArgs.validate_args(args)
        config.buffer_seconds = 0.1
        logger.info(f"Spectrum analyzer: buffer override to {config.buffer_seconds}s for low latency")
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
