"""Headless Soniq Sense app and playback-content profile switcher."""
import argparse
import ctypes
from collections import deque
from dataclasses import dataclass
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import threading
import time

from audio_content import (
    ANALYSIS_FRAMES,
    AudioBuffer,
    LOOPBACK_SAMPLE_RATE,
    SAMPLE_RATE,
    YamnetAudioClassifier,
    downsample_48k_stereo_to_16k_mono,
)
from constants import (
    APO_DEFAULT_PATH,
    CONFIG_FILE,
    DEFAULT_PROFILES,
    SENSE_BROWSER_PROCESSES as BROWSER_PROCESSES,
    SENSE_LOCAL_MUSIC_PROCESSES,
    SENSE_LOCAL_VIDEO_PROCESSES,
    SENSE_VOICE_PROCESSES as VOICE_PROCESSES,
)
from export_system_apo import generate_apo_config, install_apo_config
from windows_audio import classify_audio_stream_dynamically, get_process_name_by_pid, get_active_windows_output_device

logger = logging.getLogger("soniq_sense")

CAPTURE_BLOCK_FRAMES = 4096
CAPTURE_ANALYSIS_FRAMES = ANALYSIS_FRAMES * (
    LOOPBACK_SAMPLE_RATE // SAMPLE_RATE
)
ANALYSIS_HOP_FRAMES = CAPTURE_ANALYSIS_FRAMES // 2
DEFAULT_POLL_INTERVAL = 0.25
DEFAULT_DEBOUNCE = 3
LOCAL_MEDIA_PROCESSES = SENSE_LOCAL_MUSIC_PROCESSES | SENSE_LOCAL_VIDEO_PROCESSES


@dataclass(frozen=True)
class ForegroundApp:
    process_name: str
    process_id: int
    window_handle: int


def read_foreground_app():
    """Return foreground app metadata without querying or capturing audio."""
    if os.name != "nt":
        raise OSError("Soniq Sense requires Windows foreground-window APIs.")

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    process_id = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
    if process_id.value <= 0:
        return None
    process_name = get_process_name_by_pid(process_id.value)
    if not process_name:
        return None
    return ForegroundApp(process_name.lower(), process_id.value, int(hwnd))


def resolve_fast_profile(process_name, detected_profile=None, music_profile="bass_beast",
                         speech_profile="voice_meeting", game_profile="fps_gaming"):
    """Map known foreground apps to fast-path profiles; browsers use audio analysis."""
    process_name = process_name.casefold()
    if process_name in BROWSER_PROCESSES:
        return None
    if process_name in LOCAL_MEDIA_PROCESSES:
        return music_profile
    if process_name in VOICE_PROCESSES:
        return speech_profile
    if detected_profile == "fps_gaming":
        return game_profile
    if detected_profile == "voice_meeting":
        return speech_profile
    if detected_profile == "bass_beast":
        return music_profile
    return None


class ConsensusDebouncer:
    """Require distinct successive decisions to agree before switching."""

    def __init__(self, evaluations=DEFAULT_DEBOUNCE):
        if evaluations < 2:
            raise ValueError("Debounce must require at least two evaluations.")
        self._history = deque(maxlen=evaluations)
        self._required = evaluations

    def reset(self):
        self._history.clear()

    def observe(self, target):
        if target is None:
            self.reset()
            return None
        self._history.append(target)
        if len(self._history) == self._required and all(
            item == target for item in self._history
        ):
            return target
        return None


