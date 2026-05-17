"""
Implements the audio sinks pipeline manager.

This module defines the AudioPipeline class, responsible for orchestrating the flow
of audio data through a sequence of processors (transformers) and delivering the
result to multiple sinks (consumers).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from .core.pipeline_context import PipelineContext
from .sinks.sinks_protocol import AudioSink
from .transformers.transformers_protocol import AudioTransformer


class AudioPipeline:
    """
    Orchestrates the flow of audio through processors and into sinks.
    """

    def __init__(self, sample_rate: float):
        """
        Initialize the pipeline.

        :param sample_rate: Audio sample rate (Hz). Used when creating context.
        """
        self._sample_rate = sample_rate
        self._processors: list[AudioTransformer] = []
        self._sinks: list[AudioSink] = []

    def add_transformer(self, processor: AudioTransformer):
        """Adds a transformer to the chain (order matters)."""
        self._processors.append(processor)

    def prepend_transformer(self, processor: AudioTransformer):
        """Inserts a transformer at the front of the chain."""
        self._processors.insert(0, processor)

    def add_sink(self, sink: AudioSink):
        """Adds a consumer to the end of the chain."""
        self._sinks.append(sink)

    def execute(self, audio_chunk: np.ndarray, timestamp: datetime):
        """
        Runs the pipeline for a single audio chunk.

        Creates a PipelineContext, passes it through all transformers
        sequentially, then fans out to all sinks.
        """
        # Create context at pipeline entry point
        ctx = PipelineContext(
            audio=audio_chunk,
            timestamp=timestamp,
            sample_rate=self._sample_rate,
        )

        # Transform: pass context through processor chain
        for processor in self._processors:
            ctx = processor.process(ctx)

        # Fan-out: deliver to all sinks
        for sink in self._sinks:
            sink.handle(ctx)
