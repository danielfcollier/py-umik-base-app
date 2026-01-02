# Welcome to the UMIK Base App! 🎤 🐍

**A friendly, modular framework for building audio applications with MiniDSP UMIK microphones.**

> **⚠️ Hardware Note:** This version is currently optimized and verified for the **MiniDSP UMIK-1**.
>
> The architecture is fully compatible with the **UMIK-2** (supporting 32-bit float/192kHz natively) and other calibrated microphones.
> **New:** You can now configure the target device name (e.g., "UMIK-2") in `settings.py` or via environment variables to support auto-detection for other hardware.

**Welcome!**

Whether you are an audio engineer, a hobbyist, or a developer looking to integrate high-quality audio measurement into your Python projects, this toolkit is for you. It provides a solid foundation (the "Base App") and a suite of ready-to-run tools to record, measure, and calibrate your microphone.

## 🌟 Two Ways to Use

### 1. As a Toolkit (For Users) 🛠️

Out of the box, it includes a suite of polished CLI applications to record, measure, and analyze audio without writing any code.

* **📋 List Audio Devices:** Scans your computer and lists all connected audio input devices.
* **📏 Calibrate:** Generate scientific FIR filters from your microphone's calibration file.
* **🎙️ Recorder:** A robust audio recorder that handles file names, directory creation, and buffering to save high-quality WAV files.
* **📈 Forensic Analysis:** Generate professional charts correlating digital levels with physical pressure.
* **📊 Real Time Meter:** A real-time digital meter that displays RMS, dBFS, LUFS (Loudness), and dBSP (Sound Pressure Level).

```text
INFO AudioConsumerThread [measured_at: 2025-12-14 10:59:17.672282] {'interval_s': '3.0000', 'rms': '0.0180', 'flux': '45.8031', 'dBFS': '-34.9183', 'LUFS': '-30.4443', 'dBSPL': '77.6267'} [audio-metrics]
```

### 2. As a Framework (For Developers) 👩‍💻

Stop fighting with `pyaudio` threads and buffer overflows. This project exposes its core `AudioBaseApp` class, allowing you to build custom audio apps in minutes.

* **🛡️ Process Isolation:** Your custom logic runs in a separate process from the audio capture, preventing glitches.
* **🌐 Distributed by Default:** Your app automatically supports remote streaming via ZeroMQ.
* **🧩 Plug-and-Play Sinks:** Just implement `handle_audio(chunk)` and let the framework handle the threading, hardware reconnection, and precise timing.


## 🚀 Getting Started

### Prerequisites

* **Python 3.9+**
* **PiP**

#### 📦 System Requirements (Audio Libraries)

You may need low-level audio drivers (`PortAudio`/`LibSndFile`) and ZeroMQ headers depending on your OS.

**🐧 Linux (Debian/Ubuntu):**

```bash
sudo apt update && sudo apt install libportaudio2 libsndfile1 ffmpeg libzmq3-dev -y
```

> 🍓 Raspberry Pi 4 Model B: ✅ Verified.
>
> This toolkit is fully compatible with the Raspberry Pi 4 B. It serves as an excellent platform for building standalone, headless acoustic monitoring stations or portable measurement rigs.

**🍎 macOS:**

```bash
brew install portaudio libsndfile zeromq
```

**🪟 Windows**

Generally, Python wheels include the necessary binaries. If you have issues, ensure you have the latest Visual C++ Redistributable installed. For the UMIK series, no special driver is needed (standard USB Audio Class), but ASIO4ALL is an optional recommendation for low-latency exclusive access.

### Installation

```bash
pip install umik-base-app
```

## 🏗️ Under the Hood: Process Isolation

This project uses a **Producer-Consumer** architecture to guarantee audio stability. It supports two distinct operational modes depending on your requirements:

### 1. Monolithic Mode (Default)
By default (no flags), the application runs as a **Single Process** using threads. This is the simplest way to run the app for desktop usage or quick testing. The Producer and Consumer share memory and communicate via a highly efficient, thread-safe queue.

### 2. The Daemon Philosophy (Priority & Reliability) 🛡️
For mission-critical monitoring, you can break the monolith. Unlike standard Python scripts that use *threads* (which share the same CPU core and are limited by the GIL), this mode allows you to run the **Producer** and **Consumer** as completely separate **System Processes**.

* **The Producer (Ear):** Captures audio and broadcasts it via ZeroMQ. It has no GUI, no heavy math, and uses minimal RAM. We run this with **Real-Time Priority** (`nice -n -20`) so the OS *always* lets it run, even if the system is under load.
* **The Consumer (Brain):** Subscribes to the stream to calculate FFTs, render plots, or run AI models. If this process hangs or crashes, the audio stream remains unbroken.

