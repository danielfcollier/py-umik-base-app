"""
Voice Enhancer & Compressor (Chunked).
Applies filters and compression in 10-minute chunks to handle large files.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import logging
import math
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

    This function calculates the Second-Order Sections (SOS) for a bandpass filter,
    which are numerically more stable than standard numerator/denominator coefficients
    for high-order filtering.

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
    Applies the Butterworth bandpass filter to the audio data.

    It uses `sosfiltfilt` to apply the filter forward and backward.
    This results in zero phase distortion, meaning the timing of audio
    peaks (transients) remains aligned with the original signal, which is critical
    for maintaining voice clarity.

    :param data: The input audio array (normalized float).
    :param lowcut: Low cutoff frequency in Hz.
    :param highcut: High cutoff frequency in Hz.
    :param fs: Sample rate in Hz.
    :param order: Filter order. Default is 6.
    :return: A numpy array containing the filtered audio data.
    """
    sos = butter_bandpass(lowcut, highcut, fs, order=order)
    # sosfiltfilt is a zero-phase filter (doesn't shift the timing of the sound)
    return sosfiltfilt(sos, data)


def process_chunk(data_chunk, sample_rate, low_freq, high_freq):
    """
    Processes a specific segment (chunk) of audio data.

    This function performs the core signal processing chain on a subset of the
    original file to conserve memory:
    1. Bandpass Filtering (Scipy): Isolates the voice frequency range.
    2. Format Conversion: Converts float data back to int16 for Pydub compatibility.
    3. Dynamic Range Compression (Pydub): Boosts quiet parts without clipping loud parts.
    4. Normalization (Pydub): Maximizes the final volume headroom.

    :param data_chunk: A numpy array containing the audio samples for this chunk.
    :param sample_rate: The sample rate of the audio in Hz.
    :param low_freq: The low frequency cutoff for the filter in Hz.
    :param high_freq: The high frequency cutoff for the filter in Hz.
    :return: A Pydub AudioSegment object containing the processed and encoded audio.
    """
    # 1. Filter
    filtered = butter_bandpass_filter(data_chunk, low_freq, high_freq, sample_rate, order=6)

    # 2. Convert to Int16 for Pydub
    filtered_int16 = (filtered * 32767).astype(np.int16)

    # 3. Create AudioSegment
    seg = AudioSegment(
        filtered_int16.tobytes(),
        frame_rate=sample_rate,
        sample_width=2,
        channels=1,
    )

    # 4. Compress & Normalize
    compressed = compress_dynamic_range(seg, threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
    final = normalize(compressed, headroom=1.0)
    return final


def process_audio(input_path, output_path=None, low_freq=300, high_freq=3400, chunk_minutes=10):
    """
    Main processing pipeline that orchestrates the loading, splitting, and saving of audio.

    Steps:
    1. Loads the WAV file and converts it to normalized mono float32.
    2. Calculates the number of chunks based on `chunk_minutes` to avoid high RAM usage.
    3. Iterates through the data, processing one chunk at a time.
    4. Saves each processed chunk as a separate MP3 file (e.g., file_part001.mp3).

    :param input_path: Path to the source WAV file.
    :param output_path: Base path for the destination files. If None, uses input filename.
                        Actual outputs will append '_partXXX' to this name.
    :param low_freq: Low frequency cutoff for voice isolation in Hz. Default 300.
    :param high_freq: High frequency cutoff for voice isolation in Hz. Default 3400.
    :param chunk_minutes: The duration of each split file in minutes. Default 10.
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

    # --- CHUNK PROCESSING ---
    total_samples = len(data)
    chunk_samples = int(chunk_minutes * 60 * sample_rate)
    total_chunks = math.ceil(total_samples / chunk_samples)

    logger.info(f"Audio Duration: {total_samples / sample_rate / 60:.2f} minutes")
    logger.info(f"Splitting into {total_chunks} chunk(s) of ~{chunk_minutes} mins each.")

    base_name = os.path.splitext(input_path)[0]

    for i in range(total_chunks):
        start = i * chunk_samples
        end = min(start + chunk_samples, total_samples)

        logger.info(f"--- Processing Chunk {i + 1}/{total_chunks} ---")

        # Slicing the numpy array (Fast)
        chunk_data = data[start:end]

        # Process
        processed_seg = process_chunk(chunk_data, sample_rate, low_freq, high_freq)

        # Generate Filename
        if output_path:
            # If user gave a specific name, append part number: "output_part1.mp3"
            out_root, out_ext = os.path.splitext(output_path)
            chunk_out = f"{out_root}_part{i + 1:03d}{out_ext}"
        else:
            # Default name
            chunk_out = f"{base_name}_enhanced_part{i + 1:03d}.mp3"

        logger.info(f"Encoding {chunk_out}...")
        processed_seg.export(chunk_out, format="mp3", bitrate="192k")

    logger.info("✅ All chunks processed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhance voice in WAV and convert to MP3 (Chunked).")
    parser.add_argument("input_file", help="Path to input WAV file")
    parser.add_argument("--out", help="Path to output MP3 file (optional)")
    parser.add_argument("--low", type=int, default=300, help="Low cutoff Hz")
    parser.add_argument("--high", type=int, default=3400, help="High cutoff Hz")
    parser.add_argument("--split", type=int, default=10, help="Split size in minutes (default: 10)")

    args = parser.parse_args()
    process_audio(args.input_file, args.out, args.low, args.high, args.split)
