# CLI Reference — audio-tools

`audio-tools` is the bundled command-line toolkit that ships with the `umik-base-app` package. It is a collection of sample apps that demonstrate the framework; you can build your own CLI apps using the same base classes.

## Commands

```
audio-tools --<command> [options]
```

| Command | Standalone alias | Description |
|---------|-----------------|-------------|
| `audio-tools --devices` | `audio-tools-devices` | List available audio input devices |
| `audio-tools --meter` | `audio-tools-meter` | Real-time SPL / LUFS / dBFS meter |
| `audio-tools --record` | `audio-tools-record` | Calibrated audio recorder (WAV) |
| `audio-tools --calibrate` | `audio-tools-calibrate` | Generate FIR filter from a calibration file |
| `audio-tools --analyze` | `audio-tools-analyze` | Analyze a WAV file and export metrics to CSV |
| `audio-tools --plot` | `audio-tools-plot` | Plot a metrics CSV as a chart |
| `audio-tools --batch` | `audio-tools-batch` | Batch-analyze a directory of WAV files |
| `audio-tools --enhance` | `audio-tools-enhance` | Filter and enhance voice audio |
| `audio-tools --convert` | `audio-tools-convert` | Convert WAV recordings to OGG / MP3 / AAC |
| `audio-tools --play` | `audio-tools-play` | Headless audio file player (WAV / FLAC / OGG / AIFF) |
| `audio-tools --clip` | `audio-clip` | Trim a WAV file to a time range |
| — ¹ | `audio-tools-spectrum` | Browser-based real-time spectrum analyzer (RTA) |
| — ¹ | `audio-tools-clip` | Browser-based waveform clip editor |

¹ These tools launch their own web server and are only available as standalone commands — they are not sub-commands of `audio-tools`.

Pass `--help` after any command for full options:

```bash
audio-tools --meter --help
audio-tools --convert --help
```

## Quick Start

```bash
# 1. Find your microphone's device ID
audio-tools --devices

# 2. Run the SPL meter (system default mic)
audio-tools --meter

# 3. Run with UMIK-1 calibration file
audio-tools --meter --calibration-file "umik-1/7175488.txt"

# 4. Record calibrated audio
audio-tools --record --calibration-file "umik-1/7175488.txt" --output-dir recordings/
```

## Run Modes

### Monolithic *(Default)*

Single process — simplest for desktop and testing.

```bash
audio-tools --meter --calibration-file "umik-1/7175488.txt"
```

### Daemon Mode — Unstoppable Ear

Run capture at high priority. Processing crashes never interrupt the audio stream.

```bash
# Terminal 1: high-priority capture process
sudo nice -n -20 audio-tools --meter --producer \
  --calibration-file "umik-1/7175488.txt" --zmq-port 5555

# Terminal 2: connect consumer (safe to open/close/crash)
audio-tools --meter --consumer --zmq-host localhost --zmq-port 5555
```

### Distributed Mode — Remote Sentry

Capture on a Raspberry Pi, visualize on your laptop.

```bash
# On the Raspberry Pi
audio-tools --meter --producer \
  --calibration-file "umik-1/7175488.txt" --zmq-port 5555

# On your laptop
audio-tools --meter --consumer --zmq-host 192.168.1.50 --zmq-port 5555
```

## Calibration Files

Download the per-unit calibration file for your UMIK from miniDSP.

### Auto-discovery

Place the file in one of these locations and it will be picked up automatically on the next run — no `--calibration-file` flag needed:

| Location | Scope |
|---|---|
| `~/.config/audio-tools/` | Per-user |
| `/etc/audio-tools/` | System-wide |

If multiple files are found, the app prompts you to select one interactively. If a calibrated microphone is detected but no file is found, the app warns you and asks for confirmation before running uncalibrated.

### Sample files (installed with the package)

The `.deb` package ships sample calibration files to `/usr/share/audio-tools/calibration/`. These are reference copies only — to activate one, copy it to an auto-discovery location:

```bash
mkdir -p ~/.config/audio-tools
cp /usr/share/audio-tools/calibration/7175488_90deg.txt ~/.config/audio-tools/
```

### File layout

```
umik-1/
├── 7175488.txt           ← 0° on-axis. Use when pointing at a speaker.
├── 7175488_90deg.txt     ← 90° ambient. Use when pointing at the ceiling.
└── 7175488_fir_*.npy     ← [Generated] FIR filter cache (created on first run).
```

Generate or verify the FIR filter cache:

```bash
audio-tools --calibrate "umik-1/7175488.txt"
```

## Real-Time Dashboard (TUI)

Add `--tui` to get a live terminal dashboard instead of scrolling log output:

```bash
audio-tools --meter --tui
audio-tools --meter --tui --calibration-file "umik-1/7175488.txt"
```

