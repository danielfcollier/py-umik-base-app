# Building on the Framework

`umik-base-app` is a Python library for building real-time audio measurement applications. `AudioBaseApp` handles threading, hardware reconnection, ZMQ transport, and calibration injection — you write the signal processing logic.

## Installation

```bash
pip install umik-base-app
```

System dependencies:

```bash
# Linux (Debian/Ubuntu)
sudo apt install libportaudio2 libsndfile1 ffmpeg libzmq3-dev -y

# macOS
brew install portaudio libsndfile zeromq ffmpeg
```

## Public API

```python
from umik_base_app import (
    AppArgs,          # CLI argument parser and validator
    AppConfig,        # Validated runtime configuration
    AudioBaseApp,     # Main app class — manages threads, transport, lifecycle
    AudioMetrics,     # Static helpers: dBFS, dBSPL, RMS, LUFS, flux
    AudioPipeline,    # Ordered transformer + fan-out sink chain
    AudioSink,        # Protocol: implement handle(ctx) to consume audio
    AudioTransformer, # Protocol: implement apply(ctx) to modify audio
    CalibrationConfig,
    HardwareConfig,
    OperationalMode,
    PipelineContext,  # Per-chunk envelope passed to every transformer and sink
    QueueInMemoryTransport,
    ZmqConsumerTransport,
    ZmqProducerTransport,
)
```

## Minimal Example

```python
from umik_base_app import AppArgs, AudioBaseApp, AudioPipeline, AudioSink, PipelineContext

class LoudnessPrinter(AudioSink):
    def handle(self, ctx: PipelineContext) -> None:
        if ctx.can_calculate_dbspl():
            print(f"[{ctx.timestamp}] dBSPL: {ctx.reference_dbspl:.1f}")

def main():
    args = AppArgs.get_args()
    config = AppArgs.validate_args(args)

    pipeline = AudioPipeline(sample_rate=config.sample_rate)
    pipeline.add_sink(LoudnessPrinter())

    # If --calibration-file was passed, CalibratorAdapter is auto-injected
    app = AudioBaseApp(app_config=config, pipeline=pipeline)
    app.run()

if __name__ == "__main__":
    main()
```

Run it with any `audio-tools` flags:

```bash
python my_app.py --calibration-file "umik-1/7175488.txt"
python my_app.py --producer --zmq-port 5555
```

## PipelineContext

Every audio chunk is delivered to transformers and sinks wrapped in a `PipelineContext`:

| Property | Type | Description |
|----------|------|-------------|
| `ctx.audio` | `np.ndarray` | Audio samples for this buffer |
| `ctx.timestamp` | `datetime` | Capture time |
| `ctx.sample_rate` | `float` | Sample rate in Hz |
| `ctx.gain_applied` | `bool` | Sensitivity gain was applied by `CalibratorAdapter` |
| `ctx.fir_applied` | `bool` | FIR filter was applied by `CalibratorAdapter` |
| `ctx.sensitivity_dbfs` | `float \| None` | Mic sensitivity (set when calibration file is loaded) |
| `ctx.reference_dbspl` | `float \| None` | Reference SPL (typically 94 dBSPL) |
| `ctx.is_gain_calibrated()` | `bool` | `gain_applied` and sensitivity metadata are present |
| `ctx.is_fully_calibrated()` | `bool` | Both gain and FIR applied |
| `ctx.can_calculate_dbspl()` | `bool` | `sensitivity_dbfs` and `reference_dbspl` are set |

## dBSPL Calculation

`CalibratorAdapter` applies the sensitivity gain to `ctx.audio` before any sink sees it. Calling `AudioMetrics.dBSPL()` on already-gained audio double-counts the sensitivity offset (~18.5 dB error). Use the correct branch based on calibration state:

```python
class MetricsSink(AudioSink):
    def handle(self, ctx: PipelineContext) -> None:
        dbfs = AudioMetrics.dBFS(ctx.audio)

        if ctx.is_gain_calibrated():
            # Gain already applied to ctx.audio — do NOT call AudioMetrics.dBSPL()
            dbspl = dbfs + ctx.reference_dbspl
        elif ctx.can_calculate_dbspl():
            # Raw audio — apply the full sensitivity offset
            dbspl = AudioMetrics.dBSPL(dbfs, ctx.sensitivity_dbfs, ctx.reference_dbspl)
        else:
            dbspl = None
```

## Calibration Architecture

`CalibratorAdapter` wraps two transformers in sequence:

| Transformer | Purpose | CPU Cost | When to Use |
|-------------|---------|----------|-------------|
| `GainTransformer` | Sensitivity correction (level) | O(n) | Real-time meters |
| `FirCorrectionTransformer` | Frequency response correction | O(n × taps) | Precision recording / analysis |

Use **gain-only** for real-time applications where CPU matters. Use **full calibration** (gain + FIR) when frequency accuracy is critical.

FIR taps trade-off:

| `num_taps` | Accuracy | CPU |
|------------|----------|-----|
| 1024 (default) | High | Higher |
| 512 / 256 | Reduced below 250 Hz | Lower |

## Custom Transformer

Implement `AudioTransformer` to modify the audio signal before sinks receive it:

```python
from umik_base_app import AudioTransformer, PipelineContext
import numpy as np

class NormalizeTransformer(AudioTransformer):
    def apply(self, ctx: PipelineContext) -> PipelineContext:
        peak = np.max(np.abs(ctx.audio))
        if peak > 0:
            ctx.audio = ctx.audio / peak
        return ctx
```

Add it to the pipeline before your sinks:

```python
pipeline = AudioPipeline(sample_rate=config.sample_rate)
pipeline.add_transformer(NormalizeTransformer())
pipeline.add_sink(MyAnalysisSink())
```

## Adding a New App / CLI Command

1. Create your `main()` in `src/umik_base_app/apps/` or `src/scripts/`.
2. Register the entry point in `pyproject.toml` under `[project.scripts]`.
3. Add the flag to `_DISPATCH` and `_HELP` in `src/umik_base_app/cli.py`.
4. Add a `make` target in `Makefile` under the appropriate section.

## Supported Hardware

| Microphone | Manufacturer | Sample Rates | Sensitivity |
|------------|--------------|--------------|-------------|
| UMIK-1 | miniDSP | 48 kHz | −18 dBFS |
| UMIK-2 | miniDSP | 44.1–192 kHz | −18 dBFS |
| UMM-6 | Dayton Audio | 48 kHz | −18 dBFS |
| XREF 20 | Sonarworks | 48 kHz | −26 dBFS |
| MM 1 | Beyerdynamic | 44.1–192 kHz | −40 dBFS |
| M23/M30 | Earthworks | 44.1–192 kHz | −36 dBFS |

To add a custom microphone profile, see `src/umik_base_app/hardwares/device_profiles.py`.

## Further Reading

- [Architecture](./ARCHITECTURE.md) — Producer-Consumer design, transport layer, pipeline internals
- [Audio Metrics](./METRICS.md) — RMS, LUFS, dBFS, dBSPL formulas explained
- [UMIK Series Guide](./UMIK-Series.md) — Hardware-specific calibration details
