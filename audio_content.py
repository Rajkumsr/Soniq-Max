"""Local real-time acoustic DSP analyzer and Windows playback-loopback capture."""
from dataclasses import dataclass
import logging
import math
import threading

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
ANALYSIS_FRAMES = SAMPLE_RATE
SILENCE_RMS = 0.002
LOOPBACK_SAMPLE_RATE = 48000
DECIMATION_FACTOR = LOOPBACK_SAMPLE_RATE // SAMPLE_RATE
LOOPBACK_ANALYSIS_FRAMES = ANALYSIS_FRAMES * DECIMATION_FACTOR


class AudioBuffer(list):
    """Featherweight list subclass providing shape metadata for duck-typing compatibility."""

    @property
    def shape(self):
        if len(self) > 0 and isinstance(self[0], (list, tuple)):
            return (len(self), len(self[0]))
        return (len(self),)

    def copy(self):
        return AudioBuffer(self)

    def __getitem__(self, item):
        val = super().__getitem__(item)
        if isinstance(item, slice):
            return AudioBuffer(val)
        return val

    def __pow__(self, power):
        return AudioBuffer([x ** power for x in self])


@dataclass(frozen=True)
class AudioAnalysis:
    category: str
    category_score: float
    rms: float
    top_label: str
    top_score: float


class BiquadFilter:
    """Standard 2nd-order Audio EQ Cookbook biquad filter for real-time DSP."""

    def __init__(self, cutoff, q, sample_rate, filter_type="lowpass"):
        omega = 2.0 * math.pi * cutoff / sample_rate
        sn = math.sin(omega)
        cs = math.cos(omega)
        alpha = sn / (2.0 * q)
        a0 = 1.0 + alpha
        if filter_type == "lowpass":
            self.b0 = ((1.0 - cs) / 2.0) / a0
            self.b1 = (1.0 - cs) / a0
            self.b2 = ((1.0 - cs) / 2.0) / a0
        elif filter_type == "bandpass":
            self.b0 = alpha / a0
            self.b1 = 0.0
            self.b2 = -alpha / a0
        elif filter_type == "highpass":
            self.b0 = ((1.0 + cs) / 2.0) / a0
            self.b1 = -(1.0 + cs) / a0
            self.b2 = ((1.0 + cs) / 2.0) / a0
        else:
            raise ValueError(f"Unsupported filter type: {filter_type}")
        self.a1 = (-2.0 * cs) / a0
        self.a2 = (1.0 - alpha) / a0
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0

    def process(self, in_sample):
        out = (
            self.b0 * in_sample
            + self.b1 * self.x1
            + self.b2 * self.x2
            - self.a1 * self.y1
            - self.a2 * self.y2
        )
        self.x2 = self.x1
        self.x1 = in_sample
        self.y2 = self.y1
        self.y1 = out
        return out


def downsample_48k_stereo_to_16k_mono(samples):
    """Anti-alias and downsample 48 kHz stereo to mono 16 kHz without FIR convolution overhead."""
    if hasattr(samples, "tolist"):
        samples = samples.tolist()

    if hasattr(samples, "shape"):
        shape = samples.shape
        if len(shape) != 2 or shape[1] != 2:
            raise ValueError("Loopback input must be a frames-by-two-channels array.")
    elif isinstance(samples, (list, tuple)):
        if len(samples) > 0 and (not isinstance(samples[0], (list, tuple)) or len(samples[0]) != 2):
            raise ValueError("Loopback input must be a frames-by-two-channels array.")
    else:
        raise ValueError("Loopback input must be a frames-by-two-channels array.")

    if not samples or len(samples) == 0:
        return AudioBuffer()

    f1 = BiquadFilter(5500.0, 0.707, LOOPBACK_SAMPLE_RATE, "lowpass")
    f2 = BiquadFilter(5500.0, 0.707, LOOPBACK_SAMPLE_RATE, "lowpass")

    out = []
    step = DECIMATION_FACTOR
    for i, s in enumerate(samples):
        l, r = float(s[0]), float(s[1])
        x = 0.0 if not (math.isfinite(l) and math.isfinite(r)) else (l + r) * 0.5
        y = f2.process(f1.process(x))
        if i % step == 0:
            out.append(y)

    return AudioBuffer(out)


