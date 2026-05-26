"""
Integration tests for audio_player._play_file.

Real numpy audio data is used; sounddevice and soundfile are mocked so no
hardware or actual files are needed. The tests exercise the full control flow
of _play_file: natural completion, key bindings, and error recovery.
"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from umik_base_app.apps.audio_player import _play_file

SAMPLE_RATE = 48000
DURATION_S = 0.1
FAKE_AUDIO = np.zeros(int(SAMPLE_RATE * DURATION_S), dtype=np.float32)


def _make_stream(active_sequence: list[bool]) -> MagicMock:
    """Return a mock stream whose .active attribute cycles through active_sequence."""
    stream = MagicMock()
    type(stream).active = property(lambda self, _seq=iter(active_sequence): next(_seq, False))
    return stream


@pytest.fixture()
def mock_sf_read():
    with patch("umik_base_app.apps.audio_player.sf.read", return_value=(FAKE_AUDIO, SAMPLE_RATE)) as m:
        yield m


@pytest.fixture()
def mock_sd():
    """Patch sounddevice play/stop/get_stream together."""
    with patch("umik_base_app.apps.audio_player.sd.play") as mock_play, \
         patch("umik_base_app.apps.audio_player.sd.stop") as mock_stop, \
         patch("umik_base_app.apps.audio_player.sd.get_stream") as mock_get_stream:
        yield {"play": mock_play, "stop": mock_stop, "get_stream": mock_get_stream}


# ── natural completion ─────────────────────────────────────────────────────────


@pytest.mark.integration
def test_play_file_natural_completion_returns_next(mock_sf_read, mock_sd):
    """Stream goes inactive on its own → _play_file returns 'next' without stopping."""
    mock_sd["get_stream"].return_value.active = False

    with patch("umik_base_app.apps.audio_player._read_char", return_value=None):
        result = _play_file(Path("fake.wav"), 1, 1)

    assert result == "next"
    mock_sd["play"].assert_called_once_with(FAKE_AUDIO, SAMPLE_RATE)
    mock_sd["stop"].assert_not_called()


@pytest.mark.integration
def test_play_file_advances_after_several_polls(mock_sf_read, mock_sd):
    """Returns 'next' after a few idle polls once the stream becomes inactive."""
    active_values = [True, True, True, False]
    mock_sd["get_stream"].return_value.active.__get__ = lambda self, *a: active_values.pop(0) if active_values else False

    # Provide enough None returns so we don't hit a StopIteration
    keys = iter([None, None, None])
    with patch("umik_base_app.apps.audio_player._read_char", side_effect=lambda: next(keys, None)):
        # Patch _is_playing directly so we can control the sequence cleanly
        active_seq = [True, True, True, False]
        with patch("umik_base_app.apps.audio_player._is_playing", side_effect=active_seq):
            result = _play_file(Path("fake.wav"), 1, 3)

    assert result == "next"


# ── key bindings ───────────────────────────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.parametrize("key,expected", [
    ("\n", "next"),
    ("\r", "next"),
    (" ", "next"),
])
def test_play_file_skip_keys_return_next(key, expected, mock_sf_read, mock_sd):
    """Enter, carriage-return, and space all skip to the next file."""
    with patch("umik_base_app.apps.audio_player._is_playing", return_value=True):
        with patch("umik_base_app.apps.audio_player._read_char", return_value=key):
            result = _play_file(Path("fake.wav"), 2, 5)

    assert result == expected
    mock_sd["stop"].assert_called_once()


@pytest.mark.integration
@pytest.mark.parametrize("key", ["r", "R"])
def test_play_file_replay_key_returns_replay(key, mock_sf_read, mock_sd):
    """r/R stops playback and returns 'replay'."""
    with patch("umik_base_app.apps.audio_player._is_playing", return_value=True):
        with patch("umik_base_app.apps.audio_player._read_char", return_value=key):
            result = _play_file(Path("fake.wav"), 1, 1)

    assert result == "replay"
    mock_sd["stop"].assert_called_once()


@pytest.mark.integration
@pytest.mark.parametrize("key", ["q", "Q"])
def test_play_file_quit_key_returns_quit(key, mock_sf_read, mock_sd):
    """q/Q stops playback and returns 'quit'."""
    with patch("umik_base_app.apps.audio_player._is_playing", return_value=True):
        with patch("umik_base_app.apps.audio_player._read_char", return_value=key):
            result = _play_file(Path("fake.wav"), 3, 3)

    assert result == "quit"
    mock_sd["stop"].assert_called_once()


# ── error recovery ─────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_play_file_skips_unreadable_file(mock_sd, capsys):
    """A soundfile read error prints a skip message and returns 'next'."""
    with patch("umik_base_app.apps.audio_player.sf.read", side_effect=Exception("corrupt")):
        result = _play_file(Path("bad.wav"), 1, 2)

    assert result == "next"
    mock_sd["play"].assert_not_called()
    captured = capsys.readouterr()
    assert "skip" in captured.out.lower()
    assert "bad.wav" in captured.out


@pytest.mark.integration
def test_play_file_shows_filename_and_metadata(mock_sf_read, mock_sd, capsys):
    """Header block is printed with filename, duration, sample rate, and channel info."""
    with patch("umik_base_app.apps.audio_player._is_playing", return_value=False):
        with patch("umik_base_app.apps.audio_player._read_char", return_value=None):
            _play_file(Path("session.wav"), 2, 7)

    out = capsys.readouterr().out
    assert "session.wav" in out
    assert "2/7" in out
    assert "48000" in out
    assert "mono" in out


@pytest.mark.integration
def test_play_file_shows_stereo_label_for_2d_audio(mock_sd, capsys):
    """Two-channel audio is labelled 'stereo'."""
    stereo = np.zeros((SAMPLE_RATE, 2), dtype=np.float32)
    with patch("umik_base_app.apps.audio_player.sf.read", return_value=(stereo, SAMPLE_RATE)):
        with patch("umik_base_app.apps.audio_player._is_playing", return_value=False):
            with patch("umik_base_app.apps.audio_player._read_char", return_value=None):
                _play_file(Path("stereo.wav"), 1, 1)

    assert "stereo" in capsys.readouterr().out


@pytest.mark.integration
def test_play_file_index_and_total_displayed(mock_sf_read, mock_sd, capsys):
    """[index/total] counter reflects the arguments passed in."""
    with patch("umik_base_app.apps.audio_player._is_playing", return_value=False):
        with patch("umik_base_app.apps.audio_player._read_char", return_value=None):
            _play_file(Path("x.wav"), 4, 9)

    assert "4/9" in capsys.readouterr().out
