# SONIQ MAX PRO 🎛️

**SONIQ MAX PRO** is an advanced Windows 10/11 system-wide audio enhancement suite and intelligent controller for [Equalizer APO](https://equalizerapo.com/). It pairs parametric frequency sculpting with a **native 64-bit C++ Psychoacoustic DSP Engine (VST 2.4)** to deliver deep virtual sub-bass, crystal-clear dialogue, immersive 3D soundstages, and dynamic soft-limiting directly inside the Windows Audio Engine (`audiodg.exe`).

---

## ⚡ Key Capabilities

### 1. Native Psychoacoustic DSP Engine (VST 2.4 — `SoniqMaxDSP.dll`)
Unlike traditional static EQ that can only boost or cut existing frequencies, our custom-compiled 64-bit VST plugin runs real-time algorithmic DSP at 48 kHz:
- **Harmonic Bass Exciter (Missing Fundamental):** Synthesizes 2nd and 3rd order harmonics (<120 Hz) via gentle non-linear saturation, allowing laptop speakers and earbuds to reproduce deep, punchy sub-bass they physically cannot vibrate.
- **Formant Vocal & Dialogue Enhancer:** Dual-band resonance tracking (1.0 kHz and 3.2 kHz) that lifts spoken dialogue in movies, YouTube, podcasts, and calls without harsh treble or ear fatigue.
- **3D Haas Spatializer:** Inter-aural time delay (12 ms acoustic delay buffer on side channels) mimicking human binaural acoustics for an expansive, holographic headphone soundstage without phase cancellation.
- **Dynamic Soft-Knee Limiter:** Continuous lookahead `tanh` curve preventing harsh 0 dBFS digital clipping or distortion during loud transients, gunshots, or heavy bass drops.
- **Ultra-Low Footprint:** Compiled with C++17 `-O3` vector optimizations: **204 KB binary**, **~0.01% CPU**, and **<0.5 ms latency**.

### 2. Soniq Sense Auto-Adaptation Engine
- Continuously monitors active audio streams and foreground processes with zero lag.
- Automatically selects the ideal profile for **Music**, **FPS Gaming**, **Movies/Cinema**, and **Voice Calls**.
- **Smart Productivity Exclusions:** VS Code, Visual Studio, Windows Terminal, PowerShell, and Windows Settings are automatically whitelisted so background music playback remains uninterrupted.
- Fully debounced (600 ms hysteresis) to eliminate rapid profile flipping during song pauses or tab switching.

### 3. Precision EQ & Sound Profiles
- **6 Hand-Crafted Presets:** *Battlefield 360*, *Club Bass & EDM*, *Cinema & Dialogue*, *Laptop Lifesaver (Anti-Rattle 120Hz)*, *Voice Meeting*, and *Audiophile Flat*.
- **10-Band Parametric Equalizer:** Real-time interactive gain sliders across 32 Hz – 16 kHz.
- **Custom Profile Designer:** Create, save, and export your own custom frequency curves.
- **Night Mode:** Smart dialogue leveling that attenuates explosive dynamic peaks for comfortable late-night listening.

### 4. Native Windows 11 Experience
- **Fluent Dark Roast UI:** Crafted with CustomTkinter, DWM Mica/Acrylic glass styling, and active Windows accent-color synchronization.
- **System Tray Service:** Runs silently in the background with a minimal working set memory footprint (~15 MB).
- **Windows Boot Integration:** Auto-starts on logon directly to the system tray (`--minimized`).
- **Global Win32 Hotkeys:** Instant keyboard toggles (`Ctrl+Alt+S` master toggle, profile switching, and night mode).

---

## 🏗️ Architecture

```
Windows Audio Stream (Spotify / YouTube / Games / Discord)
   │
   ▼
audiodg.exe (Equalizer APO Host)
   ├── 1. Master Include: SONIQ_MAX_Config.txt
   ├── 2. Parametric EQ, High-Pass & Preamp Trim
   └── 3. SoniqMaxDSP.dll (Native 64-bit C++ VST Plugin)
            ├── ① Harmonic Bass Exciter
            ├── ② Vocal Formant Clarity
            ├── ③ 3D Haas Spatializer
            └── ④ Dynamic Soft-Knee Limiter
   │
   ▼
Output Hardware (Headphones / Laptop Speakers / External DAC)
```

---

## 🚀 Getting Started

### Option A: Standalone Executable (Recommended)
You can directly run the precompiled standalone executable:
```powershell
.\dist\SONIQ_MAX.exe
```
*(No Python installation or dependencies required.)*

### Option B: Run from Source

#### Prerequisites
- Windows 10 or 11 (64-bit)
- Python 3.10+
- [Equalizer APO 1.3+](https://sourceforge.net/projects/equalizerapo/) installed for system-wide processing.

#### Setup
```powershell
# Clone the repository
git clone https://github.com/Rajkumsr/Soniq-Max.git
cd "Soniq-Max"

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Launch SONIQ MAX
python app_desktop.py
```

---

## 🎛️ Equalizer APO Configuration

### Single-Include Integration
SONIQ MAX manages its own configuration file:
* **Target:** `C:\Program Files\EqualizerAPO\config\SONIQ_MAX_Config.txt`
* In Equalizer APO's master `config.txt`, simply ensure the include is present:
```text
# SONIQ MAX Master Controller
Include: SONIQ_MAX_Config.txt
```

### VST Plugin Discovery
SONIQ MAX automatically resolves `SoniqMaxDSP.dll` using a multi-path hierarchy:
1. `C:\Program Files\EqualizerAPO\VSTPlugins\SoniqMaxDSP.dll` (System-wide install)
2. `vst\bin\SoniqMaxDSP.dll` (Local project directory — **requires zero administrator privileges**)
3. `dist\vst\bin\SoniqMaxDSP.dll` (Portable distribution directory)

---

## 🛠️ Compiling the VST Plugin from Source

A precompiled 64-bit binary is already provided in [`vst/bin/SoniqMaxDSP.dll`](./vst/bin/SoniqMaxDSP.dll). If you wish to customize or recompile the C++ DSP algorithms:

1. Install **WinLibs MinGW-w64 (64-bit)** or **Visual Studio Community (MSVC)**:
   ```powershell
   winget install BrechtSanders.WinLibs.POSIX.UCRT
   ```
2. Run the automated build script:
   ```cmd
   .\vst\build_vst.bat
   ```
   *(Or click **Recompile** directly in the SONIQ MAX **Settings** tab.)*

---

## 🧪 Test Suite

SONIQ MAX includes comprehensive automated unit and integration tests covering profile generation, APO directive export, VST integration, and Soniq Sense heuristics.

Run the test suite with:
```powershell
python -m pytest
```

---

## 📁 Repository Structure

```text
Soniq Max/
├── app_desktop.py            # Main application window & UI lifecycle
├── constants.py              # Global constants, profiles, and path resolvers
├── export_system_apo.py      # Equalizer APO configuration generator
├── windows_audio.py          # Windows Core Audio APIs & process heuristics
├── audio_content.py          # Fast DSP stream classifier
├── soniq_sense_daemon.py     # Headless background profile switcher
├── vst/
│   ├── build_vst.bat         # Automated compiler detection & build script
│   ├── src/
│   │   ├── SoniqMaxDSP.cpp   # Native C++ VST 2.4 psychoacoustic plugin source
│   │   └── aeffect.h         # VST 2.4 C-ABI header definitions
│   └── bin/
│       └── SoniqMaxDSP.dll   # Precompiled 64-bit VST plugin
├── ui/                       # Modular CustomTkinter UI tabs
│   ├── tab_audio.py          # Sound profile selector & effect switches
│   ├── tab_eq.py             # 10-band parametric EQ sliders & curve visualizer
│   ├── tab_smart.py          # Soniq Sense auto-adaptation manager
│   └── tab_settings.py       # VST controls, system startup, and hotkeys
├── dist/                     # Standalone PyInstaller distribution
│   └── SONIQ_MAX.exe         # Single-file standalone executable
└── tests/                    # Automated pytest test suite
```

---

## ☕ Support Soniq Max
If this project helped you configure your audio, saved you time, or made your setup smoother, consider fueling my next coding session! 

<a href="https://buymeacoffee.com/soniqmax" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="41" width="174"></a>

## 📄 License

This project is licensed under the [MIT License](LICENSE).
