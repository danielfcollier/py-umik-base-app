"""
Voice Enhancer & Compressor (Chunked + Noise Reduction).
Applies spectral noise reduction, bandpass filtering, and dynamic range compression
in 10-minute chunks to handle large files efficiently.

This script is designed to:
1. Reduce background static/hiss using spectral subtraction (noisereduce).
2. Isolate human voice frequencies (300Hz - 3400Hz).
3. Boost quiet speech and limit loud peaks (Dynamic Range Compression).
4. Maximize final volume (Normalization).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import logging
import math
import os
import sys

import noisereduce as nr
import numpy as np
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize
from scipy.io import wavfile
from scipy.signal import butter, sosfiltfilt

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


def butter_bandpass(lowcut, highcut, fs, order=6):
    """
    Generates the Second-Order Sections (SOS) filter coefficients for a Butterworth bandpass filter.

    :param lowcut: The low frequency cutoff in Hz (e.g., 300 Hz).
    :param highcut: The high frequency cutoff in Hz (e.g., 3400 Hz).
    :param fs: The sample rate of the audio in Hz (e.g., 48000 Hz).
    :param order: The order of the filter (higher means steeper roll-off). Default is 6.
    :return: A numpy array containing the SOS filter coefficients.
    """
    nyq = 0.5 * fs  # Nyquist Frequency (half the sample rate)
    low = lowcut / nyq
    high = highcut / nyq
    # We use SOS (Second-Order Sections) output format because it is numerically
    # more stable than the standard 'ba' (numerator/denominator) format for high-order filters.
    return butter(order, [low, high], btype="band", output="sos")


def butter_bandpass_filter(data, lowcut, highcut, fs, order=6):
    """
    Applies the Butterworth bandpass filter to the audio data using zero-phase filtering.

    This uses `sosfiltfilt` (forward-backward filtering) to ensure that the
    phase of the signal is preserved. This keeps the audio transients aligned
    and prevents "smearing" of the sound.

    :param data: The input audio array (normalized float).
    :param lowcut: Low cutoff frequency in Hz.
    :param highcut: High cutoff frequency in Hz.
    :param fs: Sample rate in Hz.
    :param order: Filter order. Default is 6.
    :return: A numpy array containing the filtered audio data.
    """
    sos = butter_bandpass(lowcut, highcut, fs, order=order)
    return sosfiltfilt(sos, data)


def process_chunk(data_chunk, sample_rate, low_freq, high_freq, reduce_noise_flag):
    """
    Processes a single segment (chunk) of audio data through the enhancement pipeline.

    Pipeline Steps:
    1. Spectral Noise Reduction (Optional): Removes constant background hiss/hum.
    2. Bandpass Filter: Removes frequencies outside human voice range.
    3. Conversion: Prepares data for Pydub (int16).
    4. Compression: Boosts quiet parts and attenuates loud peaks (Voice Boost).
    5. Normalization: Maximizes headroom to -1.0 dB.

    :param data_chunk: A numpy array containing the audio samples for this chunk.
    :param sample_rate: The sample rate of the audio in Hz.
    :param low_freq: Low frequency cutoff in Hz.
    :param high_freq: High frequency cutoff in Hz.
    :param reduce_noise_flag: Boolean. If True, applies spectral noise reduction.
    :return: A Pydub AudioSegment object containing the fully processed audio.
    """

    # 1. Spectral Noise Reduction (Optional but Recommended)
    # Uses 'stationary=True' assuming the background noise (fan/hum) is constant.
    if reduce_noise_flag:
        # We process simply on the chunk. For very short chunks, this might be less accurate,
        # but for 10-min chunks, it's highly effective.
        data_chunk = nr.reduce_noise(y=data_chunk, sr=sample_rate, stationary=True, prop_decrease=0.90)

    # 2. Bandpass Filter (Scipy)
    filtered = butter_bandpass_filter(data_chunk, low_freq, high_freq, sample_rate, order=6)

    # 3. Convert to Int16 for Pydub
    # Ensure clipping is handled before conversion by re-normalizing if we exceeded 1.0
    max_val = np.max(np.abs(filtered))
    if max_val > 1.0:
        filtered = filtered / max_val

    filtered_int16 = (filtered * 32767).astype(np.int16)

    # 4. Create AudioSegment
    seg = AudioSegment(
        filtered_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1,
    )

    # 5. Compress & Normalize
    # Threshold -20dB: Sounds louder than this are compressed.
    # Ratio 4.0: Standard broadcast ratio for voice.
    # Attack 5ms: Fast reaction to sudden peaks.
    compressed = compress_dynamic_range(seg, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
    final = normalize(compressed, headroom=1.0)

    return final


def process_audio(input_path, output_path=None, low_freq=300, high_freq=3400, chunk_minutes=10, reduce_noise=True):
    """
    Main orchestration function.

    It loads the large audio file, splits it into manageable chunks to prevent RAM overflow,
    processes each chunk sequentially, and saves them as separate files.

    :param input_path: Path to the source WAV file.
    :param output_path: Base path for the destination files. If None, uses input filename.
                        Actual outputs will append '_partXXX' to this name.
    :param low_freq: Low frequency cutoff for voice isolation in Hz. Default 300.
    :param high_freq: High frequency cutoff for voice isolation in Hz. Default 3400.
    :param chunk_minutes: The duration of each split file in minutes. Default 10.
    :param reduce_noise: Boolean to enable/disable spectral noise reduction. Default True.
    """
    if not os.path.exists(input_path):
        logger.error(f"Error: File {input_path} not found.")
        sys.exit(1)

    logger.info(f"Loading {input_path}...")
    try:
        sample_rate, data = wavfile.read(input_path)
    except ValueError:
        logger.error("Error: Could not read WAV file. Ensure it is a standard PCM WAV.")
        sys.exit(1)

    # Convert to Float Normalized
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0

    # Mix to Mono
    if len(data.shape) > 1:
        logger.info("Mixing stereo to mono...")
        data = np.mean(data, axis=1)

    # --- CHUNK PROCESSING CALCULATION ---
    total_samples = len(data)
    chunk_samples = int(chunk_minutes * 60 * sample_rate)
    total_chunks = math.ceil(total_samples / chunk_samples)

    logger.info(f"Audio Duration: {total_samples / sample_rate / 60:.2f} minutes")
    logger.info(f"Splitting into {total_chunks} chunk(s) of ~{chunk_minutes} mins.")

    if reduce_noise:
        logger.info("ℹ️  Noise Reduction is ENABLED (This may take longer)")

    base_name = os.path.splitext(input_path)[0]

    for i in range(total_chunks):
        start = i * chunk_samples
        end = min(start + chunk_samples, total_samples)

        logger.info(f"--- Processing Chunk {i + 1}/{total_chunks} ---")

        chunk_data = data[start:end]

        # Process the specific chunk with the configured flags
        processed_seg = process_chunk(chunk_data, sample_rate, low_freq, high_freq, reduce_noise)

        # Generate Output Filename
        if output_path:
            out_root, out_ext = os.path.splitext(output_path)
            chunk_out = f"{out_root}_part{i + 1:03d}{out_ext}"
        else:
            chunk_out = f"{base_name}_enhanced_part{i + 1:03d}.mp3"

        logger.info(f"Encoding {chunk_out}...")
        processed_seg.export(chunk_out, format="mp3", bitrate="192k")

    logger.info("✅ All chunks processed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance voice in WAV and convert to MP3 (Chunked + Denoise).")
    parser.add_argument("input_file", help="Path to input WAV file")
    parser.add_argument("--out", help="Path to output MP3 file (optional)")
    parser.add_argument("--low", type=int, default=300, help="Low cutoff Hz")
    parser.add_argument("--high", type=int, default=3400, help="High cutoff Hz")
    parser.add_argument("--split", type=int, default=10, help="Split size in minutes")
    # New flag to disable noise reduction if needed
    parser.add_argument("--no-denoise", action="store_true", help="Disable spectral noise reduction (faster)")

    args = parser.parse_args()

    # Logic inverted: Default is True, if --no-denoise is passed it becomes False
    do_denoise = not args.no_denoise

    process_audio(args.input_file, args.out, args.low, args.high, args.split, do_denoise)
