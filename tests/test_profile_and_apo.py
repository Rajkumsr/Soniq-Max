import copy
import os
import tempfile
import unittest
from pathlib import Path

from constants import (
    DEFAULT_PROFILES,
    SENSE_LOCAL_MUSIC_PROCESSES,
    resolve_sense_profile,
    should_classify_browser_audio,
    validate_profile_data,
)
from export_system_apo import (
    MANAGED_CONFIG_NAME,
    generate_apo_config,
    estimate_peak_filter_gain_db,
    install_apo_config,
    profile_filter_values,
)


class ProfileValidationTests(unittest.TestCase):
    def test_builtin_profiles_are_valid(self):
        for profile in DEFAULT_PROFILES.values():
            validate_profile_data(profile)

    def test_rejects_invalid_eq_gain(self):
        profile = copy.deepcopy(DEFAULT_PROFILES["laptop_lifesaver"])
        profile["eq"][0] = 13
        with self.assertRaisesRegex(ValueError, "between -12 and \\+12"):
            validate_profile_data(profile)

    def test_rejects_boolean_as_numeric_value(self):
        profile = copy.deepcopy(DEFAULT_PROFILES["laptop_lifesaver"])
        profile["bass"] = True
        with self.assertRaisesRegex(ValueError, "must be a number"):
            validate_profile_data(profile)

    def test_soniq_sense_assignments_override_detected_category_defaults(self):
        assignments = {
            "gaming": "audiophile_flat",
            "music": "cinema_dialogue",
            "speech": "bass_beast",
            "other": "laptop_lifesaver",
        }

        self.assertEqual(resolve_sense_profile("fps_gaming", assignments), "audiophile_flat")
        self.assertEqual(resolve_sense_profile("bass_beast", assignments), "cinema_dialogue")
        self.assertEqual(resolve_sense_profile("voice_meeting", assignments), "bass_beast")
        self.assertEqual(resolve_sense_profile("other", assignments), "laptop_lifesaver")
        self.assertEqual(resolve_sense_profile("unknown_target", assignments), "unknown_target")

    def test_soniq_sense_runs_content_classifier_only_for_browser_sessions(self):
        self.assertTrue(should_classify_browser_audio(["chrome.exe"]))
        self.assertTrue(should_classify_browser_audio(["other.exe", "msedge.exe"]))
        self.assertFalse(should_classify_browser_audio([]))
        self.assertFalse(
            should_classify_browser_audio(["chrome.exe", "spotify.exe"])
        )
        for process_name in SENSE_LOCAL_MUSIC_PROCESSES:
            with self.subTest(process_name=process_name):
                self.assertFalse(should_classify_browser_audio([process_name]))


