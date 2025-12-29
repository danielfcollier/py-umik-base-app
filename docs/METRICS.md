# Understanding Audio Metrics: The Mathematics

This document explains the mathematical formulas and concepts behind common audio metrics used in signal processing and monitoring.

## 1. Peak Amplitude

### Definition

The Peak Amplitude is the absolute maximum instantaneous value reached by the audio waveform within a given time window. It represents the highest excursion of the signal from the zero line.

### Formula

Given a discrete audio signal represented as a sequence of samples $x[n]$ over a window of $N$ samples (from $n=0$ to $n=N-1$):

$$
\text{Peak} = \max_{0 \le n < N} |x[n]|
$$

* $x[n]$: The amplitude of the audio sample at time index $n$.
* $|x[n]$: The absolute value (magnitude) of the sample.
* $\max_{0 \le n < N}$: Finds the maximum value within the window of $N$ samples.

### Purpose

Indicates the absolute highest level reached by the signal. It's crucial for identifying potential **clipping** (distortion caused when the signal exceeds the maximum representable level), but it doesn't give a good sense of the *perceived loudness* or *average power*.


## 2. Root Mean Square (RMS)

### Definition

RMS measures the effective level or "power" of the audio signal over a time window. It's a type of average that gives more weight to higher amplitude values and is closely related to the perceived loudness of steady sounds.

### Formula

For the same discrete signal $x[n]$ over $N$ samples:

$$
\text{RMS} = \sqrt{\frac{1}{N} \sum_{n=0}^{N-1} (x[n])^2}
$$

* $(x[n])^2$: Square each individual sample's amplitude. This makes all values positive and emphasizes larger amplitudes.
* $\sum_{n=0}^{N-1}$: Sum the squared values over the window.
* $\frac{1}{N}$: Calculate the mean (average) of the squared values (this is the Mean Square).
* $\sqrt{\dots}$: Take the square root of the mean square to return the value to the original units of amplitude (this is the Root Mean Square).

### Purpose

Provides a measure of the signal's average power or effective amplitude. It correlates much better with perceived loudness for continuous sounds than peak amplitude does. It's the foundation for calculating decibel levels.


## 3. Decibels Full Scale (dBFS)

### Definition

dBFS measures the amplitude of a digital audio signal relative to the maximum possible level that the digital system can represent (Full Scale). 0 dBFS is the maximum possible level; all other values are negative.

### Formula

Based on the RMS value calculated above:

$$
\text{dBFS} = 20 \times \log_{10} \left( \frac{\text{RMS}}{\text{RMS}_{\text{max}}} \right)
$$

However, in digital audio processing where the signal $x[n]$ is typically represented as a floating-point number between -1.0 and +1.0, the maximum possible RMS for a full-scale sine wave is $1/\sqrt{2}$, and for a full-scale square wave is $1$. For simplicity and convention, $\text{RMS}_{\text{max}}$ is often treated as $1.0$ when $x[n]$ is in the range $[-1, 1]$. The formula simplifies to:

$$
\text{dBFS} = 20 \times \log_{10} (\text{RMS})
$$

* $\text{RMS}$: The Root Mean Square value of the signal (assuming values are normalized to $[-1, 1]$).
* $\log_{10}$: The base-10 logarithm.
* $20 \times$: The factor used because decibels for amplitude (like voltage or digital samples) are related to power ($P \propto V^2$), and $\log(V^2) = 2 \log(V)$.

*(Note: In practice, a small epsilon is often added inside the logarithm, `log10(RMS + epsilon)`, to prevent `log10(0)` which is negative infinity during perfect silence.)*

### Purpose

To quantify the level of a digital audio signal relative to its maximum possible value, primarily for preventing digital clipping and for mixing/mastering. It does *not* represent real-world loudness without calibration.


## 4. Decibels Sound Pressure Level (dBSPL)

### Definition

dBSPL measures the actual sound pressure in the real world relative to a standard reference pressure (the threshold of human hearing, $P_0 = 20 \, \mu \text{Pa}$). This requires a calibrated microphone with known sensitivity.

### Formula

The conversion from a measured dBFS value (obtained from a calibrated microphone) to dBSPL relies on the microphone's sensitivity:

$$
\text{dBSPL} = \text{dBFS}_{\text{measured}} - \text{Sensitivity}_{\text{dBFS}} + \text{Reference}_{\text{dBSPL}}
$$

* $\text{dBFS}_{\text{measured}}$: The dBFS value calculated from the microphone's digital output.
* $\text{Sensitivity}_{\text{dBFS}}$: The microphone's specified sensitivity (e.g., -18 dBFS for the UMIK-1 and -12 dBFs for the UMIK-2). This is the dBFS level the microphone outputs when exposed to the reference sound pressure.
* $\text{Reference}_{\text{dBSPL}}$: The standard sound pressure level used for calibration (typically 94 dBSPL, which corresponds to 1 Pascal).

### Purpose

To quantify the actual, physical loudness of a sound in the environment. This is the standard metric for noise measurements, acoustics, and hearing safety.

## 4. Decibels Sound Pressure Level (dBSPL) - Calibrated

### Definition

dBSPL measures the actual sound pressure in the real world relative to a standard reference pressure (the threshold of human hearing, $P_0 = 20 \, \mu \text{Pa}$). Calculating this accurately requires applying a **calibration correction** based on a specific microphone's sensitivity and frequency response.

### Calibration Process (Using FIR Filter)

