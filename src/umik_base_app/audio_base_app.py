"""
Defines the base application class for audio monitoring tasks.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import threading

from .app_config import AppConfig
from .audio_pipeline import AudioPipeline
from .base_thread_app import BaseThreadApp
from .consumer_thread import ConsumerThread
from .core.operational_mode import OperationalMode
from .create_transport import create_transport
from .hardware_config import HardwareConfig
from .listener_thread import ListenerThread
from .settings import get_settings
from .transformers.calibrator_adapter import CalibratorAdapter
from .transports.base_transport import AudioTransport

logger = logging.getLogger(__name__)
settings = get_settings()


class AudioBaseApp(BaseThreadApp):
    """
    Abstract base class for audio applications.
    Orchestrates Listener (Producer) and Consumer (Pipeline) threads based on Topology.
    """

    def __init__(
        self,
        app_config: AppConfig,
        pipeline: AudioPipeline,
        transport: AudioTransport | None = None,
    ):
        """
        Initializes the application with a unified configuration object.

        :param app_config: Validated AppConfig containing topology and hardware
            settings.
        :param pipeline: Configured AudioPipeline.
        :param transport: Optional transport for dependency injection. If None,
            creates transport via create_transport() based on app_config.
        """
        super().__init__()
        self._config = app_config
        self._pipeline = pipeline

        if app_config.calibration is not None:
            cal = app_config.calibration
            pipeline.prepend_transformer(
                CalibratorAdapter(
                    calibrator=cal.transformer,
                    sensitivity_dbfs=cal.sensitivity_dbfs,
                    reference_dbspl=cal.reference_dbspl,
                )
            )
            logger.info(
                f"Calibration auto-injected: {cal.sensitivity_dbfs:.3f} dBFS ref {cal.reference_dbspl:.1f} dBSPL"
            )

        # Use injected transport or create one based on config
        if transport is not None:
            self._transport = transport
        else:
            self._transport = create_transport(
                mode=app_config.run_mode,
                zmq_host=app_config.zmq_host,
                zmq_port=app_config.zmq_port,
            )
        logger.info(f"AudioBaseApp initialized in '{app_config.run_mode.value}' mode.")

    def _setup_threads(self):
        """
        Sets up threads based on the configured run_mode (Topology).
        """
        mode = self._config.run_mode

        # --- Producer Logic (Listener) ---
        # Active in MONOLITHIC or PRODUCER mode.
        if mode in (OperationalMode.MONOLITHIC, OperationalMode.PRODUCER):
            if not self._config.audio_device:
                logger.error("Cannot start Listener: No audio device configured.")
                return

            # Construct HardwareConfig on-the-fly for the listener
            hw_config = HardwareConfig(
                target_audio_device=self._config.audio_device,
                sample_rate=self._config.sample_rate,
                buffer_seconds=self._config.buffer_seconds,
            )

            logger.info("Starting Audio Listener (Producer)...")
            listener = ListenerThread(
                audio_device_config=hw_config,
                transport=self._transport,
                stop_event=self._stop_event,
            )
            self._threads.append(threading.Thread(target=self._thread_guard(listener.run), name="ListenerThread"))

        # --- Consumer Logic (Brain) ---
        # Active in MONOLITHIC or CONSUMER mode.
        if mode in (OperationalMode.MONOLITHIC, OperationalMode.CONSUMER):
            logger.info("Starting Audio Consumer (Processor)...")
            consumer = ConsumerThread(
                transport=self._transport,
                stop_event=self._stop_event,
                pipeline=self._pipeline,
                consumer_queue_timeout_seconds=settings.CONSUMER_QUEUE_TIMEOUT_SECONDS,
            )
            self._threads.append(threading.Thread(target=self._thread_guard(consumer.run), name="ConsumerThread"))

    def close(self):
        """Clean up transport resources."""
        super().close()  # sets stop event first so threads exit cleanly
        if hasattr(self, "_transport"):
            self._transport.close()