class WasapiLoopbackCapture:
    """Open stereo float loopback from the default Windows render device."""

    def __init__(self, device_hint=None):
        self.device_hint = device_hint.casefold() if device_hint else None
        self.speaker = None
        self.recorder = None

    @property
    def device_name(self):
        return str(self.speaker.name) if self.speaker else ""

    @property
    def device_id(self):
        return str(self.speaker.id) if self.speaker else ""

    def open(self):
        import soundcard as sc

        if self.device_hint:
            matches = [
                speaker for speaker in sc.all_speakers()
                if self.device_hint in str(speaker.name).casefold()
            ]
            if not matches:
                raise RuntimeError(
                    f"No playback device matches --device {self.device_hint!r}."
                )
            speaker = matches[0]
        else:
            speaker = sc.default_speaker()

        if speaker is None:
            raise RuntimeError("Windows has no active default playback device.")
        channels = speaker.channels
        try:
            channel_count = channels if isinstance(channels, int) else len(channels)
        except TypeError as error:
            raise RuntimeError(
                f"Playback endpoint {speaker.name!r} has invalid channel metadata."
            ) from error
        if channel_count < 2:
            raise RuntimeError(
                f"Playback endpoint {speaker.name!r} does not expose stereo channels."
            )

        loopback = sc.get_microphone(id=str(speaker.name), include_loopback=True)
        recorder = loopback.recorder(
            samplerate=LOOPBACK_SAMPLE_RATE,
            channels=[0, 1],
            blocksize=CAPTURE_BLOCK_FRAMES,
        )
        recorder.__enter__()
        self.speaker = speaker
        self.recorder = recorder
        logger.info(
            "Opened WASAPI loopback for %s at %d Hz, stereo float32. "
            "SoundCard does not guarantee native 24-bit hardware capture.",
            speaker.name,
            LOOPBACK_SAMPLE_RATE,
        )

    def read_block(self):
        if self.recorder is None:
            raise RuntimeError("Loopback capture is not open.")
        samples = self.recorder.record(numframes=CAPTURE_BLOCK_FRAMES)
        shape = samples.shape if hasattr(samples, "shape") else ((len(samples), len(samples[0])) if samples and isinstance(samples[0], (list, tuple)) else ())
        if shape != (CAPTURE_BLOCK_FRAMES, 2):
            raise RuntimeError(
                f"Expected a {CAPTURE_BLOCK_FRAMES}-frame stereo block; "
                f"received shape {shape}."
            )
        return AudioBuffer(samples.tolist() if hasattr(samples, "tolist") else samples)

    def default_device_changed(self):
        if self.device_hint or self.speaker is None:
            return False
        import soundcard as sc

        current_speaker = sc.default_speaker()
        return current_speaker is None or str(current_speaker.id) != self.device_id

    def close(self):
        recorder, self.recorder = self.recorder, None
        self.speaker = None
        if recorder is not None:
            recorder.__exit__(None, None, None)


def configure_logging(log_file=None, console=True, level=logging.INFO):
    log_path = log_file or os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "SONIQ_MAX",
        "soniq_sense.log",
    )
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    return log_path


