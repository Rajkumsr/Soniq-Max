import math
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from audio_content import AudioAnalysis, AudioBuffer, downsample_48k_stereo_to_16k_mono
from soniq_sense_daemon import (
    BROWSER_PROCESSES,
    CAPTURE_ANALYSIS_FRAMES,
    CAPTURE_BLOCK_FRAMES,
    ConsensusDebouncer,
    ForegroundApp,
    LOCAL_MEDIA_PROCESSES,
    SoniqSenseDaemon,
    WasapiLoopbackCapture,
    resolve_fast_profile,
)


class FakeCapture:
    def __init__(self):
        self.recorder = None
        self.open_count = 0
        self.close_count = 0
        self.device_name = "Realtek Speakers"
        self.device_id = "realtek-device"

    def open(self):
        self.recorder = self
        self.open_count += 1

    def read_block(self):
        return AudioBuffer([[0.0, 0.0] for _ in range(CAPTURE_BLOCK_FRAMES)])

    def default_device_changed(self):
        return False

    def close(self):
        if self.recorder is not None:
            self.close_count += 1
        self.recorder = None


class FakeClassifier:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def analyze(self, samples, sample_rate):
        self.calls.append((samples.copy(), sample_rate))
        return self.result


class ResamplingTests(unittest.TestCase):
    def test_downsample_preserves_duration_and_mono_output(self):
        sample_rate = 48000
        tone = [0.25 * math.sin(2 * math.pi * 1000 * i / sample_rate) for i in range(sample_rate)]
        stereo = AudioBuffer([[t, t] for t in tone])

        result = downsample_48k_stereo_to_16k_mono(stereo)

        self.assertEqual(result.shape, (16000,))
        rms = math.sqrt(sum(x * x for x in result[500:-500]) / len(result[500:-500]))
        self.assertAlmostEqual(rms, 0.25 / math.sqrt(2), delta=0.01)

    def test_downsample_rejects_out_of_band_audio_before_decimation(self):
        sample_rate = 48000
        high_tone = [0.5 * math.sin(2 * math.pi * 12000 * i / sample_rate) for i in range(sample_rate)]
        stereo = AudioBuffer([[t, t] for t in high_tone])

        result = downsample_48k_stereo_to_16k_mono(stereo)
        aliased_rms = math.sqrt(sum(x * x for x in result[500:-500]) / len(result[500:-500]))

        self.assertLess(aliased_rms, 0.01)

    def test_downsample_requires_stereo_frame_matrix(self):
        with self.assertRaisesRegex(ValueError, "two-channels"):
            downsample_48k_stereo_to_16k_mono([0.0] * 48000)


class WasapiCaptureTests(unittest.TestCase):
    def test_open_supports_integer_and_sequence_channel_metadata(self):
        for channels in (2, [0, 1]):
            with self.subTest(channels=channels):
                speaker = SimpleNamespace(
                    name="Realtek Speakers",
                    id="realtek-device",
                    channels=channels,
                )
                recorder = MagicMock()
                recorder.__enter__.return_value = recorder
                recorder.record.return_value = AudioBuffer(
                    [[0.0, 0.0] for _ in range(CAPTURE_BLOCK_FRAMES)]
                )
                soundcard = Mock()
                soundcard.default_speaker.return_value = speaker
                soundcard.get_microphone.return_value.recorder.return_value = recorder
                capture = WasapiLoopbackCapture()

                with patch.dict("sys.modules", {"soundcard": soundcard}):
                    capture.open()
                    result = capture.read_block()
                    capture.close()

                self.assertEqual(result.shape, (CAPTURE_BLOCK_FRAMES, 2))
                soundcard.get_microphone.assert_called_once_with(
                    id=speaker.name, include_loopback=True
                )
                recorder.__enter__.assert_called_once()
                recorder.__exit__.assert_called_once_with(None, None, None)

    def test_open_rejects_mono_output_endpoint(self):
        speaker = SimpleNamespace(name="Mono Speakers", id="mono", channels=1)
        soundcard = Mock()
        soundcard.default_speaker.return_value = speaker
        capture = WasapiLoopbackCapture()

        with patch.dict("sys.modules", {"soundcard": soundcard}):
            with self.assertRaisesRegex(RuntimeError, "does not expose stereo"):
                capture.open()

        soundcard.get_microphone.assert_not_called()


