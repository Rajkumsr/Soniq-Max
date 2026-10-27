"""Local YAMNet inference and Windows playback-loopback capture."""
import csv
from dataclasses import dataclass
import logging
import os
import threading

import numpy as np

from constants import get_asset_dir

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
ANALYSIS_FRAMES = SAMPLE_RATE
SILENCE_RMS = 0.002
MIN_CATEGORY_SCORE = 0.20
SPEECH_LABEL_HINTS = (
    "speech",
    "conversation",
    "narration",
    "whisper",
    "shout",
    "scream",
    "babbling",
)
MUSIC_LABEL_HINTS = ("music", "singing", "choir", "musical instrument")
LOOPBACK_SAMPLE_RATE = 48000
YAMNET_DECIMATION = LOOPBACK_SAMPLE_RATE // SAMPLE_RATE
LOOPBACK_ANALYSIS_FRAMES = ANALYSIS_FRAMES * YAMNET_DECIMATION


@dataclass(frozen=True)
class AudioAnalysis:
    category: str
    category_score: float
    rms: float
    top_label: str
    top_score: float


def downsample_48k_stereo_to_16k_mono(samples):
    """Anti-alias and downsample 48 kHz float loopback to mono 16 kHz."""
    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim != 2 or audio.shape[1] != 2:
        raise ValueError("Loopback input must be a frames-by-two-channels array.")
    if audio.shape[0] == 0:
        return np.empty(0, dtype=np.float32)
    if not np.isfinite(audio).all():
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

    mono = audio.mean(axis=1, dtype=np.float64)
    taps_count = 127
    centered = np.arange(taps_count, dtype=np.float64) - (taps_count - 1) / 2
    cutoff = 7200.0 / LOOPBACK_SAMPLE_RATE
    taps = 2.0 * cutoff * np.sinc(2.0 * cutoff * centered)
    taps *= np.hamming(taps_count)
    taps /= taps.sum()
    filtered = np.convolve(mono, taps, mode="same")
    return filtered[::YAMNET_DECIMATION].astype(np.float32)


def _classify_scores(scores, labels, rms):
    score_matrix = np.asarray(scores, dtype=np.float32)
    if score_matrix.ndim == 1:
        mean_scores = score_matrix
    elif score_matrix.ndim == 2 and score_matrix.shape[0] > 0:
        mean_scores = score_matrix.mean(axis=0)
    else:
        raise ValueError("YAMNet scores must be a non-empty class-score vector or matrix.")
    if mean_scores.size != len(labels) or not np.isfinite(mean_scores).all():
        raise ValueError("YAMNet scores do not match the loaded class map.")

    top_index = int(np.argmax(mean_scores))
    top_label = labels[top_index]
    top_score = float(mean_scores[top_index])
    normalized_labels = [label.casefold() for label in labels]
    speech_indices = [
        index for index, label in enumerate(normalized_labels)
        if any(hint in label for hint in SPEECH_LABEL_HINTS)
    ]
    music_indices = [
        index for index, label in enumerate(normalized_labels)
        if any(hint in label for hint in MUSIC_LABEL_HINTS)
    ]
    speech_score = float(mean_scores[speech_indices].max()) if speech_indices else 0.0
    music_score = float(mean_scores[music_indices].max()) if music_indices else 0.0

    if rms < SILENCE_RMS or (top_label.casefold() == "silence" and top_score >= 0.5):
        return AudioAnalysis("silence", top_score, rms, top_label, top_score)
    if speech_score >= MIN_CATEGORY_SCORE and speech_score > music_score:
        return AudioAnalysis("speech", speech_score, rms, top_label, top_score)
    if music_score >= MIN_CATEGORY_SCORE and music_score >= speech_score:
        return AudioAnalysis("music", music_score, rms, top_label, top_score)
    return AudioAnalysis("other", top_score, rms, top_label, top_score)


