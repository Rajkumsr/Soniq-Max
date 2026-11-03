"""
SONIQ MAX — Standalone VST 2.4 DSP Plugin Verification & Test Harness.
Loads SoniqMaxDSP.dll directly, performs protocol validation, runs synthetic
audio signals through all 4 DSP algorithms, and exports verification audio WAV files.

Isolated in demo/ directory so no project files are affected.
"""

import ctypes
import math
import os
import struct
import sys
import wave

# VST 2.4 Constants
VST_MAGIC = 0x56737450       # 'VstP'
PLUGIN_ID = 0x53714D78       # 'SqMx'
effOpen = 0
effClose = 1
effGetParamName = 8
effSetSampleRate = 10
effSetBlockSize = 11
effGetEffectName = 45
effGetVendorString = 47
effGetProductString = 48

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


def dummy_master(eff, op, idx, val, ptr, opt):
    return 0


class VstDemoHost:
    def __init__(self, dll_path, sample_rate=48000):
        self.dll_path = os.path.abspath(dll_path)
        self.sample_rate = sample_rate
        self.plugin = None
        self._master_cb = MASTER_CALLBACK(dummy_master)
        self._load_plugin()

    def _load_plugin(self):
        # Enable MinGW or custom DLL directory if needed
        dll_dir = os.path.dirname(self.dll_path)
        if hasattr(os, "add_dll_directory") and os.path.exists(dll_dir):
            try:
                os.add_dll_directory(dll_dir)
            except Exception:
                pass

        if not os.path.exists(self.dll_path):
            raise FileNotFoundError(f"DLL not found: {self.dll_path}")

        self.lib = ctypes.CDLL(self.dll_path)
        if not hasattr(self.lib, "VSTPluginMain"):
            raise AttributeError("DLL does not export standard VSTPluginMain entry point")

        self.lib.VSTPluginMain.restype = ctypes.POINTER(AEffect)
        self.lib.VSTPluginMain.argtypes = [MASTER_CALLBACK]

        self.plugin = self.lib.VSTPluginMain(self._master_cb)
        if not self.plugin:
            raise RuntimeError("VSTPluginMain returned NULL")

        # Basic handshake
        self.dispatch(effOpen, 0, 0, None, 0.0)
        self.dispatch(effSetSampleRate, 0, 0, None, float(self.sample_rate))
        self.dispatch(effSetBlockSize, 0, 1024, None, 0.0)

    def dispatch(self, opcode, index=0, value=0, ptr=None, opt=0.0):
        return self.plugin.contents.dispatcher(self.plugin, opcode, index, value, ptr, opt)

    def get_string_property(self, opcode):
        buf = ctypes.create_string_buffer(64)
        self.dispatch(opcode, 0, 0, ctypes.cast(buf, ctypes.c_void_p), 0.0)
        return buf.value.decode("latin1", errors="ignore").strip()

    def get_param_name(self, index):
        buf = ctypes.create_string_buffer(64)
        self.dispatch(effGetParamName, index, 0, ctypes.cast(buf, ctypes.c_void_p), 0.0)
        return buf.value.decode("latin1", errors="ignore").strip()

    def set_param(self, index, value):
        self.plugin.contents.setParameter(self.plugin, index, float(value))

    def get_param(self, index):
        return self.plugin.contents.getParameter(self.plugin, index)

    def process_audio(self, left_samples, right_samples):
        n_frames = len(left_samples)
        InLType = ctypes.c_float * n_frames
        InRType = ctypes.c_float * n_frames
        in_l = InLType(*left_samples)
        in_r = InRType(*right_samples)

        OutLType = ctypes.c_float * n_frames
        OutRType = ctypes.c_float * n_frames
        out_l = OutLType()
        out_r = OutRType()

        in_ptrs = (ctypes.POINTER(ctypes.c_float) * 2)(
            ctypes.cast(in_l, ctypes.POINTER(ctypes.c_float)),
            ctypes.cast(in_r, ctypes.POINTER(ctypes.c_float))
        )
        out_ptrs = (ctypes.POINTER(ctypes.c_float) * 2)(
            ctypes.cast(out_l, ctypes.POINTER(ctypes.c_float)),
            ctypes.cast(out_r, ctypes.POINTER(ctypes.c_float))
        )

        self.plugin.contents.processReplacing(self.plugin, in_ptrs, out_ptrs, n_frames)
        return list(out_l), list(out_r)

    def close(self):
        if self.plugin:
            self.dispatch(effClose, 0, 0, None, 0.0)
            self.plugin = None


def export_wav(filename, left_samples, right_samples, sample_rate=48000):
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        packed_frames = bytearray()
        for l, r in zip(left_samples, right_samples):
            # Clip to [-1.0, 1.0] and convert to 16-bit integer
            sl = max(-32767, min(32767, int(l * 32767.0)))
            sr = max(-32767, min(32767, int(r * 32767.0)))
            packed_frames.extend(struct.pack("<hh", sl, sr))
        wf.writeframes(packed_frames)