class SoniqSenseDaemon:
    """Coordinate fast app rules, browser-only AI analysis, and APO writes."""

    def __init__(
        self,
        config_path=APO_DEFAULT_PATH,
        device_hint=None,
        poll_interval=DEFAULT_POLL_INTERVAL,
        debounce=DEFAULT_DEBOUNCE,
        music_profile="bass_beast",
        speech_profile="voice_meeting",
        game_profile="fps_gaming",
        cinema_profile="cinema_dialogue",
        foreground_reader=read_foreground_app,
        capture=None,
        classifier=None,
    ):
        self.config_path = config_path
        self.device_hint = device_hint
        self.poll_interval = poll_interval
        self.music_profile = music_profile
        self.speech_profile = speech_profile
        self.game_profile = game_profile
        self.cinema_profile = cinema_profile
        for profile_key in (music_profile, speech_profile, game_profile, cinema_profile):
            if profile_key not in DEFAULT_PROFILES:
                raise ValueError(f"Unknown built-in profile: {profile_key}")

        self.foreground_reader = foreground_reader
        self.capture = capture or WasapiLoopbackCapture(device_hint)
        self.classifier = classifier
        self.consensus = ConsensusDebouncer(debounce)
        self.current_profile = None
        self._speech_in_music_counter = 0
        self._audio_buffer = AudioBuffer()
        self._capture_retry_at = 0.0
        self._capture_retry_delay = 1.0
        self._next_device_check = 0.0
        self._last_error_log = 0.0
        self._next_apply_retry = 0.0
        self._apply_error_logged = False

    def _detect_app_mode(self, app):
        process_name = app.process_name.casefold()
        if process_name in BROWSER_PROCESSES:
            return "browser", None
        if process_name in LOCAL_MEDIA_PROCESSES:
            return "fast", self.music_profile
        if process_name in VOICE_PROCESSES:
            return "fast", self.speech_profile

        detected_profile = None
        try:
            detected_profile, _reason = classify_audio_stream_dynamically(
                app.process_id,
                app.window_handle,
                process_name,
            )
        except Exception:
            logger.exception("Could not classify foreground app %s", process_name)

        fast_profile = resolve_fast_profile(
            process_name,
            detected_profile,
            music_profile=self.music_profile,
            speech_profile=self.speech_profile,
            game_profile=self.game_profile,
        )
        if fast_profile:
            return "fast", fast_profile
        return "idle", None

    def _ensure_classifier(self):
        if self.classifier is None:
            logger.info("Loading offline YAMNet classifier on CPU.")
            self.classifier = YamnetAudioClassifier()

    def _close_capture(self):
        try:
            self.capture.close()
        except Exception:
            logger.exception("Could not close the WASAPI loopback stream")
        self._audio_buffer = AudioBuffer()
        self._next_device_check = 0.0

    def _suspend_browser_analysis(self):
        if getattr(self.capture, "recorder", None) is not None:
            self._close_capture()

    def _apply_profile(self, profile_key, reason):
        if profile_key == self.current_profile or time.monotonic() < self._next_apply_retry:
            return

        profile = DEFAULT_PROFILES[profile_key]
        is_hp = False
        try:
            _, is_hp = get_active_windows_output_device()
        except Exception:
            try:
                import soundcard as sc
                speaker = sc.default_speaker()
                if speaker:
                    is_hp = any(
                        keyword in str(speaker.name).casefold()
                        for keyword in (
                            "headphone", "earphone", "headset", "usb-c", "type-c",
                            "buds", "airpod", "iem", "dac",
                        )
                    )
            except Exception:
                logger.warning("Could not identify output-device type; using speaker filters.", exc_info=True)

        if not is_hp:
            try:
                import json
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if cfg.get("force_full_range"):
                            is_hp = True
            except Exception:
                pass

        content = generate_apo_config(
            preset_name=profile["title"],
            eq_gains=profile["eq"],
            bass_boost=profile["bass"] / 100,
            clarity=profile["clarity"] / 100,
            spatial_width=profile["spatial"] / 100,
            volume_boost_db=profile["volume"],
            is_headphone=is_hp,
        )
        try:
            managed_path = install_apo_config(self.config_path, content)
        except (OSError, ValueError) as error:
            self._next_apply_retry = time.monotonic() + 10.0
            if not self._apply_error_logged:
                logger.error("Could not apply profile %s: %s", profile_key, error, exc_info=True)
                self._apply_error_logged = True
            return

        self.current_profile = profile_key
        self._next_apply_retry = 0.0
        self._apply_error_logged = False
        logger.info(
            "Applied %s (%s) from %s; managed filters: %s",
            profile_key,
            profile["title"],
            reason,
            managed_path,
        )

    def _add_capture_block(self):
        now = time.monotonic()
        if now < self._capture_retry_at:
            return None

        try:
            if getattr(self.capture, "recorder", None) is None:
                self.capture.open()
                self._ensure_classifier()
                self._capture_retry_delay = 1.0
                self._next_device_check = now + 1.0
            block = self.capture.read_block()
            self._audio_buffer.extend(block.tolist() if hasattr(block, "tolist") else block)

            if now >= self._next_device_check:
                self._next_device_check = now + 1.0
                if self.capture.default_device_changed():
                    logger.info("Default playback device changed; reconnecting loopback.")
                    self._close_capture()
                    self._capture_retry_at = now
                    return None

            if len(self._audio_buffer) < CAPTURE_ANALYSIS_FRAMES:
                return None

            analysis_samples = AudioBuffer(self._audio_buffer[:CAPTURE_ANALYSIS_FRAMES])
            self._audio_buffer = AudioBuffer(self._audio_buffer[ANALYSIS_HOP_FRAMES:])
            model_samples = downsample_48k_stereo_to_16k_mono(analysis_samples)
            if model_samples.shape[0] != SAMPLE_RATE:
                raise RuntimeError(
                    f"Expected {SAMPLE_RATE} downsampled frames; received {model_samples.shape[0]}."
                )
            return self.classifier.analyze(model_samples, sample_rate=SAMPLE_RATE)
        except Exception:
            self._close_capture()
            self._capture_retry_at = time.monotonic() + self._capture_retry_delay
            self._capture_retry_delay = min(self._capture_retry_delay * 2.0, 30.0)
            raise

    def run_iteration(self):
        app = self.foreground_reader()
        if app is None:
            self._suspend_browser_analysis()
            self.consensus.observe(None)
            return

        mode, profile_key = self._detect_app_mode(app)
        if mode == "fast":
            self._suspend_browser_analysis()
            if self.consensus.observe(profile_key):
                self._apply_profile(profile_key, f"foreground app {app.process_name}")
            return

        if mode != "browser":
            self._suspend_browser_analysis()
            self.consensus.observe(None)
            return

        result = self._add_capture_block()
        if result is None:
            return
        if result.category == "music":
            profile_key = self.music_profile
        elif result.category == "speech":
            profile_key = self.speech_profile
        elif result.category == "gaming":
            profile_key = self.game_profile
        elif result.category == "cinema":
            # If currently enjoying music, stick with music profile rather than switching down;
            # otherwise, switch to the dedicated cinema profile.
            if self.current_profile == self.music_profile:
                profile_key = self.music_profile
            else:
                profile_key = self.cinema_profile
        else:
            self.consensus.observe(None)
            logger.debug(
                "Content is %s (top event %s, score %.3f); holding current profile.",
                result.category,
                result.top_label,
                result.top_score,
            )
            return

        # Music Stickiness Hysteresis:
        # Prevent brief vocal breakdowns, whispering intros, or short spoken interludes
        # in songs (e.g. Manali Trance) from abruptly switching to meeting/voice profile.
        if self.current_profile == self.music_profile and profile_key == self.speech_profile:
            self._speech_in_music_counter = getattr(self, "_speech_in_music_counter", 0) + 1
            if self._speech_in_music_counter < 8:
                return
        else:
            self._speech_in_music_counter = 0

        if self.consensus.observe(profile_key):
            self._apply_profile(
                profile_key,
                f"browser playback classified as {result.category} "
                f"(top event {result.top_label}, score {result.top_score:.3f})",
            )

    def run(self, stop_event):
        logger.info(
            "Soniq Sense started: poll=%.2fs, consensus=%d, APO config=%s",
            self.poll_interval,
            self.consensus._required,
            self.config_path,
        )
        logger.info(
            "Fast app decisions skip audio capture, resampling, and YAMNet inference. "
            "Browser classification requests 48 kHz stereo float32 loopback and "
            "creates a separate 16 kHz mono model copy."
        )
        while not stop_event.is_set():
            started = time.monotonic()
            try:
                self.run_iteration()
            except Exception:
                now = time.monotonic()
                if now - self._last_error_log >= 10.0:
                    logger.exception("Soniq Sense iteration failed; will retry.")
                    self._last_error_log = now
            elapsed = time.monotonic() - started
            stop_event.wait(max(0.0, self.poll_interval - elapsed))

        self._close_capture()
        logger.info("Soniq Sense stopped.")


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Run Soniq Sense as a headless Windows profile-switching daemon."
    )
    parser.add_argument("--config", default=APO_DEFAULT_PATH, help="Equalizer APO main config.txt path.")
    parser.add_argument("--device", help="Substring of playback device name; defaults to Windows' default.")
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    parser.add_argument("--debounce", type=int, choices=(2, 3), default=DEFAULT_DEBOUNCE)
    parser.add_argument("--game-profile", choices=DEFAULT_PROFILES, default="fps_gaming")
    parser.add_argument("--music-profile", choices=DEFAULT_PROFILES, default="bass_beast")
    parser.add_argument("--speech-profile", choices=DEFAULT_PROFILES, default="voice_meeting")
    parser.add_argument("--log-file", help="Override the rotating log path.")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING"), default="INFO")
    parser.add_argument("--quiet", action="store_true", help="Disable console logging; file logging remains enabled.")
    return parser


def main(argv=None):
    if os.name != "nt":
        raise SystemExit("Soniq Sense is a Windows-only daemon.")
    args = build_argument_parser().parse_args(argv)
    if args.poll_interval <= 0:
        raise SystemExit("--poll-interval must be greater than zero.")

    log_path = configure_logging(
        args.log_file,
        console=not args.quiet,
        level=getattr(logging, args.log_level),
    )
    logger.info("Writing Soniq Sense diagnostics to %s", log_path)

    daemon = SoniqSenseDaemon(
        config_path=args.config,
        device_hint=args.device,
        poll_interval=args.poll_interval,
        debounce=args.debounce,
        music_profile=args.music_profile,
        speech_profile=args.speech_profile,
        game_profile=args.game_profile,
    )
    stop_event = threading.Event()

    def request_stop(_signal_number, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    daemon.run(stop_event)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
