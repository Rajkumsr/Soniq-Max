"""
SONIQ MAX — Equalizer APO Integration & System Status Checker.
Checks whether Equalizer APO is installed, configured, and actively
loading SoniqMaxDSP.dll on Windows audio devices.
"""

import hashlib
import os
import sys

APO_DIR = r"C:\Program Files\EqualizerAPO"
APO_CONFIG_TXT = os.path.join(APO_DIR, "config", "config.txt")
APO_SONIQ_CONFIG = os.path.join(APO_DIR, "config", "SONIQ_MAX_Config.txt")
APO_VST_DLL = os.path.join(APO_DIR, "VSTPlugins", "SoniqMaxDSP.dll")
LOCAL_VST_DLL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vst", "bin", "SoniqMaxDSP.dll"))


def file_hash(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()[:12]


def check_apo_status():
    print("=" * 70)
    print("  SONIQ MAX PRO — EQUALIZER APO & SYSTEM INTEGRATION CHECK")
    print("=" * 70)

    # 1. Check APO Installation
    apo_installed = os.path.exists(APO_DIR)
    print(f"\n[1] Equalizer APO Core Directory:")
    print(f"    Path    : {APO_DIR}")
    print(f"    Status  : {'INSTALLED' if apo_installed else 'NOT FOUND'}")
    if not apo_installed:
        print("    -> Equalizer APO is not installed on this system.")
        return False

    # 2. Check Master config.txt
    print(f"\n[2] Master Equalizer APO Config:")
    print(f"    Path    : {APO_CONFIG_TXT}")
    if os.path.exists(APO_CONFIG_TXT):
        with open(APO_CONFIG_TXT, "r", encoding="utf-8", errors="ignore") as f:
            cfg_content = f.read()
        has_soniq_include = "SONIQ_MAX_Config.txt" in cfg_content or "SONIQ_APO_Config.txt" in cfg_content
        print(f"    Include : {'ACTIVE (Points to SONIQ MAX)' if has_soniq_include else 'WARNING: Missing Soniq Max Include'}")
    else:
        print("    Status  : File missing")
        has_soniq_include = False

    # 3. Check SONIQ_MAX_Config.txt VST Directive
    print(f"\n[3] Soniq Max Managed Config:")
    print(f"    Path    : {APO_SONIQ_CONFIG}")
    if os.path.exists(APO_SONIQ_CONFIG):
        with open(APO_SONIQ_CONFIG, "r", encoding="utf-8", errors="ignore") as f:
            s_content = f.read()
        has_vst_directive = "SoniqMaxDSP.dll" in s_content
        print(f"    VST Link: {'ACTIVE (VSTPlugin: Library \"VSTPlugins\\\\SoniqMaxDSP.dll\")' if has_vst_directive else 'INACTIVE'}")
    else:
        print("    Status  : File missing (Soniq Max app has not exported its live config yet)")
        has_vst_directive = False

    # 4. Check VST Plugin DLL
    print(f"\n[4] VST Plugin DLL File:")
    print(f"    Local Build : {LOCAL_VST_DLL}")
    print(f"                  Exists: {os.path.exists(LOCAL_VST_DLL)} | Hash: {file_hash(LOCAL_VST_DLL)}")
    print(f"    APO Plugin  : {APO_VST_DLL}")
    print(f"                  Exists: {os.path.exists(APO_VST_DLL)} | Hash: {file_hash(APO_VST_DLL)}")

    dll_synced = file_hash(LOCAL_VST_DLL) == file_hash(APO_VST_DLL)
    print(f"    Sync Status : {'SYNCHRONIZED' if dll_synced else 'OUT OF SYNC (Local build newer or differing)'}")

    # 5. Visual Live Verification Guide
    editor_path = os.path.join(APO_DIR, "Editor.exe")
    print("\n" + "=" * 70)
    print("  HOW TO VISUALLY SEE THE DLL WORKING LIVE IN WINDOWS:")
    print("=" * 70)
    print(f"1. Open Equalizer APO's GUI editor:")
    print(f'   "{editor_path}"')
    print("2. In the editor view, you will see the block diagram:")
    print('   - "Include: SONIQ_MAX_Config.txt"')
    print('   - Expand it to see: "VST plugin: VSTPlugins\\SoniqMaxDSP.dll"')
    print("3. Play any audio in YouTube, Spotify, or Media Player:")
    print("   - You will see the blue peak meters bouncing in real-time.")
    print("   - A green power button next to SoniqMaxDSP.dll indicates the DSP engine is live.")
    print("=" * 70)

    return apo_installed and has_soniq_include and has_vst_directive


if __name__ == "__main__":
    check_apo_status()
