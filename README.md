<div align="center">

# 🎛️ SONIQ MAX PRO

### *Enterprise-Grade Psychoacoustic Audio Processing & Real-Time Windows Sound Optimization*
### *Engineered by CodeCraftersIndia*

[![Organization: CodeCraftersIndia](https://img.shields.io/badge/organization-CodeCraftersIndia-FF6F00?style=for-the-badge)](https://github.com/Rajkumsr/Soniq-Max)
[![Platform: Windows 10 / 11 (64-bit)](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(x64)-0078D6?style=for-the-badge&logo=windows)](https://github.com/Rajkumsr/Soniq-Max)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![C++: 17](https://img.shields.io/badge/C%2B%2B-17-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)](https://isocpp.org/)
[![VST: 2.4 (64-bit)](https://img.shields.io/badge/VST-2.4%20(x64)-FF6F00?style=for-the-badge)](https://equalizerapo.com/)
[![Python Tests: 51 Passing](https://img.shields.io/badge/pytest-51%20passed-2EA44F?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org/)
[![Native C++ Tests: 25 Passing](https://img.shields.io/badge/native%20tests-25%20passed-0078D6?style=for-the-badge)](https://github.com/Rajkumsr/Soniq-Max)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

<br/>

**SONIQ MAX PRO** is an open-source, system-wide audio enhancement suite and control plane for [Equalizer APO](https://sourceforge.net/projects/equalizerapo/) and direct Windows audio streams. It operates around a **custom-compiled, native 64-bit C++ Psychoacoustic DSP Engine (`SoniqMaxDSP.dll`)** that acts as the **Single Source of Truth (SSOT)** for all audio processing, executing directly inside the Windows Audio Processing Object pipeline (`audiodg.exe`) with **sub-millisecond latency** ($12.65\text{ }\mu\text{s}$ callback time).

[Quickstart](#-quickstart) • [Architecture](#-system-architecture) • [DSP Engine](#-native-psychoacoustic-dsp-engine) • [Equalizer APO Setup](#-equalizer-apo-configuration) • [Building from Source](#-building-the-vst-from-source) • [Test Suite](#-automated-testing)

---

</div>

## 📌 Executive Summary

Modern PC audio systems—especially laptop speakers, budget monitors, and consumer headphones—suffer from severe physical limitations:
* Small drivers physically cannot reproduce sub-bass (<100 Hz), resulting in speaker distortion and cone rattling when conventional EQ is applied.
* Dialogue in movies, streams, and calls is frequently overwhelmed by background music or SFX.
* Narrow physical speaker placement collapses the stereo soundstage.
* Static EQ configurations clip aggressively during loud transients unless output gain is severely reduced.

**SONIQ MAX PRO solves this at the Windows Audio Driver layer.** The native C++ VST engine owns 100% of the audio enhancement pipeline: 10-band parametric equalization, headroom preamp scaling, harmonic bass excitation, vocal clarity formant tracking, center-preserving spatial widening, and a genuine 4 ms lookahead brickwall peak limiter. Equalizer APO acts purely as the host pipe, eliminating all duplicate filtering and phase smear.

---

## ⚡ Key Architectural Features

* **10-Band Parametric Equalizer:** Native IIR biquad peaking filters (32 Hz, 64 Hz, 125 Hz, 250 Hz, 500 Hz, 1 kHz, 2 kHz, 4 kHz, 8 kHz, 16 kHz) with smooth parameter transitions and exact gain accuracy ($\pm 12\text{ dB}$).
* **Headroom Preamp Stage:** Ramped linear gain management ($10^{\text{Preamp}_{\text{dB}}/20}$) pulls digital levels down before boosting EQ, eliminating digital clipping.
* **Harmonic Bass Exciter (The Missing Fundamental):** Low-pass fundamental extraction (<130 Hz), 28 Hz subsonic protection, symmetrical 2nd-order ($s^2$ with 25 Hz DC blocker) and 3rd-order ($\tanh(2s) - 0.5s$) harmonic generation, and a dynamic wet/dry blend law.
* **Vocal Clarity & Presence Network:** Triple-stage formant network: $+5.5\text{ dB}$ formant boost at **2.9 kHz**, adaptive high-shelf de-esser at **7.5 kHz**, and a **300 Hz** lower-mid notch to eliminate boxiness.
* **Center-Preserving Mid/Side Spatializer:** Converts $L/R \to M/S$, expanding only the side stereo content while keeping dialogue and center images 100% intact (verified $100\%$ mono compatible with $< 6 \times 10^{-8}$ delta). Includes optional **HRTF Binaural** headphone soundstage with Interaural Time Differences (ITD) and head-shadow filtering.
* **True Lookahead Peak Limiter:** Preallocated $1024$-sample ($4\text{ ms}$) circular ring buffer with linked stereo peak detection, $1.0\text{ ms}$ attack, $60\text{ ms}$ release, and a hard $-0.2\text{ dBFS}$ ceiling ($0.9772$).
* **Sample-Rate-Aware Smoothing:** $30\text{ ms}$ one-pole parameter smoothers eliminate clicks, pops, and zipper noise during profile switches.
* **Zero Allocation in Audio Loop:** 100% preallocated static memory; zero `malloc`, zero heap allocations, zero locks in the real-time callback.

### 🧠 2. Soniq Sense Auto-Adaptation Engine
* Low-overhead background monitoring of active Windows WASAPI audio sessions and foreground processes.
* **Intelligent Content Routing:** Automatically transitions between **FPS Gaming**, **Club Bass & EDM**, **Cinema & Dialogue**, and **Voice Meeting** presets.
* **Developer & Productivity Whitelisting:** Process trees such as VS Code (`Code.exe`), Visual Studio (`devenv.exe`), Windows Terminal, PowerShell, and Windows Settings (`SystemSettings.exe`) are explicitly whitelisted to prevent false profile interruptions while working.
* **Hysteresis & Anti-Flapping:** Dual-cycle debounce (600 ms) guarantees that song pauses, tab switching, or Discord pings do not trigger jarring profile fluctuations.

### 🎨 3. Enterprise Windows 11 Desktop Client
* **Fluent Dark Roast UI:** Engineered with CustomTkinter, DWM Mica/Acrylic glass styling, and live Windows registry accent-color synchronization.
* **10-Band Interactive Graphic Equalizer:** High-precision vertical sliders (-12 to +12 dB) with preset curves (Flat, Bass Punch, Vocal Clear, Rock V-Curve, Cinema, Gaming).
* **Dual-Engine Architecture:** Choose between **Equalizer APO Mode** (zero latency system-wide via APO) or **Direct Soniq Engine** (pure Python ctypes pipeline streaming to physical outputs).
* **Instant Endpoint Detection:** Real-time WASAPI notifications detect when headphones or laptop speakers are connected, dynamically engaging 120 Hz anti-rattle protection for internal cones.
* **Global Win32 Hotkeys:** System-wide shortcuts (`Ctrl+Alt+S` master bypass, profile selectors, and night mode toggle).

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Windows System Audio Pipeline                        │
│          (Spotify • YouTube • Games • VLC • Discord • System)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│            Windows Audio Engine (audiodg.exe) + Equalizer APO          │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ 1. Master Config Include (SONIQ_MAX_Config.txt)                │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │                                    │
│   ┌───────────────────────────────▼────────────────────────────────┐   │
│   │ 2. Equalizer APO Host Layer (Zero Duplicate Filtering)         │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │                                    │
│   ┌───────────────────────────────▼────────────────────────────────┐   │
│   │ 3. SoniqMaxDSP.dll (Single Source of Truth 64-Bit VST 2.4)     │   │
│   │    ├── ① Headroom Preamp Stage (db-to-linear smooth ramping)   │   │
│   │    ├── ② 120 Hz Subsonic Highpass (Laptop Speaker Protection)  │   │
│   │    ├── ③ 10-Band Parametric EQ (32Hz to 16kHz Peaking Biquads) │   │
│   │    ├── ④ Harmonic Bass Exciter (2nd/3rd Harmonics + DC Blocker)│   │
│   │    ├── ⑤ Vocal Clarity Network (2.9kHz Formant + De-Esser)     │   │
│   │    ├── ⑥ Center-Preserving M/S Widener / HRTF Binaural Sound   │   │
│   │    ├── ⑦ Master Gain Output Trim Multiplier                    │   │
│   │    └── ⑧ True Lookahead Peak Limiter (4ms Buffer, -0.2 dBFS)   │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
└───────────────────────────────────┼────────────────────────────────────┘
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          ▼                                                   ▼
┌───────────────────────────────────┐               ┌───────────────────────────────────┐
│     Laptop / Internal Speakers    │               │       Headphones / External DAC   │
│    (120Hz Subsonic HPF Protected) │               │      (Full 20Hz Sub-Bass + 3D)    │
└───────────────────────────────────┘               └───────────────────────────────────┘
```

---

## 📊 Empirical Benchmarks & Performance Verification

Measured on Windows 11 (64-bit) under real-time audio conditions across processing block sizes:

| Processing Block Size | Measured Latency per Block | Real-time Processing Deadline | Real-Time Headroom | Estimated CPU Load |
| :--- | :--- | :--- | :--- | :--- |
| **64 samples** | **$12.65\text{ }\mu\text{s}$** | $1333.3\text{ }\mu\text{s}$ | **$105.4\times$ faster than real-time** | **$0.95\%$** |
| **128 samples** | **$23.63\text{ }\mu\text{s}$** | $2666.7\text{ }\mu\text{s}$ | **$112.8\times$ faster than real-time** | **$0.89\%$** |
| **256 samples** | **$44.52\text{ }\mu\text{s}$** | $5333.3\text{ }\mu\text{s}$ | **$119.8\times$ faster than real-time** | **$0.83\%$** |
| **512 samples** | **$90.77\text{ }\mu\text{s}$** | $10666.7\text{ }\mu\text{s}$ | **$117.6\times$ faster than real-time** | **$0.85\%$** |
| **1024 samples** | **$181.36\text{ }\mu\text{s}$** | $21333.3\text{ }\mu\text{s}$ | **$117.8\times$ faster than real-time** | **$0.85\%$** |

* **Real-Time Memory Delta:** **`+0.00 MB`** (Strict zero-allocation real-time safety over 100,000+ blocks).
* **APO Config Cache Speed:** **$1.8\text{ ms}$** (unnecessary disk writes skipped when settings are unchanged).

---

## 🚀 Quickstart

### Option 1: Standalone Portable Binary (Zero Setup)
Download or launch the precompiled standalone executable:
```powershell
.\dist\SONIQ_MAX\SONIQ_MAX.exe
```
> [!TIP]
> Built in `--onedir` portable folder mode with all C-extensions, OpenBLAS, and Python runtimes pre-extracted in `_internal\`. Includes bundled `SoniqMaxDSP.dll` and launches instantly without administrative rights.

### Option 2: Run from Source

#### Prerequisites
* Windows 10 or 11 (64-bit)
* Python 3.10 to 3.13
* [Equalizer APO 1.3+](https://sourceforge.net/projects/equalizerapo/) installed on the system drive.

```powershell
# 1. Clone repository
git clone https://github.com/Rajkumsr/Soniq-Max.git
cd "Soniq-Max"

# 2. Initialize virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install core dependencies
pip install -r requirements.txt

# 4. Launch Desktop Application
python app_desktop.py
```

---

## 🎛️ Equalizer APO Configuration

### Clean VST Single-Directive Integration
Equalizer APO's master config file (`C:\Program Files\EqualizerAPO\config\config.txt`) includes the managed configuration:
```text
# SONIQ MAX Master Controller
Include: SONIQ_MAX_Config.txt
```

When active, SONIQ MAX generates [`SONIQ_MAX_Config.txt`](file:///C:/Program%20Files/EqualizerAPO/config/SONIQ_MAX_Config.txt) dynamically without duplicate filters:
```text
# SONIQ MAX profile: Bass & EDM Beast
# Output mode: Speakers
# Engine mode: Equalizer APO (VST Host Only) · Native SONIQ MAX VST Engine
# All 10-band EQ, Preamp, Harmonic Bass, Clarity, Spatial, and Limiter processing
# are executed exclusively inside the native 64-bit VST DSP engine.

# Native VST Plugin Processing
VSTPlugin: Library "E:\RAJ\MyProjects\Soniq Max\vst\bin\SoniqMaxDSP.dll" Bass 0.9500 Clarity 0.5000 Spatial 0.2667 Limiter 1.0 MasterGain 1.0000 Preamp -2.7 EQEnable 1.0 BassEnable 1.0 ClarityEnable 1.0 SpatialEnable 1.0 EQ32Hz +4.0 EQ64Hz +6.0 EQ125Hz +5.0 EQ250Hz +0.0 EQ500Hz -1.0 EQ1kHz +0.0 EQ2kHz +2.0 EQ4kHz +3.0 EQ8kHz +4.5 EQ16kHz +4.0 SpeakerHPF 1.0
```

---

## 🛠️ Building the VST from Source

A precompiled 64-bit DLL is included in [`vst/bin/SoniqMaxDSP.dll`](./vst/bin/SoniqMaxDSP.dll). If you wish to build your own binaries:

### 1. Install a 64-bit C++ Toolchain
Install the official WinLibs MinGW-w64 toolchain via WinGet:
```powershell
winget install BrechtSanders.WinLibs.POSIX.UCRT
```
*(Or install Microsoft Visual Studio Community with "Desktop development with C++".)*

### 2. Execute Automated Build
```cmd
.\vst\build_vst.bat
```
* Compiles directly with: `g++ -O3 -shared -std=c++17 -Isrc -o bin/SoniqMaxDSP.dll src/SoniqMaxDSP.cpp -static -static-libgcc -static-libstdc++ -Wl,--kill-at`.

---

## 🧪 Automated Testing

The codebase includes automated test suites covering both native C++ DSP and Python system integration:

### 1. Python Test Suite (51 Tests)
```powershell
pytest tests/ -v
```
* Verifies profile schema bounds, headroom calculations, APO single-directive VST generation, duplicate filtering elimination, audio feature extraction, and Soniq Sense debounce heuristics.

### 2. Native C++ DSP Verification Target (25 Tests)
```powershell
.\vst\tests\test_dsp.exe
```
* Tests digital silence, harmonic synthesis, DC blocker offset, 10-band EQ peaking accuracy, headroom preamp linearity, module bypasses, lookahead limiter under $+12\text{ dB}$ overload, mid/side mono compatibility, 4 sample rates (44.1k to 96k Hz), 6 block sizes (32 to 1024), and NaN/Inf sanitization.

---

## 📁 Repository Structure

```text
Soniq-Max/
├── app_desktop.py            # Main GUI entry point, Win32 event loop & lifecycle
├── constants.py              # System constants, profiles, and path resolvers
├── export_system_apo.py      # Equalizer APO config generator (VST SSOT mode)
├── audio_bridge.py           # Direct VST streaming engine & WASAPI bridge
├── windows_audio.py          # Core Audio WASAPI endpoints & process heuristics
├── audio_content.py          # Fast DSP audio content analysis & classification
├── soniq_sense_daemon.py     # Headless background profile switcher service
│
├── vst/                      # Native C++ VST 2.4 Psychoacoustic Engine
│   ├── build_vst.bat         # Automated compiler detection & build script
│   ├── src/
│   │   ├── SoniqAther.hpp    # Pure C++ Decoupled SoniqAther DSP Engine (10-Band EQ, Limiter, Harmonics)
│   │   ├── SoniqVSTPlugin.cpp # VST 2.4 Adapter & Direct C-ABI Exports
│   │   └── aeffect.h         # Standard VST 2.4 C-ABI definitions
│   ├── tests/
│   │   ├── test_dsp.cpp      # Standalone 25-test Native C++ test harness
│   │   └── test_dsp.exe      # Compiled verification binary
│   └── bin/
│       ├── SoniqVSTPlugin.dll # Native 64-bit VST 2.4 DSP plugin (292 KB)
│       └── SoniqMaxDSP.dll   # Backward-compatible VST 2.4 DLL alias (292 KB)
│
├── ui/                       # Modular CustomTkinter Interface Components
│   ├── tab_audio.py          # Profiles, cards, volume and night mode
│   ├── tab_equalizer.py      # 10-band interactive parametric EQ sliders
│   ├── tab_smart_app.py      # Soniq Sense auto-adaptation manager
│   ├── tab_effects.py        # Direct Engine & device routing controls
│   └── tab_settings.py       # VST controls, system startup, and hotkeys
│
├── dist/                     # Portable Production Distribution
│   └── SONIQ_MAX/            # Complete portable onedir application folder
│       ├── SONIQ_MAX.exe     # Application launcher executable
│       └── _internal/        # Python runtime & SoniqMaxDSP.dll
│
├── tests/                    # Automated pytest test suite (51 tests)
│   ├── test_audio_bridge.py
│   ├── test_audio_content.py
│   ├── test_profile_and_apo.py
│   └── test_soniq_sense_daemon.py
│
├── SONIQ_MAX.spec            # PyInstaller production build specification
└── requirements.txt          # Python dependency manifest
```

---

## 🔒 Security & Privacy

* **100% Offline:** Zero telemetry, analytics, or outbound network calls.
* **Audio Privacy:** Soniq Sense inspects process metadata and local loopback buffers strictly in memory; no audio is recorded, saved to disk, or transmitted.
* **Non-Destructive:** Managed configurations are sandboxed to `SONIQ_MAX_Config.txt`, preserving existing Equalizer APO calibration curves.

---

## 🇮🇳 Engineered by CodeCraftersIndia

**SONIQ MAX PRO** is developed and maintained by **CodeCraftersIndia**.
Contributions, feature suggestions, and bug reports are warmly welcome via [GitHub Issues](https://github.com/Rajkumsr/Soniq-Max/issues).

---

## ☕ Support Soniq Max

If this project helped you configure your audio, saved you time, or made your setup smoother, consider fueling my next coding session! 

<a href="https://buymeacoffee.com/soniqmax" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="41" width="174"></a>

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
All third-party audio drivers, SDKs, and libraries remain the intellectual property of their respective owners.
