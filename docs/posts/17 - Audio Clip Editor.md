# ✂️ Building a Browser-Based WAV Clip Editor in Python

The acoustic monitoring app does its job: it captures every bark, alarm, and ambient noise event to a timestamped WAV file. A 45-second recording for a single dog bark. A 30-second file for a car horn. The event itself is three seconds long.

Before those recordings become useful training data for an MFCC classifier, someone has to trim them. The wrong way is to write `--start` and `--end` values blindly. The right way is to *see* the waveform, listen to the candidate region, and confirm the cut with your ears before saving.

That's what `audio-tools-clip` is for.

## 🧠 Two Tools, One Engine

The design is deliberately split:

```
audio_clip_engine.py  ← shared core
      ↑           ↑
audio_clip.py     audio_clip_ui.py
(CLI, scripting)  (browser, interactive)
```

**`audio-clip`** is a pure command-line tool — no server, no browser, no overhead. Perfect for automation: a shell script that iterates over a label file and trims each annotated segment in one pass.

**`audio-tools-clip`** wraps the same engine in an `aiohttp` web server and opens a browser UI. You drag handles, press Space to preview, and press Enter to save.

Both produce identical output files. The engine is tested independently of either interface.

## 🔧 The Clip Engine

The engine is five functions. Nothing else needs to exist.

```python
def clip_audio(input_path, start, end=None, output_path=None, target_sr=None) -> str:
    samples, sr, subtype = load_audio(input_path)
    duration = len(samples) / sr
    if end is None:
        end = duration
    validate_range(start, end, duration)          # raises ValueError
    chunk = samples[int(start * sr):int(end * sr)]
    if target_sr and target_sr != sr:
        chunk = _resample(chunk, sr, target_sr)   # librosa, mono or stereo
    out = output_path or default_output_path(input_path, start, end)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, chunk, sr, subtype=_safe_subtype(subtype))
    return out
```

Two design choices worth explaining:

**`soundfile` over `librosa.load`** — librosa always decodes to `float32` and loses the original bit depth. `soundfile.read()` gives you the raw samples in `float64 [-1, 1]` while preserving the subtype (`PCM_16`, `PCM_24`, `FLOAT`, etc.) for lossless round-trips.

**Output naming** — `default_output_path` formats integer seconds as `4s` and fractional as `4.5s`. The result (`bark_4s_7s.wav`) makes provenance obvious at a glance and avoids collisions when multiple clips come from the same source file.

```python
def format_time(t: float) -> str:
    return f"{int(t)}s" if t == int(t) else f"{t:.1f}s"
```

## 🖥️ The Server (Simpler Than You Think)

The spectrum analyzer needs an audio pipeline: a `ListenerThread`, a `ConsumerThread`, a ZMQ transport, and a `WebSocketSink` running its own asyncio event loop in a background thread. All that machinery is necessary because live microphone capture has strict timing requirements.

The clip editor has none of those requirements. It reads a file once. All subsequent HTTP and WebSocket requests are fast lookups into a buffer that's already in RAM. So the server is a plain `aiohttp` application with five routes:

```python
app.router.add_get("/",               handle_index)     # → index.html
app.router.add_get("/js/{filename}",  handle_js)        # → waveform.js, clip_app.js
app.router.add_get("/audio/full",     handle_audio_full)    # → FileResponse(current_path)
app.router.add_get("/audio/region",   handle_audio_region)  # → WAV bytes for preview
app.router.add_get("/ws",             handle_ws)        # → WebSocket data channel
```

No background threads. No asyncio gymnastics. `web.run_app()` blocks the process and handles Ctrl+C.

## 📡 The WebSocket Protocol

Three messages in each direction cover the full workflow:

**Client → Server:**

```json
{ "type": "load_file", "path": "recordings/2025-10-14_bark.wav" }
{ "type": "clip", "start": 4.0, "end": 7.0, "output": null, "sr": null }
```

**Server → Client:**

