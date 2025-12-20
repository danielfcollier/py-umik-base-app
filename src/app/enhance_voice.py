"""
Voice Enhancer & Compressor.
Applies a Bandpass Filter (300Hz-3400Hz) to isolate human speech,
applies Dynamic Range Compression to boost quiet voices, and exports to MP3.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import logging
import os
import sys

import numpy as np
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


def butter_bandpass(lowcut, highcut, fs, order=6):
    """
    Generates the filter coefficients for a Butterworth bandpass filter.

    :param lowcut: The low frequency cutoff (e.g., 300 Hz).
    :param highcut: The high frequency cutoff (e.g., 3400 Hz).
    :param fs: The sample rate of the audio (e.g., 48000 Hz).
    :param order: The order of the filter (higher means steeper roll-off).
    :return: Second-Order Sections (SOS) filter coefficients.
    """
    nyq = 0.5 * fs  # Nyquist Frequency (half the sample rate)
    low = lowcut / nyq
    high = highcut / nyq
    # We use SOS (Second-Order Sections) output format because it is numerically
    # more stable than the standard 'ba' (numerator/denominator) format for high-order filters.
    return butter(order, [low, high], btype="band", output="sos")


def butter_bandpass_filter(data, lowcut, highcut, fs, order=6):
    """
    Applies the Butterworth bandpass filter to the audio data.

    It uses 'sosfiltfilt', which applies the filter forward and backward.
    This results in zero phase distortion, meaning the timing of the audio
    peaks (transients) remains aligned with the original signal.

    :param data: The input audio array (normalized float).
    :param lowcut: Low cutoff frequency in Hz.
    :param highcut: High cutoff frequency in Hz.
    :param fs: Sample rate in Hz.
    :param order: Filter order.
    :return: Filtered audio data array.
    """
    sos = butter_bandpass(lowcut, highcut, fs, order=order)
    # sosfiltfilt is a zero-phase filter (doesn't shift the timing of the sound)
    return sosfiltfilt(sos, data)


def process_audio(input_path, output_path=None, low_freq=300, high_freq=3400):
    """
    Main processing pipeline:
    1. Loads WAV.
    2. Converts to Mono.
    3. Bandpass Filter (Scipy): Removes rumble and hiss.
    4. Dynamic Range Compression (Pydub): Boosts quiet speech, limits loud noises.
    5. Normalization (Pydub): Maximizes final volume.
    6. Encodes to MP3.
    :param input_path: Path to the source WAV file.
    :param output_path: Path for the destination MP3. Auto-generated if None.
    :param low_freq: Low frequency cutoff in Hz.
    :param high_freq: High frequency cutoff in Hz.
    """
    if not os.path.exists(input_path):
        logger.info(f"Error: File {input_path} not found.")
        sys.exit(1)

    logger.info("Progress: 0%")
    logger.info(f"Loading {input_path}...")
    sample_rate, data = wavfile.read(input_path)

    # 1. Convert to Float Normalized (-1.0 to 1.0)
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0

    logger.info("Progress: 10%")

    # 2. Mix to Mono
    if len(data.shape) > 1:
        logger.info("Mixing stereo to mono for better voice isolation...")
        data = np.mean(data, axis=1)

    logger.info("Progress: 20%")

    # 3. Apply Filter (Scipy)
    # Standard "Telephony" bandwidth is approx 300Hz-3400Hz.
    # This cuts out low-end rumble (AC, traffic) and high-end hiss.
    logger.info(f"Applying Bandpass Filter ({low_freq}Hz - {high_freq}Hz)...")
    filtered_data = butter_bandpass_filter(data, low_freq, high_freq, sample_rate, order=6)

    logger.info("Progress: 40%")

    # Convert back to Int16 for Pydub processing
    # We do this here because Pydub's effects work best on standard audio segments
    filtered_int16 = (filtered_data * 32767).astype(np.int16)

    # Create AudioSegment
    audio_segment = AudioSegment(
        filtered_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1,
    )

    logger.info("Progress: 50%")

    # 4. Apply Dynamic Range Compression (The "Voice Boost")
    # Threshold -20dB: Sounds louder than this get squashed.
    # Ratio 4.0: For every 4dB over the limit, it only goes up 1dB.
    # Attack 5ms: Reacts instantly to sudden shouts.
    logger.info("Applying Dynamic Range Compression (Voice Boost)...")
    compressed_segment = compress_dynamic_range(audio_segment, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)

    logger.info("Progress: 75%")

    # 5. Normalize (Make-up Gain)
    # Now that peaks are squashed, we can raise the WHOLE volume to -1dB
    logger.info("Maximizing Volume (Normalization)...")
    final_segment = normalize(compressed_segment, headroom=1.0)

    logger.info("Progress: 85%")

    # 6. Save as MP3
    if not output_path:
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}_voice_enhanced.mp3"

    logger.info(f"Encoding to MP3: {output_path}...")
    logger.info("Progress: 90%")

    final_segment.export(output_path, format="mp3", bitrate="192k")

    logger.info("Progress: 100%")
    logger.info(f"✅ Success! File saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance voice in WAV and convert to MP3.")
    parser.add_argument("input_file", help="Path to input WAV file")
    parser.add_argument("--out", help="Path to output MP3 file (optional)")
    parser.add_argument("--low", type=int, default=300, help="Low cutoff Hz (default: 300)")
    parser.add_argument("--high", type=int, default=3400, help="High cutoff Hz (default: 3400)")

    args = parser.parse_args()
    process_audio(args.input_file, args.out, args.low, args.high)
