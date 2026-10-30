import math
import unittest

from audio_content import LightweightDspClassifier, _classify_scores


class AudioContentAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier = LightweightDspClassifier()

    def test_model_detects_silence_without_retaining_audio(self):
        result = self.classifier.analyze([[0.0, 0.0] for _ in range(16000)])

        self.assertEqual(result.category, "silence")
        self.assertEqual(result.top_label, "Silence")
        self.assertEqual(result.rms, 0.0)

    def test_model_recognizes_a_music_like_multitone(self):
        sample_rate = 16000
        harmonics = (
            (110, 0.08),
            (220, 0.06),
            (330, 0.05),
            (440, 0.04),
            (660, 0.03),
            (880, 0.02),
        )
        music = [
            sum(amp * math.sin(2 * math.pi * freq * i / sample_rate) for freq, amp in harmonics)
            for i in range(sample_rate)
        ]

        result = self.classifier.analyze(music)

        self.assertEqual(result.category, "music")
        self.assertGreaterEqual(result.category_score, 0.20)
        self.assertTrue(result.top_label)
        self.assertGreater(result.top_score, 0.0)

    def test_model_recognizes_speech_formants(self):
        sample_rate = 16000
        # Formants concentrated between 500 Hz and 2500 Hz with no sub-bass
        speech = [
            0.08 * math.sin(2 * math.pi * 500 * i / sample_rate)
            + 0.06 * math.sin(2 * math.pi * 1500 * i / sample_rate)
            + 0.04 * math.sin(2 * math.pi * 2500 * i / sample_rate)
            for i in range(sample_rate)
        ]

        result = self.classifier.analyze(speech)
        self.assertEqual(result.category, "speech")
        self.assertGreaterEqual(result.category_score, 0.40)

    def test_model_recognizes_gaming_transients(self):
        # Sharp high-crest transient spike
        transient = [0.0] * 16000
        for i in range(50):
            transient[1000 + i] = 0.9 * math.sin(10 * math.pi * i / 50)
        for i in range(450):
            transient[1050 + i] = 0.5 * math.exp(-i * 5.0 / 450.0) * math.sin(
                2 * math.pi * 80 * i * 0.1 / 450.0
            )

        result = self.classifier.analyze(transient)
        self.assertEqual(result.category, "gaming")

    def test_manali_trance_style_vocal_intro_classified_as_music(self):
        sample_rate = 16000
        # Breathy whisper vocal formants (1200, 1800 Hz) with atmospheric synth shimmer / air (6000, 7500 Hz)
        # and zero sub-bass (typical of atmospheric vocal intros like Manali Trance)
        vocal_intro = [
            0.06 * math.sin(2 * math.pi * 1200 * i / sample_rate)
            + 0.05 * math.sin(2 * math.pi * 1800 * i / sample_rate)
            + 0.03 * math.sin(2 * math.pi * 6000 * i / sample_rate)
            + 0.02 * math.sin(2 * math.pi * 7500 * i / sample_rate)
            for i in range(sample_rate)
        ]

        result = self.classifier.analyze(vocal_intro)
        self.assertEqual(result.category, "music")
        self.assertGreaterEqual(result.category_score, 0.70)

    def test_edm_snare_roll_classified_as_music(self):
        sample_rate = 16000
        # Sharp transient snare hits surrounded by high-frequency energy (snare sizzle / white noise)
        snare_roll = [0.0] * 16000
        for hit_start in (1000, 3000, 5000, 7000, 9000, 11000, 13000, 15000):
            for i in range(200):
                decay = math.exp(-i / 40.0)
                snare_roll[hit_start + i] = decay * (
                    0.5 * math.sin(2 * math.pi * 200 * i / sample_rate)
                    + 0.4 * math.sin(2 * math.pi * 6000 * i / sample_rate)
                )

        result = self.classifier.analyze(snare_roll)
        self.assertEqual(result.category, "music")
        self.assertNotEqual(result.category, "gaming")

    def test_mono_and_stereo_audio_produce_consistent_results(self):
        sample_rate = 16000
        mono = [0.1 * math.sin(2 * math.pi * 440 * i / sample_rate) for i in range(sample_rate)]
        stereo = [[m, m] for m in mono]

        mono_result = self.classifier.analyze(mono)
        stereo_result = self.classifier.analyze(stereo)

        self.assertEqual(mono_result.category, stereo_result.category)
        self.assertEqual(mono_result.top_label, stereo_result.top_label)
        self.assertAlmostEqual(mono_result.rms, stereo_result.rms, places=5)

    def test_non_finite_samples_are_sanitized(self):
        result = self.classifier.analyze([float("nan")] * 16000)

        self.assertEqual(result.category, "silence")
        self.assertEqual(result.rms, 0.0)

    def test_model_requires_its_documented_sample_rate(self):
        with self.assertRaisesRegex(ValueError, "16000 Hz"):
            self.classifier.analyze([0.0] * 8000, sample_rate=8000)

    def test_group_scores_prefer_speech_over_music(self):
        labels = ["Speech", "Conversation", "Music", "Silence"]
        scores = [[0.7, 0.5, 0.2, 0.0]]

        result = _classify_scores(scores, labels, rms=0.1)

        self.assertEqual(result.category, "speech")
        self.assertEqual(result.top_label, "Speech")
        self.assertAlmostEqual(result.category_score, 0.7)

    def test_group_scores_classify_music_and_silence(self):
        labels = ["Speech", "Music", "Silence"]
        music = _classify_scores([[0.1, 0.6, 0.0]], labels, rms=0.1)
        silence = _classify_scores([[0.0, 0.0, 1.0]], labels, rms=0.1)

        self.assertEqual(music.category, "music")
        self.assertEqual(silence.category, "silence")

    def test_custom_category_map_routing(self):
        labels = ["Speech", "Music", "Gunshot", "Explosion"]
        custom_map = {2: "gaming", 3: "cinema"}
        scores = [[0.05, 0.1, 0.85, 0.2]]

        result = _classify_scores(scores, labels, rms=0.1, category_map=custom_map)
        self.assertEqual(result.category, "gaming")
        self.assertEqual(result.top_label, "Gunshot")


if __name__ == "__main__":
    unittest.main()
