"""
Tests for AudioBridge and VstDirectEngine.
Verifies hardware device discovery, parameter dispatching, and pure-math VST DSP processing.
"""

import math
import os
import pytest

from audio_bridge import (
    AudioBridge,
    VstDirectEngine,
    PARAM_BASS_BOOST,
    PARAM_CLARITY,
    PARAM_SPATIAL,
    PARAM_LIMITER,
    PARAM_MASTER_GAIN,
)


def test_device_discovery():
    devs = AudioBridge.get_audio_devices()
    assert "inputs" in devs
    assert "outputs" in devs
    assert isinstance(devs["inputs"], list)
    assert isinstance(devs["outputs"], list)


def test_find_physical_output():
    phys = AudioBridge.find_physical_output()
    assert phys is not None
    assert isinstance(phys, int)


def test_vst_engine_loading_and_processing_pure_math():
    dll_path = os.path.join(os.path.dirname(__file__), "..", "vst", "bin", "SoniqMaxDSP.dll")
    if not os.path.isfile(dll_path):
        pytest.skip("SoniqMaxDSP.dll not found in vst/bin/")

    engine = VstDirectEngine(dll_path, sample_rate=48000, max_block_size=1024)
    assert engine.plugin is not None

    # Verify parameter writes and reads
    engine.set_param(PARAM_BASS_BOOST, 0.75)
    assert pytest.approx(engine.get_param(PARAM_BASS_BOOST), 0.01) == 0.75

    engine.set_param(PARAM_CLARITY, 0.50)
    assert pytest.approx(engine.get_param(PARAM_CLARITY), 0.01) == 0.50

    # Process test block with pure math
    in_l = [math.sin(2.0 * math.pi * 60.0 * (i / 48000.0)) for i in range(512)]
    in_r = [math.sin(2.0 * math.pi * 60.0 * (i / 48000.0)) for i in range(512)]

    out_l, out_r = engine.process(in_l, in_r)
    assert len(out_l) == 512
    assert len(out_r) == 512
    assert not any(math.isnan(x) for x in out_l)
    assert not any(math.isnan(x) for x in out_r)

    engine.close()


def test_audio_bridge_profile_update():
    bridge = AudioBridge()
    profile = {
        "bass": 60.0,
        "clarity": 80.0,
        "spatial": 45.0,
        "volume": 90.0,
    }
    bridge.update_from_profile(profile, is_headphone=True, master_effects_on=True)
    assert pytest.approx(bridge.param_bass, 0.001) == 0.60
    assert pytest.approx(bridge.param_clarity, 0.001) == 0.80
    assert pytest.approx(bridge.param_spatial, 0.001) == 0.45
    assert pytest.approx(bridge.param_volume, 0.001) == 0.90
    assert bridge.is_headphone is True
    assert bridge.master_effects_on is True

    # Test master effects toggle off (clean bypass)
    bridge.update_from_profile(profile, is_headphone=True, master_effects_on=False)
    assert bridge.master_effects_on is False
    bridge.close()
