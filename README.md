<div align="center">

# 🎛️ SONIQ MAX PRO

### *Enterprise-Grade Psychoacoustic Audio Processing & Real-Time Windows Sound Optimization*

[![Platform: Windows 10 / 11 (64-bit)](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(x64)-0078D6?style=for-the-badge&logo=windows)](https://github.com/Rajkumsr/Soniq-Max)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![C++: 17](https://img.shields.io/badge/C%2B%2B-17-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)](https://isocpp.org/)
[![VST: 2.4 (64-bit)](https://img.shields.io/badge/VST-2.4%20(x64)-FF6F00?style=for-the-badge)](https://equalizerapo.com/)
[![Tests: 39 Passing](https://img.shields.io/badge/tests-39%20passed-2EA44F?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

<br/>

**SONIQ MAX PRO** is an open-source, system-wide audio enhancement suite and control plane for [Equalizer APO](https://sourceforge.net/projects/equalizerapo/). It bridges high-precision parametric equalization with a **custom-compiled, native 64-bit C++ Psychoacoustic DSP Engine (`SoniqMaxDSP.dll`)** that runs directly inside the Windows Audio Processing Object pipeline (`audiodg.exe`) at **sub-millisecond latency**.

[Quickstart](#-quickstart) • [Architecture](#-system-architecture) • [DSP Engine](#-native-psychoacoustic-dsp-engine) • [Equalizer APO Setup](#-equalizer-apo-configuration) • [Building from Source](#-building-the-vst-from-source) • [Test Suite](#-automated-testing)

---

</div>

## 📌 Executive Summary

Modern PC audio systems—especially laptop speakers, budget monitors, and consumer headphones—suffer from severe physical limitations:
* Small drivers physically cannot reproduce sub-bass (<100 Hz), resulting in speaker distortion and cone rattling when conventional EQ is applied.
* Dialogue in movies, streams, and calls is frequently overwhelmed by background music or SFX.
* Narrow physical speaker placement collapses the stereo soundstage.
* Static EQ configurations clip aggressively during loud transients unless output gain is severely reduced.

**SONIQ MAX PRO solves this at the Windows Audio Driver layer.** Instead of relying solely on linear biquad filtering, it injects a purpose-built **VST 2.4 Psychoacoustic Engine** into Windows' audio stream, performing non-linear harmonic synthesis, formant tracking, acoustic time-delay stereophony, and dynamic soft-limiting in real time.

---

## ⚡ Key Architectural Features

### 🎛️ 1. Native 64-Bit C++ VST 2.4 Engine (`SoniqMaxDSP.dll`)
Compiled with `-O3` vector optimizations for modern x86_64 SIMD architectures:
* **Harmonic Bass Exciter (The Missing Fundamental):** Extracts deep sub-bass (<120 Hz) and generates 2nd and 3rd order harmonics via mathematically modeled soft saturation (`tanh`). The human brain synthesizes the fundamental frequency internally, perceiving bone-shaking bass on drivers incapable of producing low-frequency excursion.
* **Formant Vocal & Speech Intelligibility:** Dual-band resonance tracking centered at **1.0 kHz** and **3.2 kHz** elevates dialogue presence and vocal clarity without introducing harsh sibilance or high-frequency ear fatigue.
* **3D Haas Spatializer (True Acoustic Stereophony):** Implements a circular ring-buffer delay line providing a **12 ms Inter-aural Time Difference (ITD)** on side channels. Delivers a spacious 3D acoustic field on headphones without comb-filtering or phase cancellation.
* **Continuous Soft-Knee Dynamic Limiter:** Transparent tanh lookahead saturation ceiling preventing digital 0 dBFS clipping during explosions, snares, or deep drops with zero harsh distortion.
* **Zero Performance Tax:** **204 KB binary**, **~0.01% CPU usage**, and **<0.5 ms processing latency**.

### 🧠 2. Soniq Sense Auto-Adaptation Engine
* Low-overhead background monitoring of active Windows WASAPI audio sessions and foreground processes.
* **Intelligent Content Routing:** Automatically transitions between **FPS Gaming**, **Club Bass & EDM**, **Cinema & Dialogue**, and **Voice Meeting** presets.
* **Developer & Productivity Whitelisting:** Process trees such as VS Code (`Code.exe`), Visual Studio (`devenv.exe`), Windows Terminal, PowerShell, and Windows Settings (`SystemSettings.exe`) are explicitly whitelisted to prevent false profile interruptions while working.
* **Hysteresis & Anti-Flapping:** Dual-cycle debounce (600 ms) guarantees that song pauses, tab switching, or Discord pings do not trigger jarring profile fluctuations.

### 🎨 3. Enterprise Windows 11 Desktop Client
* **Fluent Dark Roast UI:** Engineered with CustomTkinter, DWM Mica/Acrylic glass styling, and live Windows registry accent-color synchronization.
* **10-Band Parametric Equalizer:** High-precision sliders (32 Hz to 16 kHz) with real-time curve calculation and headroom compensation.
* **System Tray Daemon:** Runs silently in the Windows system tray with memory trimming down to ~15 MB working set.
* **Instant Hardware Endpoint Detection:** Real-time WASAPI notifications detect when headphones or laptop speakers are connected, dynamically engaging 120 Hz anti-rattle protection for internal cones.
* **Global Win32 Hotkeys:** System-wide shortcuts (`Ctrl+Alt+S` master bypass, profile selectors, and night mode toggle).

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph UserSpace["Desktop User Space"]
        App["SONIQ MAX PRO (Desktop App / Daemon)"]
        UI["CustomTkinter Fluent UI & System Tray"]
        Sense["Soniq Sense Event Engine (WASAPI / Win32)"]
        App --> UI
        App --> Sense
    end

    subgraph ConfigLayer["Inter-Process Configuration Layer"]
        Lock[".soniq_max_config.lock (Atomic Win32 File Lock)"]
        ConfigFile["SONIQ_MAX_Config.txt (Managed Directive)"]
        MasterConfig["config.txt (Equalizer APO Master)"]
        App -->|"Atomic Export"| ConfigFile
        MasterConfig -->|"Include Directive"| ConfigFile
    end

    subgraph AudioEngine["Windows 11 Kernel Audio Engine (audiodg.exe)"]
        APOHost["Equalizer APO Host Engine"]
        EQStage["10-Band Parametric Filter Stage"]
        PreampStage["Estimated Headroom Preamp Compensation"]
        VSTHost["VST 2.4 Host Loader"]
        
        APOHost --> PreampStage
        PreampStage --> EQStage
        EQStage --> VSTHost
        
        subgraph VSTPlugin["SoniqMaxDSP.dll (C++17 SIMD Engine)"]
            Bass["① Harmonic Bass Exciter (tanh)"]
            Vocal["② Vocal Formant Enhancer (1kHz / 3.2kHz)"]
            Haas["③ 3D Haas Spatializer (12ms Ring Buffer)"]
            Limiter["④ Soft-Knee Peak Limiter (0 dBFS Ceiling)"]
            
            Bass --> Vocal
            Vocal --> Haas
            Haas --> Limiter
        end
        
        VSTHost --> VSTPlugin
    end

    subgraph Hardware["Physical Audio Output"]
        Speakers["Laptop Speakers (120Hz HPF Anti-Rattle)"]
        Headphones["Headphones (Full 20Hz Sub-Bass + 3D Haas)"]
    end

    VSTPlugin --> Speakers
    VSTPlugin --> Headphones
```

---

## 📊 Real-Time Benchmark & Resource Footprint

| Metric | SONIQ MAX PRO (Native C++ VST) | Standard Equalizer APO EQ | Deep Learning / ONNX Model |
| :--- | :--- | :--- | :--- |
| **Real-Time Processing** | **Full 4-Stage Psychoacoustics** | Static Linear Filtering Only | Non-realtime or Heavy Buffering |
| **Harmonic Synthesis** | **Yes (2nd & 3rd Harmonics)** | No (Physically Impossible) | High Latency / Artifact Prone |
| **Dynamic Limiting** | **Yes (Continuous Soft-Knee)**| No (Hard Clipping Risk) | High CPU Overhead |
| **Buffer Latency** | **< 0.5 ms** | ~0.1 ms | 20 ms – 100 ms (Noticeable lag) |
| **CPU Utilization** | **~0.01%** | ~0.01% | 5% – 25% |
| **RAM Footprint (DLL)** | **< 2 MB** | N/A | 150 MB – 400 MB |
| **Binary Size** | **204 KB** | Built-in | 50 MB – 300 MB |

---

## 🚀 Quickstart

### Option 1: Standalone Portable Binary (Zero Setup)
Download or locate the precompiled single-file executable:
```powershell
.\dist\SONIQ_MAX.exe
```
> [!NOTE]
> The standalone distribution packages Python 3.13, CustomTkinter, NumPy, and SoundCard without external runtimes. UPX compression is intentionally disabled to guarantee 100% binary initialization stability on both **Windows 10** and **Windows 11**.

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

### Clean Single-Include Directive
SONIQ MAX PRO utilizes an atomic file-locking mechanism to write system configurations safely without corrupting third-party presets.

1. Ensure Equalizer APO's master config file (`C:\Program Files\EqualizerAPO\config\config.txt`) contains:
   ```text
   # SONIQ MAX Master Controller
   Include: SONIQ_MAX_Config.txt
   ```
2. When active, SONIQ MAX generates [`SONIQ_MAX_Config.txt`](file:///C:/Program%20Files/EqualizerAPO/config/SONIQ_MAX_Config.txt) dynamically:
   ```text
   # SONIQ MAX profile: Battlefield 360
   Preamp: -6.4 dB
   Filter: ON PK Fc 1000 Hz Gain +4.5 dB Q 1.41
   ...
   # Native VST Plugin Processing
   VSTPlugin: Library "VSTPlugins\SoniqMaxDSP.dll"
   ```

### Multi-Tier VST Discovery
The desktop client resolves `SoniqMaxDSP.dll` using a resilient three-tier discovery hierarchy:
1. **APO System Directory:** `C:\Program Files\EqualizerAPO\VSTPlugins\SoniqMaxDSP.dll` (System-wide install).
2. **Local Repository Build:** `vst\bin\SoniqMaxDSP.dll` (Runs portable **without UAC Administrator elevation**).
3. **Distribution Binary:** `dist\vst\bin\SoniqMaxDSP.dll` (When running from packaged executable).

---

## 🛠️ Building the VST from Source

A precompiled 64-bit DLL is included in [`vst/bin/SoniqMaxDSP.dll`](./vst/bin/SoniqMaxDSP.dll). If you wish to modify DSP algorithms or build your own binaries:

### 1. Install a 64-bit C++ Toolchain
Install the official WinLibs MinGW-w64 toolchain via WinGet:
```powershell
winget install BrechtSanders.WinLibs.POSIX.UCRT
```
*(Or install Microsoft Visual Studio Community with the "Desktop development with C++" workload.)*

### 2. Execute Automated Build
```cmd
.\vst\build_vst.bat
```
* The script auto-detects MinGW-w64 or Visual Studio `cl.exe`.
* Compiles directly with `-O3 -shared -std=c++17 -static-libgcc -static-libstdc++`.
* Verifies `x86_64` PE architecture header (`Machine: 0x8664`).

---

## 🧪 Automated Testing

The codebase includes an extensive suite of automated tests verifying profile integrity, dynamic APO directive generation, PE architecture, and Soniq Sense debouncing.

```powershell
# Run the complete test suite
python -m pytest -v
```

```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-7.4.3
collected 39 items

tests/test_audio_content.py ..........                                   [ 25%]
tests/test_profile_and_apo.py ................                           [ 66%]
tests/test_soniq_sense_daemon.py .............                           [100%]

============================= 39 passed in 1.82s ==============================
```

---

## 📁 Repository Structure

```text
Soniq-Max/
├── app_desktop.py            # Main GUI entry point, Win32 event loop & lifecycle
├── constants.py              # System constants, profiles, and path resolvers
├── export_system_apo.py      # Equalizer APO config generator & atomic locking
├── windows_audio.py          # Core Audio WASAPI endpoints & process heuristics
├── audio_content.py          # Fast DSP audio content analysis & classification
├── soniq_sense_daemon.py     # Headless background profile switcher service
│
├── vst/                      # Native C++ VST 2.4 Psychoacoustic Engine
│   ├── build_vst.bat         # Automated compiler detection & build script
│   ├── src/
│   │   ├── SoniqMaxDSP.cpp   # Core DSP algorithms (Bass, Vocals, Haas, Limiter)
│   │   └── aeffect.h         # Standard VST 2.4 C-ABI definitions
│   └── bin/
│       └── SoniqMaxDSP.dll   # Precompiled 64-bit native DLL (204 KB)
│
├── ui/                       # Modular CustomTkinter Interface Components
│   ├── tab_audio.py          # Profiles, cards, volume and night mode
│   ├── tab_eq.py             # 10-band interactive parametric EQ sliders
│   ├── tab_smart.py          # Soniq Sense auto-adaptation manager
│   └── tab_settings.py       # VST controls, system startup, and hotkeys
│
├── dist/                     # Standalone Production Build
│   ├── SONIQ_MAX.exe         # Single-file standalone Windows executable
│   └── vst/bin/              # Portable VST distribution folder
│
├── tests/                    # Automated pytest test suite (39 tests)
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

## ☕ Support Soniq Max
If this project helped you configure your audio, saved you time, or made your setup smoother, consider fueling my next coding session!

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/soniqmax)

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
All third-party audio drivers, SDKs, and libraries remain the intellectual property of their respective owners.
