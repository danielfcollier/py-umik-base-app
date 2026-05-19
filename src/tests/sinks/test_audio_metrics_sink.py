"""
Unit tests for AudioMetricsSink windowed buffering logic.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from umik_base_app.apps.real_time_meter import AudioMetricsSink
from umik_base_app.core.pipeline_context import PipelineContext


def _make_ctx(audio: np.ndarray) -> PipelineContext:
    return PipelineContext(audio=audio, timestamp=datetime(2025, 1, 1), sample_rate=48000.0)


def _chunk(n: int, value: float = 0.1) -> np.ndarray:
    return np.full(n, value, dtype=np.float32)


@pytest.fixture
def sink(tmp_path):
    """AudioMetricsSink with a 10-sample target window."""
    with patch("umik_base_app.apps.real_time_meter.settings") as mock_settings:
        mock_settings.METRICS.INTERVAL_SECONDS = 10 / 48000  # exactly 10 samples
        s = AudioMetricsSink(sample_rate=48000.0)
    s._target_samples = 10
    s._interval_seconds = 10 / 48000
    return s


class TestWindowedBuffering:
    def test_no_emit_before_target(self, sink):
        """Chunks below target accumulate without triggering a process call."""
        with patch.object(sink, "_process_and_log") as mock_process:
            sink.handle(_make_ctx(_chunk(5)))
            sink.handle(_make_ctx(_chunk(4)))
            mock_process.assert_not_called()
            assert sink._accumulated_samples == 9

    def test_emits_when_target_reached_exactly(self, sink):
        """Exactly reaching the target triggers one emit and leaves buffer empty."""
        with patch.object(sink, "_process_and_log") as mock_process:
            sink.handle(_make_ctx(_chunk(5)))
            sink.handle(_make_ctx(_chunk(5)))

            mock_process.assert_called_once()
            audio_sent = mock_process.call_args[0][0]
            assert len(audio_sent) == 10
            assert sink._accumulated_samples == 0
            assert sink._audio_buffer == []

    def test_overshoot_carried_into_next_window(self, sink):
        """Extra samples beyond the target are kept and start the next window."""
        with patch.object(sink, "_process_and_log") as mock_process:
            # 7 + 7 = 14 samples: emits first 10, carries 4
            sink.handle(_make_ctx(_chunk(7)))
            sink.handle(_make_ctx(_chunk(7)))

            mock_process.assert_called_once()
            audio_sent = mock_process.call_args[0][0]
            assert len(audio_sent) == 10

            assert sink._accumulated_samples == 4
            assert len(sink._audio_buffer) == 1
            assert len(sink._audio_buffer[0]) == 4

    def test_overshoot_feeds_second_window(self, sink):
        """Carried overshoot is used in the following window emit."""
        with patch.object(sink, "_process_and_log") as mock_process:
            # 7 + 7 = 14 → emit 10, carry 4
            sink.handle(_make_ctx(_chunk(7, value=1.0)))
            sink.handle(_make_ctx(_chunk(7, value=1.0)))
            assert mock_process.call_count == 1

            # 4 (carried) + 7 = 11 → emit 10, carry 1
            sink.handle(_make_ctx(_chunk(7, value=2.0)))
            assert mock_process.call_count == 2

            second_call_audio = mock_process.call_args[0][0]
            assert len(second_call_audio) == 10
            assert sink._accumulated_samples == 1

    def test_emitted_audio_has_exact_target_length(self, sink):
        """Audio passed to _process_and_log is always exactly _target_samples long."""
        received = []
        with patch.object(sink, "_process_and_log", side_effect=lambda a, *_: received.append(len(a))):
            for _ in range(5):
                sink.handle(_make_ctx(_chunk(7)))  # 5×7=35 samples → 3 full windows + 5 leftover

        assert all(n == 10 for n in received)
        assert len(received) == 3
        assert sink._accumulated_samples == 5


class TestImmediateMode:
    def test_immediate_mode_emits_every_chunk(self, tmp_path):
        """When interval is 0, every chunk is processed immediately."""
        with patch("umik_base_app.apps.real_time_meter.settings") as mock_settings:
            mock_settings.METRICS.INTERVAL_SECONDS = 0
            sink = AudioMetricsSink(sample_rate=48000.0)

        with patch.object(sink, "_process_and_log") as mock_process:
            sink.handle(_make_ctx(_chunk(100)))
            sink.handle(_make_ctx(_chunk(200)))

            assert mock_process.call_count == 2
