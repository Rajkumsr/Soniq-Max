# SONIQ MAX VST 2.4 DSP Plugin (`SoniqMaxDSP.dll`)

A dedicated 64-bit real-time VST 2.4 digital signal processing plugin designed for **Equalizer APO**.

## Features

1. **Psychoacoustic Harmonic Bass Exciter**:
   - Synthesizes 2nd (even) and 3rd (odd) harmonics from low frequencies (30–140 Hz).
   - Generates perceived deep sub-bass on small headphones, IEMs, and laptop speakers without physical driver distortion.
2. **Dynamic Vocal Presence & Clarity**:
   - Dynamic 2.8 kHz formant boost tailored for speech intelligibility, podcast clarity, and movie dialogue.
3. **3D Binaural Spatializer**:
   - Haas effect interaural delay (~0.33 ms) and stereo phase widening for an expanded 3D soundstage on headphones.
4. **Soft-Knee Brickwall Limiter**:
   - Cubic soft-clipping peak limiter preventing digital overs (0 dBFS inter-sample clipping) without having to lower master volume.

## How to Build

1. Open **Developer Command Prompt for Visual Studio** or any terminal with `g++` (MinGW) on PATH.
2. Navigate to this directory:
   ```cmd
   cd e:\RAJ\MyProjects\Soniq Max\vst
   build_vst.bat
   ```
3. The script compiles `bin\SoniqMaxDSP.dll` and installs it to `C:\Program Files\EqualizerAPO\VSTPlugins\SoniqMaxDSP.dll`.

## Equalizer APO Integration

In `config.txt` or `SONIQ_MAX_Config.txt`:
```text
VSTPlugin: Library "VSTPlugins\SoniqMaxDSP.dll"
```

