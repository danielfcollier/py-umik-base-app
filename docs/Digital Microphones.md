# Digital Microphones: A Guide for Measurement and Monitoring

This document covers the defining characteristics of digital measurement microphones — how they differ from analog microphones, what the key specifications mean in practice, and how those specifications map to the capabilities of this application.

## What Makes a Microphone "Digital"

An analog microphone outputs a continuous electrical voltage. To record or process that signal on a computer, a separate Analog-to-Digital Converter (ADC) is required — typically built into an audio interface or sound card.

A digital microphone contains the ADC inside the microphone body itself. The signal leaving the mic is already a stream of numbers. The benefits:

* **No external interface required.** The digital output (USB, AES67, etc.) connects directly to a host.
* **Controlled acoustic path.** The capsule, preamp, and ADC are designed and calibrated together at the factory, eliminating variation introduced by third-party interfaces.
* **Per-unit calibration is meaningful.** Because the entire signal chain is fixed, a frequency-response correction file generated for a specific unit remains valid for its lifetime.



## Connection Standards

| Standard | Transport | Typical Use Case |
|---|---|---|
| **USB (UAC)** | USB 2.0 / USB-C | Desktop, laptop, Raspberry Pi — driverless, plug-and-play |
| **AES67 / Dante** | Ethernet (PoE) | Large venues, installed systems, multi-zone monitoring |
| **AES/EBU (AES3)** | XLR (balanced) | Studio interfaces, broadcast consoles |
| **PDM / I²S** | PCB traces | Embedded / IoT (MEMS microphones on development boards) |

The UMIK-1 and UMIK-2 use **USB Audio Class (UAC)**, the dominant standard for desktop and edge measurement work and the only standard currently supported by this application.

### USB Audio Class — Class 1 vs Class 2

| | UAC 1 | UAC 2 |
|---|---|---|
| Max sample rate | 96 kHz | 384 kHz |
| Max channels | 2 | 256 |
| Driver requirement | None (built into every OS) | None on macOS/Linux; WinUSB or ASIO on Windows |
| UMIK-1 | ✓ | — |
| UMIK-2 | — | ✓ |

The UMIK-2's UAC 2 compliance is what enables its 192 kHz mode. On Windows, verify that the UMIK-2 driver is installed and selected before running `audio-tools-spectrum` or `audio-tools --meter`.



## Key Specifications

### Bit Depth and Dynamic Range

Bit depth determines how many discrete amplitude levels the ADC can represent. Each additional bit adds approximately 6 dB of dynamic range.

| Bit Depth | Dynamic Range | Typical Use |
|---|---|---|
| 16-bit | ~96 dB | Consumer audio, phone measurements |
| 24-bit | ~144 dB | Professional recording, UMIK-1 |
| 32-bit float | ~1528 dB (effective ~144 dB + no clipping) | UMIK-2, modern DAWs |

The application pipeline defaults to `float32` throughout. This preserves the UMIK-2's full 32-bit float output and avoids internal clipping when calibration gain is applied to a UMIK-1 signal.

### Sample Rate

Sample rate sets the highest frequency the system can reproduce (Nyquist limit = half the sample rate).

| Sample Rate | Nyquist Limit | Notes |
|---|---|---|
| 44.1 kHz | 22.05 kHz | CD standard; sufficient for all audible frequencies |
| 48 kHz | 24 kHz | Broadcast standard; UMIK-1 fixed rate |
| 96 kHz | 48 kHz | UMIK-2 default; captures ultrasonic content |
| 192 kHz | 96 kHz | UMIK-2 maximum; useful for bat detection, material analysis |

Human hearing extends to approximately 20 kHz. For most acoustic monitoring applications (room acoustics, HVAC noise, speech intelligibility), 48 kHz is more than sufficient. Higher rates are valuable when measuring tweeters, studying ultrasonic noise sources, or running FFTs with very high frequency resolution.

The application auto-detects the device's native sample rate and configures the pipeline accordingly — no manual setting is needed.

### Noise Floor and Self-Noise

Self-noise is the residual electrical noise the microphone produces even in a completely silent room, expressed as an equivalent Sound Pressure Level (dBSPL A-weighted). Lower is better.

| Class | Self-Noise | Typical Device |
|---|---|---|
| Standard | 25–35 dB(A) | Built-in laptop mic |
| Low-noise | 15–25 dB(A) | UMIK-1 (~29 dB(A)) |
| Very low-noise | < 15 dB(A) | UMIK-2 (~11 dB(A)) |

The `audio-tools-spectrum` noise floor tool measures the gap between the microphone's self-noise and the ambient environment (SNR). A higher SNR means quieter signals — HVAC rumble, distant traffic — can be reliably distinguished from electronic noise.

### Polar Pattern

Measurement microphones use an **omnidirectional** polar pattern, meaning they capture sound equally from all directions. This is the correct choice for room acoustics and environmental monitoring.

Directional patterns (cardioid, supercardioid) reject sound from certain angles, making measurements dependent on orientation and less representative of the actual acoustic field.



## Calibration Files

Every UMIK unit ships with a unique calibration file (`.txt`) that describes its frequency response deviation from a flat reference. See [UMIK-Series.md](UMIK-Series.md) for the full calibration workflow.

Calibration is only meaningful when the entire signal chain — capsule, preamp, ADC — is fixed and known. Digital microphones satisfy this requirement by design. An analog microphone measured through an uncalibrated interface cannot be corrected with a mic-only calibration file, because the interface itself introduces unknown coloration.



## Choosing a Microphone for This Application

| Requirement | Recommendation |
|---|---|
| Getting started / budget | UMIK-1 |
| Quiet room monitoring (below 30 dBSPL) | UMIK-2 |
| High sample rate FFT / ultrasonic | UMIK-2 at 96–192 kHz |
| Headless Raspberry Pi deployment | Either (both are plug-and-play on Linux) |
| Non-UMIK device | Set `TARGET_DEVICE_NAME` in `settings.py` and supply a compatible calibration file |



## References

* [USB Audio Class specification — USB-IF](https://www.usb.org/document-library/audio-devices-rev-30-and-adopters-agreement)
* [miniDSP UMIK-1 product page](https://www.minidsp.com/products/acoustic-measurement/umik-1)
* [miniDSP UMIK-2 product page](https://www.minidsp.com/products/acoustic-measurement/umik-2)
* [IEC 61094 — Measurement microphone standards](https://www.iec.ch/homepage)
