"""
Unit tests for the AudioPipeline class.
"""

from datetime import datetime
from unittest.mock import Mock

import numpy as np

from py_umik.core.interfaces import AudioSink, AudioTransformer
from py_umik.core.pipeline import AudioPipeline


def test_pipeline_execution():
    """Verify that audio flows through processors and reaches sinks."""
    pipeline = AudioPipeline()

    # --- Mocks ---
    # Processor: Multiplies audio by 2
    processor = Mock(spec=AudioTransformer)
    processor.process_audio.side_effect = lambda x: x * 2

    # AudioSink: Just receives audio
    sink1 = Mock(spec=AudioSink)
    sink2 = Mock(spec=AudioSink)

    # --- Build AudioPipeline ---
    pipeline.add_transformer(processor)
    pipeline.add_sink(sink1)
    pipeline.add_sink(sink2)

    # --- Execute ---
    original_audio = np.array([1.0, 2.0])
    timestamp = datetime.now()

    pipeline.execute(original_audio, timestamp)

    # --- Assertions ---
    # 1. Processor should have been called with original audio
    processor.process_audio.assert_called_once()

    # 2. AudioSinks should receive the *processed* audio (multiplied by 2)
    expected_audio = np.array([2.0, 4.0])

    # Check AudioSink 1
    call_args1 = sink1.handle_audio.call_args
    assert np.array_equal(call_args1[0][0], expected_audio)
    assert call_args1[0][1] == timestamp

    # Check AudioSink 2
    sink2.handle_audio.assert_called_once()
