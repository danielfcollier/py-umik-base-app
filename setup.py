import os
from setuptools import setup, find_packages


def get_scripts_data_files():
    data_files = []
    base_install_path = "/usr/lib/umik-tools"
    for root, _, files in os.walk("scripts"):
        if files:
            install_dir = os.path.join(base_install_path, root)
            file_paths = [os.path.join(root, f) for f in files]
            data_files.append((install_dir, file_paths))
    return data_files


setup(
    package_dir={"": "src"},
    packages=find_packages(
        where="src",
        include=["umik_base_app", "umik_base_app.*", "scripts", "scripts.*"],
    ),
    data_files=get_scripts_data_files(),
    description="Base utilities for audio measurement with UMIK microphones.",
    long_description=(
        "This package provides the 'umik' CLI for audio measurement and calibration\n"
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
