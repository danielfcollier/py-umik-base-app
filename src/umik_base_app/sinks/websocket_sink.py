import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from .noise_floor_tracker import NoiseFloorTracker

EPS = 1e-12
logger = logging.getLogger(__name__)


class WebSocketSink:
    FPS = 20

    def __init__(
        self,
        sample_rate: float = 48000.0,
        chunk_size: int = 1024,
        n_fft: int = 2048,
        ws_port: int = 8767,
        noise_tracker: Optional[NoiseFloorTracker] = None,
    ):
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._n_fft = n_fft
        self._ws_port = ws_port
        self._noise_tracker = noise_tracker or NoiseFloorTracker(
            sample_rate=sample_rate, chunk_size=chunk_size
        )

        self._clients: set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue] = None
        self._hann_window = np.hanning(n_fft)
        self._freqs_raw = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
        self._bin_freqs, self._bin_indices = self._build_log_bins(
            self._freqs_raw, n_bins=256, f_min=20.0, f_max=sample_rate / 2.0
        )
        self._freqs = self._bin_freqs

        self._audio_lock = threading.Lock()
        self._latest_audio: Optional[np.ndarray] = None
        self._audio_offset = 0
        self._hop = n_fft // 2

        self._recording = False
        self._recording_path: Optional[Path] = None
        self._recording_buffer: list[np.ndarray] = []

        self._ws_thread: Optional[threading.Thread] = None

    @staticmethod
    def _build_log_bins(freqs: np.ndarray, n_bins: int = 256, f_min: float = 20.0, f_max: float = 20000.0):
        log_edges = np.logspace(np.log10(f_min), np.log10(f_max), n_bins + 1)
        bin_freqs = np.sqrt(log_edges[:-1] * log_edges[1:])
        bin_indices = []
        for i in range(n_bins):
            lo, hi = log_edges[i], log_edges[i + 1]
            mask = (freqs >= lo) & (freqs < hi)
            indices = np.where(mask)[0]
            if len(indices) == 0:
                center = (lo + hi) / 2.0
                idx = int(np.argmin(np.abs(freqs - center)))
                indices = np.array([idx])
            bin_indices.append(indices)
        return bin_freqs, bin_indices

    def _bin_spectrum(self, magnitude_db: np.ndarray) -> np.ndarray:
        binned = np.empty(len(self._bin_indices))
        for i, indices in enumerate(self._bin_indices):
            binned[i] = np.mean(magnitude_db[indices])
        return binned

    @property
    def port(self) -> int:
        return self._ws_port

    @property
    def noise_tracker(self) -> NoiseFloorTracker:
        return self._noise_tracker

    def start(self):
        self._ws_thread = threading.Thread(target=self._run_ws_server, daemon=True)
        self._ws_thread.start()
        logger.info(f"WebSocketSink server thread started on port {self._ws_port}")

    def _run_ws_server(self):
        from aiohttp import web

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._queue = asyncio.Queue(maxsize=200)

        web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")

        async def ws_handler(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            self._clients.add(ws)
            logger.info(f"Client connected. Total: {len(self._clients)}")
            try:
                async for msg in ws:
                    if msg.type == 1:
                        await self._handle_client_message(msg.data)
            except Exception:
                pass
            finally:
                self._clients.discard(ws)
                logger.info(f"Client disconnected. Total: {len(self._clients)}")
            return ws

        async def index_handler(request):
            return web.FileResponse(os.path.join(web_dir, "index.html"))

        async def broadcaster():
            while True:
                msg = await self._queue.get()
                if self._clients:
                    closed = set()
                    for ws in list(self._clients):
                        try:
                            await ws.send_str(msg)
                        except Exception:
                            closed.add(ws)
                    self._clients -= closed

        async def fft_tick():
            interval = 1.0 / self.FPS
            while True:
                await asyncio.sleep(interval)
                frame = self._consume_next_frame()
                if frame is None:
                    continue
                self._process_and_broadcast(frame)

        @web.middleware
        async def no_cache(request, handler):
            resp = await handler(request)
            if request.path.startswith("/css/") or request.path.startswith("/js/") or request.path == "/":
                resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                resp.headers["Pragma"] = "no-cache"
                resp.headers["Expires"] = "0"
            return resp

        app = web.Application(middlewares=[no_cache])
        app.router.add_get("/ws", ws_handler)
        app.router.add_get("/", index_handler)
        app.router.add_static("/css", os.path.join(web_dir, "css"))
        app.router.add_static("/js", os.path.join(web_dir, "js"))

        async def on_startup(app):
            app["broadcaster_task"] = asyncio.ensure_future(broadcaster())
            app["fft_tick_task"] = asyncio.ensure_future(fft_tick())

        app.on_startup.append(on_startup)

        runner = web.AppRunner(app)
        self._loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, "0.0.0.0", self._ws_port)
        self._loop.run_until_complete(site.start())
        self._loop.run_forever()

    def _consume_next_frame(self) -> Optional[np.ndarray]:
        with self._audio_lock:
            if self._latest_audio is None:
                return None
            audio = self._latest_audio
            start = self._audio_offset * self._hop
            if start + self._n_fft > len(audio):
                self._latest_audio = None
                return None
            frame = audio[start : start + self._n_fft].copy()
            self._audio_offset += 1
            return frame

    def _process_and_broadcast(self, frame: np.ndarray):
        windowed = frame * self._hann_window
        spec = np.fft.rfft(windowed)
        magnitude_db_raw = 20.0 * np.log10(np.abs(spec) + EPS)
        magnitude_db = self._bin_spectrum(magnitude_db_raw)

        self._noise_tracker.feed(magnitude_db_raw)

        db_spl = float(np.sqrt(np.mean(frame**2)))
        if db_spl > 0:
            db_spl = 20.0 * np.log10(db_spl + EPS)

        avg_snr = 0.0
        snr_status = "N/A"
        noise_floor_binned = None
        if self._noise_tracker.has_noise_floor:
            snr_raw, avg_snr = self._noise_tracker.get_snr(magnitude_db_raw)
            snr_status = NoiseFloorTracker.snr_status(avg_snr)
            noise_floor_binned = self._bin_spectrum(self._noise_tracker.noise_floor_db).tolist()

        msg = json.dumps({
            "type": "fft",
            "data": magnitude_db.tolist(),
            "freqs": self._freqs.tolist(),
            "db_spl": db_spl,
            "snr_avg": avg_snr,
            "snr_status": snr_status,
            "noise_floor": noise_floor_binned,
            "capturing": self._noise_tracker.capturing,
        })

        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

    async def _handle_client_message(self, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "capture_quiet_room":
                self._noise_tracker.start_capture()
            elif msg_type == "start_recording":
                self._recording = True
                self._recording_buffer = []
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                self._recording_path = Path("recordings") / f"{ts}.wav"
                self._recording_path.parent.mkdir(parents=True, exist_ok=True)
            elif msg_type == "stop_recording":
                await self._stop_recording()
            elif msg_type == "export_csv":
                self._export_csv()
            elif msg_type == "load_calibration":
                await self._handle_load_calibration(data.get("content", ""))
        except Exception as e:
            logger.error(f"Error handling client message: {e}")

    async def _handle_load_calibration(self, content: str):
        from umik_base_app.apps.spectrum_analyzer import SpectrumAnalyzerApp

        app = SpectrumAnalyzerApp._instance
        if app is None:
            logger.error("SpectrumAnalyzerApp instance not found")
            return
        success = app.load_calibration(content)
        await self._broadcast(json.dumps({"type": "calibration_loaded", "success": success}))

    async def _stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        if self._recording_buffer and self._recording_path:
            import soundfile as sf

            audio = np.concatenate(self._recording_buffer)
            sf.write(str(self._recording_path), audio, int(self._sample_rate))
            logger.info(f"Recording saved: {self._recording_path}")
            self._recording_buffer = []
            await self._broadcast(json.dumps({
                "type": "recording_stopped",
                "path": str(self._recording_path),
            }))

    def _export_csv(self):
        if self._noise_tracker.noise_floor_db is None:
            return
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = Path("exports") / f"{ts}_spectrum.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write("frequency_hz,noise_floor_db\n")
            for freq, db in zip(self._freqs, self._noise_tracker.noise_floor_db):
                f.write(f"{freq:.1f},{db:.2f}\n")
        logger.info(f"CSV exported: {path}")

    async def _broadcast(self, msg: str):
        if self._queue is not None:
            await self._queue.put(msg)

    def handle_audio(self, audio_chunk: np.ndarray, timestamp: datetime) -> None:
        if self._recording:
            self._recording_buffer.append(audio_chunk.copy())

        audio = audio_chunk.flatten()
        with self._audio_lock:
            self._latest_audio = audio
            self._audio_offset = 0
