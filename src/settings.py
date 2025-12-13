"""
Centralized configuration management using Pydantic Settings.

This module defines the global application settings, allowing values to be
overridden via environment variables or a .env file.

Usage:
    from src.settings import settings
    print(settings.audio.sample_rate)
"""

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AudioSettings(BaseModel):
    """General audio application settings."""

    buffer_seconds: float = 6.0
    min_buffer_seconds: float = 3.0
    sample_rate: int = 48000
    num_taps: int = 1024
    lufs_window_seconds: int = 3
    dtype: str = "float32"
    high_priority: bool = False


class MetricsSettings(BaseModel):
    """Audio metrics calculation thresholds."""

    dbfs_lower_bound: float = -120.0
    lufs_lower_bound: float = -120.0


class RecorderSettings(BaseModel):
    """File recording settings."""

    rotation_seconds: int = 3600
    default_recording_path: Path = Path("recordings")


class HardwareSettings(BaseModel):
    """Hardware-specific defaults (e.g., Microphone sensitivity)."""

    nominal_sensitivity_dbfs: float = -18.0
    reference_dbspl: float = 94.0


class Settings(BaseSettings):
    """
    Main settings class acting as the source of truth for the application.

    Environment variables are prefixed with 'APP__'.
    Example: APP__AUDIO__SAMPLE_RATE=44100
    """

    model_config = SettingsConfigDict(env_prefix="APP__", env_nested_delimiter="__", env_file=".env", extra="ignore")

    audio: AudioSettings = AudioSettings()
    metrics: MetricsSettings = MetricsSettings()
    recorder: RecorderSettings = RecorderSettings()
    hardware: HardwareSettings = HardwareSettings()


settings = Settings()
