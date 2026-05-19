"""
Textual TUI for the real-time SPL meter.

Runs audio capture in a background thread and updates the display at 10 Hz.
"""

from __future__ import annotations

import logging
import queue
import threading
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import RichLog, Static


class TuiLogHandler(logging.Handler):
    """Routes Python log records into a queue for display inside the TUI."""

    def __init__(self, log_queue: queue.Queue[str]) -> None:
        super().__init__()
        self._log_queue = log_queue
        self.setFormatter(logging.Formatter("%(levelname)-8s %(threadName)s  %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._log_queue.put_nowait(self.format(record))
        except queue.Full:
            pass


from ..app_config import AppConfig
from ..audio_base_app import AudioBaseApp
from ..core.pipeline_context import PipelineContext
from ..sinks.sinks_protocol import AudioSink
from .real_time_meter import AudioMetricsSink


class TuiRecordingSink(AudioSink):
    """
    An AudioSink that writes audio to WAV on demand.

    Call start() to begin recording and stop() to flush and close the file.
    Thread-safe: handle() is called from the audio thread while start/stop
    are called from the Textual main thread.
    """

    def __init__(self, sample_rate: float, output_dir: str = "recordings") -> None:
        self._sample_rate = int(sample_rate)
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._recording = False
        self._wave_file: wave.Wave_write | None = None
        self._current_filename: str = ""

    def start(self) -> str:
        """Open a new WAV file and begin recording. Returns the filename."""
        with self._lock:
            if self._recording:
                return self._current_filename
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = str(self._output_dir / f"recording_{timestamp}.wav")
            wf = wave.open(filename, "wb")
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            self._wave_file = wf
            self._current_filename = filename
            self._recording = True
            return filename

    def stop(self) -> str:
        """Stop recording, close the WAV file, and return the filename."""
        with self._lock:
            if not self._recording:
                return ""
            filename = self._current_filename
            if self._wave_file is not None:
                self._wave_file.close()
                self._wave_file = None
            self._recording = False
            self._current_filename = ""
            return filename

    def is_recording(self) -> bool:
        return self._recording

    def handle(self, ctx: PipelineContext) -> None:
        with self._lock:
            if not self._recording or self._wave_file is None:
                return
            audio_int16 = (ctx.audio * 32767).astype(np.int16)
            self._wave_file.writeframes(audio_int16.tobytes())


class TuiMetricsSink(AudioMetricsSink):
    """
    Drops computed metrics into a queue instead of logging them.
    Oldest entry is evicted when the queue is full so the display always shows
    the latest reading.
    """

    def __init__(self, sample_rate: float, metrics_queue: queue.Queue[dict]) -> None:
        super().__init__(sample_rate=sample_rate)
        # Override buffered mode: TUI needs per-chunk updates for live display
        self._target_samples = 0
        self._metrics_queue = metrics_queue

    def _log_calibration_state(self, ctx: PipelineContext) -> None:
        pass  # TUI shows calibration state in the header; silence the log line.

    def _process_and_log(
        self,
        audio_data: Any,
        timestamp: datetime,
        ctx: PipelineContext,
    ) -> None:
        dbfs = self._audio_metrics.dBFS(audio_data)
        data: dict = {
            "timestamp": timestamp.strftime("%H:%M:%S"),
            "dbfs": dbfs,
            "lufs": self._audio_metrics.lufs(audio_data),
            "rms": self._audio_metrics.rms(audio_data),
            "flux": self._audio_metrics.flux(audio_data, self._sample_rate),
        }

        if ctx.can_calculate_dbspl():
            data["dbspl"] = self._calculate_dbspl(dbfs, ctx)
            if ctx.is_fully_calibrated():
                data["calibration"] = "FULL (FIR)"
            elif ctx.is_gain_calibrated():
                data["calibration"] = "GAIN"
            else:
                data["calibration"] = "RAW"
        else:
            data["calibration"] = "NONE"

        try:
            self._metrics_queue.put_nowait(data)
        except queue.Full:
            try:
                self._metrics_queue.get_nowait()
                self._metrics_queue.put_nowait(data)
            except queue.Empty:
                pass


class LevelMeter(Widget):
    """Horizontal dBFS bar that adapts to the widget's width."""

    DEFAULT_CSS = """
    LevelMeter {
        height: 7;
        padding: 1 2;
    }
    """

    level = reactive(-96.0)

    def render(self) -> Text:
        dbfs = self.level
        bar_width = max(20, self.size.width - 4)
        normalized = max(0.0, min(1.0, (dbfs + 60) / 60))
        filled = int(normalized * bar_width)
        empty = bar_width - filled

        if dbfs > -6:
            bar_style = "bold red"
            label_style = "bold red"
        elif dbfs > -18:
            bar_style = "bold yellow"
            label_style = "bold yellow"
        else:
            bar_style = "bold green"
            label_style = "bold green"

        text = Text()
        text.append("dBFS\n\n", style="bold white")
        text.append("█" * filled, style=bar_style)
        text.append("░" * empty, style="dim white")
        text.append(f"\n\n{dbfs:+.1f} dBFS", style=label_style)
        return text


class MeterTuiApp(App[None]):
    """Real-time audio measurement dashboard."""

    CSS = """
    Screen {
        layout: vertical;
        background: $surface;
    }

    #header {
        height: 3;
        background: $primary-darken-2;
        color: $text;
        content-align: center middle;
        text-style: bold;
        border-bottom: solid $primary;
    }

    #main {
        height: 1fr;
        layout: horizontal;
    }

    #level-panel {
        width: 45%;
        border-right: solid $primary-darken-1;
    }

    #stats-panel {
        width: 1fr;
        padding: 2 3;
    }

    #log-panel {
        height: 5;
        border-top: solid $primary-darken-1;
        background: $surface-darken-1;
        display: none;
    }

    #status {
        height: 1;
        background: $panel;
        color: $text-muted;
        padding: 0 2;
        content-align: center middle;
    }
    """

    BINDINGS = [
        ("r", "toggle_record", "Record"),
        ("l", "toggle_log", "Log"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(
        self,
        audio_app: AudioBaseApp,
        metrics_queue: queue.Queue[dict],
        config: AppConfig,
        recording_sink: TuiRecordingSink | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._audio_app = audio_app
        self._metrics_queue = metrics_queue
        self._config = config
        self._recording_sink = recording_sink
        self._log_queue: queue.Queue[str] = queue.Queue(maxsize=200)
        self._log_handler = TuiLogHandler(self._log_queue)

    def compose(self) -> ComposeResult:
        yield Static("audio-tools --meter   Calibration: —", id="header")
        with Horizontal(id="main"):
            with Vertical(id="level-panel"):
                yield LevelMeter()
            yield Static("Waiting for audio...", id="stats-panel")
        yield RichLog(id="log-panel", highlight=False, markup=False, wrap=True)
        yield Static("", id="status")

    def on_mount(self) -> None:
        logging.getLogger().addHandler(self._log_handler)
        self._audio_thread = threading.Thread(
            target=self._audio_app.run,
            name="AudioPipeline",
            daemon=True,
        )
        self._audio_thread.start()
        self.set_interval(1 / 10, self._poll_metrics)
        self._update_status_bar(ts="")

    def _poll_metrics(self) -> None:
        latest: dict | None = None
        while True:
            try:
                latest = self._metrics_queue.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            self._refresh_display(latest)

        log_widget = self.query_one("#log-panel", RichLog)
        while True:
            try:
                log_widget.write(self._log_queue.get_nowait())
            except queue.Empty:
                break

    def _refresh_display(self, data: dict) -> None:
        cal = data.get("calibration", "NONE")
        self.query_one("#header", Static).update(f"audio-tools --meter   Calibration: {cal}")

        self.query_one(LevelMeter).level = data["dbfs"]

        lines: list[str] = []
        if "dbspl" in data:
            lines.append(f"[bold cyan]dBSPL[/bold cyan]   {data['dbspl']:+.1f} dB")
        lines.append(f"[bold]LUFS [/bold]   {data['lufs']:.1f} LUFS")
        lines.append(f"[bold]RMS  [/bold]   {data['rms']:.4f}")
        lines.append(f"[bold]Flux [/bold]   {data['flux']:.1f}")
        if "dbspl" not in data:
            lines.append("\n[dim]Pass --calibration-file for dBSPL[/dim]")
        self.query_one("#stats-panel", Static).update("\n".join(lines))

        self._update_status_bar(ts=data.get("timestamp", ""))

    def _update_status_bar(self, ts: str) -> None:
        mode = self._config.run_mode.value.upper()
        sr = int(self._config.sample_rate)
        is_rec = self._recording_sink is not None and self._recording_sink.is_recording()
        rec_part = "  [bold red]● REC[/bold red]   [R] Stop" if is_rec else "  [R] Record"
        self.query_one("#status", Static).update(f"Mode: {mode}   SR: {sr} Hz   {ts}{rec_part}   [Q] Quit")

    def action_toggle_record(self) -> None:
        if self._recording_sink is None:
            self.notify("Recording not available", severity="warning")
            return

        if self._recording_sink.is_recording():
            filename = self._recording_sink.stop()
            self.notify(f"Saved: {filename}", title="Recording stopped")
        else:
            filename = self._recording_sink.start()
            self.notify(f"Recording to: {filename}", title="Recording started")

        self._update_status_bar(ts="")

    def action_toggle_log(self) -> None:
        log_panel = self.query_one("#log-panel", RichLog)
        log_panel.display = not log_panel.display

    def action_quit_app(self) -> None:
        if self._recording_sink is not None and self._recording_sink.is_recording():
            self._recording_sink.stop()
        logging.getLogger().removeHandler(self._log_handler)
        self._audio_app.close()
        self.exit()