```mermaid
graph TD
    subgraph "High Priority Process (Nice -20)"
        Mic((🎤 UMIK)) -->|Capture| Producer[Producer Daemon]
        Producer -->|ZMQ PUB| Socket[Localhost:5555]
    end

    subgraph "Standard User Process"
        Socket -.->|ZMQ SUB| Consumer[Consumer App]
        Consumer -->|Heavy Math| Analysis[FFT / AI / Plot]
    end
```

### 3. Distributed Mode (Remote Monitoring) 🌐

Because the components communicate over TCP/IP, you aren't limited to one machine. You can capture audio on a Raspberry Pi and monitor it on your workstation.

```mermaid
graph LR
    subgraph "Raspberry Pi (Edge)"
        Producer[Producer Daemon] -->|Broadcast| Wifi((📶 WiFi))
    end
    
    subgraph "Laptop (Remote)"
        Wifi -->|Subscribe| Consumer[Real Time Meter]
    end
```

*Want to dive deeper? Check out the [Architecture Documentation](./docs/ARCHITECTURE.md).*

## 💻 How to Run

Whether you are testing on your laptop or deploying to a headless Raspberry Pi, there is a mode for you.

### 1. The "Quick Start" (Monolithic Mode)
*Best for: Testing, Development, and simple Desktop usage.*

Run everything in a single process. It is the easiest way to verify your hardware works.

```bash
# List available devices to find your ID
umik-list-devices

# Run the meter (Default Mic)
umik-real-time-meter

# Run with UMIK-1 Calibration
umik-real-time-meter --calibration-file "umik-1/700.txt"
```

### 2. The "Unstoppable Ear" (Daemon Mode) 🛡️

*Best for: Critical Monitoring on a single machine.*

To prevent audio glitches caused by heavy processing or GUI lag, run the capture process as a high-priority system daemon.

**Step 1: Start the Daemon (Producer)**
Use `nice -n -20` to give the audio capture maximum CPU priority. It will broadcast data locally on port 5555.

```bash
# Requires sudo to set negative nice values
sudo nice -n -20 umik-real-time-meter --producer --calibration-file "umik-1/700.txt" --zmq-port 5555
```

**Step 2: Start the App (Consumer)**
Connect your GUI or Recorder to the running daemon. You can open, close, or crash this app without ever breaking the audio stream.

```bash
umik-real-time-meter --consumer --zmq-host localhost --zmq-port 5555
```

### 3. The "Remote Sentry" (Distributed Mode) 🌐

*Best for: IoT, Headless Pis, and Remote Monitoring.*

Capture audio in one room (e.g., a server closet) and visualize it in another.

**On the Raspberry Pi (Edge Node):**

```bash
# Start the stream
umik-real-time-meter --producer --calibration-file "umik-1/700.txt" --zmq-port 5555
```

**On your Laptop (Workstation):**

```bash
# Connect over WiFi
umik-real-time-meter --consumer --zmq-host 192.168.1.50 --zmq-port 5555
```

### 4. Universal Recording 🎙️

The `umik-recorder` tool works in all modes. You can record directly from hardware or "tap in" to an existing stream to save it to disk.

```bash
# Option A: Direct Recording (Monolithic)
umik-recorder --calibration-file "umik-1/700.txt" --output-dir "local_recordings"

# Option B: Record a Daemon/Remote Stream (Consumer)
umik-recorder --consumer --zmq-host 192.168.1.50 --zmq-port 5555 --output-dir "remote_recordings"
```

## 📂 Understanding Calibration Files

The microphone in the UMIK Series are measurement microphones, meaning they rely on a software file to correct their frequency response.

When you download your unique files from MiniDSP (e.g., `7175488`), you will get `.txt` files. This app uses them to generate a digital FIR filter.

```
./umik-1/
├── 7175488.txt                     <-- 0° (On-Axis). Point at speakers.
├── 7175488_90deg.txt               <-- 90° (Ambient). Point at ceiling.
├── 7175488_fir_1024taps_48000hz.npy <-- [GENERATED] The calculated Filter Cache.
└── ...
```

## 📊 Analysis & Visualization

Beyond real-time monitoring, this toolkit provides powerful scripts to analyze recordings "offline".

1. **Single File Analysis**
Calculates RMS, Flux, dBFS, LUFS, and dBSPL (if calibrated) for a specific WAV file and saves it to CSV.

```bash
umik-metrics-analyzer "file.wav" --calibration-file "umik-1/700.txt"
```

2. **Visualization (Plotting)**
Turns your CSV data into professional-grade charts.
* **View (Popup Window):**
```bash
umik-metrics-plotter "file.csv"
```

* **Save (To Image):**
```bash
# Saves to file.png by default
umik-metrics-plotter "file.csv" --save
```

