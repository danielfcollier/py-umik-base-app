# 🏠 Reading a Room: Practical Acoustics with the Spectrum Analyzer

Most developers who build audio tools stop at "does the meter move?" That's a signal detector, not an acoustic instrument.

In [the previous post](./12%20-%20Spectrum%20Analyzer.md) I explained how the browser-based RTA works internally. This post is about what to *do* with it — specifically, how to use the spectrum analyzer to diagnose real acoustic problems in a room.

You don't need to be an acoustic engineer. You need a UMIK, a browser, and a mental model of three phenomena: **room modes**, **flutter echo**, and **noise floor**.

## 🌊 Room Modes: The Standing Wave Problem

Every rectangular room has **resonant frequencies** — frequencies at which sound bounces between parallel surfaces and reinforces itself. At these frequencies, certain spots in the room are extremely loud, others are dead quiet, and the character of sound changes dramatically depending on where you stand.

The fundamental formula is simple:

```
f = (n × c) / (2 × L)
```

Where `c` is the speed of sound (~343 m/s), `L` is the room dimension, and `n` is the harmonic number (1, 2, 3…).

For a 5-metre room, the first axial mode hits at **34 Hz**. Its harmonics land at 68 Hz, 102 Hz, and so on up the spectrum.

### What It Looks Like in the RTA

Open `audio-tools-spectrum`, play pink noise through a speaker, and watch the FFT. Room modes appear as **narrow, stationary peaks** that don't move when the noise source moves — they're fixed by the room geometry, not the source position.

```
dB
 |
 |     ██
 |  ██ ██    ██
 |  ██ ██ ██ ██ ██  ██  ██
 +--+--+--+--+--+--+--+--+--→ Hz
   34  68  100 136       frequency
        ↑
    Room modes: sharp, stationary spikes
```

Compare the RTA at your listening position vs. one metre to the left. If a 60 Hz peak disappears or doubles in height when you move half a metre, that's a mode. A broadband noise source (traffic, HVAC) shifts uniformly; modes don't.

### What You Can Do

* **Subwoofer placement:** Move the speaker along the wall while watching the 20–120 Hz range in the RTA. The position where the low-frequency response is flattest produces the most accurate bass reproduction.
* **Listening position:** Avoid sitting at exact multiples of half the room's length — those are the pressure nulls (dead spots) for the axial modes.

## 🔁 Flutter Echo: The Comb Filter Signature

Clap your hands once in a bare room. The rapid sequence of reflections between two parallel hard surfaces is **flutter echo**. In the RTA it appears not as a single peak but as a **comb filter** — a regular series of notches spaced evenly across the spectrum.

```
dB
 |
 | ██  ██  ██  ██  ██  ██  ██
 | ██  ██  ██  ██  ██  ██  ██
 |  ██  ██  ██  ██  ██  ██
 +--+--+--+--+--+--+--+--+--→ Hz
    ↑ notches at regular intervals = flutter echo
```

The notch spacing (in Hz) equals `c / (2 × d)`, where `d` is the distance between the parallel surfaces. For 4-metre walls, notches repeat every ~43 Hz.

### Diagnosing with the Waterfall

The **waterfall view** (scrolling spectrogram) is the right tool for flutter echo. Flutter echo has **time structure** — it decays over 100–500 ms depending on the surface. In the waterfall, it shows up as a periodic vertical striping that gradually fades, whereas ambient noise produces a uniform horizontal band.

If you see it, the fix is acoustic treatment on at least one of the parallel surfaces — absorption panels, diffusers, or heavy curtains.

## 🔇 Noise Floor: What the Room Is Actually Doing

Before you can measure anything useful, you need to know what the room sounds like when nothing is playing. The noise floor measurement in `audio-tools-spectrum` exists precisely for this.

**Workflow:**

```bash
# 1. Launch the analyzer
audio-tools-spectrum --device <id> --calibration-file "umik-1/7175488.txt"

# 2. In the browser: turn off all deliberate sound sources.
#    Wait for HVAC to run a normal cycle, then click "Capture Noise Floor".
#    Hold quiet for 5 seconds.

# 3. Now play your source. The SNR overlay shows which bands are above the floor.
```

The SNR overlay tells you immediately which frequency bands are usable:

| Band | Common culprit if SNR is LOW |
|------|------------------------------|
| 20–60 Hz | HVAC, traffic, building structure |
| 60 Hz | Electrical mains hum |
| 1–4 kHz | Fan noise, computer cooling |
| Broadband | Mic self-noise (check UMIK-2 if critical) |

If a specific band is `NOISE` (SNR < 3 dB) before you even play anything, that band cannot be trusted for any measurement. Fix the noise source first, or exclude that range from your analysis.

## 🔊 Speaker and Microphone Alignment

The RTA is the same tool used in professional studio calibration workflows. A flat frequency response at the listening position — from 80 Hz to 16 kHz — is the goal for accurate mixing and monitoring.

**Basic alignment workflow:**

1. Place the UMIK at the primary listening position (ear height).
2. Play a calibrated pink noise track or use a signal generator.
3. Note the peaks and dips in the 100–500 Hz range — these are the room's fingerprint.
4. Compare when the speaker is against the wall vs. pulled forward 60 cm. Wall proximity almost always exaggerates the 100–300 Hz region (bass buildup).
5. Export the noise floor CSV (`exports/YYYY-MM-DD_spectrum.csv`) to keep a timestamped record before and after any room treatment.

The CSV contains per-bin frequency and dB values — easy to plot in any data tool:

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("exports/2025-05-26_spectrum.csv")
df.plot(x="frequency_hz", y="noise_floor_db", logx=True)
plt.xlabel("Frequency (Hz)")
plt.ylabel("Level (dBFS)")
plt.title("Quiet Room Noise Floor")
plt.show()
```

## 📐 What This Tool Is (and Isn't)

The `audio-tools-spectrum` RTA is a **measurement tool** — it shows the steady-state frequency response. It does not perform frequency sweeps, generate room correction filters, or calculate RT60 (reverberation time).

For full room EQ and correction filter generation, **REW (Room EQ Wizard)** is the industry standard, and the UMIK-1 is REW's recommended measurement microphone. The RTA in this project fills the gap for scenarios where you need a fast, always-on, headless-friendly view into what a room is doing — embedded deployments, long-term monitoring, or quick sanity checks before a session.

👉 **See it in action:** [github.com/danielfcollier/py-umik-base-app](https://github.com/danielfcollier/py-umik-base-app)

#RoomAcoustics #AudioEngineering #Python #DSP #AcousticMeasurement #MiniDSP #UMIK #HomeStudio #OpenSource
