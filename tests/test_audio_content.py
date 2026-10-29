import unittest

import numpy as np

from audio_content import LightweightDspClassifier, YamnetAudioClassifier, _classify_scores


class AudioContentAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier = LightweightDspClassifier()

    def test_model_detects_silence_without_retaining_audio(self):
        result = self.classifier.analyze(np.zeros((16000, 2), dtype=np.float32))

        self.assertEqual(result.category, "silence")
        self.assertEqual(result.top_label, "Silence")
        self.assertEqual(result.rms, 0.0)

    def test_model_recognizes_a_music_like_multitone(self):
        sample_rate = 16000
        time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
        music = sum(
            amplitude * np.sin(2 * np.pi * frequency * time_axis)
            for frequency, amplitude in (
                (110, 0.08),
                (220, 0.06),
                (330, 0.05),
                (440, 0.04),
                (660, 0.03),
                (880, 0.02),
            )
        ).astype(np.float32)

        result = self.classifier.analyze(music)

        self.assertEqual(result.category, "music")
        self.assertGreaterEqual(result.category_score, 0.20)
        self.assertTrue(result.top_label)
        self.assertGreater(result.top_score, 0.0)

    def test_model_recognizes_speech_formants(self):
        sample_rate = 16000
        time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
        # Formants concentrated between 500 Hz and 2500 Hz with no sub-bass
        speech = (
            0.08 * np.sin(2 * np.pi * 500 * time_axis)
            + 0.06 * np.sin(2 * np.pi * 1500 * time_axis)
            + 0.04 * np.sin(2 * np.pi * 2500 * time_axis)
        ).astype(np.float32)

        result = self.classifier.analyze(speech)
        self.assertEqual(result.category, "speech")
        self.assertGreaterEqual(result.category_score, 0.50)

    def test_model_recognizes_gaming_transients(self):
        # Sharp high-crest transient spike
        transient = np.zeros(16000, dtype=np.float32)
        transient[1000:1050] = 0.9 * np.sin(np.linspace(0, 10 * np.pi, 50))
        transient[1050:1500] = 0.5 * np.exp(-np.linspace(0, 5, 450)) * np.sin(
            2 * np.pi * 80 * np.linspace(0, 0.1, 450)
        )

        result = self.classifier.analyze(transient)
        self.assertEqual(result.category, "gaming")

    def test_mono_and_stereo_audio_produce_consistent_results(self):
        sample_rate = 16000
        time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
        mono = 0.1 * np.sin(2 * np.pi * 440 * time_axis)

        mono_result = self.classifier.analyze(mono)
        stereo_result = self.classifier.analyze(np.column_stack((mono, mono)))

        self.assertEqual(mono_result.category, stereo_result.category)
        self.assertEqual(mono_result.top_label, stereo_result.top_label)
        self.assertAlmostEqual(mono_result.rms, stereo_result.rms, places=5)

    def test_non_finite_samples_are_sanitized(self):
        result = self.classifier.analyze(np.full(16000, np.nan, dtype=np.float32))

        self.assertEqual(result.category, "silence")
        self.assertEqual(result.rms, 0.0)

    def test_model_requires_its_documented_sample_rate(self):
        with self.assertRaisesRegex(ValueError, "16000 Hz"):
            self.classifier.analyze(np.zeros(8000, dtype=np.float32), sample_rate=8000)

    def test_group_scores_prefer_speech_over_music(self):
        labels = ["Speech", "Conversation", "Music", "Silence"]
        scores = np.array([[0.7, 0.5, 0.2, 0.0]], dtype=np.float32)

        result = _classify_scores(scores, labels, rms=0.1)

        self.assertEqual(result.category, "speech")
        self.assertEqual(result.top_label, "Speech")
        self.assertAlmostEqual(result.category_score, 0.7)

    def test_group_scores_classify_music_and_silence(self):
        labels = ["Speech", "Music", "Silence"]
        music = _classify_scores(np.array([[0.1, 0.6, 0.0]]), labels, rms=0.1)
        silence = _classify_scores(np.array([[0.0, 0.0, 1.0]]), labels, rms=0.1)

        self.assertEqual(music.category, "music")
        self.assertEqual(silence.category, "silence")

    def test_custom_category_map_routing(self):
        labels = ["Speech", "Music", "Gunshot", "Explosion"]
        custom_map = {2: "gaming", 3: "cinema"}
        scores = np.array([[0.05, 0.1, 0.85, 0.2]], dtype=np.float32)

        result = _classify_scores(scores, labels, rms=0.1, category_map=custom_map)
        self.assertEqual(result.category, "gaming")
        self.assertEqual(result.top_label, "Gunshot")


if __name__ == "__main__":
    unittest.main()