class AppRuleTests(unittest.TestCase):
    def test_browser_is_routed_to_ai_fallback(self):
        for process in BROWSER_PROCESSES:
            with self.subTest(process=process):
                self.assertIsNone(resolve_fast_profile(process))

    def test_local_media_uses_fast_music_profile(self):
        for process in LOCAL_MEDIA_PROCESSES:
            with self.subTest(process=process):
                self.assertEqual(resolve_fast_profile(process), "bass_beast")

    def test_game_and_call_rules_map_to_configured_profiles(self):
        self.assertEqual(
            resolve_fast_profile("a_game.exe", "fps_gaming", game_profile="fps_gaming"),
            "fps_gaming",
        )
        self.assertEqual(
            resolve_fast_profile("teams.exe", speech_profile="voice_meeting"),
            "voice_meeting",
        )

    def test_debouncer_requires_consecutive_observations(self):
        debouncer = ConsensusDebouncer(evaluations=3)

        self.assertIsNone(debouncer.observe("bass_beast"))
        self.assertIsNone(debouncer.observe("fps_gaming"))
        self.assertIsNone(debouncer.observe("bass_beast"))
        self.assertIsNone(debouncer.observe("bass_beast"))
        self.assertEqual(debouncer.observe("bass_beast"), "bass_beast")

    def test_idle_observation_resets_pending_consensus(self):
        debouncer = ConsensusDebouncer(evaluations=2)
        debouncer.observe("bass_beast")
        self.assertIsNone(debouncer.observe(None))
        self.assertIsNone(debouncer.observe("bass_beast"))
        self.assertEqual(debouncer.observe("bass_beast"), "bass_beast")


class DaemonIntegrationTests(unittest.TestCase):
    def test_fast_app_rule_does_not_open_capture_or_run_model(self):
        capture = FakeCapture()
        classifier = FakeClassifier(
            AudioAnalysis("music", 0.9, 0.1, "Music", 0.9)
        )
        app = ForegroundApp("spotify.exe", 20, 200)
        daemon = SoniqSenseDaemon(
            config_path=os.path.join(tempfile.gettempdir(), "config.txt"),
            capture=capture,
            classifier=classifier,
            foreground_reader=lambda: app,
            debounce=2,
        )
        with patch("soniq_sense_daemon.install_apo_config") as install:
            daemon.run_iteration()
            daemon.run_iteration()

        self.assertEqual(capture.open_count, 0)
        self.assertEqual(classifier.calls, [])
        self.assertEqual(daemon.current_profile, "bass_beast")
        install.assert_called_once()

    def test_browser_only_runs_model_on_new_full_analysis_windows(self):
        capture = FakeCapture()
        classifier = FakeClassifier(
            AudioAnalysis("music", 0.9, 0.1, "Music", 0.9)
        )
        app = ForegroundApp("chrome.exe", 30, 300)
        daemon = SoniqSenseDaemon(
            config_path=os.path.join(tempfile.gettempdir(), "config.txt"),
            capture=capture,
            classifier=classifier,
            foreground_reader=lambda: app,
            debounce=2,
        )
        with patch("soniq_sense_daemon.install_apo_config") as install:
            for _ in range(24):
                daemon.run_iteration()

        self.assertEqual(capture.open_count, 1)
        self.assertEqual(len(classifier.calls), 3)
        self.assertEqual(classifier.calls[0][0].shape, (16000,))
        self.assertEqual(classifier.calls[0][1], 16000)
        self.assertEqual(daemon.current_profile, "bass_beast")
        install.assert_called_once()
        self.assertEqual(CAPTURE_ANALYSIS_FRAMES, 48000)

    def test_browser_analysis_holds_current_profile_for_unknown_audio(self):
        capture = FakeCapture()
        classifier = FakeClassifier(
            AudioAnalysis("other", 0.4, 0.1, "Engine", 0.4)
        )
        app = ForegroundApp("msedge.exe", 40, 400)
        daemon = SoniqSenseDaemon(
            config_path=os.path.join(tempfile.gettempdir(), "config.txt"),
            capture=capture,
            classifier=classifier,
            foreground_reader=lambda: app,
            debounce=2,
        )
        daemon.current_profile = "audiophile_flat"
        with patch("soniq_sense_daemon.install_apo_config") as install:
            for _ in range(18):
                daemon.run_iteration()

        self.assertEqual(daemon.current_profile, "audiophile_flat")
        install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
