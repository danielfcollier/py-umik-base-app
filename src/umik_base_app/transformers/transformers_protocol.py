"""
Defines the protocols for audio processing components and data sinks.

This module establishes the contracts for AudioTransformer (transformers) and
AudioSink (consumers) to ensure modularity and type safety in the audio pipeline.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from typing import Protocol, runtime_checkable

from ..core.pipeline_context import PipelineContext


@runtime_checkable
class AudioTransformer(Protocol):
    """
    Protocol for components that transform audio data (e.g., CalibratorTransformer, Filter).

    Transformers receive a PipelineContext, modify ctx.audio in place,
    optionally annotate ctx.metadata, and return the context.

    Example:
        def process(self, ctx: PipelineContext) -> PipelineContext:
            ctx.audio = ctx.audio * self._gain
            ctx.set("gain_applied", True)
            return ctx
    """

    def process(self, ctx: PipelineContext) -> PipelineContext: ...
