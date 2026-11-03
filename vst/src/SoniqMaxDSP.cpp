/**
 * SONIQ MAX PRO Real-Time Psychoacoustic DSP Audio Processing Plugin
 * Compatible with Equalizer APO & Direct Soniq Engine (64-bit Windows)
 *
 * Architecture:
 * - Core Algorithms: SoniqDspCore.hpp (Decoupled Pure C++ DSP Engine)
 * - VST 2.4 Interface: SoniqMaxEffect (Adapts core engine to VST 2.4 specification)
 * - Standard C ABI Exports: Direct high-performance invocation without VST wrapper overhead
 */

#include "aeffect.h"
#include "SoniqDspCore.hpp"

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

#if defined(_WIN32)
#define VST_EXPORT __declspec(dllexport)
#else
#define VST_EXPORT
#endif

class SoniqMaxEffect {
public:
    AEffect effect;
    SoniqAudio::SoniqDspEngine dsp;

    // Direct member aliases for tests & backward-compatibility
    float& sampleRate;
    float* params;
    float& smoothedBass;
    float& smoothedClarity;
    float& smoothedSpatial;
    float& smoothedMasterGain;

    SoniqMaxEffect() :
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
        SoniqMaxEffect* self = static_cast<SoniqMaxEffect*>(e->object);
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
                std::strncpy(static_cast<char*>(ptr), "SONIQ MAX DSP", 31);
                return 1;
            case effGetVendorString:
                std::strncpy(static_cast<char*>(ptr), "SONIQ MAX", 31);
                return 1;
            case effGetProductString:
                std::strncpy(static_cast<char*>(ptr), "SONIQ MAX Audio Enhancer", 31);
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
                }
                return 0;
            case effGetParamLabel:
                switch (index) {
                    case SoniqAudio::kParamBass:
                    case SoniqAudio::kParamClarity:
                    case SoniqAudio::kParamSpatial: std::strncpy(static_cast<char*>(ptr), "%", 31); return 1;
                    case SoniqAudio::kParamLimiter: std::strncpy(static_cast<char*>(ptr), "On/Off", 31); return 1;
                    case SoniqAudio::kParamMasterGain: std::strncpy(static_cast<char*>(ptr), "x", 31); return 1;
                    case SoniqAudio::kParamSpatialMode: std::strncpy(static_cast<char*>(ptr), "Mode", 31); return 1;
                    case SoniqAudio::kParamCeiling: std::strncpy(static_cast<char*>(ptr), "Linear", 31); return 1;
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
        SoniqMaxEffect* self = static_cast<SoniqMaxEffect*>(e->object);
        self->dsp.setParameter(index, value);
    }

    static float getParameterCallback(AEffect* e, int32_t index) {
        SoniqMaxEffect* self = static_cast<SoniqMaxEffect*>(e->object);
        return self->dsp.getParameter(index);
    }

    static void processReplacingCallback(AEffect* e, float** inputs, float** outputs, int32_t sampleFrames) {
        SoniqMaxEffect* self = static_cast<SoniqMaxEffect*>(e->object);
        self->dsp.process(inputs, outputs, sampleFrames);
    }
};

// ============================================================================
// Standard VST 2.4 Entry Point
// ============================================================================
extern "C" {
    VST_EXPORT AEffect* VSTPluginMain(audioMasterCallback audioMaster) {
        SoniqMaxEffect* effect = new SoniqMaxEffect();
        return &effect->effect;
    }
}

// ============================================================================
// Decoupled Pure C ABI Exports (Enables Direct Host & Future sAPO Usage)
// ============================================================================
extern "C" {
    VST_EXPORT void* Soniq_CreateEngine() {
        return new SoniqAudio::SoniqDspEngine();
    }

    VST_EXPORT void Soniq_DestroyEngine(void* handle) {
        if (handle) {
            delete static_cast<SoniqAudio::SoniqDspEngine*>(handle);
        }
    }

    VST_EXPORT void Soniq_SetSampleRate(void* handle, float sampleRate) {
        if (handle) {
            static_cast<SoniqAudio::SoniqDspEngine*>(handle)->setSampleRate(sampleRate);
        }
    }

    VST_EXPORT void Soniq_SetParameter(void* handle, int paramIndex, float value) {
        if (handle) {
            static_cast<SoniqAudio::SoniqDspEngine*>(handle)->setParameter(paramIndex, value);
        }
    }

    VST_EXPORT float Soniq_GetParameter(void* handle, int paramIndex) {
        if (handle) {
            return static_cast<SoniqAudio::SoniqDspEngine*>(handle)->getParameter(paramIndex);
        }
        return 0.0f;
    }

    VST_EXPORT void Soniq_Reset(void* handle) {
        if (handle) {
            static_cast<SoniqAudio::SoniqDspEngine*>(handle)->reset();
        }
    }

    VST_EXPORT void Soniq_ProcessReplacing(void* handle, float** inputs, float** outputs, int sampleFrames) {
        if (handle) {
            static_cast<SoniqAudio::SoniqDspEngine*>(handle)->process(inputs, outputs, sampleFrames);
        }
    }

    VST_EXPORT void Soniq_ProcessInterleaved(void* handle, float* inOutBuffer, int sampleFrames) {
        if (handle) {
            static_cast<SoniqAudio::SoniqDspEngine*>(handle)->processInterleaved(inOutBuffer, sampleFrames);
        }
    }
}
