import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

EPS = 1e-12


class NoiseFloorTracker:
    def __init__(self, capture_seconds: float = 5.0, sample_rate: float = 48000.0, chunk_size: int = 1024):
        self._capture_seconds = capture_seconds
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._target_frames = int(capture_seconds * sample_rate / chunk_size)
        self._capturing = False
        self._capture_frames: list[np.ndarray] = []
        self.noise_floor: Optional[np.ndarray] = None
        self.noise_floor_db: Optional[np.ndarray] = None

    @property
    def capturing(self) -> bool:
        return self._capturing

    @property
    def has_noise_floor(self) -> bool:
        return self.noise_floor_db is not None

    def start_capture(self):
        logger.info(f"Starting quiet room capture ({self._capture_seconds}s, {self._target_frames} frames)...")
        self._capturing = True
        self._capture_frames = []

    def feed(self, magnitude_db: np.ndarray):
        if not self._capturing:
            return
        self._capture_frames.append(magnitude_db.copy())
        if len(self._capture_frames) >= self._target_frames:
            stacked = np.array(self._capture_frames)
            self.noise_floor_db = np.mean(stacked, axis=0)
            self._capturing = False
            self._capture_frames = []
            logger.info(f"Quiet room captured. Avg level: {np.mean(self.noise_floor_db):.1f} dB")

    def get_snr(self, current_db: np.ndarray) -> tuple[np.ndarray, float]:
        if self.noise_floor_db is None:
            return np.zeros_like(current_db), 0.0
        snr_per_bin = current_db - self.noise_floor_db
        avg_snr = float(np.mean(snr_per_bin))
        return snr_per_bin, avg_snr

    @staticmethod
    def snr_status(avg_snr: float) -> str:
        if avg_snr > 10.0:
            return "OK"
        elif avg_snr > 3.0:
            return "LOW"
        else:
            return "NOISE"
