# audio-tools — Command Cheat Sheet

## Commands at a Glance

| Command | Standalone alias | What it does |
|---|---|---|
| `audio-tools --devices` | `audio-tools-devices` | List audio input devices |
| `audio-tools --meter` | `audio-tools-meter` | Real-time SPL / LUFS / dBFS meter |
| `audio-tools --meter --tui` | — | Same, with live terminal dashboard |
| `audio-tools --record` | `audio-tools-record` | Calibrated WAV recorder |
| `audio-tools --analyze` | `audio-tools-analyze` | Analyze a WAV file → CSV |
| `audio-tools --batch` | `audio-tools-batch` | Batch-analyze a directory → CSV per file |
| `audio-tools --plot` | `audio-tools-plot` | Plot a metrics CSV |
| `audio-tools --play` | `audio-tools-play` | Headless audio file player |
| `audio-tools --calibrate` | `audio-tools-calibrate` | Generate / verify FIR filter cache |
| `audio-tools --convert` | `audio-tools-convert` | Convert WAV → OGG / MP3 / AAC |
| `audio-tools --enhance` | `audio-tools-enhance` | Voice filter and enhancement |
| `audio-tools-spectrum` | — | Browser-based real-time spectrum analyzer |


## Shared Flags (most commands)

```
-c, --calibration-file FILE   Mic calibration .txt (UMIK-1 / UMIK-2)
    --device-id ID            Audio device ID (see --devices). Default: system default
-b, --buffer-seconds N        Buffer duration in seconds (default: 3 s)
-r, --sample-rate HZ          Sample rate for default device (default: 48000)
-t, --num-taps N              FIR filter taps — accuracy vs CPU (default: 1024)
    --default                 Force system default mic, ignore calibration env var
    --log-file FILE           Write logs to FILE
    --log-append              Append to --log-file instead of overwriting
```



## audio-tools --meter

```bash
# System default mic
audio-tools --meter

# With calibration file
audio-tools --meter -c umik-1/7175488.txt

# Live TUI dashboard
audio-tools --meter --tui -c umik-1/7175488.txt

# Log to file
audio-tools --meter -c umik-1/7175488.txt --log-file meter.log

# Record while metering
audio-tools --meter -c umik-1/7175488.txt --record --output-dir recordings/

# Emit only the loudest measurement per 60 s window
audio-tools --meter -c umik-1/7175488.txt --top-metrics dBSPL_A --top-window 60s

# Append top-metrics to file
audio-tools --meter -c umik-1/7175488.txt \
  --top-metrics dBSPL_A --top-window 60s --top-output log.txt
```

**`--top-metrics` valid keys:** `rms` `flux` `dBFS` `LUFS` `dBSPL` `dBSPL_A`

**`--top-window` format:** `30s` `2m` `1h`



## audio-tools --record

```bash
audio-tools --record -c umik-1/7175488.txt --output-dir recordings/
```



## audio-tools --analyze

```bash
audio-tools --analyze recording.wav -c umik-1/7175488.txt

# Custom window and output path
audio-tools --analyze recording.wav -c umik-1/7175488.txt \
  --window 200 --output-file results.csv

# File was recorded with gain already applied
audio-tools --analyze recording.wav -c umik-1/7175488.txt --gain-applied

# Force a specific start timestamp
audio-tools --analyze recording.wav -c umik-1/7175488.txt \
  --start-time "2025-06-01T08:30:00"
```

**CSV columns:** `time_sec` `timestamp` `rms` `dbfs` `flux` `lufs` `dbspl`¹ `dbspl_a`¹

**Summary output (calibrated):**
```
Peak Level:   -12.40 dBFS      Max SPL:    78.20 dBSPL
Max Loudness: -24.10 LUFS      Max SPL(A): 73.50 dBSPL(A)
Max Flux:      42.30            L_Aeq,T:   69.80 dB(A)
                                L_A90:     61.20 dB(A)
```

¹ Requires `--calibration-file`



## audio-tools --batch

```bash
audio-tools --batch recordings/ -c umik-1/7175488.txt
```

Produces one `*_metrics.csv` per WAV file in the directory.



## audio-tools --plot

```bash
# Show chart
audio-tools --plot results.csv

# Save to PNG
audio-tools --plot results.csv --save

# Choose which metrics to plot
audio-tools --plot results.csv --metrics dbspl dbspl_a lufs
```

**`--metrics` valid values:** `dbfs` `lufs` `dbspl` `dbspl_a` `flux`



## audio-tools --play

