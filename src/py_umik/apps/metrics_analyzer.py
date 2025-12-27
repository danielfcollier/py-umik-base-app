"""
Full Audio Metrics Analyzer.
Calculates RMS, Flux, dBFS, LUFS, and dBSPL for a WAV file.

This script processes a single WAV file to generate a time-series CSV of various
audio metrics. It supports determining the absolute start time from the filename
(or manual argument) to provide real-world timestamps in the output.

It uses a sliding window approach for LUFS calculation to adhere to the ITU-R BS.1770
standard, ensuring accurate loudness measurements even for short analysis chunks.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import csv
import logging
import os
import re
import sys
from datetime import datetime, timedelta

import numpy as np
from scipy.io import wavfile

from py_umik.hardware.calibrator import HardwareCalibrator
from py_umik.processing.audio_metrics import AudioMetrics

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


def load_and_normalize_wav(file_path):
    """
    Loads a WAV file and converts it to a normalized float32 format.

    This function handles the conversion of raw audio data (typically int16 or int32)
    into a floating-point range of -1.0 to 1.0, which is required for accurate
    metric calculations. It also handles stereo-to-mono downmixing.

    :param file_path: The absolute or relative path to the .wav file.
    :return: A tuple containing (sample_rate, audio_data_array).
             Exits the program if the file is not found.
    """
    try:
        sample_rate, data = wavfile.read(file_path)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0

    return sample_rate, data


def get_start_time(file_path, manual_start_str=None):
    """
    Determines the recording start time for timestamp generation.

    It attempts to parse a datetime string from the filename first. If that fails,
    it checks for a manually provided start time argument.

    Priority 1: Filename Pattern (e.g., recording_2025-12-18 01:48:06.wav)
    Priority 2: Manual Argument passed via CLI.

    :param file_path: The path to the audio file (used for filename regex).
    :param manual_start_str: An optional ISO 8601 formatted string provided by the user.
    :return: A datetime object representing the start time, or None if undetermined.
    """
    filename = os.path.basename(file_path)
    # Matches YYYY-MM-DD followed by HH:MM:SS with space, T, or _ separator
    match = re.search(r"(\d{4}-\d{2}-\d{2}[\sT_]\d{2}[:\.]\d{2}[:\.]\d{2})", filename)

    if match:
        dt_str = match.group(1).replace("_", " ").replace("T", " ").replace(".", ":")
        try:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    if manual_start_str:
        try:
            return datetime.fromisoformat(manual_start_str)
        except ValueError:
            logger.warning("Invalid manual start time format. Use ISO (YYYY-MM-DD HH:MM:SS).")

    return None


def analyze_file(file_path, output_csv, chunk_ms, sensitivity, reference, manual_start=None):
    """
    Performs the main analysis loop on the audio file.

    It chunks the audio into small segments (defined by chunk_ms), calculates metrics
    for each segment, and aggregates them into a CSV file. It handles the sliding
    window logic required for accurate LUFS calculation and computes global statistics
    at the end.

    :param file_path: Path to the input WAV file.
    :param output_csv: Path where the output CSV will be saved.
    :param chunk_ms: Size of the analysis window in milliseconds (e.g., 100ms).
    :param sensitivity: Microphone sensitivity in dBFS (from calibration). None if not calibrated.
    :param reference: Reference SPL value (usually 94.0 dB).
    :param manual_start: Optional string to force a specific start time.
    """
    logger.info(f"🎧 Loading {file_path}...")
    sample_rate, full_audio = load_and_normalize_wav(file_path)

    metrics_engine = AudioMetrics(sample_rate=sample_rate)

    start_dt = get_start_time(file_path, manual_start)
    if start_dt:
        logger.info(f"🕒 Reference Start Time: {start_dt}")
    else:
        logger.info("🕒 No absolute time reference found. Using relative time.")

    chunk_size = int(sample_rate * (chunk_ms / 1000))
    total_chunks = len(full_audio) // chunk_size
    duration = len(full_audio) / sample_rate

    # LUFS Requirement: Minimum 400ms window (ITU-R BS.1770)
    # We use 1000ms (1s) to ensure we have enough overlapping blocks for a valid reading.
    lufs_window_size = int(sample_rate * 1.0)

    logger.info(f"📊 Analyzing {duration:.2f}s audio in {chunk_ms}ms chunks.")
    if sensitivity is not None:
        logger.info(f"   dBSPL Calibration: Sens={sensitivity:.2f}dBFS, Ref={reference:.1f}dB")
    else:
        logger.warning("   ⚠️  No calibration provided. dBSPL will be skipped.")

    results = []

    # --- Processing Loop ---
    for i in range(total_chunks):
        start = i * chunk_size
        end = start + chunk_size
        chunk = full_audio[start:end]

        rel_time = end / sample_rate

        # Calculate Absolute Timestamp
        abs_time_str = ""
        if start_dt:
            current_dt = start_dt + timedelta(seconds=rel_time)
            abs_time_str = current_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # 1. Basic Metrics
        rms = metrics_engine.rms(chunk)
        dbfs = metrics_engine.dBFS(chunk)
        flux = metrics_engine.flux(chunk, sample_rate)

        # 2. LUFS (Sliding Window of 1 Second)
        # We look back 1 second to calculate the "Momentary" loudness for this point.
        lufs_start = max(0, end - lufs_window_size)
        lufs_chunk = full_audio[lufs_start:end]

        try:
            # Only calculate if we have enough data (at least ~400ms is required by spec,
            # we use 95% of our 1s window for safety)
            if len(lufs_chunk) >= lufs_window_size * 0.4:  # Require at least 400ms valid data
                lufs = metrics_engine.lufs(lufs_chunk)
            else:
                lufs = -70.0
        except ValueError:
            lufs = -70.0

        # 3. dBSPL
        dbspl = None
        if sensitivity is not None:
            dbspl = metrics_engine.dBSPL(dbfs, sensitivity, reference)

        row = {
            "time_sec": round(rel_time, 3),
            "timestamp": abs_time_str,
            "rms": round(rms, 6),
            "dbfs": round(dbfs, 2),
            "lufs": round(lufs, 2),
            "flux": round(flux, 2),
            "dbspl": round(dbspl, 2) if dbspl is not None else "",
        }
        results.append(row)

        if i % 100 == 0:
            logger.info(f"\rProcessing: {int((i / total_chunks) * 100)}%")

    logger.info("\rProcessing: 100% Complete.   ")
    # --- Global Stats ---
    global_lufs = metrics_engine.lufs(full_audio)
    max_flux = max(r["flux"] for r in results)
    max_dbfs = max(r["dbfs"] for r in results)

    logger.info("\n" + "=" * 40)
    logger.info("📈 GLOBAL SUMMARY")
    logger.info("=" * 40)
    logger.info(f"File Duration:   {duration:.2f} sec")
    logger.info(f"Integrated LUFS: {global_lufs:.2f} LUFS")
    logger.info(f"Peak dBFS:       {max_dbfs:.2f} dBFS")
    logger.info(f"Max Flux (Onset):{max_flux:.2f}")
    if sensitivity:
        max_spl = max(r["dbspl"] for r in results)
        logger.info(f"Max SPL:         {max_spl:.2f} dBSPL")
    logger.info("=" * 40)

    # Save to CSV
    keys = results[0].keys()
    with open(output_csv, "w", newline="") as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(results)

    logger.info(f"✅ Data saved to: {output_csv}")


def main():
    parser = argparse.ArgumentParser(description="Calculate full metrics for a WAV file.")
    parser.add_argument("file", help="Path to WAV file")
    parser.add_argument("--window", type=int, default=100, help="Analysis window in ms (default: 100)")
    parser.add_argument("--calibration-file", "-F", help="Path to UMIK-1 calibration file (.txt)")
    parser.add_argument("--output-file", "-o", help="Optional path for output CSV")
    parser.add_argument("--start-time", help="Force start time (YYYY-MM-DD HH:MM:SS) if filename parsing fails")

    args = parser.parse_args()

    # 1. Determine Sensitivity
    sens = None
    ref = 94.0
    if args.calibration_file:
        try:
            sens, ref = HardwareCalibrator.get_sensitivity_values(args.calibration_file)
        except Exception as e:
            logger.error(f"Failed to parse calibration file: {e}")
            sys.exit(1)

    # 2. Determine Output File
    if args.output_file:
        out_path = args.output_file
    else:
        base_name = os.path.splitext(args.file)[0]
        out_path = f"{base_name}.csv"

    analyze_file(args.file, out_path, args.window, sens, ref, args.start_time)


if __name__ == "__main__":
    main()
