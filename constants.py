"""
SONIQ MAX PRO — Global Constants, Paths, Color Theme, and Default Presets.
"""
import os
import sys
import math
import colorsys

def get_base_dir():
    """Returns directory of executable or script."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_asset_dir():
    """Returns PyInstaller bundle temp path or source directory."""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

# File Paths
CONFIG_FILE = os.path.join(get_base_dir(), "active_profile.json")
CUSTOM_PRESETS_FILE = os.path.join(get_base_dir(), "custom_presets.json")
APO_DEFAULT_PATH = os.environ.get(
    "SONIQ_MAX_APO_CONFIG_PATH",
    r"C:\Program Files\EqualizerAPO\config\config.txt"
)

try:
    import winreg
except ImportError:
    winreg = None

def get_windows_system_accent():
    """
    Reads the active Windows 10/11 system accent color directly from the Windows Registry.
    Returns hex string (e.g. '#0078d4') and integer BGR for Win32 DWM APIs.
    """
    if winreg:
        try:
            r = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            k = winreg.OpenKey(r, r"Software\Microsoft\Windows\DWM")
            val, _ = winreg.QueryValueEx(k, "AccentColor")
            # Format is 0xAABBGGRR
            r_c = val & 0xFF
            g_c = (val >> 8) & 0xFF
            b_c = (val >> 16) & 0xFF
            hex_code = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
            bgr_int = (b_c << 16) | (g_c << 8) | r_c
            return hex_code, bgr_int
        except Exception:
            pass
    return "#0078d4", 0x00d47800

def build_windows_fluent_theme():
    accent_hex, accent_bgr = get_windows_system_accent()

    # Generate Fluent lighting tints from system accent
    try:
        r_f = int(accent_hex[1:3], 16) / 255.0
        g_f = int(accent_hex[3:5], 16) / 255.0
        b_f = int(accent_hex[5:7], 16) / 255.0
        h, l, s = colorsys.rgb_to_hls(r_f, g_f, b_f)

        # High-contrast highlight tint for active text & badges
        l_light = min(1.0, max(l * 1.35, 0.68))
        rl, gl, bl = colorsys.hls_to_rgb(h, l_light, min(1.0, s * 1.1))
        accent_light = f"#{int(rl*255):02x}{int(gl*255):02x}{int(bl*255):02x}"

        # Hover state tint
        l_hover = min(1.0, l * 1.18)
        rh, gh, bh = colorsys.hls_to_rgb(h, l_hover, s)
        accent_hover = f"#{int(rh*255):02x}{int(gh*255):02x}{int(bh*255):02x}"
    except Exception:
        accent_light = "#60cdff"
        accent_hover = "#1a86e0"

    return {
        # Windows 11 Fluent Dark Surfaces (Mica glass compatible)
        "bg_dark": "#181818",             # Fluent Mica background surface
        "card_bg": "#212121",             # Fluent Dark Card Layer
        "card_border": "#2e2e2e",         # 1px Subtle Fluent Border
        "pill_bg": "#2b2b2b",             # Sub-surface interactive pills
        "pill_border": "#3a3a3a",         # Pill border
        
        # Windows Accent System Integration
        "accent_bronze": accent_hex,       # Native Windows Accent Color
        "accent_gold": accent_light,       # Native Windows Light Accent Tint
        "accent_green": "#4ade80",         # Success green
        
        # Windows 11 Fluent Typography Hierarchy
        "text_main": "#ffffff",           # Primary Text (100% white)
        "text_dim": "#c7c7c7",            # Secondary Text
        "text_subtle": "#8a8a8a",         # Tertiary Text
        
        # Fluent Interactive Controls
        "btn_primary": accent_hex,
        "btn_primary_hover": accent_hover,
        "btn_secondary": "#2b2b2b",
        "btn_secondary_hover": "#363636",
        
        # Audio Visuals
        "meter_track": "#262626",
        "clip_red": "#ef4444",
        
        # Win32 DWM Metadata
        "accent_bgr": accent_bgr,
    }

# Windows Native Fluent Theme Palette
THEME = build_windows_fluent_theme()

# 6 Built-In Default Profiles
DEFAULT_PROFILES = {
    "laptop_lifesaver": {
        "title": "Laptop Lifesaver",
        "icon": "💻",
        "badge": "RECOMMENDED",
        "desc": "A laptop-focused EQ with a low-frequency cut, added upper-bass energy, stereo channel mixing, and clearer vocal frequencies.",
        "bass": 75,
        "clarity": 80,
        "spatial": 165,
        "volume": 5.5,
        "eq": [1.0, 3.5, 4.0, -1.5, 0.5, 2.0, 4.0, 5.5, 4.0, 3.0]
    },
    "cinema_dialogue": {
        "title": "Cinema & Dialogue",
        "icon": "🎬",
        "badge": "MOVIES / OTT",
        "desc": "A dialogue-focused EQ curve with added presence and a moderate stereo channel mix.",
        "bass": 60,
        "clarity": 90,
        "spatial": 190,
        "volume": 4.0,
        "eq": [-1.0, 1.0, 2.0, -2.0, 1.5, 3.5, 5.0, 4.0, 3.0, 2.0]
    },
    "bass_beast": {
        "title": "Bass & EDM Beast",
        "icon": "⚡",
        "badge": "DEEP LOW-END",
        "desc": "An EQ curve emphasizing bass and treble for electronic music. High boosts may cause distortion on some devices.",
        "bass": 95,
        "clarity": 50,
        "spatial": 140,
        "volume": 3.0,
        "eq": [4.0, 6.0, 5.0, 0.0, -1.0, 0.0, 2.0, 3.0, 4.5, 4.0]
    },
    "fps_gaming": {
        "title": "Battlefield 360",
        "icon": "💥",
        "badge": "360° COMBAT",
        "desc": "An EQ curve emphasizing upper-mid frequencies for game audio. Results depend on the game and playback device.",
        "bass": 40,
        "clarity": 85,
        "spatial": 220,
        "volume": 4.5,
        "eq": [-2.0, 0.0, 1.0, -1.0, 2.0, 4.5, 6.0, 5.0, 3.5, 2.0]
    },
    "voice_meeting": {
        "title": "Zoom & Meeting",
        "icon": "🎙️",
        "badge": "CALLS / STUDY",
        "desc": "Reduces some low-frequency content and emphasizes vocal-presence frequencies for calls and speech.",
        "bass": 10,
        "clarity": 95,
        "spatial": 110,
        "volume": 5.0,
        "eq": [-6.0, -3.0, 0.0, -2.0, 2.0, 4.0, 5.0, 3.0, 1.0, -2.0]
    },
    "audiophile_flat": {
        "title": "Acoustic Pure",
        "icon": "🎧",
        "badge": "HI-FI / FLAT",
        "desc": "Balanced, transparent mastering response for classical, acoustic, and high-fidelity music listening.",
        "bass": 20,
        "clarity": 30,
        "spatial": 115,
        "volume": 1.0,
        "eq": [0.0, 0.5, 0.5, 0.0, 0.0, 0.5, 0.5, 0.5, 0.5, 0.0]
    }
}

SENSE_BROWSER_PROCESSES = frozenset({
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
})

SENSE_LOCAL_MUSIC_PROCESSES = frozenset({
    "spotify.exe",
    "musicbee.exe",
    "foobar2000.exe",
    "aimp.exe",
    "winamp.exe",
    "itunes.exe",
    "applemusic.exe",
    "tidal.exe",
    "deezer.exe",
    "wmplayer.exe",
    "audacious.exe",
    "cider.exe",
    "amazonmusic.exe",
    "soundcloud.exe",
})

SENSE_LOCAL_VIDEO_PROCESSES = frozenset({
    "vlc.exe",
    "mpc-hc.exe",
    "mpc-be.exe",
    "potplayermini64.exe",
    "kmplayer.exe",
})

SENSE_VOICE_PROCESSES = frozenset({
    "zoom.exe",
    "teams.exe",
    "discord.exe",
    "skype.exe",
    "slack.exe",
    "webex.exe",
    "whatsapp.exe",
})

GAMING_INDICATORS = (
    "steam", "epicgames", "riot", "valorant", "csgo", "cs2", "dota", "fortnite",
    "cod", "warzone", "minecraft", "overwatch", "apex", "pubg", "cyberpunk",
    "gta", "unreal", "unity", "directx", "vulkan", "battlefield", "rdr2", "forza",
    "eldenring", "witcher", "destiny", "tarkov", "genshin", "honkai", "gameloop",
    "roblox", "leagueoflegends", "ubisoft", "ea desktop", "origin", "battlenet",
    "tomb raider", "assassin", "halo", "fifa", "nba2k", "rocketleague"
)

VOICE_INDICATORS = (
    "zoom meeting", "zoom call", "teams meeting", "microsoft teams", "discord call",
    "skype call", "slack huddle", "google meet", "webex meeting", "incoming call",
    "in a call", "video call", "voice call", "conference call", "whatsapp call"
)

MUSIC_INDICATORS = (
    "music", "song", "track", "album", "spotify", "sound", "audio", "radio", 
    "podcast", "playlist", "official audio", "official video", "lyrics",
    "youtube music", ".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", "soundcloud"
)

VIDEO_INDICATORS = (
    "youtube", "netflix", "prime", "hotstar", "twitch", "vimeo", "movie", "film", 
    "watch", "cinema", "trailer", "season", "episode", "1080p", "720p", "2160p", "4k", 
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".webm"
)


def should_classify_browser_audio(session_process_names):
    """Classify browser playback unless a known local music player is active."""
    process_names = {
        process_name.casefold()
        for process_name in session_process_names
        if isinstance(process_name, str)
    }
    return bool(
        process_names.intersection(SENSE_BROWSER_PROCESSES)
        and not process_names.intersection(SENSE_LOCAL_MUSIC_PROCESSES)
    )


DEFAULT_SENSE_PROFILE_ASSIGNMENTS = {
    "gaming": "fps_gaming",
    "music": "bass_beast",
    "speech": "cinema_dialogue",
    "other": "laptop_lifesaver",
}

SENSE_TARGET_CATEGORIES = {
    "fps_gaming": "gaming",
    "voice_meeting": "speech",
    "cinema_dialogue": "speech",
    "bass_beast": "music",
    "other": "other",
}


def resolve_sense_profile(target, assignments):
    """Apply a user's Soniq Sense preset assignment to a detected target."""
    category = SENSE_TARGET_CATEGORIES.get(target)
    if category is None:
        return target
    return assignments.get(category, target)