Built with [Textual](https://textual.textualize.io/):

```
┌───────────────────────────────────────────────────────┐
│  audio-tools --meter          Calibration: FULL (FIR) │
├──────────────────────┬────────────────────────────────┤
│  dBFS  ████████░░░░  │  dBSPL   72.4 dB               │
│ -24.3  ████████░░░░  │  dBSPL(A) 69.1 dB(A)          │
│        ████████░░░░  │  LUFS   -28.1 LUFS             │
│                      │  RMS     0.0241                │
│                      │  Flux    38.6                  │
├──────────────────────┴────────────────────────────────┤
│  Mode: MONOLITHIC    SR: 48000 Hz   ● REC   [R] Stop  │
└───────────────────────────────────────────────────────┘
```

| Key | Action |
|-----|--------|
| `R` | Toggle recording on/off |
| `Q` | Quit |

Press **R** to start recording — audio is saved to `recordings/` as a timestamped WAV.

## Spectrum Analyzer (RTA)

<img src="../spectrum-analyzer.png" width="700" alt="Spectrum Analyzer UI">

A browser-based **Real-Time Analyzer (RTA)** for UMIK-1 and compatible USB measurement microphones. Opens a local web server and launches your browser automatically.

This is comparable to the RTA panel in REW (Room EQ Wizard) — useful for real-time acoustic monitoring, speaker alignment, and noise-floor characterization. It does not perform frequency sweeps or generate room correction filters.

### Quick Start

```bash
# 1. Find your microphone's device ID
audio-tools --devices

# 2. Launch (opens browser at http://localhost:8767)
audio-tools-spectrum --device <id>

# 3. With calibration file
audio-tools-spectrum --device <id> --calibration-file "umik-1/7175488.txt"

# 4. Custom port, suppress auto-open
audio-tools-spectrum --device <id> --port 9000 --no-open
```

### Features

| Feature | Description |
|---|---|
| **FFT plot** | 256 log-spaced bins (20 Hz – Nyquist), Hann window, configurable peak labels |
| **Waterfall** | Scrolling spectrogram with time-zoom and time-range CSV export |
| **Time-series graph** | Rolling 30 s dBSPL/dBFS and SNR; y-axis auto-scales on calibration load/clear |
| **Noise floor** | 5-second quiet room baseline; per-bin SNR with OK / LOW / NOISE status |
| **Calibration** | Load a UMIK-1 `.txt` calibration file directly from the browser toolbar |
| **Device selector** | Switch microphone input from the toolbar without restarting |
| **Recording** | WAV recording via the REC button; calibration is applied to the saved file |

> **Calibration note:** When a file is loaded the status bar switches to **dBSPL** and the time graph rescales to 20–120 dB. Switching devices automatically clears the loaded calibration.

## Audio Player

Play back recorded or reference audio files directly from the terminal — no desktop GUI required. Works over SSH.

### Quick Start

```bash
# Play a single file
audio-tools --play recording.wav

# Play all audio files in a directory (sorted by name)
audio-tools --play recordings/

# Play a specific list of files
audio-tools --play file1.wav file2.flac session/ambient.ogg
```

### Key Bindings

| Key | Action |
|-----|--------|
| `Enter` or `Space` | Skip to next file |
| `r` | Replay the current file from the start |
| `q` | Quit the player |

When the current file finishes playing it advances to the next automatically.

### Display

```
──────────────────────────────────────────────────────────
  [2/5]  recording_2025-05-26_14-32-01.wav
  1:45  ·  48000 Hz  ·  mono
  [Enter/Space] next   [r] replay   [q] quit

  ████████████░░░░░░░░░░░░░░░░░░  0:48 / 1:45
```

### Supported Formats

| Format | Notes |
|--------|-------|
| WAV | Primary format; recorded by `--record` |
| FLAC | Lossless; full quality |
| OGG | Vorbis; produced by `--convert` |
| AIFF / AU | Standard interchange formats |

Non-interactive mode (piped stdin) plays all files straight through without waiting for keystrokes.

## Audio Clip Editor

Trim a WAV recording to a specific time range. Two interfaces share the same engine:
`audio-clip` for scripting and `audio-tools-clip` for interactive visual editing.

### CLI — `audio-clip`

```
audio-clip INPUT [--start S] [--end E | --duration D] [--output PATH] [--sr RATE]
```

```bash
# Trim seconds 4–7 → recordings/clips/bark_4s_7s.wav
audio-clip recordings/bark.wav --start 4 --end 7

# Trim by duration instead of end time
audio-clip recordings/bark.wav --start 4 --duration 3

# Trim and resample output to 22 050 Hz
audio-clip recordings/bark.wav --start 4 --end 7 --sr 22050

# Explicit output path
audio-clip recordings/bark.wav --start 4 --end 7 --output dataset/bark_clean.wav
```

| Argument | Default | Description |
|----------|---------|-------------|
| `INPUT` | — | Source WAV file path |
| `--start` / `-s` | `0.0` | Clip start in seconds |
| `--end` / `-e` | end of file | Clip end in seconds (mutually exclusive with `--duration`) |
| `--duration` / `-d` | — | Clip length in seconds; sets `end = start + duration` |
| `--output` / `-o` | `<input_dir>/clips/<stem>_<start>s_<end>s.wav` | Output path |
| `--sr` | preserve source | Resample output to this rate |

**Output naming convention** — when no `--output` is given, integer seconds are formatted as `4s` and fractional as `4.5s`, making provenance obvious at a glance:

```
recordings/clips/bark_4s_7s.wav
recordings/clips/bark_4.5s_7.2s.wav
```

**Success output:**

```
✂️   Clipped 3.0s → recordings/clips/bark_4s_7s.wav  (48000 Hz, mono)
```

### Browser UI — `audio-tools-clip`

Opens a local web server at `http://localhost:8768` with a waveform editor:

```bash
# Pre-load a file (browser opens automatically)
audio-tools-clip recordings/bark.wav

# Custom port, suppress auto-open
audio-tools-clip recordings/bark.wav --port 9000 --no-open
```

```
┌──────────────────────────────────────────────────────────────────┐
│  ✂ audio-tools-clip    📂 [recordings/bark.wav]  [Open]         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ████▓▓▒▒░░░░░░░░░░▓▓▓▓▓▓▒▒░░░░░░░░░░░░░░░░░░░░░░░░░░          │
│  ↑ start                                  end ↑                 │
│  0s ─────────────────────────────────── 42.3s                   │
│                                                                  │
│  Start: [  4.0  ]s   End: [  7.0  ]s   Duration: 3.0s          │
│  [▶ Preview]   [✂ Clip]   Output: recordings/clips/bark_4s_7s.wav│
└──────────────────────────────────────────────────────────────────┘
```

| Interaction | Action |
|-------------|--------|
| Drag green handle | Move start point |
| Drag red handle | Move end point |
| Edit Start / End fields | Sync handles to typed values |
| **Space** | Preview selected region (audio playback) |
| **Enter** | Clip and save |
| Path input → **Open** | Load a different file without restarting |

> Files opened in the browser are loaded by **server-side path** — the path you type is resolved on the machine running `audio-tools-clip`. This is a local tool; both client and server are on the same machine.

## Analysis & Visualization

```bash
# Analyze one file → CSV
audio-tools --analyze "recording.wav" --calibration-file "umik-1/7175488.txt"

# Batch analyze a directory → CSV per file
audio-tools --batch recordings/ --calibration-file "umik-1/7175488.txt"

# View chart (popup window)
audio-tools --plot "recording_metrics.csv"

# Save chart to PNG
audio-tools --plot "recording_metrics.csv" --save
```

### CSV columns

| Column | Unit | Description |
|--------|------|-------------|
| `time_sec` | s | Elapsed time at end of chunk |
| `timestamp` | ISO 8601 | Wall-clock time (if derivable from filename or `--start-time`) |
| `rms` | — | Linear RMS amplitude (0–1) |
| `dbfs` | dBFS | Broadband digital level relative to full scale |
| `flux` | — | Peak spectral flux (onset strength) |
| `lufs` | LUFS | Integrated perceived loudness (ITU-R BS.1770-4) |
| `dbspl` | dBSPL | Calibrated broadband sound pressure level |
| `dbspl_a` | dB(A) | A-weighted calibrated SPL (IEC 61672, regulatory standard) |

### Analysis summary

After `--analyze` completes, a summary is printed to the terminal:

```
========================================
📈 ANALYSIS SUMMARY
========================================
Peak Level:    -12.30 dBFS
Max Loudness:  -18.40 LUFS
Max Flux:       62.10
Max SPL:        87.30 dBSPL
Max SPL(A):     84.20 dBSPL(A)
L_Aeq,T:        76.50 dB(A)
L_A90:          61.30 dB(A)
========================================
```

`L_Aeq,T` is the energy-averaged A-weighted level over the full file — the primary metric for noise regulations (OSHA, EU Directive 2002/49/EC, ABNT NBR 10151). `L_A90` is the background noise floor (10th percentile of the dBSPL(A) distribution).

## Convert Audio

Convert WAV recordings to share-friendly formats. Requires `ffmpeg`.

```bash
# OGG/Opus — smallest, WhatsApp-compatible
audio-tools --convert recordings/ --format ogg

# Multiple formats in one pass
audio-tools --convert recordings/session.wav --format ogg mp3

# Output to a different directory
audio-tools --convert recordings/ --format ogg --out converted/

# Overwrite existing files
audio-tools --convert recordings/ --format ogg --overwrite
```

| Format | Use Case |
|--------|----------|
| `ogg` | WhatsApp voice notes (smallest) |
| `mp3` | Universal |
| `aac` | Apple-friendly (`.m4a`) |

## Linux Package (APT)

For headless Raspberry Pi and Ubuntu deployments, a `.deb` package is available that installs system dependencies automatically:

```bash
curl -fsSL "https://br-se1.magaluobjects.com/audio-tools/audio-tools/pubkey.gpg" \
  | sudo gpg --dearmor -o /usr/share/keyrings/audio-tools.gpg
echo "deb [signed-by=/usr/share/keyrings/audio-tools.gpg] https://br-se1.magaluobjects.com/audio-tools/audio-tools $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/audio-tools.list
sudo apt-get update && sudo apt-get install audio-tools
```

Installs `libportaudio2`, `libsndfile1`, `ffmpeg`, and `libzmq3-dev` automatically.

> Raspberry Pi 4B verified. Suitable for headless acoustic monitoring.
