"""
Centralized configuration management using Pydantic Settings.

This module defines the global application settings, allowing values to be
overridden via environment variables or a .env file.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class AudioSettings(BaseModel):
    """General audio application settings."""

    BUFFER_SECONDS: float = 5.0
    MIN_BUFFER_SECONDS: float = 3.0
    SAMPLE_RATE: int = 48000
    NUM_TAPS: int = 1024
    LUFS_WINDOW_SECONDS: int = 3
    DTYPE: str = "float32"
    HIGH_PRIORITY: bool = False


class MetricsSettings(BaseModel):
    """Audio metrics calculation thresholds."""

    DBFS_LOWER_BOUND: float = -120.0
    LUFS_LOWER_BOUND: float = -120.0
    INTERVAL_SECONDS: int = 3


class RecorderSettings(BaseModel):
    """File recording settings."""

    ROTATION_SECONDS: int = 3600
    DEFAULT_RECORDING_PATH: Path = Path("recordings")


class HardwareSettings(BaseModel):
    """Hardware-specific defaults (e.g., Microphone sensitivity)."""

    NOMINAL_SENSITIVITY_DBFS: float = -18.0
    REFERENCE_DBSPL: float = 94.0
    TARGET_DEVICE_NAME: str = "UMIK-1"


class ZmqSettings(BaseModel):
    """Settings for ZeroMQ transport."""

    HOST: str = "127.0.0.1"
    PORT: int = 5555
    MESSAGES: int | None = None  # None means unlimited


class Settings(BaseSettings):
    """
    Main settings class acting as the source of truth for the application.

    Environment variables are prefixed with 'APP__'.
    Example: APP__AUDIO__SAMPLE_RATE=44100
    """

    model_config = SettingsConfigDict(env_prefix="APP__", env_nested_delimiter="__", env_file=".env", extra="ignore")

    AUDIO: AudioSettings = AudioSettings()
    METRICS: MetricsSettings = MetricsSettings()
    RECORDER: RecorderSettings = RecorderSettings()
    HARDWARE: HardwareSettings = HardwareSettings()
    ZMQ: ZmqSettings = ZmqSettings()

    RECONNECT_DELAY_SECONDS: int = 5
    RECONNECT_MAX_RETRIES: int = 10
    CONSUMER_QUEUE_TIMEOUT_SECONDS: int = 1


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings object.
    Use this function instead of instantiating Settings directly to ensure
    consistent state across the application.
    """
    return Settings()


settings = get_settings()