### 📉 Example Output

Below is an actual analysis generated by the toolkit. It shows the correlation between digital levels (dBFS/LUFS) and real-world pressure (dBSPL), along with the "Flux" index used to detect sudden noises.

* **View Raw Data:** [sample_recording_metrics.csv](./sample_recording_metrics.csv)
* **View High-Res Chart:** [sample_recording_metrics.png](./sample_recording_metrics.png)


To address this, you should add a **"For Developers"** section. This is crucial because it transforms your project from a "Tool" into a "Framework" in the eyes of the user.

You want to show that `AudioBaseApp`, `AudioPipeline`, and `AudioSink` are reusable building blocks.

Here is the suggested section to add to your `README.md`. I recommend placing it right after the **"How to Run"** section.

## 👩‍💻 For Developers: Build Your Own App

`umik-base-app` isn't just a set of tools; it's a framework. You can use it to build your own custom audio applications - like a baby monitor, a clap detector, or a secure stream recorder - without writing a single line of threading or hardware code.

The framework handles the heavy lifting (Producer-Consumer isolation, ZMQ transport, hardware watchdog) so you can focus on the logic.

### Minimal Example: A "Loudness Printer"
Here is how you can build a custom app in fewer than 30 lines of code.

**1. Define your Logic (The Sink)**
Inherit from `AudioSink` and implement `handle_audio`. This method receives the raw numpy arrays from the pipeline.

```python
import numpy as np
from umik_base_app import AudioSink

class LoudnessPrinterSink(AudioSink):
    def handle_audio(self, audio_chunk: np.ndarray, timestamp):
        # Calculate simple RMS
        rms = np.sqrt(np.mean(audio_chunk**2))
        
        if rms > 0.05:
            print(f"[{timestamp}] 📢 LOUD NOISE DETECTED: {rms:.4f}")
```

**2. Assemble the App**
Create a standard `AudioBaseApp` and attach your sink to the pipeline.

```python
from umik_base_app import (
    AppArgs,
    AudioBaseApp,
    AudioPipeline,
)

def main():
    # 1. Get standard Configuration (CLI args + Defaults)
    # This automatically handles --device-id, --producer, --consumer flags!
    args = AppArgs.get_args()
    config = AppArgs.validate_args(args)

    # 2. Build the Pipeline
    pipeline = AudioPipeline()
    pipeline.add_sink(LoudnessPrinterSink())

    # 3. Run the App
    # AudioBaseApp handles the threading, ZMQ, and hardware lifecycle
    app = AudioBaseApp(app_config=config, pipeline=pipeline)
    app.run()

if __name__ == "__main__":
    main()
```

### Why use the Framework?

By using `AudioBaseApp`, your custom script automatically inherits all the advanced features:

* **ZeroMQ Support:** Your "Loudness Printer" can instantly work over the network by running it with `--consumer`.
* **Process Isolation:** You can run your script as a GUI app without blocking the audio capture.
* **Calibration:** You can easily add the `CalibratorAdapter` to the pipeline to get scientifically accurate data before your Sink sees it.


## 🗺️ Roadmap: UMIK-2 Support

While the UMIK-1 is fully supported, the architecture of this base app is designed to be future-proof for the **UMIK-2**. The system already natively supports 32-bit floating-point audio and high sample rates (up to 192kHz).

The following updates are planned to make the UMIK-2 "Plug-and-Play":

- **Robust Calibration Parsing**: Implement regex support for varying calibration file headers (e.g., if the UMIK-2 file format differs from the UMIK-1 `Sens Factor` tag).

- **Configurable Sensitivity**: Add environment variable overrides for the nominal sensitivity reference (since UMIK-2 sensitivity may differ from the UMIK-1's ~-18dB default).

## 📚 Documentation & Resources

* [Architecture Overview](./docs/ARCHITECTURE.md): Deep dive into the threading, pipeline pattern, and code structure.
* [Understanding Audio Metrics](./docs/METRICS.md): Learn the math behind RMS, LUFS, and dBSPL.
* [The UMIK Series Guide](./docs/UMIK-Series.md): Specific details about handling the UMIK Series hardware.

## 🔗 Related Projects

If you are interested in taking this further, check out my **Edge AI Acoustic Monitor** project. It uses similar principles but adds **Machine Learning** to classify sounds (like detecting chainsaws or birds) on embedded devices! 👉 [py-edge-ai-acoustic-monitoring-app](https://github.com/danielfcollier/py-edge-ai-acoustic-monitoring-app)

## 🤝 Contributing

Found a bug? Want to help implement UMIK-2 or other digtal microphone support? Check out [CONTRIBUTING.md](https://github.com/danielfcollier/py-umik-base-app/CONTRIBUTING.md).

**Happy listening! 🎧**