def compute_spectral_power(samples, target_freq, sample_rate=48000):
    """Computes power at a specific frequency using Goertzel algorithm."""
    n = len(samples)
    k = int(0.5 + (n * target_freq / sample_rate))
    omega = (2.0 * math.pi * k) / n
    coeff = 2.0 * math.cos(omega)
    q0 = q1 = q2 = 0.0
    for s in samples:
        q0 = coeff * q1 - q2 + s
        q2 = q1
        q1 = q0
    power = q1 * q1 + q2 * q2 - coeff * q1 * q2
    return math.sqrt(max(0.0, power)) / n


def run_full_dll_verification(dll_path):
    print("=" * 70)
    print("  SONIQ MAX PRO — VST 2.4 DSP DLL VERIFICATION TEST")
    print("=" * 70)
    print(f"Target DLL: {dll_path}")

    host = VstDemoHost(dll_path, sample_rate=48000)
    p = host.plugin.contents

    print("\n[STEP 1: PROTOCOL & METADATA HANDSHAKE]")
    magic_str = struct.pack(">I", p.magic).decode("latin1", errors="ignore")
    uid_str = struct.pack(">I", p.uniqueID).decode("latin1", errors="ignore")
    print(f"  • Magic Header   : 0x{p.magic:08X} ('{magic_str}') -> {'PASS' if p.magic == VST_MAGIC else 'FAIL'}")
    print(f"  • Plugin ID      : 0x{p.uniqueID:08X} ('{uid_str}') -> {'PASS' if p.uniqueID == PLUGIN_ID else 'FAIL'}")
    print(f"  • Effect Name    : '{host.get_string_property(effGetEffectName)}'")
    print(f"  • Vendor String  : '{host.get_string_property(effGetVendorString)}'")
    print(f"  • Product String : '{host.get_string_property(effGetProductString)}'")
    print(f"  • I/O Channels   : {p.numInputs} In / {p.numOutputs} Out")
    print(f"  • Total Params   : {p.numParams}")

    print("\n  Parameter Roster:")
    for i in range(p.numParams):
        name = host.get_param_name(i)
        val = host.get_param(i)
        print(f"    - Param [{i}] {name:<18} = {val:.2f}")

    output_dir = os.path.join(os.path.dirname(__file__), "output")

    # TEST 1: Psychoacoustic Harmonic Bass Exciter
    print("\n[STEP 2: HARMONIC BASS EXCITER DSP TEST]")
    sr = 48000
    duration = 1.0
    n_samples = int(sr * duration)
    freq = 60.0  # 60 Hz deep sub-bass (often inaudible on laptop speakers)
    sub_bass = [0.6 * math.sin(2.0 * math.pi * freq * (i / sr)) for i in range(n_samples)]

    # Run with Bass Boost = 0%
    host.set_param(0, 0.0)  # Bass Boost = 0
    host.set_param(1, 0.0)  # Clarity = 0
    host.set_param(2, 0.0)  # Spatial = 0
    host.set_param(3, 1.0)  # Limiter = ON
    host.set_param(4, 1.0)  # Master Gain = 1.0
    out_b0_l, out_b0_r = host.process_audio(sub_bass, sub_bass)

    # Run with Bass Boost = 100%
    host.set_param(0, 1.0)  # Bass Boost = 100%
    out_b1_l, out_b1_r = host.process_audio(sub_bass, sub_bass)

    p_f0 = compute_spectral_power(out_b1_l, 60.0, sr)
    p_h2 = compute_spectral_power(out_b1_l, 120.0, sr)  # 2nd harmonic
    p_h3 = compute_spectral_power(out_b1_l, 180.0, sr)  # 3rd harmonic

    print(f"  • Fundamental (60 Hz) Power    : {p_f0:.4f}")
    print(f"  • 2nd Harmonic (120 Hz) Synthesized: {p_h2:.4f}")
    print(f"  • 3rd Harmonic (180 Hz) Synthesized: {p_h3:.4f}")

    bass_works = (p_h2 > 0.01 and p_h3 > 0.005)
    print(f"  -> Bass Harmonic Exciter Result : {'ACTIVE & FUNCTIONAL' if bass_works else 'FAILED'}")

    export_wav(os.path.join(output_dir, "1_sub_bass_60hz_original.wav"), sub_bass, sub_bass, sr)
    export_wav(os.path.join(output_dir, "1_sub_bass_with_synthesized_harmonics.wav"), out_b1_l, out_b1_r, sr)

    # TEST 2: Dynamic Vocal Clarity & Presence Enhancer (2.8 kHz Peak EQ)
    print("\n[STEP 3: VOCAL PRESENCE & CLARITY DSP TEST]")
    vocal_freq = 2800.0  # Speech clarity presence peak
    vocal_in = [0.4 * math.sin(2.0 * math.pi * vocal_freq * (i / sr)) for i in range(n_samples)]

    host.set_param(0, 0.0)
    host.set_param(1, 0.0)  # Clarity = 0%
    out_c0_l, out_c0_r = host.process_audio(vocal_in, vocal_in)

    host.set_param(1, 1.0)  # Clarity = 100% (+6 dB boost)
    out_c1_l, out_c1_r = host.process_audio(vocal_in, vocal_in)

    p_v0 = compute_spectral_power(out_c0_l, vocal_freq, sr)
    p_v1 = compute_spectral_power(out_c1_l, vocal_freq, sr)
    db_gain = 20.0 * math.log10(max(1e-9, p_v1 / max(1e-9, p_v0)))
    print(f"  • 2.8 kHz Power at 0% Clarity   : {p_v0:.4f}")
    print(f"  • 2.8 kHz Power at 100% Clarity : {p_v1:.4f} (Boost: +{db_gain:.2f} dB)")
    clarity_works = (db_gain >= 4.5)
    print(f"  -> Vocal Presence Result        : {'ACTIVE & FUNCTIONAL' if clarity_works else 'FAILED'}")

    export_wav(os.path.join(output_dir, "2_vocal_tone_2800hz_original.wav"), vocal_in, vocal_in, sr)
    export_wav(os.path.join(output_dir, "2_vocal_tone_with_clarity_boost.wav"), out_c1_l, out_c1_r, sr)

    # TEST 3: 3D Stereo Spatializer & Haas Delay
    print("\n[STEP 4: 3D STEREO SPATIALIZER DSP TEST]")
    # Feed sound only into LEFT channel; Right channel is silent (0.0)
    host.set_param(0, 0.0)
    host.set_param(1, 0.0)
    host.set_param(2, 0.8)  # Spatializer = 80%
    out_sp_l, out_sp_r = host.process_audio(vocal_in, [0.0] * n_samples)

    r_cross_bleed = math.sqrt(sum(x * x for x in out_sp_r) / n_samples)
    print(f"  • Left-to-Right Haas Cross-Bleed RMS: {r_cross_bleed:.4f}")
    spatial_works = (r_cross_bleed > 0.05)
    print(f"  -> 3D Spatializer Result        : {'ACTIVE & FUNCTIONAL' if spatial_works else 'FAILED'}")

    export_wav(os.path.join(output_dir, "3_spatializer_mono_left_in_3d_out.wav"), out_sp_l, out_sp_r, sr)

    # TEST 4: Soft-Knee Brickwall Limiter
    print("\n[STEP 5: BRICKWALL LIMITER CLIP PREVENTION TEST]")
    # Injects an over-driven +8 dB signal (amplitude 2.50)
    hot_signal = [2.5 * math.sin(2.0 * math.pi * 440.0 * (i / sr)) for i in range(n_samples)]

    host.set_param(0, 0.0)
    host.set_param(1, 0.0)
    host.set_param(2, 0.0)
    host.set_param(3, 1.0)  # Limiter = ON
    host.set_param(4, 1.0)  # Master Gain = 1.0
    out_lim_l, out_lim_r = host.process_audio(hot_signal, hot_signal)

    peak_in = max(abs(x) for x in hot_signal)
    peak_out = max(abs(x) for x in out_lim_l)
    print(f"  • Input Signal Peak Amplitude   : {peak_in:.2f} (Severely clipped / +8 dBFS)")
    print(f"  • Limiter Output Peak Amplitude : {peak_out:.4f} (Safe threshold: <= 1.000)")
    limiter_works = (peak_out <= 1.0001)
    print(f"  -> Peak Limiter Result          : {'ACTIVE & FUNCTIONAL' if limiter_works else 'FAILED'}")

    export_wav(os.path.join(output_dir, "4_hot_signal_clipped_input.wav"), hot_signal, hot_signal, sr)
    export_wav(os.path.join(output_dir, "4_hot_signal_limited_clean.wav"), out_lim_l, out_lim_r, sr)

    host.close()

    print("\n" + "=" * 70)
    all_passed = bass_works and clarity_works and spatial_works and limiter_works
    if all_passed:
        print("  VERIFICATION RESULT: ALL 4 DSP MODULES ARE FULLY OPERATIONAL!")
    else:
        print("  VERIFICATION RESULT: ONE OR MORE DSP TESTS FAILED.")
    print("=" * 70)
    print(f"Verification audio files generated in: {output_dir}")
    print("You can listen to the generated .wav files directly to hear each effect.")
    return all_passed


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "vst", "bin", "SoniqMaxDSP.dll"
    )
    success = run_full_dll_verification(target)
    sys.exit(0 if success else 1)
