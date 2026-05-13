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
class AudioSink(Protocol):
    """
    Protocol for components that consume audio data (e.g., Recorder, Meter, GUI).

    Sinks receive a PipelineContext containing the final audio
    and all metadata annotations from the transformer chain.

    Example:
        def handle(self, ctx: PipelineContext) -> None:
            if ctx.sensitivity_dbfs is not None:
                dbspl = calculate_dbspl(ctx.audio, ctx.sensitivity_dbfs)
    """

    def handle(self, ctx: PipelineContext) -> None: ...
