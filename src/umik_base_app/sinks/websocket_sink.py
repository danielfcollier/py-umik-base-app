import asyncio
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from .noise_floor_tracker import NoiseFloorTracker

EPS = 1e-12
logger = logging.getLogger(__name__)


class WebSocketSink:
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
        self._hann_window = np.hanning(chunk_size)
        self._freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)

        self._recording = False
        self._recording_path: Optional[Path] = None
        self._recording_buffer: list[np.ndarray] = []

        self._ws_thread: Optional[threading.Thread] = None

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
        import websockets

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._queue = asyncio.Queue(maxsize=100)

        async def handler(websocket):
            self._clients.add(websocket)
            logger.info(f"Client connected. Total: {len(self._clients)}")
            try:
                async for message in websocket:
                    await self._handle_client_message(message)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self._clients.discard(websocket)
                logger.info(f"Client disconnected. Total: {len(self._clients)}")

        async def broadcaster():
            while True:
                msg = await self._queue.get()
                if self._clients:
                    await asyncio.gather(
                        *[c.send(msg) for c in list(self._clients)],
                        return_exceptions=True,
                    )

        async def main():
            import websockets.server

            async with websockets.server.serve(handler, "0.0.0.0", self._ws_port):
                await broadcaster()

        self._loop.run_until_complete(main())

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
        except Exception as e:
            logger.error(f"Error handling client message: {e}")

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
        chunk = audio_chunk[:self._chunk_size]
        windowed = chunk * self._hann_window[:len(chunk)]
        spec = np.fft.rfft(windowed, n=self._n_fft)
        magnitude_db = 20.0 * np.log10(np.abs(spec) + EPS)

        db_spl = float(np.sqrt(np.mean(audio_chunk**2)))
        if db_spl > 0:
            db_spl = 20.0 * np.log10(db_spl + EPS)

        self._noise_tracker.feed(magnitude_db)

        snr_per_bin = []
        avg_snr = 0.0
        snr_status = "N/A"
        if self._noise_tracker.has_noise_floor:
            snr_per_bin, avg_snr = self._noise_tracker.get_snr(magnitude_db)
            snr_status = NoiseFloorTracker.snr_status(avg_snr)

        msg = json.dumps({
            "type": "fft",
            "data": magnitude_db.tolist(),
            "freqs": self._freqs.tolist(),
            "db_spl": db_spl,
            "snr_avg": avg_snr,
            "snr_status": snr_status,
            "noise_floor": self._noise_tracker.noise_floor_db.tolist() if self._noise_tracker.noise_floor_db is not None else None,
            "capturing": self._noise_tracker.capturing,
        })

        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

        if self._recording:
            self._recording_buffer.append(audio_chunk.copy())
