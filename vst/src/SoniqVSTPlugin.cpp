/**
 * SoniqVSTPlugin — Real-Time Psychoacoustic DSP Audio Processing Plugin
 * Engineered by CodeCraftersIndia
 * Compatible with Equalizer APO & Direct Soniq Engine (64-bit Windows)
 *
 * Single Source of Truth Architecture:
 * - Core Algorithms: SoniqAther.hpp (Decoupled Pure C++ SoniqAther DSP Engine)
 * - VST 2.4 Interface: SoniqVSTPlugin (Adapts core engine to VST 2.4 specification)
 * - 23 Parameters: 10-Band EQ, Preamp, Harmonics, Clarity, Spatial, Limiter, Bypasses
 * - Standard C ABI Exports: Direct high-performance invocation without VST wrapper overhead
 */

#include "aeffect.h"
#include "SoniqAther.hpp"

// Bring parameter constants into global scope for backward compatibility
using SoniqAudio::NUM_PARAMS;
using SoniqAudio::PLUGIN_UNIQUE_ID;
using SoniqAudio::ParamIndex;
using SoniqAudio::kParamBass;
using SoniqAudio::kParamClarity;
using SoniqAudio::kParamSpatial;
using SoniqAudio::kParamLimiter;
using SoniqAudio::kParamMasterGain;
using SoniqAudio::kParamSpatialMode;
using SoniqAudio::kParamCeiling;
using SoniqAudio::kParamPreamp;
using SoniqAudio::kParamEQEnable;
using SoniqAudio::kParamBassEnable;
using SoniqAudio::kParamClarityEnable;
using SoniqAudio::kParamSpatialEnable;
using SoniqAudio::kParamEQ_32Hz;
using SoniqAudio::kParamEQ_64Hz;
using SoniqAudio::kParamEQ_125Hz;
using SoniqAudio::kParamEQ_250Hz;
using SoniqAudio::kParamEQ_500Hz;
using SoniqAudio::kParamEQ_1kHz;
using SoniqAudio::kParamEQ_2kHz;
using SoniqAudio::kParamEQ_4kHz;
using SoniqAudio::kParamEQ_8kHz;
using SoniqAudio::kParamEQ_16kHz;
using SoniqAudio::kParamSpeakerHPF;

#if defined(_WIN32)
#define VST_EXPORT __declspec(dllexport)
#else
#define VST_EXPORT
#endif

class SoniqVSTPlugin {
public:
    AEffect effect;
    SoniqAudio::SoniqAther dsp;

    // Direct member aliases for tests & backward-compatibility
    float& sampleRate;
    float* params;
    float& smoothedBass;
    float& smoothedClarity;
    float& smoothedSpatial;
    float& smoothedMasterGain;

    SoniqVSTPlugin() :
        sampleRate(dsp.sampleRate),
        params(dsp.params),
        smoothedBass(dsp.smoothedBass),
        smoothedClarity(dsp.smoothedClarity),
        smoothedSpatial(dsp.smoothedSpatial),
        smoothedMasterGain(dsp.smoothedMasterGain)
    {
        std::memset(&effect, 0, sizeof(AEffect));
        effect.magic = kEffectMagic;
        effect.dispatcher = dispatcherCallback;
        effect.process = processReplacingCallback;
        effect.processReplacing = processReplacingCallback;
        effect.setParameter = setParameterCallback;
        effect.getParameter = getParameterCallback;
        effect.numPrograms = 1;
        effect.numParams = SoniqAudio::NUM_PARAMS;
        effect.numInputs = 2;
        effect.numOutputs = 2;
        effect.flags = effFlagsCanReplacing;
        effect.uniqueID = SoniqAudio::PLUGIN_UNIQUE_ID;
        effect.version = 2400; // VST 2.4 rev 2
        effect.object = this;
    }

    void reset() {
        dsp.reset();
    }

    void setParameter(int index, float value) {
        dsp.setParameter(index, value);
    }

    float getParameter(int index) const {
        return dsp.getParameter(index);
    }

    void process(float** in, float** out, int frames) {
        dsp.process(in, out, frames);
    }

    void recalculateSampleRateDependent() {
        dsp.recalculateSampleRateDependent();
    }

    void updateFilters() {
        dsp.updateFilters();
    }

