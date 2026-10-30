"""
Equalizer APO configuration generation and safe SONIQ MAX installation.

SONIQ MAX writes its filters to a separate managed file and includes that file
from Equalizer APO's main config, preserving existing user configuration.
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

    # Pure python biquad response calculation



    return _calc_response_magnitude(frequencies, sample_rate, b0, b1, b2, a0, a1, a2)


def _apply_response_mags(response, mags):
    for i, m in enumerate(mags):
        response[i] *= m


def estimate_peak_filter_gain_db(eq_gains, bass_boost, clarity, spatial_width, is_headphone=False):
    """Estimate the maximum combined static-filter gain across common device rates."""
    if not isinstance(eq_gains, (list, tuple)) or len(eq_gains) != len(EQ_FREQUENCIES):
        raise ValueError(f"EQ must contain exactly {len(EQ_FREQUENCIES)} gains.")
    for gain in eq_gains:
        _validate_number("EQ gain", gain, -12, 12)
    _validate_number("Bass level", bass_boost, 0, 1)
    _validate_number("Clarity level", clarity, 0, 1)
    _validate_number("Stereo width", spatial_width, 1, 2.5)
    if type(is_headphone) is not bool:
        raise ValueError("is_headphone must be a boolean value.")

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

    cross_gain = 0.0
    if spatial_width > 1.05:
        cross_gain = min(0.18, max(0.04, (spatial_width - 1.0) * 0.18))
    spatial_peak = 1.0 + cross_gain * 0.5
    spatial_gain_db = 20.0 * math.log10(spatial_peak)
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
    """Generate Equalizer APO filters for a profile."""
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

    effective_boost = volume_boost_db - (2.0 if night_mode else 0.0)
    estimated_peak_gain = estimate_peak_filter_gain_db(
        eq_gains, bass_boost, clarity, spatial_width, is_headphone
    )
    preamp = min(4.0, effective_boost - estimated_peak_gain)
    device_tag = "Headphones" if is_headphone else "Speakers"
    lines = [
        f"# SONIQ MAX profile: {preset_name}",
        f"# Output mode: {device_tag}",
        "# Static EQ with estimated peak headroom compensation; no dynamic limiter or compressor.",
        "",
    ]

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

    if vst_plugins:
        lines.extend(("", "# Native VST Plugin Processing"))
        for plugin in vst_plugins:
            lines.append(f'VSTPlugin: Library "{plugin}"')

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


def export_to_file(filepath, content):
    """Atomically write a local generated config file."""
    _atomic_write(filepath, content)
    return filepath


@contextmanager
def _process_config_lock(config_dir, timeout=30.0):
    """Serialize managed-config changes across SONIQ processes."""
    lock_path = os.path.join(config_dir, ".soniq_max_config.lock")
    lock_file = open(lock_path, "a+b")
    acquired = False
    with _CONFIG_WRITE_LOCK:
        try:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()

            deadline = time.monotonic() + timeout
            while True:
                lock_file.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (OSError, BlockingIOError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            f"Timed out waiting for SONIQ config lock: {lock_path}"
                        )
                    time.sleep(0.05)

            yield
        finally:
            if acquired:
                lock_file.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()


def install_apo_config(config_path, content, managed_name=MANAGED_CONFIG_NAME):
    """Write managed filters under a process-safe lock; preserve user config."""
    config_dir = os.path.dirname(os.path.abspath(config_path))
    if not os.path.isdir(config_dir):
        raise FileNotFoundError(f"Equalizer APO config directory does not exist: {config_dir}")
    with _process_config_lock(config_dir):
        return _install_apo_config_unlocked(config_path, content, managed_name)


def _install_apo_config_unlocked(config_path, content, managed_name):
    """Write SONIQ's managed config and add an idempotent Include to APO config."""
    if (
        not isinstance(managed_name, str)
        or "/" in managed_name
        or "\\" in managed_name
        or managed_name in ("", ".", "..")
    ):
        raise ValueError("Managed config name must be a simple file name.")

    config_dir = os.path.dirname(os.path.abspath(config_path))
    if not os.path.isdir(config_dir):
        raise FileNotFoundError(f"Equalizer APO config directory does not exist: {config_dir}")

    managed_path = os.path.join(config_dir, managed_name)
    _atomic_write(managed_path, content)

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8", newline="") as stream:
            original = stream.read()
    else:
        original = ""

    target_name = os.path.basename(managed_path).casefold()
    include_exists = False
    include_pattern = re.compile(r"^\s*Include\s*:\s*[\"']?([^\"']+)", re.IGNORECASE)
    for line in original.splitlines():
        match = include_pattern.match(line)
        if match:
            include_target = match.group(1).strip().replace("\\", "/").casefold()
            if os.path.basename(include_target) == target_name:
                include_exists = True
                break

    if not include_exists:
        separator = "" if not original or original.endswith(("\n", "\r")) else "\n"
        original = (
            f"{original}{separator}\n{MANAGED_INCLUDE_MARKER}\n"
            f"Include: {managed_name}\n"
        )
        _atomic_write(config_path, original)

    return managed_path
