"""
A module dedicated to calculating various audio metrics, including
digital levels (dBFS), real-world sound pressure (dBSPL), and
perceived loudness (LUFS).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging

import librosa
import numpy as np
import pyloudnorm as pyln

from ..settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


class AudioMetrics:
    """A class to handle audio metric calculations."""

    def __init__(self, sample_rate: float):
        """
        Initializes the AudioMetrics calculator.

        :param sample_rate: The sample rate of the audio to be processed (e.g., 48.000 Hz).
        """
        self._lufs_meter = pyln.Meter(sample_rate)
        self._lufs_chunks: list[np.ndarray] = []
        self._lufs_block_size = int(settings.AUDIO.LUFS_WINDOW_SECONDS * sample_rate)

    @staticmethod
    def rms(audio_chunk: np.ndarray) -> float:
        """
        Calculates the Root Mean Square (RMS) of an audio chunk.
        RMS is a measure of the effective signal power or intensity.

        :param audio_chunk: A numpy array of audio samples.
        :return: The calculated RMS value as a float.
        """
        return np.sqrt(np.mean(audio_chunk**2))

    @staticmethod
    def flux(audio_chunk: np.ndarray, sample_rate: float) -> float:
        """
        Calculates the peak spectral flux of an audio chunk.

        Spectral flux is a measure of how quickly the frequency content (the
        spectrum) of a signal is changing over time. A high value indicates a
        sudden change in the sound's timbre, which is characteristic of a new
        sound event starting (an "onset").

        This method is highly effective at distinguishing new, dynamic sounds
        (like a bark or speech) from steady, continuous background noise
        (like a fan or an air conditioner hum).

        :param audio_chunk: A numpy array of audio samples.
        :param sample_rate: The sample rate of the audio chunk.
        :return: A single float representing the maximum spectral flux detected within the chunk.
        """
        onset_env = librosa.onset.onset_strength(y=np.squeeze(audio_chunk), sr=sample_rate)
        flux = np.max(onset_env)
        return flux

    @staticmethod
    def dBFS(audio_chunk: np.ndarray) -> float:
        """
        Calculates Decibels Full Scale (dBFS).

        dBFS measures the digital signal level relative to the maximum possible
        level (0 dBFS). It is the standard for uncalibrated microphones.
        A value of 0 dBFS represents clipping (distortion), while silence is
        represented by the lower bound.

        :param audio_chunk: A numpy array of audio samples.
        :return: The calculated dBFS value.
        """
        rms = AudioMetrics.rms(audio_chunk)
        epsilon = 1e-10
        dbfs = 20 * np.log10(rms + epsilon)

        return dbfs if dbfs > settings.METRICS.DBFS_LOWER_BOUND else settings.METRICS.DBFS_LOWER_BOUND

    @staticmethod
    def dBSPL(dbfs_level: float, sensitivity_dbfs: float, reference_dbspl: float) -> float:
        """
        Converts a dBFS level to Decibels Sound Pressure Level (dBSPL) using microphone sensitivity.

        dBSPL estimates the actual sound pressure in the real-world environment relative
        to the threshold of human hearing. This conversion requires the microphone's specific
        sensitivity values, obtained during calibration.

        The formula applied is: dBSPL = dBFS_calibrated - Sensitivity_dBFS + Reference_dBSPL

        :param dbfs_level: The input audio level expressed in dBFS. For accurate dBSPL
                           results across all frequencies, this value should have been calculated
                           from an audio signal that was *already processed* by a frequency
                           response correction filter (e.g., the FIR filter).
        :param sensitivity_dbfs: The microphone's specific sensitivity, expressed in dBFS.
                                 This is the digital level the microphone outputs when
                                 exposed to the reference sound pressure (e.g., -18.5 dBFS).
                                 Obtained from the microphone's calibration data.
        :param reference_dbspl: The standard sound pressure level used during the microphone's
                                calibration (usually 94.0 dBSPL, corresponding to 1 Pascal).
                                Obtained from the microphone's calibration data.
        :return: The calculated dBSPL value, representing the estimated real-world
                 sound pressure level based on the input dBFS.
        """
        return dbfs_level - sensitivity_dbfs + reference_dbspl

    def aggregate_lufs_chunks(self, audio_chunk: np.ndarray):
        """
        Adds an audio chunk to the internal buffer for later LUFS calculation.

        :param audio_chunk: A numpy array of audio samples.
        """
        self._lufs_chunks.append(audio_chunk)

    def get_lufs_chunks(self) -> list[np.ndarray]:
        """
        Retrieves and clears the buffered audio chunks. This is used by a
        monitoring loop to get the collected data for a processing interval.

        :return: A list of the buffered numpy arrays.
        """
        chunks = self._lufs_chunks[:]
        self._lufs_chunks.clear()
        return chunks

    def lufs(self, audio_chunk: np.ndarray) -> float:
        """
        Calculates the perceived loudness (LUFS) of an audio segment.

        LUFS (Loudness Units Full Scale) is an international standard (ITU-R BS.1770-4)
        that measures loudness in a way that aligns with human hearing, taking
        frequency sensitivity into account. This method uses the "integrated"
        loudness algorithm from the pyloudnorm library.

        :param audio_chunk: A numpy array of audio samples.
        :return: The calculated loudness in LUFS.
        """
        loudness = self._lufs_meter.integrated_loudness(audio_chunk)
        return loudness if loudness > settings.METRICS.LUFS_LOWER_BOUND else settings.METRICS.LUFS_LOWER_BOUND

    @staticmethod
    def show_metrics(**metrics: float):
        """
        Prints a dictionary of provided metrics to the console.

        This method is highly flexible and will only display the metrics that
        are passed to it as keyword arguments.

        :param metrics: A variable number of keyword arguments (e.g., rms=0.1, dbfs=-25.3).
        """

        formatted_metrics = {key: f"{value:.4f}" for key, value in metrics.items() if key != "measured_at"}
        measured_at = metrics["measured_at"]

        logger.info(f"[measured_at: {measured_at}] {formatted_metrics} [audio-metrics]")
