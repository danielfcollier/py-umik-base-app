"""
Unit tests for umik_base_app.apps.audio_player.

Covers pure helpers (_fmt, _collect_files, _is_playing, _read_char) with no
real file I/O or audio hardware. All external dependencies are mocked.
"""

import sys
from unittest.mock import MagicMock, patch

from umik_base_app.apps.audio_player import (
    AUDIO_EXTENSIONS,
    _collect_files,
    _fmt,
    _is_playing,
    _read_char,
)

# ── _fmt ──────────────────────────────────────────────────────────────────────


class TestFmt:
    def test_zero(self):
        assert _fmt(0) == "0:00"

    def test_seconds_only(self):
        assert _fmt(30) == "0:30"

    def test_one_minute(self):
        assert _fmt(60) == "1:00"

    def test_minutes_and_seconds(self):
        assert _fmt(65) == "1:05"

    def test_leading_zero_on_seconds(self):
        assert _fmt(61) == "1:01"

    def test_large_value(self):
        # 61 minutes 1 second
        assert _fmt(3661) == "61:01"

    def test_float_truncates(self):
        # fractional seconds are truncated, not rounded
        assert _fmt(59.9) == "0:59"


# ── _collect_files ─────────────────────────────────────────────────────────────


class TestCollectFiles:
    def test_single_wav_file(self, tmp_path):
        f = tmp_path / "a.wav"
        f.touch()
        result = _collect_files([str(f)])
        assert result == [f]

    def test_directory_returns_sorted_audio_files(self, tmp_path):
        (tmp_path / "c.wav").touch()
        (tmp_path / "a.flac").touch()
        (tmp_path / "b.ogg").touch()
        (tmp_path / "z.txt").touch()  # should be skipped
        result = _collect_files([str(tmp_path)])
        names = [p.name for p in result]
        assert names == sorted(names)
        assert "z.txt" not in names

    def test_skips_unsupported_extensions(self, tmp_path, capsys):
        (tmp_path / "audio.mp3").touch()
        result = _collect_files([str(tmp_path / "audio.mp3")])
        assert result == []
        captured = capsys.readouterr()
        assert "unsupported" in captured.err

    def test_multiple_explicit_files(self, tmp_path):
        a = tmp_path / "a.wav"
        b = tmp_path / "b.flac"
        a.touch()
        b.touch()
        result = _collect_files([str(a), str(b)])
        assert result == [a, b]

    def test_deduplicates_same_file(self, tmp_path):
        f = tmp_path / "a.wav"
        f.touch()
        result = _collect_files([str(f), str(f)])
        assert len(result) == 1

    def test_nonexistent_path_warns(self, tmp_path, capsys):
        result = _collect_files([str(tmp_path / "ghost.wav")])
        assert result == []
        captured = capsys.readouterr()
        assert "no files matched" in captured.err.lower()

    def test_all_supported_extensions_accepted(self, tmp_path):
        for ext in AUDIO_EXTENSIONS:
            (tmp_path / f"file{ext}").touch()
        result = _collect_files([str(tmp_path)])
        assert len(result) == len(AUDIO_EXTENSIONS)

    def test_empty_directory(self, tmp_path):
        result = _collect_files([str(tmp_path)])
        assert result == []

    def test_mixed_directory_and_file(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.wav").touch()
        extra = tmp_path / "b.wav"
        extra.touch()
        result = _collect_files([str(sub), str(extra)])
        assert len(result) == 2


# ── _is_playing ────────────────────────────────────────────────────────────────


class TestIsPlaying:
    def test_returns_true_when_stream_active(self):
        mock_stream = MagicMock()
        mock_stream.active = True
        with patch("umik_base_app.apps.audio_player.sd.get_stream", return_value=mock_stream):
            assert _is_playing() is True

    def test_returns_false_when_stream_inactive(self):
        mock_stream = MagicMock()
        mock_stream.active = False
        with patch("umik_base_app.apps.audio_player.sd.get_stream", return_value=mock_stream):
            assert _is_playing() is False

    def test_returns_false_when_no_stream_exists(self):
        with patch("umik_base_app.apps.audio_player.sd.get_stream", side_effect=Exception("no stream")):
            assert _is_playing() is False


# ── _read_char ─────────────────────────────────────────────────────────────────


class TestReadChar:
    def test_returns_char_when_data_available(self):
        with patch("umik_base_app.apps.audio_player.select.select", return_value=([sys.stdin], [], [])):
            with patch.object(sys.stdin, "read", return_value="r"):
                result = _read_char()
        assert result == "r"

    def test_returns_none_on_timeout(self):
        with patch("umik_base_app.apps.audio_player.select.select", return_value=([], [], [])):
            result = _read_char()
        assert result is None

    def test_respects_custom_timeout(self):
        captured_timeout = []

        def fake_select(rlist, wlist, xlist, timeout):
            captured_timeout.append(timeout)
            return ([], [], [])

        with patch("umik_base_app.apps.audio_player.select.select", side_effect=fake_select):
            _read_char(timeout=0.25)

        assert captured_timeout[0] == 0.25
