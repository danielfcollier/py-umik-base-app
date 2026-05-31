"""
audio-tools-clip: Browser-based WAV trimming UI.

Opens a local aiohttp server on port 8768 and launches a browser with a
waveform editor. Drag the start/end handles, preview the selection with
audio playback, then click Clip to save the result.

Usage:
    audio-tools-clip [INPUT] [--port PORT] [--no-open]

    INPUT may be an audio file (pre-loaded) or a directory (file picker shown).

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import threading
import webbrowser
from pathlib import Path

import aiohttp
from aiohttp import web

from .audio_clip_engine import clip_audio, format_time, load_audio, region_to_wav_bytes, waveform_envelope

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).parent.parent / "web" / "clip"
_AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".au"}


class ClipUIServer:
    """Self-contained aiohttp server that serves the waveform editor UI."""

    def __init__(
        self,
        port: int = 8768,
        initial_file: str | None = None,
        initial_dir: str | None = None,
    ) -> None:
        self._port = port
        self._current_path: str | None = initial_file
        self._initial_dir: str | None = initial_dir
        self._samples = None
        self._sr: int | None = None
        self._subtype: str | None = None
        self._duration: float = 0.0
        self._websockets: set[web.WebSocketResponse] = set()
        self._last_broadcast: dict | None = None  # replayed on reconnection

    # ── File loading ──────────────────────────────────────────────────────────

    def _load_file(self, path: str) -> dict:
        """Load *path* into memory and return the ``file_loaded`` message dict."""
        samples, sr, subtype = load_audio(path)
        n = samples.shape[0] if samples.ndim > 1 else len(samples)
        channels = 1 if samples.ndim == 1 else samples.shape[1]

        self._current_path = path
        self._samples = samples
        self._sr = sr
        self._subtype = subtype
        self._duration = n / sr

        envelope = waveform_envelope(samples)
        logger.info("Loaded %s  (%.2fs, %d Hz, %dch)", Path(path).name, self._duration, sr, channels)

        return {
            "type": "file_loaded",
            "filename": Path(path).name,
            "path": path,
            "duration": round(self._duration, 4),
            "sr": sr,
            "channels": channels,
            "subtype": subtype,
            "waveform": envelope,
        }

    def _list_dir(self, path: str) -> dict:
        """Return a ``file_list`` message for all audio files in *path*, newest first."""
        p = Path(path).resolve()
        files = sorted(
            (f for f in p.iterdir() if f.is_file() and f.suffix.lower() in _AUDIO_EXTENSIONS),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        logger.info("Listed directory %s  (%d file(s))", p, len(files))
        return {
            "type": "file_list",
            "dir": str(p),
            "files": [{"name": f.name, "path": str(f)} for f in files],
        }

    # ── HTTP handlers ─────────────────────────────────────────────────────────

    async def _handle_index(self, _request: web.Request) -> web.FileResponse:
        return web.FileResponse(_WEB_DIR / "index.html")

    async def _handle_js(self, request: web.Request) -> web.FileResponse:
        filename = request.match_info["filename"]
        return web.FileResponse(_WEB_DIR / "js" / filename)

    async def _handle_audio_full(self, _request: web.Request) -> web.Response:
        """Serve the current file as raw WAV bytes for HTML5 Audio playback."""
        if self._current_path is None:
            raise web.HTTPNotFound(text="No file loaded")
        return web.FileResponse(self._current_path)

    async def _handle_audio_region(self, request: web.Request) -> web.Response:
        """Serve a clipped region as WAV bytes for preview playback."""
        if self._samples is None or self._sr is None:
            raise web.HTTPNotFound(text="No file loaded")
        try:
            start = float(request.rel_url.query.get("start", 0))
            end = float(request.rel_url.query.get("end", self._duration))
        except ValueError:
            raise web.HTTPBadRequest(text="start and end must be numbers")

        wav_bytes = region_to_wav_bytes(self._samples, self._sr, self._subtype or "PCM_16", start, end)
        return web.Response(
            body=wav_bytes,
            content_type="audio/wav",
            headers={"Content-Disposition": "inline"},
        )

    # ── WebSocket handler ─────────────────────────────────────────────────────

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._websockets.add(ws)

        try:
            # Send initial state on connect; replay cached message on reconnections
            if self._initial_dir is not None:
                initial_dir, self._initial_dir = self._initial_dir, None  # clear before any await
                try:
                    msg = self._list_dir(initial_dir)
                    self._last_broadcast = msg
                    await ws.send_json(msg)
                except Exception as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
            elif self._current_path is not None:
                try:
                    msg = self._load_file(self._current_path)
                    self._last_broadcast = msg
                    await ws.send_json(msg)
                except Exception as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
            elif self._last_broadcast is not None:
                await ws.send_json(self._last_broadcast)

            async for raw in ws:
                if raw.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(raw.data)
                        await self._dispatch(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_json({"type": "error", "message": "Invalid JSON"})
                elif raw.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break

        except asyncio.CancelledError:
            pass  # clean shutdown (Ctrl+C)
        finally:
            self._websockets.discard(ws)

        return ws

    async def _dispatch(self, ws: web.WebSocketResponse, data: dict) -> None:
        msg_type = data.get("type")

        if msg_type == "load_file":
            path = str(data.get("path", "")).strip()
            if not path:
                await ws.send_json({"type": "error", "message": "No path provided"})
                return
            p = Path(path)
            try:
                if p.is_dir():
                    await self._broadcast(self._list_dir(path))
                else:
                    await self._broadcast(self._load_file(path))
            except Exception as exc:
                await ws.send_json({"type": "error", "message": str(exc)})

        elif msg_type == "list_dir":
            path = str(data.get("path", "")).strip()
            if not path:
                await ws.send_json({"type": "error", "message": "No path provided"})
                return
            try:
                await self._broadcast(self._list_dir(path))
            except Exception as exc:
                await ws.send_json({"type": "error", "message": str(exc)})

        elif msg_type == "clip":
            if self._current_path is None:
                await ws.send_json({"type": "error", "message": "No file loaded"})
                return
            try:
                start = float(data.get("start", 0))
                end = float(data.get("end", self._duration))
                target_sr = int(data["sr"]) if data.get("sr") else None
                output = data.get("output") or None
                output_dir = data.get("output_dir") or None
                if output is None and output_dir:
                    stem = f"{Path(self._current_path).stem}_{format_time(start)}_{format_time(end)}.wav"
                    output = str(Path(output_dir) / stem)
                out_path = clip_audio(self._current_path, start, end, output, target_sr)
                await self._broadcast(
                    {
                        "type": "clip_done",
                        "output": out_path,
                        "duration": round(end - start, 3),
                    }
                )
            except (ValueError, FileNotFoundError, RuntimeError) as exc:
                await ws.send_json({"type": "error", "message": str(exc)})

        else:
            await ws.send_json({"type": "error", "message": f"Unknown message type: {msg_type!r}"})

    async def _broadcast(self, msg: dict) -> None:
        self._last_broadcast = msg
        dead: set[web.WebSocketResponse] = set()
        for ws in list(self._websockets):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.add(ws)
        self._websockets -= dead

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/js/{filename}", self._handle_js)
        app.router.add_get("/audio/full", self._handle_audio_full)
        app.router.add_get("/audio/region", self._handle_audio_region)
        app.router.add_get("/ws", self._handle_ws)
        logger.info("Starting audio-tools-clip server on http://localhost:%d", self._port)
        web.run_app(app, host="localhost", port=self._port, access_log=None, shutdown_timeout=1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="audio-tools-clip",
        description="Browser-based WAV trimming UI. Visualise, preview, and clip.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        metavar="INPUT",
        help="Audio file or directory to open on startup (optional)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8768,
        help="HTTP / WebSocket port",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not launch the browser automatically",
    )
    args = parser.parse_args()

    initial_file: str | None = None
    initial_dir: str | None = None

    if args.input is not None:
        p = Path(args.input)
        if p.is_dir():
            initial_dir = str(p.resolve())
        elif p.is_file():
            initial_file = str(p)
        else:
            print(f"error: Path not found: {args.input}", file=sys.stderr)
            sys.exit(1)

    server = ClipUIServer(port=args.port, initial_file=initial_file, initial_dir=initial_dir)

    if not args.no_open:
        url = f"http://localhost:{args.port}"
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        logger.info("Opening browser: %s", url)

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user.")


if __name__ == "__main__":
    main()
