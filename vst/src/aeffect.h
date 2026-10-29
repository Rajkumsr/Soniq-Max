#pragma once
#include <stdint.h>

#define kEffectMagic 0x56737450 // 'VstP'

// Standard VST 2.4 opcodes
enum VstOpcode {
    effOpen = 0,
    effClose = 1,
    effSetProgram = 2,
    effGetProgram = 3,
    effSetProgramName = 4,
    effGetProgramName = 5,
    effGetParamLabel = 6,
    effGetParamDisplay = 7,
    effGetParamName = 8,
    effSetSampleRate = 10,
    effSetBlockSize = 11,
    effMainsChanged = 12,
    effEditGetRect = 13,
    effEditOpen = 14,
    effEditClose = 15,
    effGetChunk = 23,
    effSetChunk = 24,
    effGetEffectName = 45,
    effGetVendorString = 47,
    effGetProductString = 48,
    effGetVendorVersion = 49,
    effCanDo = 51,
    effGetVstVersion = 58
};

enum VstAEffectFlags {
    effFlagsHasEditor = 1 << 0,
    effFlagsCanReplacing = 1 << 4,
    effFlagsProgramChunks = 1 << 5,
    effFlagsIsSynth = 1 << 8,
    effFlagsNoSoundInStop = 1 << 9,
    effFlagsCanDoubleReplacing = 1 << 12
};

struct AEffect;
typedef intptr_t (*audioMasterCallback)(AEffect* effect, int32_t opcode, int32_t index, intptr_t value, void* ptr, float opt);

struct AEffect {
    int32_t magic;
    intptr_t (*dispatcher)(AEffect* effect, int32_t opcode, int32_t index, intptr_t value, void* ptr, float opt);
    void (*process)(AEffect* effect, float** inputs, float** outputs, int32_t sampleFrames);
    void (*setParameter)(AEffect* effect, int32_t index, float parameter);
    float (*getParameter)(AEffect* effect, int32_t index);
    int32_t numPrograms;
    int32_t numParams;
    int32_t numInputs;
    int32_t numOutputs;
    int32_t flags;
    intptr_t resvd1;
    intptr_t resvd2;
    int32_t initialDelay;
    int32_t realQualities;
    int32_t offQualities;
    float ioRatio;
    void* object;
    void* user;
    int32_t uniqueID;
    int32_t version;
    void (*processReplacing)(AEffect* effect, float** inputs, float** outputs, int32_t sampleFrames);
    void (*processDoubleReplacing)(AEffect* effect, double** inputs, double** outputs, int32_t sampleFrames);
    char future[56];
};

