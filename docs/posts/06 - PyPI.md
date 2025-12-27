# From "Script Spaghetti" to `pip install`: Open Sourcing My Audio Toolkit for the UMIK-1 🎤🐍

I am thrilled to announce a personal milestone: I have just published my very first Python package to PyPI! 🎉

Meet `umik-base-app`, a modular toolkit designed to make building high-performance audio applications with the **MiniDSP UMIK-1** measurement microphone effortless.

👉 Get it now: `pip install umik-base-app

Here is the story of why I built it, how I packaged it, and why I’m so excited to share it with the open-source community.

## The Problem: Great Hardware, "Raw" Data

I bought the UMIK-1 because it is the gold standard for USB measurement microphones. But when I tried to use it in Python projects, I hit a wall.

While libraries like `sounddevice` make capturing audio easy, getting **scientifically accurate** data is a different beast. I found myself constantly rewriting code to:
- Parse the manufacturer's calibration files (because raw USB audio is uncalibrated).
- Manually calculate FIR filters to flatten the frequency response.
- Juggle threading to prevent audio dropouts during recording.

I realized I wasn't building my app; I was just fighting with plumbing.

## The Solution: The "Base App" Framework

I decided to abstract all that pain away into a reusable core. `umik-base-app` isn't just a collection of scripts; it is a robust framework based on a **Producer-Consumer Architecture**.
- **The "Ear" (Producer):** A dedicated thread that does nothing but listen to the hardware and buffer audio, ensuring zero dropped frames.
- **The "Brain" (Consumer):** A separate thread that processes the audio pipeline—handling complex math like FIR filtering and metric calculation without blocking the input.

Out of the box, it provides real-time metrics for **RMS**, **dBFS**, **LUFS** (Loudness), and **dBSPL** (Sound Pressure Level).

## The "Aha!" Moment: Proper Packaging 📦

For a long time, this project lived as a folder of loose scripts. I’d copy-paste `utils.py` from project to project. It was messy.

The turning point was embracing modern Python packaging standards.
1. **The `src` Layout**: I moved my messy root scripts into a clean `src/py_umik/` directory.
2. `pyproject.toml`: I ditched `setup.py` and `requirements.txt` for a declarative configuration that defines dependencies and entry points like `umik-real-time-meter`.

Suddenly, my "hacked together" scripts felt like professional software. I could install them anywhere with a single command.

## The Tech Stack

I leaned on some amazing modern tools to make this happen:
- [uv](https://github.com/astral-sh/uv): For blazing fast dependency management and packaging.
- **sounddevice:** For low-level PortAudio bindings.
- **scipy:** For signal processing and filter design.

## Try It Out!

If you are an audio engineer, a hobbyist, or just curious about Python audio processing, please give it a spin.

```bash
pip install umik-base-app
```

You can check out the source code, contribute, or star the repo on GitHub here: [https://github.com/danielfcollier/py-umik-base-app](https://github.com/danielfcollier/py-umik-base-app)

Here is to the open-source spirit and the joy of sharing code! 🚀

#Python #OpenSource #AudioProgramming #DataScience #PyPI #MiniDSP