    static intptr_t dispatcherCallback(AEffect* e, int32_t opcode, int32_t index, intptr_t value, void* ptr, float opt) {
        SoniqVSTPlugin* self = static_cast<SoniqVSTPlugin*>(e->object);
        switch (opcode) {
            case effOpen:
                return 0;
            case effClose:
                delete self;
                return 0;
            case effSetSampleRate:
                self->dsp.setSampleRate(opt);
                return 0;
            case effGetEffectName:
                std::strncpy(static_cast<char*>(ptr), "SoniqVSTPlugin", 31);
                return 1;
            case effGetVendorString:
                std::strncpy(static_cast<char*>(ptr), "CodeCraftersIndia", 31);
                return 1;
            case effGetProductString:
                std::strncpy(static_cast<char*>(ptr), "SONIQ MAX PRO by CodeCrafters", 31);
                return 1;
            case effGetParamName:
                switch (index) {
                    case SoniqAudio::kParamBass: std::strncpy(static_cast<char*>(ptr), "Bass", 31); return 1;
                    case SoniqAudio::kParamClarity: std::strncpy(static_cast<char*>(ptr), "Clarity", 31); return 1;
                    case SoniqAudio::kParamSpatial: std::strncpy(static_cast<char*>(ptr), "Spatial", 31); return 1;
                    case SoniqAudio::kParamLimiter: std::strncpy(static_cast<char*>(ptr), "Limiter", 31); return 1;
                    case SoniqAudio::kParamMasterGain: std::strncpy(static_cast<char*>(ptr), "MasterGain", 31); return 1;
                    case SoniqAudio::kParamSpatialMode: std::strncpy(static_cast<char*>(ptr), "SpatialMode", 31); return 1;
                    case SoniqAudio::kParamCeiling: std::strncpy(static_cast<char*>(ptr), "Ceiling", 31); return 1;
                    case SoniqAudio::kParamPreamp: std::strncpy(static_cast<char*>(ptr), "Preamp", 31); return 1;
                    case SoniqAudio::kParamEQEnable: std::strncpy(static_cast<char*>(ptr), "EQEnable", 31); return 1;
                    case SoniqAudio::kParamBassEnable: std::strncpy(static_cast<char*>(ptr), "BassEnable", 31); return 1;
                    case SoniqAudio::kParamClarityEnable: std::strncpy(static_cast<char*>(ptr), "ClarityEnable", 31); return 1;
                    case SoniqAudio::kParamSpatialEnable: std::strncpy(static_cast<char*>(ptr), "SpatialEnable", 31); return 1;
                    case SoniqAudio::kParamEQ_32Hz: std::strncpy(static_cast<char*>(ptr), "EQ32Hz", 31); return 1;
                    case SoniqAudio::kParamEQ_64Hz: std::strncpy(static_cast<char*>(ptr), "EQ64Hz", 31); return 1;
                    case SoniqAudio::kParamEQ_125Hz: std::strncpy(static_cast<char*>(ptr), "EQ125Hz", 31); return 1;
                    case SoniqAudio::kParamEQ_250Hz: std::strncpy(static_cast<char*>(ptr), "EQ250Hz", 31); return 1;
                    case SoniqAudio::kParamEQ_500Hz: std::strncpy(static_cast<char*>(ptr), "EQ500Hz", 31); return 1;
                    case SoniqAudio::kParamEQ_1kHz: std::strncpy(static_cast<char*>(ptr), "EQ1kHz", 31); return 1;
                    case SoniqAudio::kParamEQ_2kHz: std::strncpy(static_cast<char*>(ptr), "EQ2kHz", 31); return 1;
                    case SoniqAudio::kParamEQ_4kHz: std::strncpy(static_cast<char*>(ptr), "EQ4kHz", 31); return 1;
                    case SoniqAudio::kParamEQ_8kHz: std::strncpy(static_cast<char*>(ptr), "EQ8kHz", 31); return 1;
                    case SoniqAudio::kParamEQ_16kHz: std::strncpy(static_cast<char*>(ptr), "EQ16kHz", 31); return 1;
                    case SoniqAudio::kParamSpeakerHPF: std::strncpy(static_cast<char*>(ptr), "SpeakerHPF", 31); return 1;
                }
                return 0;
            case effGetParamLabel:
                switch (index) {
                    case SoniqAudio::kParamBass:
                    case SoniqAudio::kParamClarity:
                    case SoniqAudio::kParamSpatial: std::strncpy(static_cast<char*>(ptr), "%", 31); return 1;
                    case SoniqAudio::kParamLimiter:
                    case SoniqAudio::kParamEQEnable:
                    case SoniqAudio::kParamBassEnable:
                    case SoniqAudio::kParamClarityEnable:
                    case SoniqAudio::kParamSpatialEnable:
                    case SoniqAudio::kParamSpeakerHPF: std::strncpy(static_cast<char*>(ptr), "On/Off", 31); return 1;
                    case SoniqAudio::kParamMasterGain: std::strncpy(static_cast<char*>(ptr), "x", 31); return 1;
                    case SoniqAudio::kParamSpatialMode: std::strncpy(static_cast<char*>(ptr), "Mode", 31); return 1;
                    case SoniqAudio::kParamCeiling: std::strncpy(static_cast<char*>(ptr), "Linear", 31); return 1;
                    case SoniqAudio::kParamPreamp:
                    case SoniqAudio::kParamEQ_32Hz:
                    case SoniqAudio::kParamEQ_64Hz:
                    case SoniqAudio::kParamEQ_125Hz:
                    case SoniqAudio::kParamEQ_250Hz:
                    case SoniqAudio::kParamEQ_500Hz:
                    case SoniqAudio::kParamEQ_1kHz:
                    case SoniqAudio::kParamEQ_2kHz:
                    case SoniqAudio::kParamEQ_4kHz:
                    case SoniqAudio::kParamEQ_8kHz:
                    case SoniqAudio::kParamEQ_16kHz: std::strncpy(static_cast<char*>(ptr), "dB", 31); return 1;
                }
                return 0;
            case effGetVstVersion:
                return 2400;
            case effCanDo:
                if (ptr) {
                    if (std::strcmp(static_cast<const char*>(ptr), "bypass") == 0) return 1;
                }
                return 0;
            default:
                return 0;
        }
    }