class YamnetAudioClassifier:
    """CPU-only YAMNet classifier; input is mono float audio at 16 kHz."""

    def __init__(self, model_path=None, class_map_path=None):
        asset_dir = os.path.join(get_asset_dir(), "models", "yamnet")
        self.model_path = model_path or os.path.join(asset_dir, "yamnet.onnx")
        self.class_map_path = class_map_path or os.path.join(asset_dir, "yamnet_class_map.csv")
        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(f"YAMNet model was not found: {self.model_path}")
        if not os.path.isfile(self.class_map_path):
            raise FileNotFoundError(f"YAMNet class map was not found: {self.class_map_path}")

        with open(self.class_map_path, newline="", encoding="utf-8") as stream:
            self.labels = [row["display_name"] for row in csv.DictReader(stream)]
        if len(self.labels) != 521:
            raise ValueError(f"Expected 521 YAMNet class labels, found {len(self.labels)}.")

        try:
            import onnxruntime as ort
        except ImportError as error:
            raise RuntimeError("ONNX Runtime is required for local audio classification.") from error

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self._session = ort.InferenceSession(
            self.model_path,
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        inputs = self._session.get_inputs()
        if len(inputs) != 1 or inputs[0].name != "waveform":
            raise ValueError("The bundled YAMNet ONNX model has an unexpected input signature.")
        self._input_name = inputs[0].name

    def analyze(self, samples, sample_rate=SAMPLE_RATE):
        if sample_rate != SAMPLE_RATE:
            raise ValueError(f"YAMNet requires {SAMPLE_RATE} Hz audio.")
        audio = np.asarray(samples, dtype=np.float32)
        if audio.size == 0:
            return AudioAnalysis("silence", 1.0, 0.0, "Silence", 1.0)
        if audio.ndim > 1:
            if audio.ndim != 2:
                raise ValueError("Audio must be mono or a frames-by-channels array.")
            audio = audio.mean(axis=1)
        audio = audio.reshape(-1)
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
        audio = np.clip(audio, -1.0, 1.0)
        rms = float(np.sqrt(np.mean(np.square(audio))))
        if rms < SILENCE_RMS:
            return AudioAnalysis("silence", 1.0, rms, "Silence", 1.0)

        scores = self._session.run(
            ["output_0"],
            {self._input_name: audio},
        )[0]
        return _classify_scores(scores, self.labels, rms)


class AudioContentMonitor:
    """Capture short playback-loopback blocks and analyze them without saving."""

    def __init__(self, on_result=None, on_status=None):
        self._on_result = on_result
        self._on_status = on_status
        self._enabled_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._reconnect_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_result = None
        self._thread = None

    @property
    def latest_result(self):
        with self._lock:
            return self._latest_result

    def start(self):
        with self._lock:
            self._latest_result = None
        self._enabled_event.set()
        if self._thread and self._thread.is_alive():
            self._reconnect_event.set()
            return
        self._shutdown_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="SONIQ MAX audio content monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._enabled_event.clear()
        self._reconnect_event.set()
        with self._lock:
            self._latest_result = None
        self._report_status("Audio analysis paused.")

    def shutdown(self):
        self.stop()
        self._shutdown_event.set()

    def reconnect(self):
        self._reconnect_event.set()

    def _report_status(self, message):
        if self._on_status:
            self._on_status(message)

    def _capture_loop(self):
        try:
            import soundcard as sc
        except ImportError:
            message = "Audio analysis unavailable: install the 'soundcard' package."
            logger.exception(message)
            self._report_status(message)
            return

        classifier = None
        while not self._shutdown_event.is_set():
            if not self._enabled_event.wait(0.25):
                continue
            try:
                if classifier is None:
                    self._report_status("Loading offline YAMNet sound classifier.")
                    classifier = YamnetAudioClassifier()
                speaker = sc.default_speaker()
                if speaker is None:
                    raise RuntimeError("Windows has no active default playback device.")
                speaker_name = str(speaker.name)
                loopback = sc.get_microphone(
                    id=speaker_name,
                    include_loopback=True,
                )
                self._report_status(f"Analyzing playback locally: {speaker_name}")
                self._reconnect_event.clear()
                with loopback.recorder(
                    samplerate=LOOPBACK_SAMPLE_RATE,
                    channels=[0, 1],
                    blocksize=4096,
                ) as recorder:
                    blocks_since_device_check = 0
                    while (
                        self._enabled_event.is_set()
                        and not self._shutdown_event.is_set()
                        and not self._reconnect_event.is_set()
                    ):
                        samples = recorder.record(numframes=LOOPBACK_ANALYSIS_FRAMES)
                        if not self._enabled_event.is_set() or self._shutdown_event.is_set():
                            break
                        mono_16k = downsample_48k_stereo_to_16k_mono(samples)
                        result = classifier.analyze(mono_16k, SAMPLE_RATE)
                        with self._lock:
                            self._latest_result = result
                        if self._on_result:
                            self._on_result(result)

                        blocks_since_device_check += 1
                        if blocks_since_device_check >= 5:
                            blocks_since_device_check = 0
                            current_speaker = sc.default_speaker()
                            if current_speaker is None or str(current_speaker.name) != speaker_name:
                                self._reconnect_event.set()
            except Exception as error:
                if self._shutdown_event.is_set():
                    break
                if self._enabled_event.is_set():
                    logger.warning("Playback loopback analysis failed: %s", error, exc_info=True)
                    self._report_status(f"Audio analysis unavailable: {error}")
                    self._shutdown_event.wait(5.0)

        self._report_status("Audio analysis stopped.")
