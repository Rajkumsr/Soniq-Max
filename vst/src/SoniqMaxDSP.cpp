/**
 * SONIQ MAX Real-Time DSP Audio Processing VST 2.4 Plugin
 * Compatible with Equalizer APO (64-bit Windows)
 *
 * Modules:
 * 1. Psychoacoustic Harmonic Bass Exciter (synthesizes 2nd & 3rd harmonics for deep bass on small speakers)
 * 2. Dynamic Vocal Clarity & Presence Enhancer (2.8 kHz dynamic formant boost)
 * 3. 3D Stereo Spatializer (Binaural Haas delay & interaural phase widening)
 * 4. Zero-Clipping Soft-Knee Brickwall Limiter
 */

#include "aeffect.h"
#include <cmath>
#include <cstring>
#include <algorithm>

#define PLUGIN_UNIQUE_ID 0x53714D78 // 'SqMx'
#define NUM_PARAMS 5

enum ParamIndex {
    kParamBassBoost = 0,
    kParamClarity = 1,
    kParamSpatial = 2,
    kParamLimiter = 3,
    kParamMasterGain = 4
};

// 2nd-order Biquad Filter for Bass extraction and Vocal Presence
class Biquad {
public:
    float b0, b1, b2, a1, a2;
    float x1[2], x2[2], y1[2], y2[2];

    Biquad() {
        b0 = 1.0f; b1 = b2 = a1 = a2 = 0.0f;
        reset();
    }

    void reset() {
        for (int ch = 0; ch < 2; ++ch) {
            x1[ch] = x2[ch] = y1[ch] = y2[ch] = 0.0f;
        }
    }

    void setLowPass(float freq, float sampleRate, float q = 0.707f) {
        float omega = 2.0f * 3.14159265f * freq / sampleRate;
        float sn = std::sin(omega);
        float cs = std::cos(omega);
        float alpha = sn / (2.0f * q);

        float a0 = 1.0f + alpha;
        b0 = ((1.0f - cs) / 2.0f) / a0;
        b1 = (1.0f - cs) / a0;
        b2 = ((1.0f - cs) / 2.0f) / a0;
        a1 = (-2.0f * cs) / a0;
        a2 = (1.0f - alpha) / a0;
    }

    void setPeaking(float freq, float gainDb, float sampleRate, float q = 1.5f) {
        float A = std::pow(10.0f, gainDb / 40.0f);
        float omega = 2.0f * 3.14159265f * freq / sampleRate;
        float sn = std::sin(omega);
        float cs = std::cos(omega);
        float alpha = sn / (2.0f * q);

        float a0 = 1.0f + alpha / A;
        b0 = (1.0f + alpha * A) / a0;
        b1 = (-2.0f * cs) / a0;
        b2 = (1.0f - alpha * A) / a0;
        a1 = (-2.0f * cs) / a0;
        a2 = (1.0f - alpha / A) / a0;
    }

    inline float process(int ch, float in) {
        float out = b0 * in + b1 * x1[ch] + b2 * x2[ch] - a1 * y1[ch] - a2 * y2[ch];
        x2[ch] = x1[ch];
        x1[ch] = in;
        y2[ch] = y1[ch];
        y1[ch] = out;
        return out;
    }
};

class SoniqMaxEffect {
public:
    AEffect effect;
    float sampleRate;
    float params[NUM_PARAMS];

    Biquad bassFilter;
    Biquad vocalFilter;

    // Spatial delay buffer (Haas effect ~0.35ms)
    static const int DELAY_SIZE = 64;
    float delayBufferL[DELAY_SIZE];
    float delayBufferR[DELAY_SIZE];
    int delayIndex;

    SoniqMaxEffect() {
        std::memset(&effect, 0, sizeof(AEffect));
        effect.magic = kEffectMagic;
        effect.dispatcher = dispatcherCallback;
        effect.process = processReplacingCallback;
        effect.processReplacing = processReplacingCallback;
        effect.setParameter = setParameterCallback;
        effect.getParameter = getParameterCallback;
        effect.numPrograms = 1;
        effect.numParams = NUM_PARAMS;
        effect.numInputs = 2;
        effect.numOutputs = 2;
        effect.flags = effFlagsCanReplacing;
        effect.uniqueID = PLUGIN_UNIQUE_ID;
        effect.version = 1000;
        effect.object = this;

        sampleRate = 48000.0f;
        params[kParamBassBoost] = 0.5f;   // 50%
        params[kParamClarity] = 0.5f;     // 50%
        params[kParamSpatial] = 0.35f;    // 35%
        params[kParamLimiter] = 1.0f;     // ON
        params[kParamMasterGain] = 1.0f;  // 0 dB

        std::memset(delayBufferL, 0, sizeof(delayBufferL));
        std::memset(delayBufferR, 0, sizeof(delayBufferR));
        delayIndex = 0;

        updateFilters();
    }

    void updateFilters() {
        bassFilter.setLowPass(140.0f, sampleRate);
        float vocalGainDb = params[kParamClarity] * 6.0f;
        vocalFilter.setPeaking(2800.0f, vocalGainDb, sampleRate, 1.4f);
    }

