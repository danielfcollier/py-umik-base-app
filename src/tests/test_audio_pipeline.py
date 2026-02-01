"""
Unit tests for the AudioPipeline class.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from datetime import datetime
from unittest.mock import Mock, sentinel

import numpy as np

from umik_base_app import (
    AudioPipeline,
    AudioSink,
    AudioTransformer,
    PipelineContext,
)


def test_pipeline_execution():
    """Verify that audio flows through processors and reaches sinks."""
    sample_rate = 48000.0
    pipeline = AudioPipeline(sample_rate=sample_rate)

    # --- Mocks ---
    # Processor: Should transform audio via context
    processor = Mock(spec=AudioTransformer)

    def mock_process(ctx):
        # Simulate processing by modifying the audio
        ctx.audio = sentinel.processed_audio
        return ctx

    processor.process.side_effect = mock_process

    # AudioSink: Just receives context
    sink1 = Mock(spec=AudioSink)
    sink2 = Mock(spec=AudioSink)

    # --- Build AudioPipeline ---
    pipeline.add_transformer(processor)
    pipeline.add_sink(sink1)
    pipeline.add_sink(sink2)

    # --- Execute ---
    pipeline.execute(sentinel.original_audio, sentinel.timestamp)

    # --- Assertions ---
    # 1. Processor should have been called with a context containing original audio
    processor.process.assert_called_once()
    call_ctx = processor.process.call_args[0][0]
    assert isinstance(call_ctx, PipelineContext)

    # 2. Sinks should receive context with processed audio
    sink1.handle.assert_called_once()
    sink2.handle.assert_called_once()

    # Verify sinks received context with processed audio
    sink1_ctx = sink1.handle.call_args[0][0]
    sink2_ctx = sink2.handle.call_args[0][0]
    assert sink1_ctx.audio == sentinel.processed_audio
    assert sink2_ctx.audio == sentinel.processed_audio


def test_pipeline_context_creation():
    """Verify that pipeline creates context with correct fields."""
    sample_rate = 44100.0
    pipeline = AudioPipeline(sample_rate=sample_rate)

    captured_ctx = None

    def capture_sink(ctx):
        nonlocal captured_ctx
        captured_ctx = ctx

    sink = Mock(spec=AudioSink)
    sink.handle.side_effect = capture_sink

    pipeline.add_sink(sink)

    test_audio = np.array([0.1, 0.2, 0.3])
    test_timestamp = datetime(2025, 1, 15, 12, 0, 0)

    pipeline.execute(test_audio, test_timestamp)

    assert captured_ctx is not None
    assert np.array_equal(captured_ctx.audio, test_audio)
    assert captured_ctx.timestamp == test_timestamp
    assert captured_ctx.sample_rate == sample_rate
    assert captured_ctx.metadata == {}


def test_pipeline_metadata_propagation():
    """Verify that transformer metadata annotations reach sinks."""
    pipeline = AudioPipeline(sample_rate=48000.0)

    def annotating_processor(ctx):
        ctx.set("gain_applied", True)
        ctx.set("sensitivity_dbfs", -18.5)
        return ctx

    processor = Mock(spec=AudioTransformer)
    processor.process.side_effect = annotating_processor

    sink = Mock(spec=AudioSink)
    pipeline.add_transformer(processor)
    pipeline.add_sink(sink)

    pipeline.execute(np.array([0.0]), datetime.now())

    sink_ctx = sink.handle.call_args[0][0]
    assert sink_ctx.gain_applied is True
    assert sink_ctx.sensitivity_dbfs == -18.5


def test_pipeline_without_transformers():
    """Verify that pipeline works with only sinks (no transformers)."""
    pipeline = AudioPipeline(sample_rate=48000.0)

    sink = Mock(spec=AudioSink)
    pipeline.add_sink(sink)

    test_audio = np.array([1.0, 2.0, 3.0])
    pipeline.execute(test_audio, sentinel.timestamp)

    sink.handle.assert_called_once()
    ctx = sink.handle.call_args[0][0]
    assert np.array_equal(ctx.audio, test_audio)


def test_pipeline_transformer_chain():
    """Verify that multiple transformers are applied in order."""
    pipeline = AudioPipeline(sample_rate=48000.0)

    def multiply_by_2(ctx):
        ctx.audio = ctx.audio * 2
        ctx.set("step1", True)
        return ctx

    def add_10(ctx):
        ctx.audio = ctx.audio + 10
        ctx.set("step2", True)
        return ctx

    transformer1 = Mock(spec=AudioTransformer)
    transformer1.process.side_effect = multiply_by_2

    transformer2 = Mock(spec=AudioTransformer)
    transformer2.process.side_effect = add_10

    sink = Mock(spec=AudioSink)

    pipeline.add_transformer(transformer1)
    pipeline.add_transformer(transformer2)
    pipeline.add_sink(sink)

    input_audio = np.array([1.0, 2.0, 3.0])
    pipeline.execute(input_audio, datetime.now())

    ctx = sink.handle.call_args[0][0]
    # (input * 2) + 10 = [12, 14, 16]
    expected = np.array([12.0, 14.0, 16.0])
    assert np.array_equal(ctx.audio, expected)
    assert ctx.get("step1") is True
    assert ctx.get("step2") is True
