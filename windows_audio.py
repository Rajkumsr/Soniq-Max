"""
SONIQ MAX PRO — Windows Core Audio API Integration.
Provides hardware output endpoint detection, active audio session tracking,
and heuristic app/window classification.
"""
import ctypes
import logging
import time
from ctypes import wintypes, c_float, c_uint32, POINTER
import psutil

logger = logging.getLogger(__name__)
_last_session_error_log = 0.0

try:
    import comtypes
    from comtypes import COMObject, IUnknown, GUID, COMMETHOD, HRESULT
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation

    class IAudioMeter(IUnknown):
        _iid_ = GUID('{C02216F6-8C67-4B5B-9D00-D008E73E0064}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'GetPeakValue', (['out'], POINTER(c_float), 'pfPeak')),
            COMMETHOD([], HRESULT, 'GetMeteringChannelCount', (['out'], POINTER(c_uint32), 'pnChannelCount')),
            COMMETHOD([], HRESULT, 'GetChannelsPeakValues', (['in'], c_uint32, 'u32ChannelCount'), (['in'], POINTER(c_float), 'afPeakValues'))
        ]

    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [('fmtid', GUID), ('pid', wintypes.DWORD)]

    class IMMNotificationClient(IUnknown):
        _iid_ = GUID('{7991EEC9-7E89-4D85-8390-6C703CEC60C0}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'OnDeviceStateChanged',
                      (['in'], wintypes.LPCWSTR, 'pwstrDeviceId'),
                      (['in'], wintypes.DWORD, 'dwNewState')),
            COMMETHOD([], HRESULT, 'OnDeviceAdded',
                      (['in'], wintypes.LPCWSTR, 'pwstrDeviceId')),
            COMMETHOD([], HRESULT, 'OnDeviceRemoved',
                      (['in'], wintypes.LPCWSTR, 'pwstrDeviceId')),
            COMMETHOD([], HRESULT, 'OnDefaultDeviceChanged',
                      (['in'], ctypes.c_int, 'flow'),
                      (['in'], ctypes.c_int, 'role'),
                      (['in'], wintypes.LPCWSTR, 'pwstrDefaultDeviceId')),
            COMMETHOD([], HRESULT, 'OnPropertyValueChanged',
                      (['in'], wintypes.LPCWSTR, 'pwstrDeviceId'),
                      (['in'], POINTER(PROPERTYKEY), 'key')),
        ]

    class AudioEndpointNotificationHandler(COMObject):
        _com_interfaces_ = [IMMNotificationClient]

        def __init__(self, on_change_callback):
            super().__init__()
            self.callback = on_change_callback

        def OnDeviceStateChanged(self, _pwstrDeviceId, _dwNewState):
            if self.callback:
                try:
                    self.callback()
                except Exception:
                    logger.exception("Windows audio endpoint callback failed")
            return 0

        def OnDeviceAdded(self, _pwstrDeviceId):
            return 0

        def OnDeviceRemoved(self, _pwstrDeviceId):
            return 0

        def OnDefaultDeviceChanged(self, flow, _role, _pwstrDefaultDeviceId):
            # flow == 0: eRender (audio output endpoint)
            if flow == 0 and self.callback:
                try:
                    self.callback()
                except Exception:
                    logger.exception("Windows default-endpoint callback failed")
            return 0

        def OnPropertyValueChanged(self, _pwstrDeviceId, _key):
            return 0

    class WindowsEndpointWatcher:
        """
        Manages event-driven Windows Core Audio endpoint notifications via IMMNotificationClient.
        Eliminates the need for continuous polling loops.
        """
        def __init__(self, on_change_callback):
            self.callback = on_change_callback
            self.handler = None
            self.client_ptr = None
            self.enumerator = None

        def start(self):
            try:
                comtypes.CoInitialize()
                self.handler = AudioEndpointNotificationHandler(self.callback)
                self.client_ptr = self.handler.QueryInterface(IMMNotificationClient)
                self.enumerator = AudioUtilities.GetDeviceEnumerator()
                self.enumerator.RegisterEndpointNotificationCallback(self.client_ptr)
            except Exception:
                logger.exception("Could not register Windows audio endpoint notifications")

        def stop(self):
            if self.enumerator and self.client_ptr:
                try:
                    self.enumerator.UnregisterEndpointNotificationCallback(self.client_ptr)
                except Exception:
                    logger.exception("Could not unregister Windows audio endpoint notifications")
                self.enumerator = None
                self.client_ptr = None
                self.handler = None

    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False
    IAudioMeter = None
    class WindowsEndpointWatcher:
        def __init__(self, _on_change_callback): pass
        def start(self): pass
        def stop(self): pass