def _classify_scores(scores, labels, rms, category_map=None):
    """Backwards-compatible helper for scoring unit tests."""
    if hasattr(scores, "tolist"):
        scores = scores.tolist()
    if not scores:
        raise ValueError("Scores must be a non-empty vector or matrix.")

    if isinstance(scores[0], (list, tuple)):
        num_rows = len(scores)
        num_cols = len(scores[0])
        mean_scores = [
            sum(scores[r][c] for r in range(num_rows)) / num_rows
            for c in range(num_cols)
        ]
    else:
        mean_scores = [float(s) for s in scores]

    if len(mean_scores) != len(labels) or not all(math.isfinite(s) for s in mean_scores):
        raise ValueError("Scores do not match labels.")

    top_index = max(range(len(mean_scores)), key=lambda i: mean_scores[i])
    top_label = labels[top_index]
    top_score = float(mean_scores[top_index])

    if rms < SILENCE_RMS or (top_label.casefold() == "silence" and top_score >= 0.5):
        return AudioAnalysis("silence", top_score, rms, top_label, top_score)

    if category_map:
        category_scores = {}
        for idx, label in enumerate(labels):
            cat = category_map.get(idx) or category_map.get(label.casefold())
            if cat and cat != "other":
                val = float(mean_scores[idx])
                if val > category_scores.get(cat, 0.0):
                    category_scores[cat] = val

        for cat in ("gaming", "speech", "cinema", "music"):
            if category_scores.get(cat, 0.0) >= 0.20:
                return AudioAnalysis(cat, category_scores[cat], rms, top_label, top_score)

    norm = [l.casefold() for l in labels]
    speech_indices = [i for i, l in enumerate(norm) if "speech" in l or "voice" in l]
    music_indices = [i for i, l in enumerate(norm) if "music" in l or "song" in l]
    s_score = max([mean_scores[i] for i in speech_indices], default=0.0)
    m_score = max([mean_scores[i] for i in music_indices], default=0.0)

    if s_score >= 0.20 and s_score > m_score:
        return AudioAnalysis("speech", s_score, rms, top_label, top_score)
    if m_score >= 0.20:
        return AudioAnalysis("music", m_score, rms, top_label, top_score)
    return AudioAnalysis("other", top_score, rms, top_label, top_score)