# 10-Band Graphic Equalizer Frequencies & Genre Curves
EQ_FREQS = ["32Hz", "64Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz"]
EQ_CURVES = {
    "Flat": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "Bass Punch": [6.0, 5.0, 3.5, 1.5, 0.0, 0.0, 0.5, 1.0, 1.5, 2.0],
    "Vocal Clear": [-2.0, -1.0, 0.0, 0.5, 2.0, 4.0, 3.5, 2.0, 1.0, 0.0],
    "Rock / V-Curve": [5.0, 4.0, 2.0, -1.0, -2.0, -0.5, 2.0, 4.0, 5.0, 5.5],
    "Cinema": [3.0, 2.5, 1.0, 0.0, 1.5, 3.0, 2.5, 1.5, 2.0, 2.5],
    "Gaming": [1.0, 1.5, 0.0, -1.0, 1.0, 3.5, 4.0, 3.0, 2.0, 1.0]
}


def validate_profile_data(profile):
    """Validate the fields consumed by the UI and APO config generator."""
    if not isinstance(profile, dict):
        raise ValueError("Profile must be a JSON object.")

    for field in ("title", "icon", "badge", "desc"):
        value = profile.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Profile field '{field}' must be a non-empty string.")
        if field == "title" and any(character in value for character in "\r\n"):
            raise ValueError("Profile title cannot contain line breaks.")

    limits = {
        "bass": (0, 100),
        "clarity": (0, 100),
        "spatial": (100, 250),
        "volume": (0, 12),
    }
    for field, (minimum, maximum) in limits.items():
        value = profile.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Profile field '{field}' must be a number.")
        if (isinstance(value, float) and not math.isfinite(value)) or not minimum <= value <= maximum:
            raise ValueError(
                f"Profile field '{field}' must be between {minimum} and {maximum}."
            )

    eq = profile.get("eq")
    if not isinstance(eq, list) or len(eq) != len(EQ_FREQS):
        raise ValueError(f"Profile EQ must contain exactly {len(EQ_FREQS)} gains.")
    for gain in eq:
        if isinstance(gain, bool) or not isinstance(gain, (int, float)):
            raise ValueError("Profile EQ gains must be numbers.")
        if (isinstance(gain, float) and not math.isfinite(gain)) or not -12 <= gain <= 12:
            raise ValueError("Profile EQ gains must be between -12 and +12 dB.")

    return profile
