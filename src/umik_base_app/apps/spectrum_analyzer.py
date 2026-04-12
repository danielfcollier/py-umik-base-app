import logging
import sys
import webbrowser

from umik_base_app import AppArgs, AppConfig, AudioBaseApp, AudioPipeline
from umik_base_app.sinks.websocket_sink import WebSocketSink
from umik_base_app.transformers.calibrator_adapter import CalibratorAdapter

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
        logger.info(f"SpectrumAnalyzerApp initialized. WebSocket on port {ws_port}")

    def close(self):
        super().close()


def main():
    logger.info("Initializing Spectrum Analyzer...")

    parser = AppArgs.get_parser()
    parser.add_argument("--port", type=int, default=8767, help="WebSocket/HTTP port (default: 8767)")
    args = parser.parse_args()

    app = None
    try:
        config = AppArgs.validate_args(args)
        app = SpectrumAnalyzerApp(config, ws_port=args.port)
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
