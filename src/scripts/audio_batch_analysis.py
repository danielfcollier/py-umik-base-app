"""
Batch Audio Metrics Analyzer.
Processes all WAV files in a directory and saves metrics to a single CSV.

This script iterates through a specified directory, loads every .wav file,
normalizes the audio data, and calculates time-series metrics (RMS, dBFS,
LUFS, Spectral Flux, and dBSPL) using the project's audio libraries.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import csv
import glob
import logging
import os
import sys

import numpy as np
from scipy.io import wavfile

from umik_base_app import AudioMetrics
from umik_base_app.transformers.calibrator_transformer import CalibratorTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def load_and_normalize_wav(file_path):
    """
    Loads a WAV file and converts it to a normalized float32 format.

    Handles bit-depth conversion (int16/int32 to -1.0..1.0 float) and
    mixes stereo files down to mono for consistent analysis.

    :param file_path: The absolute or relative path to the .wav file.
    :return: A tuple containing (sample_rate, audio_data_array). Returns (None, None) on failure.
    """
    try:
        sample_rate, data = wavfile.read(file_path)
    except Exception as e:
        logger.error(f"Failed to read {file_path}: {e}")
        return None, None

    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0

    return sample_rate, data


def process_directory(input_dir, output_csv, chunk_ms, sensitivity, reference):
    """
    Iterates through all WAV files in a directory and generates a combined metrics CSV.

    Applies sliding window logic for LUFS calculation and uses calibration data
    (if provided) to compute real-world dBSPL.

    :param input_dir: Directory containing the .wav files to analyze.
    :param output_csv: Path where the resulting CSV file will be saved.
    :param chunk_ms: The size of each analysis window in milliseconds.
    :param sensitivity: The microphone sensitivity in dBFS (optional, for dBSPL).
    :param reference: The reference pressure level in dB (default 94.0).
    """
    wav_files = sorted(glob.glob(os.path.join(input_dir, "*.wav")))
    if not wav_files:
        logger.error(f"No .wav files found in {input_dir}")
        raise Exception("No WAV files to process.")

    logger.info(f"📂 Found {len(wav_files)} WAV files.")
    if sensitivity:
        logger.info(f"   Using Calibration: Sens={sensitivity:.2f}, Ref={reference:.1f}")

    fieldnames = ["filename", "time_sec", "rms", "dbfs", "lufs", "flux", "dbspl"]

    with open(output_csv, mode="w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for file_idx, file_path in enumerate(wav_files):
            filename = os.path.basename(file_path)
            logger.info(f"[{file_idx + 1}/{len(wav_files)}] Processing {filename}...")

            sample_rate, full_audio = load_and_normalize_wav(file_path)
            if full_audio is None:
                continue

            metrics_engine = AudioMetrics(sample_rate=sample_rate)
            chunk_size = int(sample_rate * (chunk_ms / 1000))
            total_chunks = len(full_audio) // chunk_size

            # LUFS Window Calculation (Updated to 1.0s for stability)
            lufs_window_size = int(sample_rate * 1.0)

            if total_chunks == 0:
                logger.warning(f"Skipping {filename}: Audio shorter than {chunk_ms}ms")
                continue

            rows = []
            for i in range(total_chunks):
                start = i * chunk_size
                end = start + chunk_size
                chunk = full_audio[start:end]
                timestamp = end / sample_rate

                try:
                    rms = metrics_engine.rms(chunk)
                    dbfs = metrics_engine.dBFS(chunk)
                    flux = metrics_engine.flux(chunk, sample_rate)

                    # Sliding Window for LUFS
                    # Look back 1 second to calculate "Momentary" loudness
                    lufs_start = max(0, end - lufs_window_size)
                    lufs_chunk = full_audio[lufs_start:end]

                    try:
                        # Only calculate if we have enough data (at least 400ms is required by spec,
                        # we use 40% of our 1s window)
                        if len(lufs_chunk) >= lufs_window_size * 0.4:
                            lufs = metrics_engine.lufs(lufs_chunk)
                        else:
                            lufs = -70.0  # Not enough history
                    except ValueError:
                        lufs = -70.0

                    dbspl = None
                    if sensitivity is not None:
                        dbspl = metrics_engine.dBSPL(dbfs, sensitivity, reference)

                    rows.append(
                        {
                            "filename": filename,
                            "time_sec": round(timestamp, 3),
                            "rms": round(rms, 6),
                            "dbfs": round(dbfs, 2),
                            "lufs": round(lufs, 2),
                            "flux": round(flux, 2),
                            "dbspl": round(dbspl, 2) if dbspl is not None else "",
                        }
                    )
                except Exception as e:
                    logger.warning(f"Math error in {filename} at chunk {i}: {e}")

            writer.writerows(rows)
            csvfile.flush()

    logger.info(f"✅ Batch analysis complete. Data saved to {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process WAV files.")
    parser.add_argument("input_dir", help="Directory containing WAV files")
    parser.add_argument("--window", type=int, default=100, help="Window size in ms (default: 100)")
    parser.add_argument("--calibration-file", "-F", help="Path to UMIK-1 calibration file (.txt)")
    parser.add_argument("--output-file", "-o", help="Optional path for output CSV")

    args = parser.parse_args()

    sens = None
    ref = 94.0
    if args.calibration_file:
        try:
            sens, ref = CalibratorTransformer.get_sensitivity_values(args.calibration_file)
        except Exception as e:
            logger.error(f"Failed to parse calibration file: {e}")
            sys.exit(1)

    if args.output_file:
        out_csv = args.output_file
    else:
        out_csv = os.path.join(args.input_dir, "batch_metrics.csv")

    process_directory(args.input_dir, out_csv, args.window, sens, ref)
