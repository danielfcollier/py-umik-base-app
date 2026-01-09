"""
Full Audio Metrics Analyzer.
Calculates RMS, Flux, dBFS, LUFS, and dBSPL for a WAV file.

This script processes a single WAV file to generate a time-series CSV of various
audio metrics. It supports determining the absolute start time from the filename
(or manual argument) to provide real-world timestamps in the output.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from scipy.io import wavfile

from umik_base_app import AudioMetrics
from umik_base_app.settings import get_settings
from umik_base_app.transformers.calibrator_transformer import CalibratorTransformer

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)

settings = get_settings()


class MetricsAnalyzer:
    """
    Engine for analyzing audio files and generating scientific metrics.
    """

    def __init__(self, file_path: str, calibration_file: str | None = None, is_calibrated: bool = False):
        """
        Initialize the analyzer with the target file and optional calibration.
        """
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.is_calibrated = is_calibrated

        # 1. Load Calibration
        self.sensitivity: float | None = None
        self.reference: float = settings.HARDWARE.REFERENCE_DBSPL

        if calibration_file:
            self._load_calibration(calibration_file)

        # 2. Load Audio
        self.sample_rate, self.audio_data = self._load_and_normalize_wav(file_path)
        self.metrics_engine = AudioMetrics(sample_rate=self.sample_rate)

    def _load_calibration(self, path: str):
        """Helper to parse the UMIK-1 calibration file."""
        try:
            sens, ref = CalibratorTransformer.get_sensitivity_values(
                path,
                settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS,
                settings.HARDWARE.REFERENCE_DBSPL,
            )
            logger.info(self.is_calibrated)
            if self.is_calibrated:
                logger.info(f"Calibration Mode: PRE-CALIBRATED FILE. Ignoring sensitivity offset {sens:.2f}dB.")
                self.sensitivity = 0.0
            else:
                self.sensitivity = sens

            self.reference = ref
            logger.info(f"Calibration Loaded: Sens={sens:.2f}dB, Ref={ref:.1f}dB")
        except Exception as e:
            logger.error(f"Failed to parse calibration file: {e}")
            sys.exit(1)

    def _load_and_normalize_wav(self, path: str) -> tuple[int, np.ndarray]:
        """Loads WAV, converts to mono, and normalizes to float32."""
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            sys.exit(1)

        try:
            sample_rate, data = wavfile.read(path)
            if data.size == 0:
                raise ValueError("File is empty")
        except Exception as e:
            logger.error(f"Error reading WAV file: {e}")
            sys.exit(1)

        # Convert to Mono
        if data.ndim > 1:
            data = data.mean(axis=1)

        # Normalize to float32 (-1.0 to 1.0) based on bit depth
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
        Main processing loop. Chunks audio, calculates metrics, and saves CSV.
        """
        if len(self.audio_data) == 0:
            logger.warning("Audio data is empty. Skipping analysis.")
            return

        duration = len(self.audio_data) / self.sample_rate
        logger.info(f"🎧 Analyzing {self.filename} ({duration:.2f}s)...")

        start_dt = self._get_start_time(manual_start)
        logger.info(f"🕒 Start Time: {start_dt if start_dt else 'Relative (0.0s)'}")

        # Processing Setup
        chunk_size = max(1, int(self.sample_rate * (chunk_ms / 1000)))
        lufs_window = int(self.sample_rate * 1.0)

        # Split into chunks
        # Using array_split or simple slicing logic
        num_chunks = len(self.audio_data) // chunk_size
        results = []

        print(f"Processing {num_chunks} chunks...")

        for i in range(num_chunks):
            start = i * chunk_size
            end = start + chunk_size
            chunk = self.audio_data[start:end]
            rel_time = end / self.sample_rate

            # Timestamp
            timestamp = ""
            if start_dt:
                timestamp = (start_dt + timedelta(seconds=rel_time)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # Metrics
            metrics = {
                "time_sec": round(rel_time, 3),
                "timestamp": timestamp,
                "rms": round(self.metrics_engine.rms(chunk), 6),
                "dbfs": round(self.metrics_engine.dBFS(chunk), 2),
                "flux": round(self.metrics_engine.flux(chunk, self.sample_rate), 2),
                "lufs": -70.0,
                "dbspl": "",
            }

            # LUFS (Windowed)
            lufs_chunk = self.audio_data[max(0, end - lufs_window) : end]
            if len(lufs_chunk) >= lufs_window * 0.4:
                try:
                    metrics["lufs"] = round(self.metrics_engine.lufs(lufs_chunk), 2)
                except ValueError:
                    pass

            # dBSPL (Calibrated)
            if self.sensitivity is not None:
                spl = self.metrics_engine.dBSPL(metrics["dbfs"], self.sensitivity, self.reference)
                metrics["dbspl"] = round(spl, 2)

            results.append(metrics)

            if i % 100 == 0:
                print(f"\rProgress: {int((i / num_chunks) * 100)}%", end="")

        print("\rProgress: 100% Complete.   \n")

        # Use Pandas for Output
        df = pd.DataFrame(results)
        if not df.empty:
            df.to_csv(output_csv, index=False)
            logger.info(f"✅ Results saved to: {output_csv}")
            self._print_summary(df)
        else:
            logger.warning("No data generated.")

    def _print_summary(self, df: pd.DataFrame):
        logger.info("=" * 40)
        logger.info("📈 ANALYSIS SUMMARY")
        logger.info("=" * 40)

        logger.info(f"Peak Level:    {df['dbfs'].max():.2f} dBFS")
        logger.info(f"Max Loudness:  {df['lufs'].max():.2f} LUFS")
        logger.info(f"Max Flux:      {df['flux'].max():.2f}")

        if "dbspl" in df.columns:
            # Handle empty strings if any using pd.to_numeric with coercion
            spl_series = pd.to_numeric(df["dbspl"], errors="coerce")
            if not spl_series.isna().all():
                logger.info(f"Max SPL:       {spl_series.max():.2f} dBSPL")

        logger.info("=" * 40)


def main():
    parser = argparse.ArgumentParser(description="Calculate audio metrics (RMS, LUFS, dBSPL).")
    parser.add_argument("file", help="Path to input WAV file")
    parser.add_argument("--window", type=int, default=100, help="Analysis window in ms (default: 100)")
    parser.add_argument("--calibration-file", "-F", help="Path to UMIK-1 calibration file (.txt)")
    parser.add_argument(
        "--calibrated-input",
        action="store_true",
        help="Use this if the WAV file was saved with calibration gain applied.",
    )
    parser.add_argument("--output-file", "-o", help="Optional output CSV path")
    parser.add_argument("--start-time", help="Force start time (ISO format)")

    args = parser.parse_args()

    out_path = args.output_file or (os.path.splitext(args.file)[0] + ".csv")

    try:
        analyzer = MetricsAnalyzer(args.file, args.calibration_file, args.calibrated_input)
        analyzer.run_analysis(out_path, args.window, args.start_time)
    except KeyboardInterrupt:
        logger.info("\nAnalysis stopped by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
