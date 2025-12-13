"""
Implements the audio processing pipeline manager.

This module defines the AudioPipeline class, responsible for orchestrating the flow
of audio data through a sequence of processors (transformers) and delivering the
result to multiple sinks (consumers).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from datetime import datetime

import numpy as np

from src.library.interfaces import AudioProcessor, AudioSink


class AudioPipeline:
    """
    Orchestrates the flow of audio through processors and into sinks.
    """

    def __init__(self):
        self._processors: list[AudioProcessor] = []
        self._sinks: list[AudioSink] = []

    def add_processor(self, processor: AudioProcessor):
        """Adds a transformer to the chain (order matters)."""
        self._processors.append(processor)

    def add_sink(self, sink: AudioSink):
        """Adds a consumer to the end of the chain."""
        self._sinks.append(sink)

    def execute(self, audio_chunk: np.ndarray, timestamp: datetime):
        """
        Runs the pipeline for a single audio chunk.
        """
        # 1. Transform: Pass audio through all processors sequentially
        processed_chunk = audio_chunk
        for processor in self._processors:
            processed_chunk = processor.process_audio(processed_chunk)

        # 2. Fan-out: Deliver the final audio to all sinks
        for sink in self._sinks:
            sink.handle_audio(processed_chunk, timestamp)
