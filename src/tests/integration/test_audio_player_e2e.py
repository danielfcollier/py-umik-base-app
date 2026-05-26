"""
End-to-end tests for audio_player.main().

Real WAV files are written to a tmp directory via soundfile. The audio
hardware (sounddevice) and terminal control (termios/tty) are mocked so the
tests run headless without speakers or a TTY.

Two execution paths are covered:
  - Non-interactive  (sys.stdin.isatty() == False): plays straight through.
  - Interactive      (sys.stdin.isatty() == True):  responds to key bindings.
"""

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from umik_base_app.apps.audio_player import main

SAMPLE_RATE = 48000


# ── helpers ───────────────────────────────────────────────────────────────────


def _write_wav(path, duration_s: float = 0.05, channels: int = 1):
    """Write a minimal silent WAV to path."""
    samples = int(SAMPLE_RATE * duration_s)
    data = np.zeros((samples, channels) if channels > 1 else samples, dtype=np.float32)
    sf.write(str(path), data, SAMPLE_RATE)
    return path


@contextmanager
def _mock_sd():
    """Patch sounddevice play/wait/stop; stream.active=False so loops exit."""
    stream = MagicMock()
    stream.active = False
    with patch("umik_base_app.apps.audio_player.sd.play") as mock_play, \
         patch("umik_base_app.apps.audio_player.sd.wait") as mock_wait, \
         patch("umik_base_app.apps.audio_player.sd.stop"), \
         patch("umik_base_app.apps.audio_player.sd.get_stream", return_value=stream):
        yield {"play": mock_play, "wait": mock_wait}


@contextmanager
def _mock_terminal():
    """Replace stdin with a TTY-like mock and patch termios/tty.

    sys.stdin.fileno() is called before tty.setcbreak() receives it, so we
    must replace sys.stdin entirely — patching only tty.setcbreak is not
    sufficient because the argument is evaluated first.
    """
    fake_stdin = MagicMock()
    fake_stdin.isatty.return_value = True
    fake_stdin.fileno.return_value = 0
    with patch("sys.stdin", fake_stdin), \
         patch("umik_base_app.apps.audio_player.termios.tcgetattr", return_value=[]) as mock_get, \
         patch("umik_base_app.apps.audio_player.termios.tcsetattr") as mock_set, \
         patch("umik_base_app.apps.audio_player.tty.setcbreak"):
        yield {"tcgetattr": mock_get, "tcsetattr": mock_set, "stdin": fake_stdin}


# ── non-interactive mode ───────────────────────────────────────────────────────
# pytest captures stdin so isatty() is already False — no extra patching needed.


@pytest.mark.integration
def test_main_noninteractive_plays_all_files(tmp_path, monkeypatch, capsys):
    """Non-interactive: plays every file in order via sd.play + sd.wait."""
    for i in range(3):
        _write_wav(tmp_path / f"track{i:02d}.wav")
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(tmp_path)])

    with _mock_sd() as sd_mocks:
        main()

    assert sd_mocks["play"].call_count == 3
    assert sd_mocks["wait"].call_count == 3


@pytest.mark.integration
def test_main_noninteractive_single_file(tmp_path, monkeypatch, capsys):
    """Non-interactive: a single file path works without a directory."""
    wav = _write_wav(tmp_path / "only.wav")
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(wav)])

    with _mock_sd() as sd_mocks:
        main()

    sd_mocks["play"].assert_called_once()
    assert "only.wav" in capsys.readouterr().out


@pytest.mark.integration
def test_main_noninteractive_multiple_explicit_files(tmp_path, monkeypatch):
    """Non-interactive: explicit list of files plays each one."""
    wavs = [_write_wav(tmp_path / f"{c}.wav") for c in "abc"]
    monkeypatch.setattr(sys, "argv", ["audio-tools-play"] + [str(w) for w in wavs])

    with _mock_sd() as sd_mocks:
        main()

    assert sd_mocks["play"].call_count == 3