1.  **Calibration File:** A unique file provided by the microphone manufacturer (e.g., for a UMIK series) lists the microphone's gain deviation (in dB) at various frequencies.
2.  **Filter Design:** A digital filter, typically a **Finite Impulse Response (FIR) filter**, is designed based on this file. The filter's frequency response is calculated to be the *exact inverse* of the microphone's response. Its goal is to apply the opposite gain correction at each frequency, effectively flattening the microphone's inaccuracies. This design process (e.g., using `scipy.signal.firwin2`) is computationally intensive and is usually performed only once when the application starts, with the filter coefficients being cached.
3.  **Real-Time Filtering:** The raw audio signal coming directly from the microphone, $x_{\text{raw}}[n]$, is continuously passed through this pre-designed FIR filter (e.g., using `scipy.signal.lfilter`). This produces a *calibrated* audio signal, $x_{\text{cal}}[n]$. This filtering step happens in real-time for every audio chunk.

$$
x_{\text{cal}}[n] = \text{FIR}_{\text{FILTER}}(x_{\text{raw}}[n])
$$

### Formula (Using Calibrated Signal)

The dBSPL is then calculated using the dBFS value derived from the **calibrated** audio signal, combined with the microphone's overall sensitivity:

1.  Calculate the RMS of the *calibrated* signal:

$$
\text{RMS}_{\text{cal}} = \sqrt{\frac{1}{N} \sum_{n=0}^{N-1} (x_{\text{cal}}[n])^2}
$$

2.  Calculate the dBFS of the *calibrated* signal:

$$
\text{dBFS}_{\text{cal}} = 20 \times \log_{10} (\text{RMS}_{\text{cal}})
$$

3.  Convert the calibrated dBFS to dBSPL:

$$
\text{dBSPL} = \text{dBFS}_{\text{cal}} - \text{Sensitivity}_{\text{dBFS}} + \text{Reference}_{\text{dBSPL}}
$$

* $\text{dBFS}_{\text{cal}}$: The dBFS value calculated from the microphone's *filtered* digital output.
* $\text{Sensitivity}_{\text{dBFS}}$: The microphone's specified broadband sensitivity (e.g., -18 dBFS for the UMIK-1 and -12 dBFS for the UMIK-2). This is the overall dBFS level the (now notionally flat) microphone outputs when exposed to the reference sound pressure.
* $\text{Reference}_{\text{dBSPL}}$: The standard sound pressure level used for calibration (typically 94 dBSPL, which corresponds to 1 Pascal).

### Purpose

To quantify the actual, physical loudness of a sound in the environment with high accuracy across the frequency spectrum. This is the standard metric for noise measurements, acoustics, and hearing safety when precision is required.


## 5. Spectral Flux

### Definition

Spectral Flux measures the rate of change in the frequency spectrum of an audio signal between consecutive short time frames. It quantifies how much the "timbre" or frequency content of the sound is changing.

### Formula

1.  Divide the signal into short, overlapping frames (e.g., 20ms).
2.  For each frame $t$, compute its magnitude spectrum $S_t(k)$, typically using the Short-Time Fourier Transform (STFT). $k$ represents the frequency bin index.
3.  Normalize the spectrum (optional but common, e.g., unit norm). Let the normalized spectrum be $\hat{S}_t(k)$.
4.  Calculate the spectral flux $F_t$ between frame $t$ and the previous frame $t-1$:

$$
F_t = \sum_{k} \left( \hat{S}_t(k) - \hat{S}_{t-1}(k) \right)^2
$$

> *(Variations exist, sometimes using absolute difference or other distance metrics)*
* $\hat{S}_t(k)$: Normalized spectral magnitude of frequency bin $k$ at frame $t$.
* $\hat{S}_{t-1}(k)$: Normalized spectral magnitude of frequency bin $k$ at the previous frame $t-1$.
* $\sum_{k}$: Sum the squared differences across all frequency bins $k$.

### Purpose

Excellent for **onset detection** (finding the start of new sound events). Steady sounds (like hums or wind) have low spectral flux, while the beginning of a note, a bark, or speech has high spectral flux. It helps distinguish dynamic events from constant background noise.


## 6. Loudness (LUFS)

### Definition

LUFS (Loudness Units Full Scale) is a standardized measure (ITU-R BS.1770) designed to quantify the *perceived* loudness of audio, taking human hearing characteristics into account. **For accurate results, LUFS should be calculated on the calibrated audio signal.**

### Formula (Conceptual Overview)

The full LUFS calculation is complex, involving multiple stages:

1.  **K-Weighting Filter:** The **calibrated** audio signal ($x_{\text{cal}}[n]$) is passed through a specific frequency-weighting filter. This filter has two stages:
    * A high-shelf filter to boost higher frequencies (mimicking the head's acoustic effects).
    * A high-pass filter to roll off very low frequencies (below ~30-40 Hz), as humans are less sensitive to them.
    Let the K-weighted signal be $x_K[n]$.
2.  **Mean Square Calculation:** Calculate the mean square of the K-weighted signal over specific time windows (e.g., 400ms for Momentary, 3s for Short-Term).
    $$Z_i = \frac{1}{T \times \text{SR}} \sum_{n} (x_{K,i}[n])^2$$
    * $Z_i$: Mean square value for window $i$.
    * $T$: Window duration in seconds.
    * SR: Sample Rate.
    * $x_{K,i}[n]$: Samples of the K-weighted signal within window $i$.
3.  **Channel Summation:** For multi-channel audio, the mean square values are weighted and summed across channels (e.g., surrounds contribute less than fronts).
4.  **Logarithmic Conversion:** The final loudness value is calculated logarithmically:
    $$\text{Loudness} (\text{LUFS}) = -0.691 + 10 \times \log_{10} (Z_{\text{total}})$$
    * $Z_{\text{total}}$: The summed mean square value.
    * $-0.691$: A specific offset defined in the standard.

### Purpose

To provide a consistent, perceptually relevant measure of loudness, crucial for broadcast audio, streaming services, and accurately quantifying the subjective impact of noise. It correlates much better with human perception than simple dB levels.
