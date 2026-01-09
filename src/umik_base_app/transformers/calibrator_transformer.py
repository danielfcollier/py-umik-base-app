"""
Handles the loading of a microphone calibration file, designing a correction filter,
and providing methods to apply the filter and retrieve sensitivity data.

This class manages the frequency response correction for calibrated microphones like the UMIK-1.
It includes caching for the designed filter coefficients to optimize startup time.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import os

import numpy as np
from scipy.signal import firwin2, lfilter

from .calibrator_cache_strategy import CalibratorCacheStrategy, FileCalibratorCache

logger = logging.getLogger(__name__)


class CalibratorTransformer:
    """
    Manages microphone calibration using data from a manufacturer-provided file.

    Handles FIR filter design for frequency response correction and extraction
    of broadband sensitivity values for dBSPL calculations. Caches the FIR
    filter taps for faster subsequent initializations.
    """

    def __init__(
        self,
        calibration_file_path: str,
        sample_rate: float,
        nominal_sensitivity_dbfs: float,
        reference_dbspl: float,
        num_taps: int = 1024,
        force_write: bool = False,
        cache_strategy: CalibratorCacheStrategy | None = None,
    ):
        """
        Initializes the CalibratorTransformer.

        Determines the cache file path based on the calibration file's directory.
        Calculates the sensitivity gain from the file header and designs/loads
        the FIR correction filter.

        :param calibration_file_path: Path to the unique .txt calibration file.
        :param sample_rate: The native sample rate of the audio stream.
        :param nominal_sensitivity_dbfs: The assumed sensitivity of the hardware (e.g., -18.0).
        :param reference_dbspl: The reference SPL level (e.g., 94.0).
        :param num_taps: The number of coefficients (taps) for the FIR filter.
        :param force_write: If True, always redesign the filter and overwrite the cache.
        :param cache_strategy: Strategy for loading/saving filter taps.
        :raises RuntimeError: If the filter taps cannot be loaded or designed.
        :raises ValueError: If the sensitivity factor cannot be parsed from the file.
        :raises FileNotFoundError: If the calibration file does not exist.
        """
        logger.debug("Initializing CalibratorTransformer...")
        self._sample_rate = sample_rate
        self._calibration_file_path = calibration_file_path

        sens_db, _ = self.get_sensitivity_values(
            file_path=calibration_file_path,
            nominal_sensitivity_dbfs=nominal_sensitivity_dbfs,
            reference_dbspl=reference_dbspl,
        )
        self._sensitivity_gain = 10 ** (sens_db / 20.0)

        logger.info(f"🎚️ Calculated Gain: {self._sensitivity_gain:.4f} ({sens_db}dB)")

        # Use provided strategy or default to File System cache
        self._cache_strategy = cache_strategy or FileCalibratorCache()

        calibration_dir = os.path.dirname(calibration_file_path)
        calibration_basename = os.path.splitext(os.path.basename(calibration_file_path))[0]
        taps_filename = f"{calibration_basename}_fir_{num_taps}taps_{int(sample_rate)}hz.npy"
        taps_file = os.path.join(calibration_dir, taps_filename)
        logger.debug(f"Using cache key/path: {taps_file}")

        self._filter_taps = None

        if not force_write:
            loaded_taps = self._cache_strategy.load(taps_file)
            if loaded_taps is not None:
                if len(loaded_taps) != (num_taps - 1):
                    logger.warning(
                        f"Cached filter length ({len(loaded_taps)}) does not match "
                        f"requested length ({num_taps} - 1). Will redesign."
                    )
                else:
                    self._filter_taps = loaded_taps
                    logger.debug("Cached filter loaded successfully.")

        if self._filter_taps is None:
            if force_write:
                logger.info("Force_write enabled. Redesigning filter...")
            else:
                logger.info(f"No valid cached filter found for '{taps_file}'.")

            logger.info(f"Designing new {num_taps}-tap filter from '{calibration_file_path}'...")

            freqs, gains = self._parse_frequency_response(calibration_file_path)

            self._filter_taps = self._design_fir_filter(freqs, gains, num_taps)

            logger.info("Saving new filter to cache...")
            self._cache_strategy.save(taps_file, self._filter_taps)

        if self._filter_taps is None:
            raise RuntimeError(
                f"Failed to initialize calibration filter for {calibration_file_path}. Filter design returned None."
            )

        self._filter_state = np.zeros(len(self._filter_taps) - 1)

        logger.info(
            f"✅ CalibratorTransformer ready. Gain: {self._sensitivity_gain:.4f}x, Taps: {len(self._filter_taps)}"
        )

    def _parse_frequency_response(self, file_path: str) -> tuple[np.ndarray, np.ndarray]:
        """
        Parses the frequency response data (Hz vs dB) from a calibration file.

        Handles files with whitespace delimiters (tabs, spaces) and skips
        initial header/comment lines until it finds the first line containing
        two valid numeric values (frequency and gain).

        :param file_path: The full path to the calibration .txt file.
        :return: A tuple containing two NumPy arrays: (frequencies, gains_db).
        :raises ValueError: If the file is empty or contains no valid data pairs.
        :raises FileNotFoundError: If the file is not found.
        """
        frequencies, gains_db = [], []
        data_started = False

        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, start=1):
                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    try:
                        freq = float(parts[0])
                        gain = float(parts[1])

                        frequencies.append(freq)
                        gains_db.append(gain)
                        data_started = True

                    except ValueError:
                        if not data_started:
                            logger.debug(f"Skipping potential header/comment line {line_num}: '{line}'")
                            continue
                        else:
                            logger.warning(
                                f"Found non-numeric data after valid data started (line {line_num}). "
                                f"Stopping parse. Line: '{line}'"
                            )
                            break
                elif not data_started:
                    logger.debug(f"Skipping potential header/comment line {line_num}: '{line}'")
                    continue
                else:
                    logger.warning(
                        "Found line with unexpected format after valid data "
                        f"started (line {line_num}). Stopping parse. Line: '{line}'"
                    )
                    break

            if not frequencies:
                msg = (
                    "No valid frequency/gain data pairs (two numeric columns "
                    f"separated by whitespace) found in '{file_path}'."
                )
                logger.error(msg)
                raise ValueError(msg)

            logger.info(f"Parsed {len(frequencies)} frequency/gain points.")
            return np.array(frequencies), np.array(gains_db)

        except FileNotFoundError:
            logger.error(f"Calibration file not found at '{file_path}'. Please check the path.")
            raise
        except Exception as e:
            if isinstance(e, ValueError) and "No valid frequency" in str(e):
                raise e

            logger.error(
                f"An unexpected error occurred while reading calibration file '{file_path}': {e}", exc_info=True
            )
            raise

    def _design_fir_filter(self, freqs: np.ndarray, gains: np.ndarray, num_taps: int) -> np.ndarray:
        """
        Designs a Finite Impulse Response (FIR) filter based on microphone calibration data.

        This method uses the frequency response data (frequencies and corresponding gains in dB)
        parsed from the calibration file to compute the coefficients ('taps') of an FIR filter.
        The designed filter aims to have a frequency response that is the *inverse* of the
        microphone's measured response, effectively flattening it and correcting for inaccuracies.

        It utilizes the `scipy.signal.firwin2` function, which designs filters based on
        arbitrary frequency response specifications.

        :param freqs: A NumPy array of frequencies (in Hz) from the calibration file.
        :param gains: A NumPy array of corresponding microphone gains (in dB) at those frequencies.
        :param num_taps: The desired number of coefficients (taps) for the FIR filter.
                        This determines the filter's length, accuracy, and computational cost.
                        A higher number generally provides better accuracy, especially at
                        low frequencies, but increases the processing load during filtering.
        :return: A NumPy array containing the calculated FIR filter coefficients (taps).
        """
        # Calculate the required correction gains (inverse of microphone's gain in dB).
        correction_gains_db = -gains
        # Convert dB correction gains to linear amplitude scale for filter design.
        correction_gains_linear = 10.0 ** (correction_gains_db / 20.0)

        # Normalize the frequency axis to the range [0, 1], where 1 represents Nyquist frequency.
        nyquist = self._sample_rate / 2.0
        normalized_freqs = freqs / nyquist

        # firwin2 requires the frequency list to start at 0 and end at 1.
        # We extrapolate the gains at these boundaries based on the nearest measured points.
        full_freqs = np.concatenate(([0], normalized_freqs, [1]))
        extrapolated_gains = np.concatenate(
            ([correction_gains_linear[0]], correction_gains_linear, [correction_gains_linear[-1]])
        )

        # Design the FIR filter coefficients using the specified number of taps.
        logger.info(f"Designing FIR filter with {num_taps} taps...")
        filter_taps = firwin2(num_taps - 1, full_freqs, extrapolated_gains)
        logger.info("Filter design complete.")

        return filter_taps

    def reset_state(self):
        """
        Resets the internal filter state (zi) to zeros.

        This is necessary when starting to process a new, discontinuous audio stream
        (e.g., jumping from a pre-roll buffer to a new recording event) to avoid
        filter ringing artifacts caused by the state of previous, unrelated audio.
        """
        if self._filter_taps is not None:
            self._filter_state = np.zeros(len(self._filter_taps) - 1)

    def apply(self, audio_chunk: np.ndarray, reset_state: bool = False) -> np.ndarray:
        """
        Applies Sensitivity Gain AND FIR correction.

        :param audio_chunk: A numpy array of raw audio samples.
        :param reset_state: If True, resets the filter state (zi) to zeros before processing.
        :return: A numpy array of calibrated (frequency-corrected + level-corrected) audio.
        """
        # 0. Optional: Reset State
        if reset_state:
            self.reset_state()

        # 1. Apply Scalar Gain (Absolute Level)
        # We apply this FIRST so the filter acts on the "True Level" signal.
        gained_chunk = audio_chunk * self._sensitivity_gain

        # 2. Apply Vector Filter (Frequency Response)
        # `zi` provides the initial state from the previous chunk.
        # `zo` (returned as the second element) becomes the state for the *next* chunk.
        calibrated_chunk, self._filter_state = lfilter(self._filter_taps, 1.0, gained_chunk, zi=self._filter_state)

        if calibrated_chunk.dtype != audio_chunk.dtype:
            calibrated_chunk = calibrated_chunk.astype(audio_chunk.dtype)

        return calibrated_chunk

    @staticmethod
    def get_sensitivity_values(
        file_path: str, nominal_sensitivity_dbfs: float, reference_dbspl: float
    ) -> tuple[float, float]:
        """
        Reads a calibration file and extracts sensitivity values, specifically
        looking for a "Sens Factor" line.

        This method assumes the file contains a header line like:
        "Sens Factor =-X.XXXdB, SERNO: YYYYYYY"

        It calculates the actual sensitivity by applying the Sens Factor to a
        nominal sensitivity assumed for the microphone type (e.g., -18 dBFS for UMIK-1).
        It assumes the standard reference sound pressure level of 94.0 dBSPL.

        :param file_path: Path to the .txt calibration file.
        :return: A tuple containing (calculated_sensitivity_dbfs, reference_dbspl).
                 Example: (-18.545, 94.0)
        :raises ValueError: If the "Sens Factor" line cannot be found or parsed,
                           or if the file cannot be read.
        :raises FileNotFoundError: If the file_path does not exist.
        """
        logger.debug(f"Reading sensitivity data from '{file_path}' (expecting 'Sens Factor' format)...")

        try:
            with open(file_path, encoding="utf-8") as f:
                # Iterate through the first few lines to find the header
                for line_num, line in enumerate(f):
                    line = line.strip()  # Remove leading/trailing whitespace
                    if "Sens Factor" in line:
                        try:
                            # --- Parse the "Sens Factor" line ---
                            factor_str = line.split("=")[1].split("dB")[0].strip()
                            sens_factor_db = float(factor_str)

                            calculated_sensitivity_dbfs = nominal_sensitivity_dbfs + sens_factor_db

                            logger.info(
                                f"✅ Found 'Sens Factor': {sens_factor_db:.3f} dB for reference"
                                f" {reference_dbspl:.2f} dBSPL"
                            )
                            return calculated_sensitivity_dbfs, reference_dbspl

                        except (ValueError, IndexError, TypeError) as parse_error:
                            raise ValueError(
                                f"Could not parse 'Sens Factor' line (line {line_num + 1}): '{line}'. "
                                f"Expected format like 'Sens Factor =-X.Xd B,...'. Error: {parse_error}"
                            )
        except FileNotFoundError:
            logger.error(f"Calibration file not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading calibration file '{file_path}': {e}")
            raise

        raise ValueError(f"'Sens Factor' header line not found in the first few lines of file: {file_path}.")
