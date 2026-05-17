"""
Unified entry point for the audio-tools CLI.
Dispatches flag-based commands to the appropriate application module.
"""

import argparse
import importlib
import sys

_DISPATCH = {
    "meter": ("umik_base_app.apps.real_time_meter", "main", "umik-real-time-meter"),
    "record": ("umik_base_app.apps.basic_recorder", "main", "umik-recorder"),
    "calibrate": ("umik_base_app.apps.umik1_calibrator", "main", "umik-calibrate"),
    "devices": ("umik_base_app.apps.list_audio_devices", "main", "umik-list-devices"),
    "analyze": ("umik_base_app.apps.metrics_analyzer", "main", "umik-metrics-analyzer"),
    "plot": ("umik_base_app.apps.metrics_plotter", "main", "umik-metrics-plotter"),
    "batch": ("scripts.audio_batch_analysis", "main", "umik-batch-analyze"),
    "enhance": ("scripts.enhance_voice", "main", "umik-enhance-audio"),
    "convert": ("umik_base_app.scripts.convert_audio", "main", "umik-convert"),
}

_HELP = {
    "meter": "Real-time SPL / LUFS / dBFS meter",
    "record": "Calibrated audio recorder (WAV)",
    "calibrate": "Generate FIR filter from a calibration file",
    "devices": "List available audio input devices",
    "analyze": "Analyze a WAV file and export metrics to CSV",
    "plot": "Plot a metrics CSV as a chart",
    "batch": "Batch-analyze a directory of WAV files",
    "enhance": "Filter and enhance voice audio",
    "convert": "Convert WAV recordings to OGG, MP3, or AAC",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="audio-tools",
        description="Audio measurement and processing toolkit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Pass additional flags after the mode flag:\n"
               "  audio-tools --meter --calibration-file umik-1/700.txt\n"
               "  audio-tools --convert recordings/ --format ogg mp3\n"
               "  audio-tools --record --output-dir recordings/\n",
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    for flag, desc in _HELP.items():
        mode.add_argument(f"--{flag}", action="store_true", help=desc)

    args, remaining = parser.parse_known_args()

    for flag, (module_path, func_name, argv0) in _DISPATCH.items():
        if getattr(args, flag):
            module = importlib.import_module(module_path)
            sys.argv = [argv0] + remaining
            getattr(module, func_name)()
            return
