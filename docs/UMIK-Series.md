# The UMIK Series Microphones: A Guide for Accurate Sound Monitoring

> **⚠️ Hardware Note:** This guide covers concepts for both the **UMIK-1** and **UMIK-2**.
> While the **UMIK-1** is verified out-of-the-box, the **UMIK-2** is fully supported by this application's architecture (native 32-bit float/192kHz). UMIK-2 users may need to manually verify their calibration file headers match the expected format (see Section 3) until full auto-detection is added.

This document provides a comprehensive overview of the **miniDSP UMIK Series** USB measurement microphones, their importance for audio analysis applications, and the process for using their calibration data in a real-time monitoring script.

## 1. The UMIK Family (1 & 2)

The **miniDSP UMIK-1** and **UMIK-2** are specialized omnidirectional USB measurement microphones. Unlike microphones designed for voice or music, their primary purpose is to provide a scientifically accurate, linear, and repeatable way to capture sound.

### Configuring for Other Devices
While the application defaults to searching for "UMIK-1", you can configure it to detect **UMIK-2** or any other specific microphone name.

1. Open `src/umik_base_app/settings.py` (or use environment variables).
2. Update the `HARDWARE` settings:
   ```python
   class HardwareSettings(BaseModel):
       TARGET_DEVICE_NAME: str = "UMIK-2"  # or any substring of your device name
       NOMINAL_SENSITIVITY_DBFS: float = -12.0  # Adjust for your specific hardware

```

3. The `umik-list-devices --only` command and auto-detection logic will now target your specified device.

| Feature | UMIK-1 | UMIK-2 | Application Support |
| --- | --- | --- | --- |
| **Bit Depth** | 24-bit | 32-bit | **Native 32-bit Float:** The pipeline defaults to `float32` to preserve the full dynamic range of the UMIK-2. |
| **Sample Rate** | 48 kHz (Fixed) | 44.1 - 192 kHz | **Auto-Switching:** The app detects the device's native rate (e.g., 192kHz) and adapts the pipeline automatically. |
| **Noise Floor** | Good | Excellent | Lower noise floor on UMIK-2 allows for more sensitive quiet-room monitoring. |

### Key Shared Features:

* **Plug-and-Play:** Both are UAC (USB Audio Class) compliant devices, requiring no special drivers for Windows, macOS, Linux, or Raspberry Pi OS.
* **Unique, Individual Calibration:** Every single unit is tested at the factory, and a unique calibration file is generated based on its serial number.
* **Omnidirectional Polar Pattern:** Captures sound equally from all directions, ideal for room acoustics and environmental monitoring.

### References:

* **Product Pages:** [miniDSP UMIK-1](https://www.minidsp.com/products/acoustic-measurement/umik-1) | [miniDSP UMIK-2](https://www.minidsp.com/products/acoustic-measurement/umik-2)
* **Calibration File Download:** [miniDSP Calibration Tool](https://www.google.com/search?q=https://www.minidsp.com/support/community-powered-tutorials/201-umik-1-setup-with-rew)

## 2. Relevance for Your Sound Monitoring Application

Using a calibrated microphone is the difference between building a simple "volume detector" and a true **acoustic monitoring instrument**.

The principle is simple: **Garbage In, Garbage Out.** The quality of your analysis is fundamentally limited by the quality of your input data.

* **Uncalibrated Microphones (Laptops, Phones):** These are "colored." They are designed to boost speech frequencies and cut low-frequency rumble. When you feed this biased signal into your application:
* **LUFS measurements will be inaccurate**, as they are calculated on an altered signal.
* **Low-frequency noise** (traffic, HVAC, machinery) will be underestimated.
* **Calibrated UMIK Series:** This provides a "ground truth" signal.
* It ensures that a sound's energy is represented accurately across the entire frequency spectrum, **including critical low frequencies**.
* This allows metrics like **LUFS** and **dBSPL** to be calculated with scientific accuracy.
* It provides Machine Learning models with a clean, unbiased signal, leading to more reliable classification.

## 3. The Real-Time Calibration Process

Calibration is not a hardware setting. It is a **continuous, real-time software process** that corrects the audio signal as it comes in.

The process has three phases:

### Phase 1: One-Time Setup (Manual)

1. **Find Serial Number:** Locate the serial number on your microphone body (e.g., `700xxxx` for UMIK-1 or `800xxxx` for UMIK-2).
2. **Download File:** Go to the miniDSP calibration tool website and download your unique `.txt` file.

* **Note for UMIK-2 Users:** The UMIK-2 calibration file might use a different header tag for sensitivity (e.g., `Sensitivity` instead of `Sens Factor`). You may need to manually adjust the text file header to match the expected format `Sens Factor =-XXdB` until the parser is updated.

### Phase 2: Application Startup (Filter Design & Caching)

This happens once, every time your `umik-base-app` starts.

1. **Check for Cache:** The `CalibratorTransformer` looks for a pre-computed filter file (e.g., `..._fir_1024taps_48000hz.npy`).
2. **Design Filter (First Run):** If no cache is found, the `CalibratorTransformer`:

* Reads the frequency/gain pairs from your `.txt` file.
* Uses `scipy.signal.firwin2` to design a digital **FIR (Finite Impulse Response) filter**. This filter applies the *exact inverse* of your microphone's unique frequency response.
* Saves the filter coefficients to a `.npy` cache file for instant startup next time.

### Phase 3: Real-Time Correction (Continuous Loop)

This is the core of the process inside the Consumer Thread:

1. **Receive Raw Audio:** The thread gets a raw chunk (e.g., `float32` array) from the input queue.
2. **Apply Filter:** It passes the chunk to `CalibratorTransformer.apply()`. This uses `scipy.signal.lfilter` to convolve the audio with the correction filter.
3. **Process Further:** **All subsequent operations** - Metrics (RMS/Flux), LUFS calculation, and recording- are performed on this clean, calibrated audio.

This ensures that every piece of data your application analyzes is a scientifically accurate representation of the acoustic environment.

### Optional Step: Adjusting Filter Complexity

If you find that the real-time correction is consuming too much CPU (e.g., on a Raspberry Pi Zero), you can reduce the load by adjusting the **number of filter taps** in `CalibratorTransformer`:

* `num_taps=1024` (Default): High accuracy, higher CPU.
* `num_taps=512` or `256`: Lower CPU, but reduced accuracy in the low-frequency range (20Hz-250Hz).

> **Trade-off:** Reducing `num_taps` sacrifices the accuracy of your low-frequency measurements. Use this optimization only if absolutely necessary.

## 4. Other Related Applications

A calibrated UMIK microphone is a versatile tool for any serious audio work. Its applications extend far beyond noise monitoring:

* **Room Acoustics Measurement:** Using software like **REW (Room EQ Wizard)** to measure reverberation time (RT60) and identifying standing waves.
* **Speaker Calibration:** Fine-tuning home theater systems (using **Dirac Live** or **Audyssey**).
* **Scientific Measurement:** Environmental noise impact studies and psychoacoustic research.
* **Recording Reference:** Capturing an accurate "snapshot" of a room's sound for mixing decisions.
