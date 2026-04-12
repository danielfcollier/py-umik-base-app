import logging
import sys

from umik_base_app import AppArgs, AppConfig, AudioBaseApp, AudioPipeline
from umik_base_app.transformers.calibrator_adapter import CalibratorAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(threadName)s %(message)s")
logger = logging.getLogger(__name__)


class SpectrumAnalyzerApp(AudioBaseApp):
    def __init__(self, config: AppConfig):
        pipeline = AudioPipeline()
        if config.audio_calibrator:
            pipeline.add_transformer(CalibratorAdapter(config.audio_calibrator))
        super().__init__(app_config=config, pipeline=pipeline)
        logger.info("SpectrumAnalyzerApp initialized.")


def main():
    logger.info("Initializing Spectrum Analyzer...")
    args = AppArgs.get_args()
    app = None
    try:
        config = AppArgs.validate_args(args)
        app = SpectrumAnalyzerApp(config)
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