```json
{ "type": "file_loaded", "filename": "bark.wav", "duration": 42.3,
  "sr": 48000, "channels": 1, "subtype": "PCM_24",
  "waveform": [{"min": -0.12, "max": 0.45}, ...] }

{ "type": "clip_done", "output": "recordings/clips/bark_4s_7s.wav", "duration": 3.0 }

{ "type": "error", "message": "start (8.0s) must be less than end (4.0s)" }
```

When a new client connects via WebSocket and a file is already loaded, the server immediately sends `file_loaded` so the browser renders the waveform without any user action — even if the file was specified as a CLI argument.

## 🌊 Waveform Display: The Envelope Trick

A 45-second WAV at 48 kHz is 2.16 million samples. Sending all of them to the browser would be wasteful and slow. The solution is a **min/max envelope**: split the samples into N blocks, compute the minimum and maximum of each block, and send only those 2N numbers.

```python
def waveform_envelope(samples, n_points=4_000):
    mono = samples if samples.ndim == 1 else samples.mean(axis=1)
    block_size = max(1, len(mono) // n_points)
    trim = (len(mono) // block_size) * block_size
    blocks = mono[:trim].reshape(-1, block_size)
    return [{"min": float(mn), "max": float(mx)}
            for mn, mx in zip(blocks.min(axis=1), blocks.max(axis=1))]
```

4 000 points renders a waveform that looks indistinguishable from the real thing — the min/max envelope captures every transient peak — while transmitting less than 64 KB of JSON.

The browser renders this with a Canvas `fillRect` per block: each block becomes a vertical bar from `min` to `max`, mapped from the `[-1, 1]` sample range to pixel coordinates.

## 🎧 Audio Preview: Fetch → Blob → Audio

The most satisfying feature: press Space to hear the selected region before committing the cut.

The implementation avoids the Web Audio API entirely. When the user hits Preview:

1. The browser calls `GET /audio/region?start=4&end=7`
2. The server clips the in-memory buffer and writes it to a `BytesIO` as WAV bytes
3. The browser receives the response, creates a `Blob URL`, and hands it to `new Audio()`

```javascript
fetch(`/audio/region?start=${start}&end=${end}`)
  .then(r => r.blob())
  .then(blob => {
    const url = URL.createObjectURL(blob);
    new Audio(url).play();
  });
```

No streaming. No Web Audio `AudioContext`. No codec negotiation. WAV bytes in, audio out.

## 🐾 The Training Data Workflow

The companion app `py-edge-ai-acoustic-monitoring-app` stores recordings in `recordings/` and labels them with a `.neighbor_dog_labels.json` file. The standard workflow after a long monitoring session:

```bash
# 1. Review the 45-second bark recording visually
audio-tools-clip recordings/2025-10-14_bark.wav
# → drag handles to 4s–7s, press Space to confirm → press Enter

# 2. The clip appears at the conventional path
ls recordings/clips/
# 2025-10-14_bark_4s_7s.wav

# 3. Label the clip as 'neighbor-dog' in the label file
# 4. Relabel the original 45s recording as 'mixed' (has bark but too noisy)
```

The `clips/<stem>_<start>s_<end>s.wav` path convention is intentional: it shows both origin and time range, making the label file human-readable.

For batch processing — trimming dozens of pre-annotated recordings — the CLI is faster:

```bash
# Trim all clips defined in a JSON label file
jq -r '.[] | "\(.file) \(.start) \(.end)"' labels.json | while read f s e; do
    audio-clip "recordings/$f" --start "$s" --end "$e"
done
```

## 🔮 What's Next

The clip editor is a data curation tool, not a measurement tool. The natural next step is closing the loop: after trimming and labelling a batch of events, feed the clips directly into the MFCC pipeline — feature extraction, classifier training, and deployment back onto the Raspberry Pi that captured them. That's the arc from sensor to model, completed in Python.

👉 **Try it:** [github.com/danielfcollier/py-umik-base-app](https://github.com/danielfcollier/py-umik-base-app)

#Python #AudioEngineering #MachineLearning #DSP #WebSockets #TrainingData #AcousticMonitoring #aiohttp #OpenSource
