"""
Equalizer APO configuration generation and safe SONIQ MAX installation.

SONIQ MAX writes its filters to a separate managed file and includes that file
from Equalizer APO's main config, preserving existing user configuration.

VST-Centric Architecture:
- VST Mode: The native C++ VST engine (SoniqMaxDSP.dll) owns ALL audio processing:
  10-band EQ, Preamp, Harmonic Bass Exciter, Vocal Clarity, Spatializer, and Lookahead Limiter.
  Zero duplicate filters or preamps are emitted into Equalizer APO.
- APO-Only Mode: Safe fallback when VST is disabled or missing; uses static biquads & software preamp.
"""
import cmath
import math
import os
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from constants import validate_profile_data


EQ_FREQUENCIES = (32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
EQ_FREQ_TOKENS = ("32Hz", "64Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz")
MANAGED_CONFIG_NAME = "SONIQ_MAX_Config.txt"
MANAGED_INCLUDE_MARKER = "# SONIQ MAX managed include"
_CONFIG_WRITE_LOCK = threading.RLock()


def _validate_number(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number.")
    if (isinstance(value, float) and not math.isfinite(value)) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")


def _calc_response_magnitude(frequencies, sample_rate, b0, b1, b2, a0, a1, a2):
    if isinstance(frequencies, (int, float)):
        omega_f = 2.0 * math.pi * frequencies / sample_rate
        z1 = cmath.rect(1.0, -omega_f)
        z2 = z1 * z1
        return abs((b0 + b1 * z1 + b2 * z2) / (a0 + a1 * z1 + a2 * z2))
    mags = []
    for f in frequencies:
        omega_f = 2.0 * math.pi * f / sample_rate
        z1 = cmath.rect(1.0, -omega_f)
        z2 = z1 * z1
        mags.append(abs((b0 + b1 * z1 + b2 * z2) / (a0 + a1 * z1 + a2 * z2)))
    return mags


def _response_magnitude(frequencies, sample_rate, frequency, gain_db, q, filter_type):
    amplitude = 10.0 ** (gain_db / 40.0)
    omega = 2.0 * math.pi * frequency / sample_rate
    cosine = math.cos(omega)
    sine = math.sin(omega)
    if filter_type == "peak":
        alpha = sine / (2.0 * q)
        b0 = 1.0 + alpha * amplitude
        b1 = -2.0 * cosine
        b2 = 1.0 - alpha * amplitude
        a0 = 1.0 + alpha / amplitude
        a1 = -2.0 * cosine
        a2 = 1.0 - alpha / amplitude
    elif filter_type == "low_shelf":
        alpha = sine * 0.5 * math.sqrt(2.0)
        beta = 2.0 * math.sqrt(amplitude) * alpha
        b0 = amplitude * ((amplitude + 1.0) - (amplitude - 1.0) * cosine + beta)
        b1 = 2.0 * amplitude * ((amplitude - 1.0) - (amplitude + 1.0) * cosine)
        b2 = amplitude * ((amplitude + 1.0) - (amplitude - 1.0) * cosine - beta)
        a0 = (amplitude + 1.0) + (amplitude - 1.0) * cosine + beta
        a1 = -2.0 * ((amplitude - 1.0) + (amplitude + 1.0) * cosine)
        a2 = (amplitude + 1.0) + (amplitude - 1.0) * cosine - beta
    elif filter_type == "high_shelf":
        alpha = sine * 0.5 * math.sqrt(2.0)
        beta = 2.0 * math.sqrt(amplitude) * alpha
        b0 = amplitude * ((amplitude + 1.0) + (amplitude - 1.0) * cosine + beta)
        b1 = -2.0 * amplitude * ((amplitude - 1.0) + (amplitude + 1.0) * cosine)
        b2 = amplitude * ((amplitude + 1.0) + (amplitude - 1.0) * cosine - beta)
        a0 = (amplitude + 1.0) - (amplitude - 1.0) * cosine + beta
        a1 = 2.0 * ((amplitude - 1.0) - (amplitude + 1.0) * cosine)
        a2 = (amplitude + 1.0) - (amplitude - 1.0) * cosine - beta
    else:
        raise ValueError(f"Unsupported filter response type: {filter_type}")

    return _calc_response_magnitude(frequencies, sample_rate, b0, b1, b2, a0, a1, a2)


def _apply_response_mags(response, mags):
    for i, m in enumerate(mags):
        response[i] *= m


def estimate_peak_filter_gain_db(
    eq_gains, bass_boost, clarity, spatial_width, is_headphone=False, vst_mode=False
):
    """Estimate the maximum combined filter gain across common device rates."""
    if not isinstance(eq_gains, (list, tuple)) or len(eq_gains) != len(EQ_FREQUENCIES):
        raise ValueError(f"EQ must contain exactly {len(EQ_FREQUENCIES)} gains.")
    for gain in eq_gains:
        _validate_number("EQ gain", gain, -12, 12)
    _validate_number("Bass level", bass_boost, 0, 1)
    _validate_number("Clarity level", clarity, 0, 1)
    _validate_number("Stereo width", spatial_width, 1, 2.5)
    if type(is_headphone) is not bool:
        raise ValueError("is_headphone must be a boolean value.")
    if type(vst_mode) is not bool:
        raise ValueError("vst_mode must be a boolean value.")

    peak_gain_db = 0.0
    for sample_rate in (44100, 48000, 96000):
        max_f = min(20000.0, sample_rate * 0.45)
        log_ratio = math.log(max_f / 20.0) / 767.0
        frequencies = [20.0 * math.exp(i * log_ratio) for i in range(768)]
        response = [1.0] * 768
        for frequency, gain in zip(EQ_FREQUENCIES, eq_gains):
            if abs(gain) > 0.1:
                _apply_response_mags(response, _response_magnitude(
                    frequencies, sample_rate, frequency, gain, 1.41, "peak"
                ))

        if not vst_mode:
            # Static APO tone shaping filters (only active in APO-only mode)
            if bass_boost > 0.01:
                bass_gain = bass_boost * 6.0
                _apply_response_mags(response, _response_magnitude(
                    frequencies, sample_rate, 150.0, bass_gain, 1.2, "peak"
                ))
                _apply_response_mags(response, _response_magnitude(
                    frequencies, sample_rate, 200.0, bass_gain * 0.6, 1.0, "low_shelf"
                ))

            if clarity > 0.01:
                clarity_gain = clarity * 4.5
                _apply_response_mags(response, _response_magnitude(
                    frequencies, sample_rate, 2800.0, clarity_gain, 1.5, "peak"
                ))
                _apply_response_mags(response, _response_magnitude(
                    frequencies, sample_rate, 7000.0, clarity_gain * 0.7, 1.0, "high_shelf"
                ))
                if not is_headphone:
                    _apply_response_mags(response, _response_magnitude(
                        frequencies, sample_rate, 320.0, -2.5, 2.0, "peak"
                    ))

        max_magnitude = max(1.0, max(response))
        peak_gain_db = max(peak_gain_db, 20.0 * math.log10(max_magnitude))

    spatial_gain_db = 0.0
    if not vst_mode and spatial_width > 1.05:
        cross_gain = min(0.18, max(0.04, (spatial_width - 1.0) * 0.18))
        spatial_peak = 1.0 + cross_gain * 0.5
        spatial_gain_db = 20.0 * math.log10(spatial_peak)
    elif vst_mode:
        # Margin for inter-band resonance in VST mode
        spatial_gain_db = 0.5

    return peak_gain_db + spatial_gain_db


def generate_apo_config(
    preset_name,
    eq_gains,
    bass_boost,
    clarity,
    spatial_width,
    volume_boost_db,
    night_mode=False,
    is_headphone=False,
    vst_plugins=None,
):
    """
    Generate Equalizer APO configuration.
    In VST Mode: SoniqMaxDSP.dll is the Single Source of Truth for all audio processing.
    Zero duplicate EQ, Preamp, or Filter directives are emitted in APO.
    In APO-Only Mode: Emits static biquad filters and preamp as fallback.
    """
    if not isinstance(preset_name, str) or not preset_name.strip():
        raise ValueError("Preset name must be a non-empty string.")
    if any(character in preset_name for character in "\r\n"):
        raise ValueError("Preset name cannot contain line breaks.")
    if not isinstance(eq_gains, (list, tuple)) or len(eq_gains) != len(EQ_FREQUENCIES):
        raise ValueError(f"EQ must contain exactly {len(EQ_FREQUENCIES)} gains.")
    for gain in eq_gains:
        _validate_number("EQ gain", gain, -12, 12)
    _validate_number("Bass level", bass_boost, 0, 1)
    _validate_number("Clarity level", clarity, 0, 1)
    _validate_number("Stereo width", spatial_width, 1, 2.5)
    _validate_number("Volume level", volume_boost_db, 0, 12)
    if type(night_mode) is not bool or type(is_headphone) is not bool:
        raise ValueError("night_mode and is_headphone must be boolean values.")

    is_vst_mode = bool(vst_plugins)
    effective_boost = volume_boost_db - (2.0 if night_mode else 0.0)
    estimated_peak_gain = estimate_peak_filter_gain_db(
        eq_gains, bass_boost, clarity, spatial_width, is_headphone, vst_mode=is_vst_mode
    )
    preamp = min(4.0, effective_boost - estimated_peak_gain)
    device_tag = "Headphones" if is_headphone else "Speakers"

    lines = [
        f"# SONIQ MAX profile: {preset_name}",
        f"# Output mode: {device_tag}",
    ]

    if is_vst_mode:
        # VST is the Single Source of Truth for ALL audio processing
        lines.extend([
            "# Engine mode: Equalizer APO (VST Host Only) · Native SONIQ MAX VST Engine",
            "# All 10-band EQ, Preamp, Harmonic Bass, Clarity, Spatial, and Limiter processing",
            "# are executed exclusively inside the native 64-bit VST DSP engine.",
            "",
            "# Native VST Plugin Processing",
        ])
        norm_bass = max(0.0, min(1.0, float(bass_boost)))
        norm_clarity = max(0.0, min(1.0, float(clarity)))
        norm_spatial = max(0.0, min(1.0, (float(spatial_width) - 1.0) / 1.5))
        norm_limiter = 1.0
        norm_master = 1.0
        speaker_hpf_val = 0.0 if is_headphone else 1.0

        eq_tokens = " ".join([
            f"EQ{token} {gain:+.1f}"
            for token, gain in zip(EQ_FREQ_TOKENS, eq_gains)
        ])

        for plugin in vst_plugins:
            lines.append(
                f'VSTPlugin: Library "{plugin}" Bass {norm_bass:.4f} Clarity {norm_clarity:.4f} '
                f'Spatial {norm_spatial:.4f} Limiter {norm_limiter:.1f} MasterGain {norm_master:.4f} '
                f'Preamp {preamp:+.1f} EQEnable 1.0 BassEnable 1.0 ClarityEnable 1.0 SpatialEnable 1.0 '
                f'{eq_tokens} SpeakerHPF {speaker_hpf_val:.1f}'
            )
    else:
        # APO-only fallback mode: static biquad approximations and software preamp
        lines.extend([
            "# Static EQ with estimated peak headroom compensation; no dynamic limiter or compressor.",
            "",
        ])
        if not is_headphone:
            lines.extend(("# Low-frequency high-pass filter (120 Hz)", "Filter: ON HP Fc 120 Hz", ""))
        else:
            lines.extend(("# Headphone mode: no speaker high-pass filter", ""))

        lines.extend(("# Output level trim", f"Preamp: {preamp:+.1f} dB", "", "# 10-band parametric EQ"))
        for frequency, gain in zip(EQ_FREQUENCIES, eq_gains):
            if abs(gain) > 0.1:
                lines.append(f"Filter: ON PK Fc {frequency} Hz Gain {gain:+.1f} dB Q 1.41")

        if bass_boost > 0.01:
            bass_db = bass_boost * 6.0
            lines.extend((
                "",
                "# Bass tone shaping (static EQ; does not synthesize harmonics)",
                f"Filter: ON LSC 6 dB Fc 200 Hz Gain {bass_db * 0.6:+.1f} dB",
                f"Filter: ON PK Fc 150 Hz Gain {bass_db:+.1f} dB Q 1.2",
            ))

        if clarity > 0.01:
            clarity_db = clarity * 4.5
            lines.extend((
                "",
                "# Vocal-presence and high-shelf EQ",
                f"Filter: ON PK Fc 2800 Hz Gain {clarity_db:+.1f} dB Q 1.5",
                f"Filter: ON HSC 6 dB Fc 7000 Hz Gain {clarity_db * 0.7:+.1f} dB",
            ))
            if not is_headphone:
                lines.append("Filter: ON PK Fc 320 Hz Gain -2.5 dB Q 2.0")

        if spatial_width > 1.05:
            cross_gain = min(0.18, max(0.04, (spatial_width - 1.0) * 0.18))
            direct_gain = max(0.80, 1.0 - cross_gain * 0.5)
            lines.extend((
                "",
                f"# Stereo channel mix (width control {spatial_width:.2f}x; no Haas delay)",
                f"Copy: L={direct_gain:.2f}*L+-{cross_gain:.2f}*R R={direct_gain:.2f}*R+-{cross_gain:.2f}*L",
            ))

    if night_mode:
        lines.extend(("", "# Night mode is a static 2 dB output trim, not dynamic compression."))

    return "\n".join(lines) + "\n"


def profile_filter_values(profile, enabled_effects):
    """Return normalized APO inputs from one profile and current effect switches."""
    validate_profile_data(profile)
    effect_names = ("bass", "clarity", "spatial", "volume")
    if not isinstance(enabled_effects, dict) or any(
        type(enabled_effects.get(name)) is not bool for name in effect_names
    ):
        raise ValueError("Effect switches must provide boolean values for all controls.")

    return {
        "bass_boost": profile["bass"] / 100 if enabled_effects["bass"] else 0.0,
        "clarity": profile["clarity"] / 100 if enabled_effects["clarity"] else 0.0,
        "spatial_width": profile["spatial"] / 100 if enabled_effects["spatial"] else 1.0,
        "volume_boost_db": profile["volume"] if enabled_effects["volume"] else 0.0,
    }


def _atomic_write(path, content):
    directory = os.path.dirname(os.path.abspath(path))
    fd, temp_path = tempfile.mkstemp(prefix=".soniq-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def export_to_file(path, content):
    """Export configuration directly to a local target file."""
    _atomic_write(path, content)


def _ensure_managed_include(main_config_content, managed_config_name):
    include_line = f"Include: {managed_config_name}"
    escaped_name = re.escape(managed_config_name)
    pattern = re.compile(rf"^\s*Include:\s*{escaped_name}\s*$", re.IGNORECASE | re.MULTILINE)
    if pattern.search(main_config_content):
        return main_config_content

    header = "" if main_config_content.endswith("\n") or not main_config_content else "\n"
    managed_block = (
        f"{header}{MANAGED_INCLUDE_MARKER}\n"
        f"{include_line}\n"
    )
    return main_config_content + managed_block


def _install_apo_config_unlocked(main_config_path, soniq_config_content):
    main_dir = os.path.dirname(os.path.abspath(main_config_path))
    if not os.path.isdir(main_dir):
        raise FileNotFoundError(f"Equalizer APO config directory does not exist: {main_dir}")

    managed_path = os.path.join(main_dir, MANAGED_CONFIG_NAME)

    # Avoid redundant disk writes if the managed file is already identical
    if os.path.isfile(managed_path):
        try:
            with open(managed_path, "r", encoding="utf-8") as existing_file:
                if existing_file.read() == soniq_config_content:
                    # Content is already identical; verify main include and return
                    if os.path.isfile(main_config_path):
                        with open(main_config_path, "r", encoding="utf-8") as mf:
                            if re.search(rf"^\s*Include:\s*{re.escape(MANAGED_CONFIG_NAME)}\s*$", mf.read(), re.IGNORECASE | re.MULTILINE):
                                return managed_path
        except Exception:
            pass

    _atomic_write(managed_path, soniq_config_content)

    if os.path.isfile(main_config_path):
        with open(main_config_path, "r", encoding="utf-8") as stream:
            main_content = stream.read()
    else:
        main_content = ""

    updated_main = _ensure_managed_include(main_content, MANAGED_CONFIG_NAME)
    if updated_main != main_content:
        _atomic_write(main_config_path, updated_main)

    return managed_path


@contextmanager
def config_write_lock():
    """Acquire the shared configuration lock for safe concurrent updates."""
    with _CONFIG_WRITE_LOCK:
        yield


def install_apo_config(main_config_path, soniq_config_content):
    """Thread-safe and process-safe install of the SONIQ MAX configuration into Equalizer APO."""
    with config_write_lock():
        return _install_apo_config_unlocked(main_config_path, soniq_config_content)
