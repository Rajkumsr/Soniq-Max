"""
SONIQ MAX — Real-Time System Audio Bridge & Direct VST Pipeline.
Enables system-wide audio processing via SoniqMaxDSP.dll without Equalizer APO.

Routes audio captured from Windows (Virtual Audio Cable / loopback) through
our native C++ VST DSP engine, and streams directly to physical speakers or headphones.

Uses 100% pure Python math and ctypes buffers (zero NumPy dependency).
"""

import ctypes
import logging
import math
import os
import sys
import threading
import time
from typing import Dict, List, Optional, Sequence, Tuple

import sounddevice as sd

logger = logging.getLogger(__name__)

# VST 2.4 Protocol Constants
VST_MAGIC = 0x56737450       # 'VstP'
effOpen = 0
effClose = 1
effSetSampleRate = 10
effSetBlockSize = 11
effGetParamName = 8
effGetEffectName = 45

# SoniqMaxDSP Parameter Indices (Single Source of Truth)
PARAM_BASS_BOOST = 0     # 0.0 - 1.0 (Harmonic Bass Exciter)
PARAM_CLARITY = 1        # 0.0 - 1.0 (Vocal Formant Clarity)
PARAM_SPATIAL = 2        # 0.0 - 1.0 (3D Spatializer)
PARAM_LIMITER = 3        # 0.0 or 1.0 (Lookahead Peak Limiter)
PARAM_MASTER_GAIN = 4    # 0.0 - 4.0 (Output Gain Multiplier, default 1.0)
PARAM_SPATIAL_MODE = 5   # 0.0 = Mid/Side Stereo, 1.0 = HRTF Binaural
PARAM_CEILING = 6        # Limiter Ceiling Linear (default 0.9772 = -0.2 dBFS)
PARAM_PREAMP = 7         # Preamp Gain in dB (-24.0 to +12.0 dB)
PARAM_EQ_ENABLE = 8      # 10-Band EQ On/Off (0.0 or 1.0)
PARAM_BASS_ENABLE = 9    # Bass Module On/Off (0.0 or 1.0)
PARAM_CLARITY_ENABLE = 10# Clarity Module On/Off (0.0 or 1.0)
PARAM_SPATIAL_ENABLE = 11# Spatial Module On/Off (0.0 or 1.0)
PARAM_EQ_32HZ = 12       # Band 0: 32 Hz
PARAM_EQ_64HZ = 13       # Band 1: 64 Hz
PARAM_EQ_125HZ = 14      # Band 2: 125 Hz
PARAM_EQ_250HZ = 15      # Band 3: 250 Hz
PARAM_EQ_500HZ = 16      # Band 4: 500 Hz
PARAM_EQ_1KHZ = 17       # Band 5: 1000 Hz
PARAM_EQ_2KHZ = 18       # Band 6: 2000 Hz
PARAM_EQ_4KHZ = 19       # Band 7: 4000 Hz
PARAM_EQ_8KHZ = 20       # Band 8: 8000 Hz
PARAM_EQ_16KHZ = 21      # Band 9: 16000 Hz
PARAM_SPEAKER_HPF = 22   # Speaker 120Hz HPF (0.0 = Full-Range, 1.0 = Speaker HPF)


# Ctypes VST Structures
class AEffect(ctypes.Structure):
    pass


DISPATCHER_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_int64, ctypes.POINTER(AEffect), ctypes.c_int32, ctypes.c_int32,
    ctypes.c_int64, ctypes.c_void_p, ctypes.c_float
)
PROCESS_PROC = ctypes.WINFUNCTYPE(
    None, ctypes.POINTER(AEffect), ctypes.POINTER(ctypes.POINTER(ctypes.c_float)),
    ctypes.POINTER(ctypes.POINTER(ctypes.c_float)), ctypes.c_int32
)
SET_PARAM_PROC = ctypes.WINFUNCTYPE(
    None, ctypes.POINTER(AEffect), ctypes.c_int32, ctypes.c_float
)
GET_PARAM_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_float, ctypes.POINTER(AEffect), ctypes.c_int32
)

