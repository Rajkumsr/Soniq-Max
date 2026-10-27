import unittest

import numpy as np

from audio_content import YamnetAudioClassifier, _classify_scores


class AudioContentAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier = YamnetAudioClassifier()

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


if __name__ == "__main__":
    unittest.main()