class LightweightDspClassifier:
    """
    Ultra-lightweight real-time acoustic DSP classifier.
    Computes spectral energy distribution, sub-bass ratio, vocal formant presence,
    and crest factor in pure Python with zero external C-dependencies.
    """

    def __init__(self, *args, **kwargs):
        self.labels = ["Silence", "Music", "Speech", "Cinema", "Gaming"]

    def analyze(self, samples, sample_rate=SAMPLE_RATE):
        if sample_rate != SAMPLE_RATE:
            raise ValueError(f"Classifier requires {SAMPLE_RATE} Hz audio.")

        if hasattr(samples, "tolist"):
            samples = samples.tolist()

        if not samples or len(samples) == 0:
            return AudioAnalysis("silence", 1.0, 0.0, "Silence", 1.0)

        # Handle 2D / Stereo
        if isinstance(samples[0], (list, tuple)):
            if len(samples[0]) != 2:
                raise ValueError("Audio must be mono or a frames-by-channels array.")
            mono = [(float(s[0]) + float(s[1])) * 0.5 for s in samples]
        else:
            mono = [float(s) for s in samples]

        # Sanitize non-finite values and clip
        cleaned = []
        for s in mono:
            if not math.isfinite(s):
                cleaned.append(0.0)
            elif s > 1.0:
                cleaned.append(1.0)
            elif s < -1.0:
                cleaned.append(-1.0)
            else:
                cleaned.append(s)
        mono = cleaned

        n = len(mono)
        if n == 0:
            return AudioAnalysis("silence", 1.0, 0.0, "Silence", 1.0)

        sum_sq = sum(s * s for s in mono)
        rms = math.sqrt(sum_sq / n)
        if rms < SILENCE_RMS:
            return AudioAnalysis("silence", 1.0, rms, "Silence", 1.0)

        peak = max(abs(s) for s in mono)
        crest = peak / (rms + 1e-9)

        # Spectral energy via 3 Biquad IIR filters
        # Bass: 100 Hz bandpass (Q=0.7)
        bass_filter = BiquadFilter(100.0, 0.7, sample_rate, "bandpass")
        # Vocal: 1400 Hz bandpass (Q=0.55)
        vocal_filter = BiquadFilter(1400.0, 0.55, sample_rate, "bandpass")
        # High: 5000 Hz highpass (Q=0.7)
        high_filter = BiquadFilter(5000.0, 0.7, sample_rate, "highpass")

        bass_energy = 0.0
        vocal_energy = 0.0
        high_energy = 0.0

        for x in mono:
            by = bass_filter.process(x)
            bass_energy += by * by

            vy = vocal_filter.process(x)
            vocal_energy += vy * vy

            hy = high_filter.process(x)
            high_energy += hy * hy

        total_power = sum_sq + 1e-12
        bass_ratio = bass_energy / total_power
        vocal_ratio = vocal_energy / total_power
        high_ratio = high_energy / total_power

        # 1. Impulsive transient spikes (Gunshots, explosions, impact cues in games)
        # Note: In gaming, gunshots occur against low ambient backgrounds with low spectral spread.
        # In music (e.g. EDM snare rolls, builds), transients are surrounded by high-frequency synth/sparkle.
        if crest > 7.5 and high_ratio < 0.10 and bass_ratio < 0.10:
            return AudioAnalysis("gaming", min(1.0, crest / 10.0), rms, "Dynamic Impact", 0.90)

        # 2. Pure human speech (Podcasts, meetings, calls)
        # Real speech has vocal formants, but negligible sub-bass (< 80 Hz) AND negligible high-frequency air (> 4 kHz).
        # Vocal songs (e.g., Manali Trance intro) have shimmering synth pads, breath air, and reverb tail (high_ratio >= 0.05).
        if vocal_ratio > 0.40 and bass_ratio < 0.08 and high_ratio < 0.05:
            return AudioAnalysis("speech", min(1.0, vocal_ratio), rms, "Dialogue / Voice", vocal_ratio)

        # 3. Music: Sub-bass, electronic hi-hats/synths, or singing with atmospheric air
        if bass_ratio >= 0.08 or high_ratio >= 0.10 or (vocal_ratio > 0.35 and high_ratio >= 0.05):
            score = min(1.0, max((bass_ratio + high_ratio) * 2.0, 0.70))
            return AudioAnalysis("music", score, rms, "Music / Audio Track", score)

        # 4. Cinema: Cinematic balance (Dialogue + background score/ambience)
        return AudioAnalysis("cinema", max(0.5, vocal_ratio), rms, "Cinema / Media", max(0.5, vocal_ratio))






class AudioContentMonitor:
    """Capture short playback-loopback blocks and analyze them with zero-latency DSP."""

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
                    classifier = LightweightDspClassifier()
                speaker = sc.default_speaker()
                if speaker is None:
                    raise RuntimeError("Windows has no active default playback device.")
                speaker_name = str(speaker.name)
                loopback = sc.get_microphone(
                    id=speaker_name,
                    include_loopback=True,
                )
                self._report_status(f"DSP acoustic monitor: {speaker_name}")
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
