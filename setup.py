import importlib.util
import os

_version_file = os.path.join(os.path.dirname(__file__), "src", "umik_base_app", "_version.py")
_spec = importlib.util.spec_from_file_location("_version", _version_file)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
__version__ = _mod.__version__

from setuptools import find_packages, setup


setup(
    version=__version__,
    package_dir={"": "src"},
    packages=find_packages(
        where="src",
        include=["umik_base_app", "umik_base_app.*"],
    ),
    description="Base utilities for audio measurement with UMIK microphones.",
    long_description=(
        "This package provides the 'audio-tools' CLI for audio measurement and calibration\n"
        "using measurement microphones like the miniDSP UMIK-1 and UMIK-2. It includes:\n"
        "\n"
        " * Real-time SPL / LUFS / dBFS meter\n"
        " * Calibrated audio recorder (WAV)\n"
        " * Microphone calibration and FIR filter generation\n"
        " * Audio metrics analysis and visualization\n"
        " * WAV to OGG/MP3/AAC converter\n"
        "\n"
        "Designed for Linux (Raspberry Pi, Ubuntu) and macOS."
    ),
)
