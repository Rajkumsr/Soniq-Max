# SONIQ MAX

SONIQ MAX is a Windows desktop utility for selecting audio profiles and generating Equalizer APO filters. The interface uses CustomTkinter; Windows Core Audio APIs are used for endpoint detection and audio-session tracking.

## What it does

- Provides six built-in EQ profiles, custom profiles, and a 10-band EQ.
- Uses the bundled YAMNet AudioSet model (521 sound labels) locally for browser playback classification. Known local music-player apps use app rules and do not invoke the model. Soniq Sense automatically adapts profiles for games, music, speech/calls, and other playback.
- The SONIQ SENSE tab keeps automatic switching simple: turn it on and optionally choose which preset is used for each detected category. Automatic changes apply in the background without changing the visible manual profile selection or showing detection diagnostics.
- Generates profile EQ, bass and vocal-presence shaping, speaker high-pass filters, stereo channel mixing, and estimated peak headroom compensation.
- Provides a system tray icon, global hotkeys, and an optional Windows startup entry.
- Writes its filters to its own managed `SONIQ_MAX_Config.txt` file and adds an `Include` line to Equalizer APO's main configuration. Existing config text is retained.

## What it does not do

SONIQ MAX itself does not yet process audio buffers; Equalizer APO applies its generated filters in the system audio path. EQ, bass shaping, voice presence, channel mixing, and headroom compensation are static; there is no dynamic limiter/compressor, bass-harmonic synthesis, or HRTF binaural processing. Headroom compensation reduces estimated filter-peak clipping risk but is not a hard limiter and cannot account for the source signal or other APO filters. Night Mode subtracts 2 dB from the requested output-level target before headroom compensation.

Automatic profile switching combines process/window heuristics with the bundled offline YAMNet model for browser playback. Known local music players take the fast app-rule path without loading/running the content classifier. YAMNet scores broad AudioSet labels; mixed or unusual content can be misclassified. Playback samples are analyzed in memory only and are not saved or transmitted. The app needs Windows playback-loopback access for browser analysis; no microphone capture is used. Soniq Sense preset assignments are saved with the app settings.

## Headless Soniq Sense daemon

`soniq_sense_daemon.py` runs profile switching without the desktop interface. Fast app rules handle known local music players and call applications; the existing foreground-app classifier handles supported games. These paths do not open loopback capture or run the model. Foreground browsers use YAMNet to distinguish music from speech in the system playback mix. A profile changes only after two or three successive matching decisions.

Run it from the project directory after installing the requirements:

```powershell
.\.venv\Scripts\python.exe .\soniq_sense_daemon.py
```

By default, the daemon targets the Windows default playback device, writes to the configured Equalizer APO main config, polls every 250 ms, requires three matching decisions, and records rotating logs under `%LOCALAPPDATA%\SONIQ_MAX\soniq_sense.log`. Options include `--device "Realtek"` to select an endpoint by name, `--config "C:\path\to\config.txt"` to override the APO path, `--poll-interval 0.5`, `--debounce 2`, `--log-file "C:\path\to\soniq_sense.log"`, and `--quiet` to disable console logging. Run `.\.venv\Scripts\python.exe .\soniq_sense_daemon.py --help` for the full list.

SoundCard supplies shared-mode float32 loopback and cannot guarantee native 24-bit capture. Browser analysis uses the default output mix, not an isolated browser audio stream, so other apps playing simultaneously may affect classification. The daemon analyzes one-second, overlapping playback windows after downsampling a copy to 16 kHz mono; normal playback remains at the device's configured rate. Do not run the daemon alongside the desktop app's automatic profile switching: both can write profiles, and although writes are serialized, profile ownership is not coordinated. Stop the daemon with Ctrl+C.

## Requirements

- Windows 10 or 11
- Python 3.10 or later for running from source
- NumPy, SoundCard, and ONNX Runtime (installed by `requirements.txt`) for offline inference and playback-loopback analysis
- Equalizer APO for system-wide filtering (optional; without it, the app only writes a local config)

## Run from source

If a packaged `SONIQ_MAX.exe` is present, you can launch it directly.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app_desktop.py
```

Alternatively, install the dependencies and launch `run_desktop.bat`.

## Equalizer APO integration

The default main config path is:

`C:\Program Files\EqualizerAPO\config\config.txt`

If your installation uses another path, set `SONIQ_MAX_APO_CONFIG_PATH` to the full path of its main `config.txt` before launching the app. SONIQ MAX writes its generated filters to `SONIQ_MAX_Config.txt` in that directory and adds an `Include: SONIQ_MAX_Config.txt` line to the main config if it is not already present. It does not replace existing config text. Updating files under Program Files may require running the app with appropriate permissions.

The app also writes a local `SONIQ_APO_Config.txt` beside the application. If Equalizer APO is not found or cannot be updated, the status area reports the issue and the local config remains available.

Bypass replaces SONIQ MAX's managed filter content with a neutral preamp config. Other filters in Equalizer APO's main config continue to run.

## Build the Windows executable

Install PyInstaller, then build from the project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --clean SONIQ_MAX.spec
```

The executable is produced under `dist\SONIQ_MAX.exe`.

## Tests

Run the profile, APO filter-response, and YAMNet tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Configuration files

- `active_profile.json`: active profile key and application toggles.
- `custom_presets.json`: validated user-created profiles.
- `SONIQ_APO_Config.txt`: local generated filter file.
- `SONIQ_MAX_Config.txt`: managed Equalizer APO filter file when integration is enabled.
- `models\yamnet\`: bundled YAMNet ONNX model, AudioSet class map, and Apache-2.0 license.

## Model attribution

The bundled [`yamnet.onnx`](./models/yamnet/yamnet.onnx) is a format conversion of [Google YAMNet v1](https://tfhub.dev/google/yamnet/1), trained on AudioSet and distributed from [audiomagic/yamnet-onnx](https://huggingface.co/audiomagic/yamnet-onnx). The upstream model and code are licensed under Apache-2.0; the AudioSet class labels are released under CC BY 4.0. The full Apache license and class map are included in `models\yamnet\`. Inference uses ONNX Runtime's CPU execution provider and does not require network access.