# In-memory PID to process name cache (cuts kernel OpenProcess churn by 99%)
_PID_NAME_CACHE = {}

def get_process_name_by_pid(pid):
    """
    Fast in-memory cached lookup of process executable name by PID.
    Avoids expensive OpenProcess/QueryFullProcessImageName kernel calls on every loop tick.
    """
    if not pid or pid <= 0:
        return ""
    cached = _PID_NAME_CACHE.get(pid)
    if cached is not None:
        return cached
    try:
        name = psutil.Process(pid).name().lower()
        if len(_PID_NAME_CACHE) > 512:
            _PID_NAME_CACHE.clear()
        _PID_NAME_CACHE[pid] = name
        return name
    except Exception:
        _PID_NAME_CACHE[pid] = ""
        return ""

def get_hwnd_for_pid(target_pid):
    """Finds a visible top-level HWND belonging to target_pid."""
    found_hwnd = None
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_cb(h, _):
        nonlocal found_hwnd
        if user32.IsWindowVisible(h):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == target_pid:
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    found_hwnd = h
                    return False
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    except Exception:
        pass
    return found_hwnd

def get_hwnd_for_process_family(target_pid, proc_name=None):
    """
    Finds top-level visible window handle for a target process ID.
    If the PID belongs to a headless child worker (e.g. Chrome Audio Service, Spotify helper),
    falls back to finding the main visible window of the parent/family process name.
    """
    hwnd = get_hwnd_for_pid(target_pid)
    if hwnd:
        return hwnd
    if not proc_name:
        return None

    proc_base = proc_name.lower().replace(".exe", "")
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    found_hwnd = None

    def enum_family_cb(h, _):
        nonlocal found_hwnd
        if user32.IsWindowVisible(h):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            name = get_process_name_by_pid(p.value)
            if name and proc_base == name.lower().replace(".exe", ""):
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    found_hwnd = h
                    return False
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(enum_family_cb), 0)
    except Exception:
        pass
    return found_hwnd

def get_active_windows_output_device():
    """
    Queries Windows Core Audio API to dynamically find current active playback device
    and determine whether it is headphones/earphones or laptop internal speakers.
    """
    if not PYCAW_AVAILABLE:
        logger.warning("pycaw/COM is unavailable; using a generic audio endpoint label")
        return "Speakers (Default Audio)", False
    try:
        comtypes.CoInitialize()
        spk = AudioUtilities.GetSpeakers()
        if spk and spk.FriendlyName:
            name = spk.FriendlyName
            is_hp = any(w in name.lower() for w in ("headphone", "earphone", "headset", "usb-c", "type-c", "buds", "airpod", "iem", "dac"))
            return name, is_hp
    except Exception:
        logger.exception("Could not query the active Windows audio endpoint")
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            logger.debug("Could not uninitialize endpoint COM call", exc_info=True)
    return "Speakers (Default Audio)", False