    void process(float** inputs, float** outputs, int sampleFrames) {
        float* inL = inputs[0];
        float* inR = inputs[1];
        float* outL = outputs[0];
        float* outR = outputs[1];

        float bassAmount = params[kParamBassBoost];
        float spatialAmount = params[kParamSpatial];
        float masterGain = params[kParamMasterGain];
        bool limiterOn = params[kParamLimiter] > 0.5f;

        for (int i = 0; i < sampleFrames; ++i) {
            float l = inL[i];
            float r = inR[i];

            // 1. Psychoacoustic Harmonic Bass Exciter
            if (bassAmount > 0.01f) {
                float subL = bassFilter.process(0, l);
                float subR = bassFilter.process(1, r);

                // Non-linear saturation generates 2nd (even) and 3rd (odd) harmonics
                float harmL = std::tanh(2.2f * subL) - 0.3f * std::tanh(1.2f * subL * subL);
                float harmR = std::tanh(2.2f * subR) - 0.3f * std::tanh(1.2f * subR * subR);

                l += harmL * bassAmount * 0.75f;
                r += harmR * bassAmount * 0.75f;
            }

            // 2. Vocal Presence & Clarity
            if (params[kParamClarity] > 0.01f) {
                l = vocalFilter.process(0, l);
                r = vocalFilter.process(1, r);
            }

            // 3. 3D Spatializer (Interaural Phase & Haas delay)
            if (spatialAmount > 0.01f) {
                delayBufferL[delayIndex] = l;
                delayBufferR[delayIndex] = r;

                int readIndex = (delayIndex - 16 + DELAY_SIZE) % DELAY_SIZE; // ~0.33ms delay at 48k
                float delayedL = delayBufferL[readIndex];
                float delayedR = delayBufferR[readIndex];

                delayIndex = (delayIndex + 1) % DELAY_SIZE;

                float side = (l - r) * 0.5f;
                l += (side - delayedR * 0.25f) * spatialAmount;
                r -= (side - delayedL * 0.25f) * spatialAmount;
            }

            // Master Gain
            l *= masterGain;
            r *= masterGain;

            // 4. Soft-Knee Brickwall Limiter (prevents digital clipping)
            if (limiterOn) {
                auto softLimit = [](float x) -> float {
                    const float threshold = 0.85f;
                    if (std::abs(x) <= threshold) return x;
                    float sign = (x > 0.0f) ? 1.0f : -1.0f;
                    float excess = (std::abs(x) - threshold) / (1.0f - threshold);
                    return sign * (threshold + (1.0f - threshold) * std::tanh(excess));
                };
                l = softLimit(l);
                r = softLimit(r);
            }

            outL[i] = l;
            outR[i] = r;
        }
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
                self->sampleRate = opt > 8000.0f ? opt : 48000.0f;
                self->updateFilters();
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
                    case kParamBassBoost: std::strncpy(static_cast<char*>(ptr), "Bass Harmonic", 31); return 1;
                    case kParamClarity: std::strncpy(static_cast<char*>(ptr), "Vocal Clarity", 31); return 1;
                    case kParamSpatial: std::strncpy(static_cast<char*>(ptr), "3D Spatializer", 31); return 1;
                    case kParamLimiter: std::strncpy(static_cast<char*>(ptr), "Peak Limiter", 31); return 1;
                    case kParamMasterGain: std::strncpy(static_cast<char*>(ptr), "Master Gain", 31); return 1;
                }
                return 0;
            case effGetParamLabel:
                switch (index) {
                    case kParamBassBoost:
                    case kParamClarity:
                    case kParamSpatial: std::strncpy(static_cast<char*>(ptr), "%", 31); return 1;
                    case kParamLimiter: std::strncpy(static_cast<char*>(ptr), "On/Off", 31); return 1;
                    case kParamMasterGain: std::strncpy(static_cast<char*>(ptr), "x", 31); return 1;
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
        if (index >= 0 && index < NUM_PARAMS) {
            self->params[index] = value;
            if (index == kParamClarity) {
                self->updateFilters();
            }
        }
    }

    static float getParameterCallback(AEffect* e, int32_t index) {
        SoniqMaxEffect* self = static_cast<SoniqMaxEffect*>(e->object);
        if (index >= 0 && index < NUM_PARAMS) {
            return self->params[index];
        }
        return 0.0f;
    }

    static void processReplacingCallback(AEffect* e, float** inputs, float** outputs, int32_t sampleFrames) {
        SoniqMaxEffect* self = static_cast<SoniqMaxEffect*>(e->object);
        self->process(inputs, outputs, sampleFrames);
    }
};

// VST 2.4 Entry Point
#if defined(_WIN32)
#define VST_EXPORT __declspec(dllexport)
#else
#define VST_EXPORT
#endif

extern "C" {
    VST_EXPORT AEffect* VSTPluginMain(audioMasterCallback audioMaster) {
        SoniqMaxEffect* effect = new SoniqMaxEffect();
        return &effect->effect;
    }

    // Legacy entry point for compatibility with older VST 2.4 hosts
    VST_EXPORT AEffect* main(audioMasterCallback audioMaster) {
        return VSTPluginMain(audioMaster);
    }
}