AEffect._fields_ = [
    ('magic', ctypes.c_int32),
    ('dispatcher', DISPATCHER_PROC),
    ('process', PROCESS_PROC),
    ('setParameter', SET_PARAM_PROC),
    ('getParameter', GET_PARAM_PROC),
    ('numPrograms', ctypes.c_int32),
    ('numParams', ctypes.c_int32),
    ('numInputs', ctypes.c_int32),
    ('numOutputs', ctypes.c_int32),
    ('flags', ctypes.c_int32),
    ('resvd1', ctypes.c_int64),
    ('resvd2', ctypes.c_int64),
    ('initialDelay', ctypes.c_int32),
    ('realQualities', ctypes.c_int32),
    ('offQualities', ctypes.c_int32),
    ('ioRatio', ctypes.c_float),
    ('object', ctypes.c_void_p),
    ('user', ctypes.c_void_p),
    ('uniqueID', ctypes.c_int32),
    ('version', ctypes.c_int32),
    ('processReplacing', PROCESS_PROC),
    ('processDoubleReplacing', ctypes.c_void_p),
    ('future', ctypes.c_char * 56),
]

MASTER_CALLBACK = ctypes.WINFUNCTYPE(
    ctypes.c_int64, ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32,
    ctypes.c_int64, ctypes.c_void_p, ctypes.c_float
)


def _dummy_master(eff, op, idx, val, ptr, opt):
    return 0


class VstDirectEngine:
    """
    Zero-overhead native C++ VST 2.4 loader and processor.
    Pre-allocates C-contiguous float32 ctypes buffers and pointers to achieve
    sub-millisecond execution times without garbage collection pauses.
    Uses pure standard library math and ctypes (no NumPy).
    """
    def __init__(self, dll_path: str, sample_rate: int = 48000, max_block_size: int = 2048):
        self.dll_path = os.path.abspath(dll_path)
        self.sample_rate = sample_rate
        self.max_block_size = max_block_size
        self._master_cb = MASTER_CALLBACK(_dummy_master)
        self.plugin = None
        self.lib = None

        # Pre-allocated aligned ctypes buffers for zero-allocation real-time streaming
        ArrayType = ctypes.c_float * max_block_size
        self.buf_in_l = ArrayType()
        self.buf_in_r = ArrayType()
        self.buf_out_l = ArrayType()
        self.buf_out_r = ArrayType()

        self.ptr_in_l = ctypes.cast(self.buf_in_l, ctypes.POINTER(ctypes.c_float))
        self.ptr_in_r = ctypes.cast(self.buf_in_r, ctypes.POINTER(ctypes.c_float))
        self.ptr_out_l = ctypes.cast(self.buf_out_l, ctypes.POINTER(ctypes.c_float))
        self.ptr_out_r = ctypes.cast(self.buf_out_r, ctypes.POINTER(ctypes.c_float))

        self.in_ptrs = (ctypes.POINTER(ctypes.c_float) * 2)(self.ptr_in_l, self.ptr_in_r)
        self.out_ptrs = (ctypes.POINTER(ctypes.c_float) * 2)(self.ptr_out_l, self.ptr_out_r)

        self._load_plugin()

    def _load_plugin(self):
        if not os.path.isfile(self.dll_path):
            raise FileNotFoundError(f"SoniqMaxDSP.dll not found at: {self.dll_path}")

        dll_dir = os.path.dirname(self.dll_path)
        if hasattr(os, "add_dll_directory") and os.path.exists(dll_dir):
            try:
                os.add_dll_directory(dll_dir)
            except Exception:
                pass

        self.lib = ctypes.CDLL(self.dll_path)
        if not hasattr(self.lib, "VSTPluginMain"):
            raise AttributeError("DLL does not export VSTPluginMain entry point")

        self.lib.VSTPluginMain.restype = ctypes.POINTER(AEffect)
        self.lib.VSTPluginMain.argtypes = [MASTER_CALLBACK]

        self.plugin = self.lib.VSTPluginMain(self._master_cb)
        if not self.plugin:
            raise RuntimeError("VSTPluginMain returned NULL")

        # Handshake with VST host protocol
        self.plugin.contents.dispatcher(self.plugin, effOpen, 0, 0, None, 0.0)
        self.plugin.contents.dispatcher(self.plugin, effSetSampleRate, 0, 0, None, float(self.sample_rate))
        self.plugin.contents.dispatcher(self.plugin, effSetBlockSize, 0, self.max_block_size, None, 0.0)

        # Set safe default parameters
        self.set_param(PARAM_BASS_BOOST, 0.35)
        self.set_param(PARAM_CLARITY, 0.40)
        self.set_param(PARAM_SPATIAL, 0.25)
        self.set_param(PARAM_LIMITER, 1.0)
        self.set_param(PARAM_MASTER_GAIN, 1.0)

    def set_param(self, index: int, value: float):
        if self.plugin:
            self.plugin.contents.setParameter(self.plugin, index, float(value))

    def get_param(self, index: int) -> float:
        if self.plugin:
            return self.plugin.contents.getParameter(self.plugin, index)
        return 0.0

    def process(self, in_left: Sequence[float], in_right: Sequence[float]) -> Tuple[List[float], List[float]]:
        """
        Pure ctypes real-time DSP processing (zero NumPy dependency).
        Loads inputs into aligned C-float buffers and runs C++ SIMD DSP.
        """
        n_frames = min(len(in_left), self.max_block_size)
        for i in range(n_frames):
            self.buf_in_l[i] = float(in_left[i])
            self.buf_in_r[i] = float(in_right[i])

        self.plugin.contents.processReplacing(self.plugin, self.in_ptrs, self.out_ptrs, n_frames)
        return list(self.buf_out_l[:n_frames]), list(self.buf_out_r[:n_frames])

    def close(self):
        if self.plugin:
            try:
                self.plugin.contents.dispatcher(self.plugin, effClose, 0, 0, None, 0.0)
            except Exception:
                pass
            self.plugin = None