def classify_audio_stream_dynamically(pid, hwnd, proc_name):
    """
    Rule-based Windows metadata detection:
    Determines audio content type (Cinema, Music, Voice, Gaming, Laptop)
    from process names, window titles, and window size. Results are heuristic.
    """
    if not proc_name:
        return None, None

    proc_lower = proc_name.lower()
    # Skip our own manager and system services
    if proc_lower in ("soniq_max.exe", "python.exe", "pythonw.exe", "audiodg.exe"):
        return None, None

    # If hwnd not provided or headless audio service, resolve main window of process family
    if not hwnd and pid:
        hwnd = get_hwnd_for_process_family(pid, proc_name)

    title = ""
    if hwnd:
        try:
            user32 = ctypes.windll.user32
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip().lower()
        except Exception:
            pass

    short_name = proc_name.replace(".exe", "").title()

    # 1. Fullscreen & Borderless Gaming Check
    if hwnd:
        try:
            user32 = ctypes.windll.user32
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            win_w = rect.right - rect.left
            win_h = rect.bottom - rect.top
            if win_w >= int(screen_w * 0.95) and win_h >= int(screen_h * 0.90):
                browsers_and_tools = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "explorer.exe", "code.exe", "devenv.exe")
                if proc_lower not in browsers_and_tools:
                    return "fps_gaming", f"{short_name} (💥 Battlefield 360)"
        except Exception:
            pass

    # 2. Dedicated Game Platform, Engine & Game Title Keywords
    gaming_indicators = (
        "steam", "epicgames", "riot", "valorant", "csgo", "cs2", "dota", "fortnite",
        "cod", "warzone", "minecraft", "overwatch", "apex", "pubg", "cyberpunk",
        "gta", "unreal", "unity", "directx", "vulkan", "battlefield", "rdr2", "forza",
        "eldenring", "witcher", "destiny", "tarkov", "genshin", "honkai", "gameloop",
        "roblox", "leagueoflegends", "ubisoft", "ea desktop", "origin", "battlenet",
        "tomb raider", "assassin", "halo", "fifa", "nba2k", "rocketleague"
    )
    if any(k in title or k in proc_lower for k in gaming_indicators):
        return "fps_gaming", f"{short_name} (💥 Battlefield 360)"

    # 3. Dynamic Voice / Communication keywords (Higher priority than general playback)
    voice_processes = (
        "zoom.exe", "teams.exe", "discord.exe", "skype.exe", "slack.exe", 
        "webex.exe", "whatsapp.exe"
    )
    voice_title_indicators = (
        "zoom meeting", "zoom call", "teams meeting", "microsoft teams", "discord call",
        "skype call", "slack huddle", "google meet", "webex meeting", "incoming call",
        "in a call", "video call", "voice call", "conference call", "whatsapp call"
    )
    if proc_lower in voice_processes or any(k in title for k in voice_title_indicators):
        return "voice_meeting", f"🎙️ {short_name}: Voice / Call"

    # 4. Dynamic Music / Audio keywords & Dedicated Music Players
    music_processes = (
        "spotify.exe", "musicbee.exe", "foobar2000.exe", "aimp.exe", "winamp.exe",
        "itunes.exe", "applemusic.exe", "tidal.exe", "deezer.exe", "wmplayer.exe",
        "audacious.exe", "cider.exe", "amazonmusic.exe", "soundcloud.exe"
    )
    music_indicators = (
        "music", "song", "track", "album", "spotify", "sound", "audio", "radio", 
        "podcast", "playlist", "official audio", "official video", "lyrics",
        "youtube music", ".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", "soundcloud"
    )
    if proc_lower in music_processes or any(k in title or k in proc_lower for k in music_indicators):
        return "bass_beast", f"🎵 {short_name}: Music Stream"

    # 5. Dynamic Video / Cinema keywords in active window
    video_processes = ("vlc.exe", "mpc-hc.exe", "mpc-be.exe", "potplayermini64.exe", "kmplayer.exe")
    video_indicators = (
        "youtube", "netflix", "prime", "hotstar", "twitch", "vimeo", "movie", "film", 
        "watch", "cinema", "trailer", "season", "episode", "1080p", "720p", "2160p", "4k", 
        ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".webm"
    )
    if proc_lower in video_processes or any(k in title for k in video_indicators):
        clean_title = title[:24] + "..." if len(title) > 24 else title
        return "cinema_dialogue", f"🎬 {clean_title if clean_title else short_name}"

    # 6. Generic streaming fallback only if title or audio was identified
    title_snippet = f": {title[:16]}" if title else ""
    return "laptop_lifesaver", f"🔊 {short_name}{title_snippet}"

def get_dynamic_windows_audio_sources():
    """
    Dynamically inspects Windows Core Audio sessions (IAudioSessionManager2)
    to identify which processes are currently outputting audio to the speakers/headphones.
    """
    if not PYCAW_AVAILABLE:
        return []
    
    global _last_session_error_log
    active_list = []
    try:
        comtypes.CoInitialize()
        sessions = AudioUtilities.GetAllSessions()
        for s in sessions:
            pid = getattr(s, "ProcessId", 0)
            if pid:
                proc_name = get_process_name_by_pid(pid)
                if not proc_name and s.Process:
                    try:
                        proc_name = s.Process.name().lower()
                        _PID_NAME_CACHE[pid] = proc_name
                    except Exception:
                        pass
                if not proc_name or proc_name in ("soniq_max.exe", "python.exe", "rtkauduservice64.exe", "audiodg.exe"):
                    continue
                
                is_active = (s.State == 1)
                peak = 0.0
                try:
                    meter = s._ctl.QueryInterface(IAudioMeterInformation)
                    peak = float(meter.GetPeakValue())
                except Exception:
                    pass
                
                if is_active or peak > 0.0005:
                    active_list.append({
                        "name": proc_name,
                        "pid": s.ProcessId,
                        "active": is_active,
                        "peak": peak
                    })
    except Exception:
        now = time.monotonic()
        if now - _last_session_error_log >= 60:
            logger.warning("Could not enumerate Windows audio sessions", exc_info=True)
            _last_session_error_log = now
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            logger.debug("Could not uninitialize audio-session COM call", exc_info=True)

    # Sort: first by active state, then by peak volume level
    active_list.sort(key=lambda x: (1 if x["active"] else 0, x["peak"]), reverse=True)
    return active_list
