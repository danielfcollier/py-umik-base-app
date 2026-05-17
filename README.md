# 🎤 audio-tools — Audio Measurement CLI

**A modular Python CLI for real-time audio measurement with USB microphones.**

Supports UMIK-1, UMIK-2, Dayton UMM-6, Earthworks M23/M30, and other USB measurement mics.
Auto-detects known devices, validates sample rate support, and applies per-unit calibration files.

## 📦 Installation

### APT — Linux *(Recommended for Raspberry Pi and Ubuntu)*

```bash
BASE_URL="https://<your-s3-endpoint>/<bucket>/audio-tools"
curl -fsSL "$BASE_URL/pubkey.gpg" | sudo gpg --dearmor -o /usr/share/keyrings/audio-tools.gpg
echo "deb [signed-by=/usr/share/keyrings/audio-tools.gpg] $BASE_URL noble main" \
  | sudo tee /etc/apt/sources.list.d/audio-tools.list
sudo apt-get update && sudo apt-get install audio-tools
```

System dependencies (`libportaudio2`, `libsndfile1`, `ffmpeg`, `libzmq3-dev`) are installed automatically.

> 🍓 **Raspberry Pi 4B verified.** Perfect headless acoustic monitoring box.

### pip

```bash
pip install umik-base-app
```

Requires system libraries:

```bash
# Linux (Debian/Ubuntu)
sudo apt install libportaudio2 libsndfile1 ffmpeg libzmq3-dev -y

# macOS
brew install portaudio libsndfile zeromq ffmpeg
```


## 🕹️ CLI Reference

```
audio-tools --<command> [options]
```

| Command | Description |
|---------|-------------|
| `audio-tools --devices` | 🔍 List available audio input devices |
| `audio-tools --meter` | 📊 Real-time SPL / LUFS / dBFS meter |
| `audio-tools --record` | 🎙️ Calibrated audio recorder (WAV) |
| `audio-tools --calibrate` | 🔧 Generate FIR filter from a calibration file |
| `audio-tools --analyze` | 🔬 Analyze a WAV file and export metrics to CSV |
| `audio-tools --plot` | 📈 Plot a metrics CSV as a chart |
| `audio-tools --batch` | 📁 Batch-analyze a directory of WAV files |
| `audio-tools --enhance` | ✨ Filter and enhance voice audio |
| `audio-tools --convert` | 🔄 Convert WAV recordings to OGG / MP3 / AAC |

Pass `--help` after any command for full options:

```bash
audio-tools --meter --help
audio-tools --convert --help
```

## ⚡ Quick Start

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

## 🏃 Run Modes

### Monolithic *(Default)*

Single process — simplest for desktop and testing.

```bash
audio-tools --meter --calibration-file "umik-1/7175488.txt"
```

### 👹 Daemon Mode — Unstoppable Ear

Run capture at high priority. Processing crashes never interrupt the audio stream.

```bash
# Terminal 1: high-priority capture process
sudo nice -n -20 audio-tools --meter --producer \
  --calibration-file "umik-1/7175488.txt" --zmq-port 5555

# Terminal 2: connect consumer (safe to open/close/crash)
audio-tools --meter --consumer --zmq-host localhost --zmq-port 5555
```

### 🌐 Distributed Mode — Remote Sentry

Capture on a Raspberry Pi, visualize on your laptop.

```bash
# On the Raspberry Pi
audio-tools --meter --producer \
  --calibration-file "umik-1/7175488.txt" --zmq-port 5555

# On your laptop
audio-tools --meter --consumer --zmq-host 192.168.1.50 --zmq-port 5555
```

## 🎛️ Calibration Files

Download the per-unit calibration file for your UMIK from miniDSP. Place it in your project:

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


## 🖥️ Real-Time Dashboard (TUI)

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
│ -24.3  ████████░░░░  │  LUFS   -28.1 LUFS             │
│        ████████░░░░  │  RMS     0.0241                │
│                      │  Flux    38.6                  │
├──────────────────────┴────────────────────────────────┤
│  Mode: MONOLITHIC    SR: 48000 Hz   ● REC   [R] Stop  │
└───────────────────────────────────────────────────────┘
```

| Key | Action |
|-----|--------|
| `R` | 🔴 Toggle recording on/off |
| `Q` | ❌ Quit |

Press **R** to start recording — audio is saved to `recordings/` as a timestamped WAV. Press **R** again to stop; a notification pops with the filename.


## 🔬 Analysis & Visualization

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

## 🔄 Convert Audio

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
| `ogg` | 📱 WhatsApp voice notes (smallest) |
| `mp3` | 🎵 Universal |
| `aac` | 🍎 Apple-friendly (`.m4a`) |


## 🔗 Related Projects

**AI Acoustic Monitor** — adds ML sound classification (chainsaws, glass breaking, birds) on embedded devices, built on this framework:
[py-edge-ai-acoustic-monitoring-app](https://github.com/danielfcollier/py-edge-ai-acoustic-monitoring-app)

## 🛠️ For Developers

Building a custom app on this framework? See [CONTRIBUTING.md](./CONTRIBUTING.md).

Full technical documentation: [docs/](./docs/)
- [Architecture](./docs/ARCHITECTURE.md) — Producer-Consumer design, pipeline internals
- [Audio Metrics](./docs/METRICS.md) — RMS, LUFS, dBFS, dBSPL explained
- [UMIK Series Guide](./docs/UMIK-Series.md) — Hardware-specific details
