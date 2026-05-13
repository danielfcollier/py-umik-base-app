"""
Defines an adapter class to integrate the CalibratorTransformer into the audio pipeline.

This module provides the CalibratorAdapter, which wraps the underlying
calibrator logic to satisfy the generic AudioTransformer protocol interface.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from ..core.pipeline_context import PipelineContext
from .calibrator_transformer import CalibratorTransformer
from .transformers_protocol import AudioTransformer


class CalibratorAdapter(AudioTransformer):
    """
    Adapts CalibratorTransformer to the AudioTransformer protocol.

    This adapter bridges the calibration domain logic with the pipeline's
    PipelineContext-based interface. It applies calibration to audio and
    annotates the context with calibration metadata for downstream sinks.
    """

    def __init__(
        self,
        calibrator: CalibratorTransformer,
        sensitivity_dbfs: float,
        reference_dbspl: float,
    ):
        """
        Initialize the adapter.

        :param calibrator: The CalibratorTransformer to wrap.
        :param sensitivity_dbfs: Calibrated sensitivity in dBFS.
        :param reference_dbspl: Reference SPL level in dBSPL.
        """
        self._calibrator = calibrator
        self._sensitivity_dbfs = sensitivity_dbfs
        self._reference_dbspl = reference_dbspl

    def process(self, ctx: PipelineContext) -> PipelineContext:
        """
        Apply calibration and annotate context with calibration metadata.

        :param ctx: The pipeline context containing audio data.
        :return: The same context with calibrated audio and metadata.
        """
        ctx.audio = self._calibrator.apply(ctx.audio)
        ctx.set("calibration_applied", True)
        ctx.set("sensitivity_dbfs", self._sensitivity_dbfs)
        ctx.set("reference_dbspl", self._reference_dbspl)
        ctx.set("gain_applied", True)
        ctx.set("fir_applied", True)
        return ctx