```bash
# Play a directory (sorted)
audio-tools-play recordings/

# Play specific files
audio-tools-play a.wav b.flac c.ogg

# Non-interactive (piped / headless)
audio-tools-play recordings/ | tee play.log
```

**Key bindings (interactive / TTY only):**

| Key | Action |
|---|---|
| `Enter` / `Space` | Skip to next |
| `r` / `R` | Replay current |
| `q` / `Q` | Quit |

**Supported formats:** WAV · FLAC · OGG · AIFF · AU



## audio-tools-spectrum

```bash
audio-tools-spectrum --device <id>                      # opens browser at :8767
audio-tools-spectrum --device <id> -c umik-1/7175488.txt
audio-tools-spectrum --device <id> --port 9000 --no-open
```



## audio-tools --calibrate

```bash
# Generate FIR cache (runs once; cached as .npy)
audio-tools --calibrate umik-1/7175488.txt

# Custom taps and sample rate
audio-tools --calibrate umik-1/7175488.txt --num-taps 512 --sample-rate 96000
```



## audio-tools --convert

```bash
audio-tools --convert recordings/ --format ogg
audio-tools --convert session.wav --format ogg mp3
audio-tools --convert recordings/ --format ogg --out converted/ --overwrite
```

**Formats:** `ogg` (smallest) · `mp3` (universal) · `aac` (Apple)



## Distributed / Daemon Mode

All meter flags work with `--producer` / `--consumer`:

```bash
# Producer (high-priority capture, e.g. Raspberry Pi)
sudo nice -n -20 audio-tools --meter --producer \
  -c umik-1/7175488.txt --zmq-port 5555

# Consumer (processing / display, any machine)
audio-tools --meter --consumer --zmq-host 192.168.1.50 --zmq-port 5555

# Consumer with TUI
audio-tools --meter --consumer --zmq-host 192.168.1.50 --zmq-port 5555 --tui
```

**ZMQ defaults:** host `localhost`, port `5555`



## Calibration Auto-Discovery

Place the `.txt` calibration file in one of these locations; `--calibration-file` is then optional:

```
~/.config/audio-tools/     per-user
/etc/audio-tools/          system-wide
```

If multiple files are found, the app prompts interactively. For headless/unattended use, keep exactly one file at the path.



## Environment Variables

```bash
CALIBRATION_FILE=/path/to/calib.txt  # fallback when -c is not passed
```



## Metrics Reference

| Metric | Unit | Calibration | Standard |
|---|---|---|---|
| `dBFS` | dBFS | — | Digital level relative to clipping |
| `LUFS` | LUFS | — | ITU-R BS.1770-4 perceived loudness (K-weighted) |
| `RMS` | linear | — | Effective signal power |
| `Flux` | onset strength | — | Spectral change rate; onset detection |
| `dBSPL` | dBSPL | ✓ | Absolute sound pressure level |
| `dBSPL(A)` | dB(A) | ✓ | A-weighted SPL (IEC 61672) — regulatory standard |
| `L_Aeq,T` | dB(A) | ✓ | Energy-averaged dBSPL(A) over period T |
| `L_A90` | dB(A) | ✓ | Background noise (10th percentile over T) |



## Python Library — AudioMetrics API

```python
from umik_base_app import AudioMetrics

m = AudioMetrics(sample_rate=48000)

# Per-chunk metrics (call each buffer)
m.rms(chunk)                                          # float, linear
m.flux(chunk, sample_rate)                            # float, onset strength
AudioMetrics.dBFS(chunk)                              # float, dBFS
m.lufs(chunk)                                         # float, LUFS
AudioMetrics.dBSPL(dbfs, sensitivity, reference)      # float, dBSPL
m.dBSPL_A(chunk, sensitivity, reference)              # float, dBSPL(A)

# Time-window metrics (collect samples over T, then call once)
AudioMetrics.L_Aeq(samples)   # float, dB(A) — energy average
AudioMetrics.L_A90(samples)   # float, dB(A) — 10th percentile (background)
```

**Typical calibration values (UMIK-1):** `sensitivity = -18.0 dBFS`, `reference = 94.0 dBSPL`



## Makefile Targets

```bash
make install                          # create .venv and install all dependencies
make test                             # run unit tests
make coverage                         # tests with HTML coverage report
make test-integration                 # integration + e2e tests
make lint                             # ruff check
make format                           # ruff format
make spell-check                      # codespell

make real-time-meter-default-mic      # run meter on system mic
make real-time-meter-calibrated F="path/to/calib.txt"
make record-default-mic
make record-calibrated F="path/to/calib.txt"
make get-device-id                    # find UMIK device ID
make calibrate F="path/to/calib.txt" # generate FIR cache
```
