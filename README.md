# Welcome to the UMIK Base App! 🎤 🐍

**A friendly, modular framework for building audio applications with MiniDSP UMIK microphones.**

> **⚠️ Hardware Note:** This version is currently optimized and verified for the **MiniDSP UMIK-1**.
>
> The architecture is fully compatible with the **UMIK-2** (supporting 32-bit float/192kHz natively), but specific device auto-detection logic is currently tuned for the UMIK-1. Full UMIK-2 plug-and-play support is **[on the roadmap](#-roadmap-umik-2-support)**.

Welcome! Whether you are an audio engineer, a hobbyist, or a developer looking to integrate high-quality audio measurement into your Python projects, this toolkit is for you. It provides a solid foundation (the "Base App") and a suite of ready-to-run tools to record, measure, and calibrate your microphone.

## 🌟 What's Inside?

It includes several ready-made applications to get you started immediately:

* **📋 List Audio Devices:** Scans your computer and lists all connected audio input devices to help you find the specific "Device ID".
* **🔍 Get UMIK ID:** A helper utility that hunts for a device named "UMIK-1" and prints its ID automatically.
* **📏 Calibrate:** Reads the UMIK unique calibration file and creates a digital filter to ensure your measurements are scientifically accurate.
* **🎙️ Recorder:** A robust audio recorder that handles file names, directory creation, and buffering to save high-quality WAV files.
* **📊 Real Time Meter:** A real-time digital meter that displays RMS, dBFS, LUFS (Loudness), and dBSPL (Sound Pressure Level).

```text
INFO AudioConsumerThread [measured_at: 2025-12-14 10:59:17.672282] {'interval_s': '3.0000', 'rms': '0.0180', 'flux': '45.8031', 'dBFS': '-34.9183', 'LUFS': '-30.4443', 'dBSPL': '77.6267'} [audio-metrics]
```

## 🚀 Getting Started

### Prerequisites
* **Python 3.12+**
* **PiP**

#### 📦 System Requirements (Audio Libraries)

Depending on your OS, you may need to install low-level audio drivers for `pyaudio`/`sounddevice` and `soundfile` to work.

##### 🐧 Linux (Ubuntu/Debian)

You must install `PortAudio` and `LibSndFile` headers:
```bash
sudo apt update && sudo apt install libportaudio2 libsndfile1 ffmpeg -y
```

##### 🍎 macOS

If you encounter issues, install these libraries via Homebrew:

```bash
brew install portaudio libsndfile
```

##### 🪟 Windows

Generally, Python wheels include the necessary binaries. If you have issues, ensure you have the latest Visual C++ Redistributable installed. For the UMIK series, no special driver is needed (standard USB Audio Class), but ASIO4ALL is an optional recommendation for low-latency exclusive access.

### Installation

```bash
pip install umik-base-app
```

### 🍓 Hardware Compatibility

This project is lightweight and efficient, making it perfect for embedded devices.

#### Raspberry Pi 4 Model B: ✅ Verified.

> This toolkit is fully compatible with the Raspberry Pi 4 B. It serves as an excellent platform for building standalone, headless acoustic monitoring stations or portable measurement rigs.

## 🏗️ Under the Hood: The Base App

Curious how it works? This project isn't just a script; it's a multi-threaded framework designed for stability.

**The "Producer-Consumer" Model**: Instead of doing everything in one loop (which can cause audio glitches), the work has been split:

1. **The Ear (Producer)**: One thread does nothing but listen to the hardware and put audio into a queue.
2. **The Brain (Consumer)**: Another thread takes audio from the queue and processes it (calculates metrics, saves to disk, etc.).

```mermaid
graph LR
    Mic((🎤 UMIK)) -->|Raw Audio| Producer[Listener Thread]
    Producer -->|Buffer| Queue[Queue]
    Queue -->|Audio| Consumer[Consumer Thread]
    
    Consumer -->|Execute| Calibrator[Calibrator]
    Calibrator -->|Clean Audio| Meter[Decibel Meter]
    Calibrator -->|Clean Audio| Recorder[Recorder]
```

*Want to dive deeper? Check out the [Architecture Documentation](./docs/ARCHITECTURE.md).*

## 📂 Understanding Calibration Files

The microphone in the UMIK Series are measurement microphones, meaning they rely on a software file to correct their frequency response.

When you download your unique files from MiniDSP (using your serial number, e.g., `7175488`), you will get `.txt` files. When you run this app, it calculates a digital filter and saves a "Cache" file (`.npy`) so it starts up instantly next time.

Here is what the file structure looks like:

```
./umik-1/
├── 7175488.txt                     <-- Standard Calibration (0° / On-Axis). Use this for pointing at speakers.
├── 7175488_90deg.txt               <-- 90° Calibration. Use this for ambient room measurement (mic pointing at ceiling).
├── 7175488_fir_1024taps_48000hz.npy <-- [GENERATED] The calculated Filter Cache.
└── ...
```

## 📊 Analysis & Visualization

Beyond real-time monitoring, this toolkit provides powerful scripts to analyze recordings "offline". This is perfect for tuning trigger thresholds or generating reports for noise complaints.

1. **Single File Analysis**
Calculates RMS, Flux, dBFS, LUFS, and dBSPL (if calibrated) for a specific WAV file and saves it to CSV.
```bash
umik-metrics-analyzer "file.wav" --calibration-file "umik-1/700.txt"
```

2. **Visualization (Plotting)**
Turns your CSV data into professional-grade charts.
* **View (Popup Window):**
```bash
umik-metrics-plot "file.csv"
```

* **Save (To Image):**
```bash
# Saves to file.png by default
umik-metrics-plot "file.csv" --save
```

### 📉 Example Output

Below is an actual analysis generated by the toolkit. It shows the correlation between digital levels (dBFS/LUFS) and real-world pressure (dBSPL), along with the "Flux" index used to detect sudden noises.

* **View Raw Data:** [sample_recording_metrics.csv](./sample_recording_metrics.csv)
* **View High-Res Chart:** [sample_recording_metrics.png](./sample_recording_metrics.png)

## 💻 How to Run

There are easy-to-use commands for every tool.

1. **List Devices:**
```bash
umik-list-devices
```

2. **Calibrate:**
```bash
umik-calibrate "umik-1/700.txt"
```

3. **Run Real Time Meter:**
```bash
# Default Mic
umik-real-time-meter

# UMIK-1 (Requires calibration file)
umik-real-time-meter --calibration-file "umik-1/700.txt"
```

4. **Record Audio:**
```bash
# Default Mic
umik-recorder

# UMIK-1 (Requires calibration file)
umik-recorder --calibration-file "umik-1/700.txt" --output-dir "my_folder"
```

5. **Audio Analysis & Visualization:**

**Step 1:** Analyze a WAV file to generate a time-series CSV containing RMS, dBFS, LUFS, and dBSPL data.
```bash
# Analyze raw audio (Relative dBFS only)
umik-metrics-analyzer "recordings/my_audio.wav"

# Analyze with calibration (Absolute dBSPL & LUFS)
umik-metrics-analyzer "recordings/my_audio.wav" --calibration-file "umik-1/700.txt"
```

**Step 2:** Visualize the Results. Create a professional dual-axis plot.
```bash
# Open interactive plot window
umik-metrics-plot "analysis.csv"

# Save plot to an image file (PNG)
umik-metrics-plot "analysis.csv" --save "chart.png"
```

## 🗺️ Roadmap: UMIK-2 Support

While the UMIK-1 is fully supported, the architecture of this base app is designed to be future-proof for the **UMIK-2**. The system already natively supports 32-bit floating-point audio and high sample rates (up to 192kHz).

The following updates are planned to make the UMIK-2 "Plug-and-Play":

* **Generalized Device Detection:** Update the auto-discovery logic to find generic "UMIK" devices rather than strictly searching for "UMIK-1".
* **Robust Calibration Parsing:** Implement regex support for varying calibration file headers (e.g., if the UMIK-2 file format differs from the UMIK-1 `Sens Factor` tag).
* **Configurable Sensitivity:** Add environment variable overrides for the nominal sensitivity reference (since UMIK-2 sensitivity may differ from the UMIK-1's ~-18dB default).

## 📚 Documentation & Resources

* [Architecture Overview](./docs/ARCHITECTURE.md): Deep dive into the threading, pipeline pattern, and code structure.
* [Understanding Audio Metrics](./docs/METRICS.md): Learn the math behind RMS, LUFS, and dBSPL.
* [The UMIK-1 Guide](./docs/UMIK-Series.md): Specific details about handling the UMIK-1 hardware.

## 🔗 Related Projects

If you are interested in taking this further, check out my **Edge AI Acoustic Monitor** project. It uses similar principles but adds **Machine Learning** to classify sounds (like detecting chainsaws or birds) on embedded devices! 👉 [py-edge-ai-acoustic-monitoring-app](https://github.com/danielfcollier/py-edge-ai-acoustic-monitoring-app)

## 🤝 Contributing

Found a bug? Want to help implement UMIK-2 support? Check out [CONTRIBUTING.md](https://github.com/danielfcollier/py-umik-base-app/CONTRIBUTING.md) to see how to run tests, lint your code, and submit Pull Requests.

**Happy listening! 🎧**
