"""
Unit tests for the AudioPipeline class.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import Mock, sentinel

from umik_base_app import (
    AudioPipeline,
    AudioSink,
    AudioTransformer,
)


def test_pipeline_execution():
    """Verify that audio flows through processors and reaches sinks."""
    pipeline = AudioPipeline()

    # --- Mocks ---
    # Processor: Should transform 'original_audio' into 'processed_audio'
    processor = Mock(spec=AudioTransformer)
    processor.process_audio.return_value = sentinel.processed_audio

    # AudioSink: Just receives audio
    sink1 = Mock(spec=AudioSink)
    sink2 = Mock(spec=AudioSink)

    # --- Build AudioPipeline ---
    pipeline.add_transformer(processor)
    pipeline.add_sink(sink1)
    pipeline.add_sink(sink2)

    # --- Execute ---
    pipeline.execute(sentinel.original_audio, sentinel.timestamp)

    # --- Assertions ---
    # 1. Processor should have been called with original audio
    processor.process_audio.assert_called_once_with(sentinel.original_audio)

    # 2. AudioSinks should receive the *processed* audio returned by the transformer
    sink1.handle_audio.assert_called_once_with(sentinel.processed_audio, sentinel.timestamp)
    sink2.handle_audio.assert_called_once_with(sentinel.processed_audio, sentinel.timestamp)