    static void setParameterCallback(AEffect* e, int32_t index, float value) {
        SoniqVSTPlugin* self = static_cast<SoniqVSTPlugin*>(e->object);
        self->dsp.setParameter(index, value);
    }

    static float getParameterCallback(AEffect* e, int32_t index) {
        SoniqVSTPlugin* self = static_cast<SoniqVSTPlugin*>(e->object);
        return self->dsp.getParameter(index);
    }

    static void processReplacingCallback(AEffect* e, float** inputs, float** outputs, int32_t sampleFrames) {
        SoniqVSTPlugin* self = static_cast<SoniqVSTPlugin*>(e->object);
        self->dsp.process(inputs, outputs, sampleFrames);
    }
};

// Backward compatibility alias for tests and direct callers
using SoniqMaxEffect = SoniqVSTPlugin;

// ============================================================================
// Standard VST 2.4 Entry Point
// ============================================================================
extern "C" {
    VST_EXPORT AEffect* VSTPluginMain(audioMasterCallback audioMaster) {
        SoniqVSTPlugin* effect = new SoniqVSTPlugin();
        return &effect->effect;
    }
}

// ============================================================================
// Decoupled Pure C ABI Exports (Enables Direct Host & Future sAPO Usage)
// ============================================================================
extern "C" {
    VST_EXPORT void* Soniq_CreateEngine() {
        return new SoniqAudio::SoniqAther();
    }

    VST_EXPORT void Soniq_DestroyEngine(void* handle) {
        if (handle) {
            delete static_cast<SoniqAudio::SoniqAther*>(handle);
        }
    }

    VST_EXPORT void Soniq_SetSampleRate(void* handle, float sampleRate) {
        if (handle) {
            static_cast<SoniqAudio::SoniqAther*>(handle)->setSampleRate(sampleRate);
        }
    }

    VST_EXPORT void Soniq_SetParameter(void* handle, int paramIndex, float value) {
        if (handle) {
            static_cast<SoniqAudio::SoniqAther*>(handle)->setParameter(paramIndex, value);
        }
    }

    VST_EXPORT float Soniq_GetParameter(void* handle, int paramIndex) {
        if (handle) {
            return static_cast<SoniqAudio::SoniqAther*>(handle)->getParameter(paramIndex);
        }
        return 0.0f;
    }

    VST_EXPORT void Soniq_Reset(void* handle) {
        if (handle) {
            static_cast<SoniqAudio::SoniqAther*>(handle)->reset();
        }
    }

    VST_EXPORT void Soniq_ProcessReplacing(void* handle, float** inputs, float** outputs, int sampleFrames) {
        if (handle) {
            static_cast<SoniqAudio::SoniqAther*>(handle)->process(inputs, outputs, sampleFrames);
        }
    }

    VST_EXPORT void Soniq_ProcessInterleaved(void* handle, float* inOutBuffer, int sampleFrames) {
        if (handle) {
            static_cast<SoniqAudio::SoniqAther*>(handle)->processInterleaved(inOutBuffer, sampleFrames);
        }
    }
}
