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


class MetricsAnalyzer:
    """
    Engine for analyzing audio files and generating scientific metrics.
    """

    def __init__(self, file_path: str, calibration_file: str | None = None):
        """
        Initialize the analyzer with the target file and optional calibration.
        """
        self.file_path = file_path
        self.filename = os.path.basename(file_path)

        # 1. Load Calibration (if provided)
        self.sensitivity: float | None = None
        self.reference: float = 94.0

        if calibration_file:
            self._load_calibration(calibration_file)

        # 2. Load Audio
        self.sample_rate, self.audio_data = self._load_and_normalize_wav(file_path)
        self.metrics_engine = AudioMetrics(sample_rate=self.sample_rate)

    def _load_calibration(self, path: str):
        """Helper to parse the UMIK-1 calibration file."""
        try:
            sens, ref = HardwareCalibrator.get_sensitivity_values(path)
            self.sensitivity = sens
            self.reference = ref
            logger.info(f"Calibration Loaded: Sens={sens:.2f}dB, Ref={ref:.1f}dB")
        except Exception as e:
            logger.error(f"Failed to parse calibration file: {e}")
            sys.exit(1)

    def _load_and_normalize_wav(self, path: str) -> tuple[int, np.ndarray]:
        """Loads WAV, converts to mono, and normalizes to float32 (-1.0 to 1.0)."""
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            sys.exit(1)

        try:
            sample_rate, data = wavfile.read(path)
            # Handle empty files
            if data.size == 0:
                logger.error("WAV file contains no data.")
                return sample_rate, np.array([])
        except Exception as e:
            logger.error(f"Error reading WAV file: {e}")
            sys.exit(1)

        # Mix to Mono
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)

        # Normalize Bit Depth
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0

        return sample_rate, data

    def _get_start_time(self, manual_str: str | None = None) -> datetime | None:
        """Attempts to determine the absolute start time of the recording."""
        if manual_str:
            try:
                return datetime.fromisoformat(manual_str)
            except ValueError:
                logger.warning("Invalid manual start time format. Expected ISO.")

        # Try Filename Parsing (YYYY-MM-DD HH:MM:SS)
        match = re.search(r"(\d{4}-\d{2}-\d{2}[\sT_]\d{2}[:\.]\d{2}[:\.]\d{2})", self.filename)
        if match:
            dt_str = match.group(1).replace("_", " ").replace("T", " ").replace(".", ":")
            try:
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        return None

    def run_analysis(self, output_csv: str, chunk_ms: int = 100, manual_start: str | None = None):
        """
        Main processing loop.Chunks audio, calculates metrics, and saves CSV.
        """
        if len(self.audio_data) == 0:
            logger.warning("Audio data is empty. Skipping analysis.")
            return

        logger.info(f"🎧 Analyzing {self.filename} ({len(self.audio_data) / self.sample_rate:.2f}s)...")

        start_dt = self._get_start_time(manual_start)
        if start_dt:
            logger.info(f"🕒 Start Time: {start_dt}")
        else:
            logger.info("🕒 Using relative time (0.0s).")

        # Setup Windows
        chunk_size = int(self.sample_rate * (chunk_ms / 1000))
        if chunk_size == 0:
            chunk_size = 1  # prevent divide by zero for tiny files

        lufs_window = int(self.sample_rate * 1.0)  # 1s window for valid LUFS
        total_chunks = len(self.audio_data) // chunk_size

        results = []

        # --- Processing Loop ---
        for i in range(total_chunks):
            start = i * chunk_size
            end = start + chunk_size
            chunk = self.audio_data[start:end]
            rel_time = end / self.sample_rate

            # 1. Timestamp
            abs_time_str = ""
            if start_dt:
                curr_dt = start_dt + timedelta(seconds=rel_time)
                abs_time_str = curr_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # 2. Basic Metrics
            rms = self.metrics_engine.rms(chunk)
            dbfs = self.metrics_engine.dBFS(chunk)
            flux = self.metrics_engine.flux(chunk, self.sample_rate)

            # 3. LUFS (Sliding Window)
            lufs_start = max(0, end - lufs_window)
            lufs_chunk = self.audio_data[lufs_start:end]
            lufs = -70.0
            if len(lufs_chunk) >= lufs_window * 0.4:
                try:
                    lufs = self.metrics_engine.lufs(lufs_chunk)
                except ValueError:
                    pass

            # 4. dBSPL
            dbspl = None
            if self.sensitivity is not None:
                dbspl = self.metrics_engine.dBSPL(dbfs, self.sensitivity, self.reference)

            # Store Row
            results.append(
                {
                    "time_sec": round(rel_time, 3),
                    "timestamp": abs_time_str,
                    "rms": round(rms, 6),
                    "dbfs": round(dbfs, 2),
                    "lufs": round(lufs, 2),
                    "flux": round(flux, 2),
                    "dbspl": round(dbspl, 2) if dbspl is not None else "",
                }
            )

            if i % 100 == 0:
                print(f"\rProcessing: {int((i / total_chunks) * 100)}%", end="")

        print("\rProcessing: 100% Complete.   \n")

        self._save_csv(results, output_csv)
        self._print_summary(results)

    def _save_csv(self, data: list, path: str):
        if not data:
            logger.warning("No data generated.")
            return

        keys = data[0].keys()
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        logger.info(f"✅ Results saved to: {path}")

    def _print_summary(self, results: list):
        if not results:
            logger.warning("Summary: No results to display.")
            return

        logger.info("=" * 40)
        logger.info("📈 ANALYSIS SUMMARY")
        logger.info("=" * 40)
        max_dbfs = max(r["dbfs"] for r in results)
        max_lufs = max(r["lufs"] for r in results)
        max_flux = max(r["flux"] for r in results)

        logger.info(f"Peak Level:    {max_dbfs:.2f} dBFS")
        logger.info(f"Max Loudness:  {max_lufs:.2f} LUFS")
        logger.info(f"Max Flux:      {max_flux:.2f}")

        if self.sensitivity:
            # Handle potential empty strings in dBSPL if uncalibrated data mixed in (unlikely but safe)
            spl_values = [r["dbspl"] for r in results if r["dbspl"] != ""]
            if spl_values:
                max_spl = max(spl_values)
                logger.info(f"Max SPL:       {max_spl:.2f} dBSPL")
        logger.info("=" * 40)


def main():
    parser = argparse.ArgumentParser(description="Calculate audio metrics (RMS, LUFS, dBSPL).")
    parser.add_argument("file", help="Path to input WAV file")
    parser.add_argument("--window", type=int, default=100, help="Analysis window in ms (default: 100)")
    parser.add_argument("--calibration-file", "-F", help="Path to UMIK-1 calibration file (.txt)")
    parser.add_argument("--output-file", "-o", help="Optional output CSV path")
    parser.add_argument("--start-time", help="Force start time (ISO format) if filename parsing fails")

    args = parser.parse_args()

    if args.output_file:
        out_path = args.output_file
    else:
        out_path = os.path.splitext(args.file)[0] + ".csv"

    try:
        analyzer = MetricsAnalyzer(args.file, args.calibration_file)
        analyzer.run_analysis(out_path, args.window, args.start_time)
    except KeyboardInterrupt:
        print("\nAnalysis stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