class AudioBridge:
    """
    Manages real-time audio interception and hardware playback.
    Directly streams between a virtual input device (or loopback) and
    the physical sound card via VstDirectEngine.
    Pure math implementation with zero NumPy requirement.
    """
    def __init__(self, dll_path: Optional[str] = None, sample_rate: int = 48000, block_size: int = 1024):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.max_block_size = block_size * 2
        self.dll_path = dll_path or self._find_vst_dll()

        self.vst_engine: Optional[VstDirectEngine] = None
        self.stream: Optional[sd.Stream] = None
        self.is_running = False
        self.master_effects_on = True

        # Active parameters
        self.param_bass = 0.35
        self.param_clarity = 0.40
        self.param_spatial = 0.25
        self.param_volume = 1.0
        self.param_limiter = 1.0
        self.is_headphone = False

        # Live telemetry (thread-safe scalar values using pure math)
        self.peak_in_l = 0.0
        self.peak_in_r = 0.0
        self.peak_out_l = 0.0
        self.peak_out_r = 0.0
        self.underruns = 0
        self.last_status_msg = "Initialized"

        # Selected devices (None = auto-detect)
        self.input_device_id: Optional[int] = None
        self.output_device_id: Optional[int] = None

        self._lock = threading.Lock()
        self._init_vst()

    def _find_vst_dll(self) -> str:
        candidates = [
            os.path.join(os.path.dirname(__file__), "vst", "bin", "SoniqVSTPlugin.dll"),
            os.path.join(os.path.dirname(__file__), "vst", "bin", "SoniqMaxDSP.dll"),
            r"C:\Program Files\EqualizerAPO\VSTPlugins\SoniqVSTPlugin.dll",
            r"C:\Program Files\EqualizerAPO\VSTPlugins\SoniqMaxDSP.dll",
            os.path.join(os.path.dirname(__file__), "SoniqVSTPlugin.dll"),
            os.path.join(os.path.dirname(__file__), "SoniqMaxDSP.dll"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return os.path.abspath(p)
        return os.path.abspath(candidates[0])

    def _init_vst(self):
        try:
            if os.path.isfile(self.dll_path):
                self.vst_engine = VstDirectEngine(self.dll_path, self.sample_rate, self.max_block_size)
                self.last_status_msg = "VST DLL Loaded"
                logger.info("VstDirectEngine initialized with %s", self.dll_path)
            else:
                self.last_status_msg = f"VST DLL missing at: {self.dll_path}"
                logger.warning(self.last_status_msg)
        except Exception as e:
            self.last_status_msg = f"VST Load Error: {e}"
            logger.exception("Failed to load VST direct engine")

    @staticmethod
    def get_audio_devices() -> Dict[str, List[Dict]]:
        """Enumerates all input and output devices with metadata."""
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()

        inputs = []
        outputs = []

        for idx, dev in enumerate(devices):
            api_name = hostapis[dev['hostapi']]['name']
            info = {
                "id": idx,
                "name": dev["name"],
                "api": api_name,
                "in_channels": dev["max_input_channels"],
                "out_channels": dev["max_output_channels"],
                "default_sr": dev["default_samplerate"],
            }
            if dev["max_input_channels"] > 0:
                inputs.append(info)
            if dev["max_output_channels"] > 0:
                outputs.append(info)

        return {"inputs": inputs, "outputs": outputs}

    @classmethod
    def find_virtual_cable_input(cls) -> Optional[int]:
        """Looks for common virtual audio cable input endpoints."""
        devs = cls.get_audio_devices()["inputs"]
        # Prefer WASAPI Virtual Cable first, then MME/DirectSound
        virtual_keywords = ["cable output", "vb-audio", "virtual cable", "voicemeeter", "line in"]
        
        # Pass 1: WASAPI virtual device
        for d in devs:
            lower = d["name"].lower()
            if "wasapi" in d["api"].lower() and any(k in lower for k in virtual_keywords):
                return d["id"]
        
        # Pass 2: Any host API virtual device
        for d in devs:
            lower = d["name"].lower()
            if any(k in lower for k in virtual_keywords):
                return d["id"]

        # Pass 3: Stereo Mix (fallback if available)
        for d in devs:
            if "stereo mix" in d["name"].lower() and "wasapi" in d["api"].lower():
                return d["id"]

        return None

    @classmethod
    def find_physical_output(cls, preferred_name: Optional[str] = None) -> Optional[int]:
        """Finds the best physical output device (Speakers / Headphones)."""
        devs = cls.get_audio_devices()["outputs"]
        
        # If user has a preferred device name
        if preferred_name:
            p_lower = preferred_name.lower()
            for d in devs:
                if p_lower in d["name"].lower() and "wasapi" in d["api"].lower():
                    return d["id"]
            for d in devs:
                if p_lower in d["name"].lower():
                    return d["id"]

        # Auto-match standard physical speakers/headphones
        physical_keywords = ["speakers", "headphones", "realtek", "creative", "headset"]
        virtual_keywords = ["cable", "vb-audio", "voicemeeter", "virtual"]

        # Pass 1: WASAPI physical output that is NOT virtual
        for d in devs:
            lower = d["name"].lower()
            if "wasapi" in d["api"].lower():
                if any(k in lower for k in physical_keywords) and not any(v in lower for v in virtual_keywords):
                    return d["id"]

        # Pass 2: Any physical output that is NOT virtual
        for d in devs:
            lower = d["name"].lower()
            if any(k in lower for k in physical_keywords) and not any(v in lower for v in virtual_keywords):
                return d["id"]

        # Pass 3: Default system output
        return sd.default.device[1]

    def set_devices(self, input_id: Optional[int], output_id: Optional[int]):
        """Configures specific input and output endpoints and restarts stream if active."""
        restart = self.is_running
        if restart:
            self.stop()
        self.input_device_id = input_id
        self.output_device_id = output_id
        if restart:
            self.start()

    def update_from_profile(self, profile: Dict, is_headphone: bool = False, master_effects_on: bool = True):
        """Dispatches profile parameters directly into the live VST engine in RAM."""
        with self._lock:
            self.master_effects_on = master_effects_on
            self.is_headphone = is_headphone

            # Bass & clarity: 0.0 - 1.0 (normalize if passed as 0-100 percentage)
            raw_bass = float(profile.get("bass", 35.0))
            self.param_bass = raw_bass / 100.0 if raw_bass > 1.0 else raw_bass

            raw_clarity = float(profile.get("clarity", 40.0))
            self.param_clarity = raw_clarity / 100.0 if raw_clarity > 1.0 else raw_clarity

            raw_spatial = float(profile.get("spatial", 25.0))
            self.param_spatial = raw_spatial / 100.0 if raw_spatial > 1.0 else raw_spatial

            # Master Gain / Volume calculation:
            # Handles both decibels (e.g. 5.5 dB boost) and legacy linear/percentage values
            if "volume_db" in profile:
                vol_db = float(profile["volume_db"])
                self.param_volume = 10.0 ** (vol_db / 20.0)
            elif "volume" in profile:
                v = float(profile["volume"])
                if v <= 20.0:
                    # Decibel boost (e.g. 0.0 dB to 12.0 dB)
                    self.param_volume = 10.0 ** (v / 20.0)
                else:
                    # Percentage / linear scale (e.g. 90.0 -> 0.90)
                    self.param_volume = v / 100.0
            else:
                self.param_volume = 1.0

            self.param_limiter = 1.0

            # 10-Band EQ & Preamp parameters
            raw_eq = profile.get("eq", [0.0] * 10)
            if not isinstance(raw_eq, (list, tuple)) or len(raw_eq) != 10:
                raw_eq = [0.0] * 10

            preamp_db = float(profile.get("preamp", 0.0))

            if self.vst_engine:
                self.vst_engine.set_param(PARAM_BASS_BOOST, self.param_bass)
                self.vst_engine.set_param(PARAM_CLARITY, self.param_clarity)
                self.vst_engine.set_param(PARAM_SPATIAL, self.param_spatial)
                self.vst_engine.set_param(PARAM_LIMITER, self.param_limiter)
                self.vst_engine.set_param(PARAM_MASTER_GAIN, self.param_volume)
                self.vst_engine.set_param(PARAM_SPATIAL_MODE, 1.0 if is_headphone else 0.0)
                self.vst_engine.set_param(PARAM_PREAMP, preamp_db)
                self.vst_engine.set_param(PARAM_EQ_ENABLE, 1.0)
                self.vst_engine.set_param(PARAM_BASS_ENABLE, 1.0 if self.param_bass > 0.005 else 0.0)
                self.vst_engine.set_param(PARAM_CLARITY_ENABLE, 1.0 if self.param_clarity > 0.005 else 0.0)
                self.vst_engine.set_param(PARAM_SPATIAL_ENABLE, 1.0 if self.param_spatial > 0.005 else 0.0)
                self.vst_engine.set_param(PARAM_SPEAKER_HPF, 0.0 if is_headphone else 1.0)

                for b in range(10):
                    self.vst_engine.set_param(PARAM_EQ_32HZ + b, float(raw_eq[b]))

    def _audio_callback(self, indata, outdata, frames, time_info, status):
        """
        High-performance real-time audio callback.
        Pure math & ctypes implementation with zero Python list or heap allocations inside loop.
        """
        if status:
            self.underruns += 1

        n_frames = min(frames, self.max_block_size)
        vol = self.param_volume

        peak_in_l = 0.0
        peak_in_r = 0.0

        if not self.master_effects_on or not self.vst_engine:
            # Clean bypass: pass through at unity gain (true system passthrough)
            for i in range(n_frames):
                l_val = float(indata[i, 0])
                r_val = float(indata[i, 1]) if getattr(indata, "shape", (0, 2))[1] > 1 else l_val

                al = abs(l_val)
                ar = abs(r_val)
                if al > peak_in_l:
                    peak_in_l = al
                if ar > peak_in_r:
                    peak_in_r = ar

                outdata[i, 0] = l_val
                outdata[i, 1] = r_val

            self.peak_in_l = peak_in_l
            self.peak_in_r = peak_in_r
            self.peak_out_l = peak_in_l
            self.peak_out_r = peak_in_r
        else:
            # Stream directly into pre-allocated VST float32 buffers
            vst = self.vst_engine
            has_stereo = getattr(indata, "shape", (0, 2))[1] > 1

            for i in range(n_frames):
                l_val = float(indata[i, 0])
                r_val = float(indata[i, 1]) if has_stereo else l_val

                al = abs(l_val)
                ar = abs(r_val)
                if al > peak_in_l:
                    peak_in_l = al
                if ar > peak_in_r:
                    peak_in_r = ar

                vst.buf_in_l[i] = l_val
                vst.buf_in_r[i] = r_val

            # Process through native C++ VST DSP (SoniqMaxDSP.dll)
            # Master Gain and soft-knee brickwall limiter are applied inside C++ VST
            vst.plugin.contents.processReplacing(vst.plugin, vst.in_ptrs, vst.out_ptrs, n_frames)

            # Output processed stream directly from VST buffers
            peak_out_l = 0.0
            peak_out_r = 0.0
            for i in range(n_frames):
                out_l = vst.buf_out_l[i]
                out_r = vst.buf_out_r[i]
                outdata[i, 0] = out_l
                outdata[i, 1] = out_r

                al = abs(out_l)
                ar = abs(out_r)
                if al > peak_out_l:
                    peak_out_l = al
                if ar > peak_out_r:
                    peak_out_r = ar

            self.peak_in_l = peak_in_l
            self.peak_in_r = peak_in_r
            self.peak_out_l = peak_out_l
            self.peak_out_r = peak_out_r

    def start(self) -> bool:
        """Starts real-time system audio streaming."""
        if self.is_running:
            return True

        in_dev = self.input_device_id if self.input_device_id is not None else self.find_virtual_cable_input()
        out_dev = self.output_device_id if self.output_device_id is not None else self.find_physical_output()

        if in_dev is None or out_dev is None:
            self.last_status_msg = f"Cannot start: In={in_dev}, Out={out_dev}"
            logger.warning(self.last_status_msg)
            return False

        try:
            self.stream = sd.Stream(
                device=(in_dev, out_dev),
                channels=2,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                dtype="float32",
                latency="high",
                callback=self._audio_callback
            )
            self.stream.start()
            self.is_running = True
            devs = sd.query_devices()
            in_name = devs[in_dev]['name']
            out_name = devs[out_dev]['name']
            self.last_status_msg = f"Active: {in_name[:18]} → {out_name[:18]}"
            logger.info("AudioBridge streaming started: %s", self.last_status_msg)
            return True
        except Exception as e:
            self.last_status_msg = f"Stream start failed: {e}"
            logger.exception("Failed to start AudioBridge stream")
            return False

    def stop(self):
        """Stops real-time streaming cleanly."""
        self.is_running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self.last_status_msg = "Stopped"

    def close(self):
        self.stop()
        if self.vst_engine:
            self.vst_engine.close()
            self.vst_engine = None


if __name__ == "__main__":
    print("=== SONIQ MAX — DIRECT AUDIO PIPELINE DIAGNOSTIC (PURE MATH) ===")
    devices = AudioBridge.get_audio_devices()
    print(f"\nDiscovered {len(devices['inputs'])} Inputs and {len(devices['outputs'])} Outputs.")

    virt_in = AudioBridge.find_virtual_cable_input()
    phys_out = AudioBridge.find_physical_output()

    print(f"Auto-detected Input Endpoint:  {virt_in} ({sd.query_devices(virt_in)['name'] if virt_in is not None else 'None'})")
    print(f"Auto-detected Output Endpoint: {phys_out} ({sd.query_devices(phys_out)['name'] if phys_out is not None else 'None'})")

    bridge = AudioBridge()
    print(f"VST Engine Status: {bridge.last_status_msg}")
    if bridge.vst_engine:
        print("✓ VST 2.4 DLL loaded and verified!")
        print(f"  Bass Boost:   {bridge.vst_engine.get_param(PARAM_BASS_BOOST)}")
        print(f"  Vocal Clarity:{bridge.vst_engine.get_param(PARAM_CLARITY)}")
        print(f"  3D Spatial:   {bridge.vst_engine.get_param(PARAM_SPATIAL)}")
        print(f"  Limiter:      {bridge.vst_engine.get_param(PARAM_LIMITER)}")
        print(f"  Master Gain:  {bridge.vst_engine.get_param(PARAM_MASTER_GAIN)}")