class ApoConfigTests(unittest.TestCase):
    def test_selected_profile_values_do_not_depend_on_old_slider_values(self):
        profile = DEFAULT_PROFILES["cinema_dialogue"]
        values = profile_filter_values(
            profile,
            {"bass": True, "clarity": True, "spatial": True, "volume": True},
        )

        self.assertEqual(values["bass_boost"], profile["bass"] / 100)
        self.assertEqual(values["clarity"], profile["clarity"] / 100)
        self.assertEqual(values["spatial_width"], profile["spatial"] / 100)
        self.assertEqual(values["volume_boost_db"], profile["volume"])

    def test_disabled_effects_generate_neutral_filter_values(self):
        values = profile_filter_values(
            DEFAULT_PROFILES["laptop_lifesaver"],
            {"bass": False, "clarity": False, "spatial": False, "volume": False},
        )

        self.assertEqual(
            values,
            {
                "bass_boost": 0.0,
                "clarity": 0.0,
                "spatial_width": 1.0,
                "volume_boost_db": 0.0,
            },
        )

    def test_generates_speaker_and_headphone_configs(self):
        gains = [0.0] * 10
        speaker = generate_apo_config("Test", gains, 0.5, 0.5, 1.5, 4.0)
        headphones = generate_apo_config(
            "Test", gains, 0.5, 0.5, 1.5, 4.0, is_headphone=True
        )

        self.assertIn("Filter: ON HP Fc 120 Hz", speaker)
        self.assertNotIn("Filter: ON HP Fc 120 Hz", headphones)
        self.assertIn("static eq with estimated peak headroom compensation", speaker.lower())
        self.assertIn("no dynamic limiter or compressor", speaker.lower())
        self.assertIn("does not synthesize harmonics", speaker.lower())
        self.assertIn("no haas delay", speaker.lower())
        self.assertIn("Filter: ON LSC 6 dB Fc 200 Hz", speaker)
        self.assertIn("Filter: ON PK Fc 2800 Hz", speaker)

    def test_peak_headroom_covers_combined_eq_bass_voice_and_spatial_filters(self):
        gains = [6.0, 5.0, 4.0, 3.0, 2.0, 3.0, 5.0, 6.0, 4.0, 2.0]
        bass = 0.8
        clarity = 0.9
        width = 2.5
        target_boost = 6.0

        estimated_peak = estimate_peak_filter_gain_db(
            gains, bass, clarity, width, is_headphone=False
        )
        config = generate_apo_config(
            "Headroom Test", gains, bass, clarity, width, target_boost
        )
        preamp_line = next(line for line in config.splitlines() if line.startswith("Preamp:"))
        applied_preamp = float(preamp_line.split()[1])

        self.assertGreater(estimated_peak, 0.0)
        self.assertLessEqual(applied_preamp + estimated_peak, target_boost + 0.1)
        self.assertIn("Copy: L=", config)

    def test_builtin_profiles_receive_headroom_for_their_generated_effects(self):
        for profile in DEFAULT_PROFILES.values():
            with self.subTest(profile=profile["title"]):
                bass = profile["bass"] / 100
                clarity = profile["clarity"] / 100
                width = profile["spatial"] / 100
                estimated_peak = estimate_peak_filter_gain_db(
                    profile["eq"], bass, clarity, width, is_headphone=False
                )
                config = generate_apo_config(
                    profile["title"],
                    profile["eq"],
                    bass,
                    clarity,
                    width,
                    profile["volume"],
                )
                preamp_line = next(
                    line for line in config.splitlines() if line.startswith("Preamp:")
                )
                applied_preamp = float(preamp_line.split()[1])

                self.assertLessEqual(
                    applied_preamp + estimated_peak,
                    profile["volume"] + 0.1,
                )

    def test_flat_profile_preserves_requested_output_target(self):
        target_boost = 3.0
        config = generate_apo_config(
            "Flat", [0.0] * 10, 0.0, 0.0, 1.0, target_boost
        )

        preamp_line = next(line for line in config.splitlines() if line.startswith("Preamp:"))
        self.assertEqual(float(preamp_line.split()[1]), target_boost)

    def test_rejects_invalid_eq_shape_and_out_of_range_input(self):
        with self.assertRaisesRegex(ValueError, "exactly 10 gains"):
            generate_apo_config("Test", [0.0], 0.0, 0.0, 1.0, 0.0)
        with self.assertRaisesRegex(ValueError, "Bass level"):
            generate_apo_config("Test", [0.0] * 10, 1.1, 0.0, 1.0, 0.0)
        with self.assertRaisesRegex(ValueError, "line breaks"):
            generate_apo_config("Test\nPreamp: +20 dB", [0.0] * 10, 0.0, 0.0, 1.0, 0.0)

    def test_checked_in_local_config_matches_battlefield_profile(self):
        profile = DEFAULT_PROFILES["fps_gaming"]
        expected = generate_apo_config(
            "Battlefield 360",
            profile["eq"],
            profile["bass"] / 100,
            profile["clarity"] / 100,
            profile["spatial"] / 100,
            profile["volume"],
        )
        actual = (Path(__file__).resolve().parents[1] / "SONIQ_APO_Config.txt").read_text(
            encoding="utf-8"
        )
        self.assertEqual(actual, expected)

    def test_install_preserves_existing_config_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            main_config = os.path.join(temp_dir, "config.txt")
            original = "\ufeff# User filters\nPreamp: -1 dB\n"
            with open(main_config, "w", encoding="utf-8") as stream:
                stream.write(original)

            managed_path = install_apo_config(main_config, "Preamp: +1 dB\n")
            with open(main_config, "r", encoding="utf-8") as stream:
                first_result = stream.read()

            install_apo_config(main_config, "Preamp: +2 dB\n")
            with open(main_config, "r", encoding="utf-8") as stream:
                second_result = stream.read()
            with open(managed_path, "r", encoding="utf-8") as stream:
                managed_content = stream.read()

            self.assertTrue(os.path.isfile(managed_path))
            self.assertTrue(managed_path.endswith(MANAGED_CONFIG_NAME))
            self.assertIn(original, first_result)
            self.assertEqual(first_result.count("Include: SONIQ_MAX_Config.txt"), 1)
            self.assertEqual(second_result.count("Include: SONIQ_MAX_Config.txt"), 1)
            self.assertIn("Preamp: +2 dB", managed_content)

    def test_vst_plugin_directive_generation(self):
        config = generate_apo_config(
            "VST Test",
            [0.0] * 10,
            0.5,
            0.5,
            1.2,
            2.0,
            vst_plugins=["VSTPlugins\\SoniqMaxDSP.dll"]
        )
        self.assertIn("# Native VST Plugin Processing", config)
        self.assertIn('VSTPlugin: Library "VSTPlugins\\SoniqMaxDSP.dll"', config)

    def test_install_creates_main_config_without_replacing_managed_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            main_config = os.path.join(temp_dir, "config.txt")
            managed_path = install_apo_config(main_config, "Preamp: 0 dB\n")

            self.assertTrue(os.path.isfile(main_config))
            self.assertTrue(os.path.isfile(managed_path))
            self.assertIn(
                "Include: SONIQ_MAX_Config.txt",
                Path(main_config).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