@pytest.mark.integration
def test_main_noninteractive_skips_corrupt_file(tmp_path, monkeypatch, capsys):
    """Non-interactive: a file that fails to read is skipped; others still play."""
    good = _write_wav(tmp_path / "good.wav")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio data")

    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(bad), str(good)])

    with _mock_sd() as sd_mocks:
        main()

    assert sd_mocks["play"].call_count == 1
    assert "skip" in capsys.readouterr().err.lower()


@pytest.mark.integration
def test_main_empty_directory_exits_cleanly(tmp_path, monkeypatch, capsys):
    """No audio files found → prints message and exits with code 0."""
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        with _mock_sd():
            main()

    assert exc_info.value.code == 0
    assert "no supported audio files" in capsys.readouterr().out.lower()


@pytest.mark.integration
def test_main_noninteractive_stereo_file(tmp_path, monkeypatch):
    """Non-interactive: stereo WAV files are played without error."""
    _write_wav(tmp_path / "stereo.wav", channels=2)
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(tmp_path)])

    with _mock_sd() as sd_mocks:
        main()

    sd_mocks["play"].assert_called_once()


# ── interactive mode ───────────────────────────────────────────────────────────


@pytest.mark.integration
def test_main_interactive_plays_through_all_files(tmp_path, monkeypatch, capsys):
    """Interactive: natural playback completion advances through the whole queue."""
    for i in range(3):
        _write_wav(tmp_path / f"f{i}.wav")
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(tmp_path)])

    with _mock_terminal():
        with _mock_sd():
            with patch("umik_base_app.apps.audio_player._is_playing", return_value=False):
                with patch("umik_base_app.apps.audio_player._read_char", return_value=None):
                    main()

    assert "3/" in capsys.readouterr().out


@pytest.mark.integration
def test_main_interactive_quit_stops_early(tmp_path, monkeypatch, capsys):
    """Interactive: pressing q after the first file stops the session."""
    for i in range(3):
        _write_wav(tmp_path / f"f{i:02d}.wav")
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(tmp_path)])

    with _mock_terminal():
        with _mock_sd():
            with patch("umik_base_app.apps.audio_player._is_playing", return_value=True):
                with patch("umik_base_app.apps.audio_player._read_char", return_value="q"):
                    main()

    assert "2/3" not in capsys.readouterr().out


@pytest.mark.integration
def test_main_interactive_replay_reruns_same_file(tmp_path, monkeypatch):
    """Interactive: pressing r plays the same file twice before moving on."""
    _write_wav(tmp_path / "a.wav")
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(tmp_path)])

    keys = iter(["r", "\n"])

    with _mock_terminal():
        with _mock_sd() as sd_mocks:
            with patch("umik_base_app.apps.audio_player._is_playing", return_value=True):
                with patch("umik_base_app.apps.audio_player._read_char", side_effect=lambda: next(keys, None)):
                    main()

    assert sd_mocks["play"].call_count == 2


@pytest.mark.integration
def test_main_interactive_terminal_restored_on_completion(tmp_path, monkeypatch):
    """Interactive: tcsetattr is called in finally so the terminal is always restored."""
    _write_wav(tmp_path / "a.wav")
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(tmp_path)])

    with _mock_terminal() as term_mocks:
        with _mock_sd():
            with patch("umik_base_app.apps.audio_player._is_playing", return_value=False):
                with patch("umik_base_app.apps.audio_player._read_char", return_value=None):
                    main()

    term_mocks["tcsetattr"].assert_called_once()


@pytest.mark.integration
def test_main_interactive_terminal_restored_on_keyboard_interrupt(tmp_path, monkeypatch):
    """Interactive: terminal is restored even when KeyboardInterrupt is raised."""
    _write_wav(tmp_path / "a.wav")
    monkeypatch.setattr(sys, "argv", ["audio-tools-play", str(tmp_path)])

    with _mock_terminal() as term_mocks:
        with _mock_sd():
            with patch("umik_base_app.apps.audio_player._is_playing", side_effect=KeyboardInterrupt):
                with patch("umik_base_app.apps.audio_player._read_char", return_value=None):
                    main()  # must not re-raise

    term_mocks["tcsetattr"].assert_called_once()
