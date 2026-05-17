# Contributing to the Audio Measurement Framework

Thank you for your interest in contributing! I welcome contributions to help improve this audio analysis framework.

This guide will help you set up your development environment and understand the workflows.

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your system:

* **Python 3.9+**: [Download Python](https://www.python.org/downloads/)
* **uv**: An extremely fast Python package installer and resolver.
    * [Installation Guide for uv](https://github.com/astral-sh/uv) (e.g., `curl -LsSf https://astral.sh/uv/install.sh | sh`)
* **Make**: Standard build tool (usually pre-installed on Linux/macOS).

## 🚀 Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/danielfcollier/py-umik-base-app.git
    cd py-umik-base-app
    ```

2.  **Install dependencies:**
    It's used `uv` to manage the virtual environment and dependencies efficiently. The `make install` command handles everything for you (syncing both production and development dependencies).
    ```bash
    make install
    ```
    *This creates a virtual environment in `.venv/`.*

3.  **Activate the environment:**
    ```bash
    source .venv/bin/activate
    ```

## 💻 Development Workflow

Use a `Makefile` to streamline common development tasks.

### Code Quality & Linting
Enforce strict code quality standards using **Ruff** (for linting and formatting) and **MyPy** (for static type checking).

* **Run Linter:** Checks for style violations and potential errors.
    ```bash
    make lint
    ```
* **Format Code:** Automatically fixes formatting issues.
    ```bash
    make format
    ```
* **Spell Check:** Checks for spelling errors in code and documentation.
    ```bash
    make spell-check
    ```

### Testing
Use `pytest` for unit testing and our custom shell script for end-to-end integration testing.

* **Run Unit Tests:**
    ```bash
    make test
    ```
* **Run Tests with Coverage Report:**
    This generates a coverage report to help identify untested code paths.
    ```bash
    make coverage
    ```
* **Run Integration Tests:**
    Verifies the entire application pipeline (CLI entry points, audio capture simulation, and file outputs) to ensure the system works as a whole.
    ```bash
    make test-integration
    ```

### Running the Basic Applications
You can run the built-in applications directly using `make` targets.

* **Real Time Meter:** Runs the real-time real time meter app.
    ```bash
    # Run with default settings (uses default mic)
    make real-time-meter-default-mic
    
    # Run specifically with a UMIK-1 (requires calibration file path in F variable)
    make real-time-meter-umik F="path/to/calib.txt"
    ```

* **Audio Recorder:** Runs the recording utility.
    ```bash
    # Record with default mic
    make record-default-mic
    
    # Record with UMIK-1 (requires calibration file)
    make record-umik F="path/to/calib.txt"
    ```

*(Note: Use `make help` to see all available commands).*

## 🏗️ Project Structure & Standards

* **Strict Typing:** Enforce static typing throughout the codebase using `mypy`. Please ensure all new functions and classes have type hints.
* **Formatting:** All code must be formatted with `ruff`. The CI pipeline will fail if code is not properly formatted.
* **CI Pipeline:** Every Pull Request runs the `make lint`, `make coverage`, `make spell-check`, and `make test-integration` targets via GitHub Actions. Ensure these pass locally before submitting your PR.

## 📝 Submitting a Pull Request

1.  Create a new branch for your feature or fix (`git checkout -b feature/my-new-feature`).
2.  Commit your changes (`git commit -am 'Add some feature'`).
3.  Push to the branch (`git push origin feature/my-new-feature`).
4.  Open a Pull Request against the `main` branch.

Happy Coding! 🎧

## Building on the Framework

`audio-tools` is installable as a Python library (`umik-base-app`) for building custom audio applications. `AudioBaseApp` handles threading, hardware reconnection, ZMQ transport, and calibration injection — you write the logic.

### Minimal Example

```python
from umik_base_app import AppArgs, AudioBaseApp, AudioPipeline, AudioSink, PipelineContext

class LoudnessPrinter(AudioSink):
    def handle(self, ctx: PipelineContext) -> None:
        if ctx.can_calculate_dbspl():
            dbspl = ctx.reference_dbspl if ctx.is_gain_calibrated() else None
            print(f"[{ctx.timestamp}] dBSPL: {dbspl:.1f}")

def main():
    args = AppArgs.get_args()
    config = AppArgs.validate_args(args)

    pipeline = AudioPipeline(sample_rate=config.sample_rate)
    pipeline.add_sink(LoudnessPrinter())

    # If --calibration-file was passed, CalibratorAdapter is auto-injected
    app = AudioBaseApp(app_config=config, pipeline=pipeline)
    app.run()
```

Run it with any `audio-tools` flags:

```bash
python my_app.py --calibration-file "umik-1/7175488.txt"
```

### PipelineContext

Every audio chunk is delivered to sinks wrapped in a `PipelineContext`:

| Property | Type | Description |
|----------|------|-------------|
| `ctx.audio` | `np.ndarray` | Audio samples for this buffer |
| `ctx.timestamp` | `datetime` | Capture time |
| `ctx.sample_rate` | `float` | Sample rate in Hz |
| `ctx.gain_applied` | `bool` | Sensitivity gain was applied by `CalibratorAdapter` |
| `ctx.fir_applied` | `bool` | FIR filter was applied by `CalibratorAdapter` |
| `ctx.sensitivity_dbfs` | `float \| None` | Mic sensitivity (set when calibration file is loaded) |
| `ctx.reference_dbspl` | `float \| None` | Reference SPL (e.g. 94 dBSPL) |
| `ctx.is_gain_calibrated()` | `bool` | `gain_applied` and sensitivity metadata are present |
| `ctx.is_fully_calibrated()` | `bool` | Both gain and FIR applied |
| `ctx.can_calculate_dbspl()` | `bool` | `sensitivity_dbfs` and `reference_dbspl` are set |

### dBSPL Calculation

`CalibratorAdapter` applies the sensitivity gain to `ctx.audio` before any sink sees it. Calling `AudioMetrics.dBSPL()` on already-gained audio double-counts the sensitivity offset (~18.5 dB error). Use the correct formula based on calibration state:

```python
class MetricsSink(AudioSink):
    def handle(self, ctx: PipelineContext) -> None:
        dbfs = AudioMetrics.dBFS(ctx.audio)

        if ctx.is_gain_calibrated():
            # Gain already applied to ctx.audio; do NOT use AudioMetrics.dBSPL()
            dbspl = dbfs + ctx.reference_dbspl
        elif ctx.can_calculate_dbspl():
            # Raw audio — apply the full sensitivity offset
            dbspl = AudioMetrics.dBSPL(dbfs, ctx.sensitivity_dbfs, ctx.reference_dbspl)
        else:
            dbspl = None
```

### Calibration Architecture

`CalibratorAdapter` wraps two transformers in sequence:

| Transformer | Purpose | CPU Cost | Use Case |
|-------------|---------|----------|----------|
| `GainTransformer` | Sensitivity correction (level) | O(n) | Real-time meters |
| `FirCorrectionTransformer` | Frequency response correction | O(n × taps) | Precision recording |

Use **gain-only** for real-time applications where CPU matters. Use **full calibration** (gain + FIR) when frequency accuracy is critical (e.g. recording for analysis).

### Adding a New Command

1. Create your `main()` in `src/umik_base_app/apps/` or `src/scripts/`.
2. Register the entry point in `pyproject.toml` under `[project.scripts]`.
3. Add the flag to `_DISPATCH` and `_HELP` in `src/umik_base_app/cli.py`.
4. Add a `make` target in `Makefile` under the appropriate section.

### Device Profiles

| Microphone | Manufacturer | Sample Rates | Sensitivity |
|------------|--------------|--------------|-------------|
| UMIK-1 | miniDSP | 48kHz | −18 dBFS |
| UMIK-2 | miniDSP | 48/96/192kHz | −18 dBFS |
| UMM-6 | Dayton Audio | 48kHz | −18 dBFS |
| XREF 20 | Sonarworks | 48kHz | −26 dBFS |
| MM 1 | Beyerdynamic | 44.1–192kHz | −40 dBFS |
| M23/M30 | Earthworks | 44.1–192kHz | −36 dBFS |

To add a custom microphone profile, see `src/umik_base_app/hardwares/device_profiles.py`.