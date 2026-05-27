"""
A module dedicated to calculating various audio metrics, including
digital levels (dBFS), real-world sound pressure (dBSPL and dBSPL(A)),
equivalent continuous level (L_Aeq,T), and perceived loudness (LUFS).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging

import librosa
import numpy as np
import pyloudnorm as pyln
from scipy.signal import bilinear_zpk, freqz_zpk, sosfilt, zpk2sos

from ..settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


def _design_a_weighting_sos(fs: float) -> np.ndarray:
    """Design IEC 61672 A-weighting filter as second-order sections.

    Analog prototype poles at 20.6, 107.7, 737.9, and 12194 Hz (IEC 61672),
    converted to digital via the bilinear transform and normalized to 0 dB at
    1 kHz. Accuracy is within IEC 61672 Class 1 tolerances up to ~8 kHz at
    48 kHz sample rate; at 192 kHz the accurate range extends to ~32 kHz.
    """
    f1, f2, f3, f4 = 20.598997, 107.65265, 737.86223, 12194.222
    w1, w2, w3, w4 = [2 * np.pi * f for f in (f1, f2, f3, f4)]
    z = np.zeros(4)
    p = np.array([-w1, -w1, -w2, -w3, -w4, -w4])
    z_d, p_d, k_d = bilinear_zpk(z, p, 1.0, fs=fs)
    _, h = freqz_zpk(z_d, p_d, k_d, worN=[2 * np.pi * 1000.0 / fs])
    k_d /= abs(h[0])
    return zpk2sos(z_d, p_d, k_d)


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
        self._a_weighting_sos = _design_a_weighting_sos(sample_rate)

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

    def _dBFS_A(self, audio_chunk: np.ndarray) -> float:
        mono = audio_chunk.squeeze()
        if mono.ndim > 1:
            mono = mono.mean(axis=1)
        return self.dBFS(sosfilt(self._a_weighting_sos, mono))

    def dBSPL_A(self, audio_chunk: np.ndarray, sensitivity_dbfs: float, reference_dbspl: float) -> float:
        """
        Calculates the calibrated A-weighted sound pressure level (dBSPL(A)).

        This is the physically meaningful dB(A) metric used by noise regulations
        (OSHA, WHO, ABNT NBR 10151, EU Directive 2002/49/EC). It combines the
        A-weighting filter with the microphone's calibration data to produce an
        absolute acoustic level.

        For L_Aeq,T (the time-averaged regulatory metric), collect
        ``dBSPL_A`` samples over the measurement period T and compute the
        energy average: ``10 * log10(mean(10 ** (samples / 10)))``.

        :param audio_chunk: A numpy array of audio samples, shape (N,) or (N, C).
        :param sensitivity_dbfs: Microphone sensitivity in dBFS (from calibration file).
        :param reference_dbspl: Reference SPL used during calibration, typically 94.0 dBSPL.

        :return: The calibrated A-weighted sound pressure level in dBSPL(A).
        """
        return self.dBSPL(self._dBFS_A(audio_chunk), sensitivity_dbfs, reference_dbspl)

    @staticmethod
    def L_Aeq(dbspl_a_samples: list[float] | np.ndarray) -> float:
        """
        Calculates the A-weighted equivalent continuous sound level (L_Aeq,T).

        L_Aeq,T is the primary metric for environmental noise regulations
        (ABNT NBR 10151, ISO 1996, EU Directive 2002/49/EC, OSHA). It
        represents the steady level that would deliver the same acoustic energy
        as the time-varying signal over the measurement period T.

        Formula: L_Aeq,T = 10 · log₁₀( mean( 10^(L_i / 10) ) )

        The caller is responsible for defining T: collect ``dBSPL_A()`` values
        over the desired window (e.g. 10 min per NBR 10151, 8 h for occupational
        dose) and pass them here.

        :param dbspl_a_samples: Sequence of calibrated dBSPL(A) values measured
                                over the period T.
        :return: L_Aeq,T in dB(A).
        """
        samples = np.asarray(dbspl_a_samples, dtype=float)
        return 10.0 * np.log10(np.mean(10.0 ** (samples / 10.0)))

    @staticmethod
    def L_A90(dbspl_a_samples: list[float] | np.ndarray) -> float:
        """
        Calculates the A-weighted background noise level (L_A90).

        L_A90 is the dBSPL(A) level exceeded 90 % of the time over the
        measurement period T — statistically, the quietest 10 % of the
        signal is above this value. It characterises the residual background
        noise in the absence of the disturbing source.

        L_A90 is used alongside L_Aeq,T in:

        * **ISO 1996** acoustic impact assessments
        * **ABNT NBR 10151** environmental noise evaluation
        * **BS 4142** (UK) industrial/commercial noise complaints
        * Court proceedings, to establish the pre-existing ambient level

        :param dbspl_a_samples: Sequence of calibrated dBSPL(A) values over T.
        :return: L_A90 in dB(A) (10th percentile of the sample distribution).
        """
        return float(np.percentile(np.asarray(dbspl_a_samples, dtype=float), 10))

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

        formatted_metrics = {
            key: f"{float(value):.4f}" if np.isscalar(value) and not isinstance(value, str) else value
            for key, value in metrics.items()
            if key != "measured_at"
        }
        measured_at = metrics["measured_at"]

        logger.info(f"[measured_at: {measured_at}] {formatted_metrics} [audio-metrics]")
