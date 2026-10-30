"""
SONIQ MAX PRO — Native Desktop Sound Profile Manager.
A modular Windows desktop application designed to set and manage sound profiles
for budget laptops with zero OEM lock.

Modular Architecture:
- constants.py: Paths, Color themes, Default presets, Equalizer curves
- windows_audio.py: Windows Core Audio API, Endpoint detection, Stream classification
- hotkey_manager.py: Win32 global system hotkey listener
- system_tray.py: Windows system tray icon and background lifecycle
- ui/: Modular tabs (Audio, Equalizer, Soniq Sense, Settings, Dialogs)
- export_system_apo.py: System-wide Equalizer APO generator
"""
import os
import re
import sys
import json
import time
import threading
import copy
import logging
import tempfile
from logging.handlers import RotatingFileHandler
import winreg
import ctypes
import customtkinter as ctk
import psutil

from audio_content import AudioContentMonitor
from constants import (
    THEME, DEFAULT_PROFILES, CONFIG_FILE, CUSTOM_PRESETS_FILE, APO_DEFAULT_PATH, APO_VST_PLUGIN_PATH, APO_VST_PLUGIN_NAME, LOCAL_VST_PLUGIN_PATH,
    DEFAULT_SENSE_PROFILE_ASSIGNMENTS, SENSE_LOCAL_MUSIC_PROCESSES, SENSE_VOICE_PROCESSES, get_asset_dir,
    get_base_dir, resolve_sense_profile,
    should_classify_browser_audio, validate_profile_data
)
from windows_audio import (
    get_active_windows_output_device, classify_audio_stream_dynamically,
    get_dynamic_windows_audio_sources,
    WindowsEndpointWatcher, get_process_name_by_pid,
    get_hwnd_for_process_family
)
from hotkey_manager import GlobalHotkeyManager
from system_tray import SystemTrayService
from export_system_apo import (
    generate_apo_config,
    profile_filter_values,
    export_to_file,
    install_apo_config,
)

from ui.dialogs import (
    open_sound_control_panel, open_system_driver_setup_dialog,
    prompt_save_custom_preset_dialog
)
from ui.tab_audio import AudioTab
from ui.tab_equalizer import EqualizerTab
from ui.tab_smart import SmartAppTab
from ui.tab_settings import SettingsTab
from ui.fluent_effects import ToastNotificationBanner, FluentTooltip

logger = logging.getLogger(__name__)


def configure_logging():
    """Write rotating diagnostics to the current user's application data folder."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    data_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    log_dir = os.path.join(data_dir, "SONIQ_MAX")
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(log_dir, "soniq_max.log"),
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
    except OSError:
        logging.basicConfig(level=logging.WARNING)


configure_logging()

# Set appearance mode
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def apply_windows_glass_theme(window):
    """
    Applies native Windows 11 DWM Mica glass backdrop, custom dark roast
    titlebar, glowing warm bronze window border, and gold typography via DWM.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()

        dwmapi = ctypes.windll.dwmapi

        # 1. Windows 11 Immersive Dark Mode (DWMWA_USE_IMMERSIVE_DARK_MODE = 20)
        dark = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))

        # 2. Modern Rounded Corners (DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2)
        corner = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), ctypes.sizeof(corner))

        # 3. Native Windows 11 System Backdrop: Mica (2)
        backdrop = ctypes.c_int(2)
        if dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop)) != 0:
            # Fallback for Windows 11 21H2 builds
            dwmapi.DwmSetWindowAttribute(hwnd, 1029, ctypes.byref(dark), ctypes.sizeof(dark))

        # 4. Windows 11 Fluent Dark Caption / Titlebar (#181818 -> BGR 0x00181818)
        caption_bgr = ctypes.c_int(0x00181818)
        dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption_bgr), ctypes.sizeof(caption_bgr))

        # 5. Windows System Accent Window Border
        border_bgr = ctypes.c_int(THEME.get("accent_bgr", 0x00d47800))
        dwmapi.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border_bgr), ctypes.sizeof(border_bgr))

        # 6. Fluent Clean White Title text (0x00ffffff)
        title_bgr = ctypes.c_int(0x00ffffff)
        dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(title_bgr), ctypes.sizeof(title_bgr))
    except Exception:
        pass

class SoniqDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SONIQ MAX PRO — Audio Suite")
        self.geometry("940x740")
        self.minsize(900, 680)
        self.configure(fg_color=THEME["bg_dark"])

        # Core State
        self.profiles = copy.deepcopy(DEFAULT_PROFILES)
        self.active_profile_key = "laptop_lifesaver"
        self.is_enhanced = True
        self.night_mode = False
        self.auto_app_enabled = True
        self.running = True
        self._auto_applied_profile_key = None
        self._auto_apply_pending_profile_key = None
        self._auto_apply_retry_after = 0.0
        self._sense_content_monitor_active = False
        self.use_vst = True
        self.sense_profile_assignments = DEFAULT_SENSE_PROFILE_ASSIGNMENTS.copy()
        self.audio_content_monitor = AudioContentMonitor()

        # Fast Instant Hardware Endpoint Placeholder (populated asynchronously)
        self.current_device_name = "Speakers (Realtek Audio)"
        self.is_headphone = False
        self.force_full_range = False

        # Initialize Background Services
        self.hotkey_service = GlobalHotkeyManager(self.on_hotkey_triggered)
        self.tray_service = SystemTrayService({
            "show": self.show_from_tray,
            "quit": self.quit_application,
            "toggle_bypass": self.tray_toggle_bypass,
            "toggle_auto_adapt": self.tray_toggle_auto_adapt,
            "select_profile": self.tray_switch_profile,
            "get_profiles": lambda: self.profiles
        })

        # Load persisted settings and user custom presets
        self.load_custom_presets()
        self.load_persisted_profile()

        # Build Main UI
        self.build_ui()
        self.select_profile(self.active_profile_key, apply_system=False)

        # Window protocols
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # Start Services
        self.hotkey_service.start()
        self.tray_service.start()
        self.endpoint_watcher = WindowsEndpointWatcher(self.on_endpoint_hardware_event)
        self.endpoint_watcher.start()
        threading.Thread(target=self.auto_app_monitor_loop, daemon=True).start()

        # Asynchronously detect initial active Windows endpoint
        self.after(30, self.initial_endpoint_detect)

        # Apply native Windows 11 Mica Glass, dark roast titlebar, and glowing bronze border
        self.after(20, lambda: apply_windows_glass_theme(self))

        self.is_window_visible = ("--minimized" not in sys.argv)

        # If launched with --minimized, start hidden in tray and flush working set memory
        if "--minimized" in sys.argv:
            self.withdraw()
            try:
                ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
            except Exception:
                pass

    @property
    def effective_is_headphone(self):
        return self.is_headphone or getattr(self, "force_full_range", False)

    # =========================================================================
    # Persistence & Profiles
    # =========================================================================
    def load_persisted_profile(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as stream:
                data = json.load(stream)
            if not isinstance(data, dict):
                raise ValueError("Settings file must contain a JSON object.")

            profile_key = data.get("active_profile", "laptop_lifesaver")
            if isinstance(profile_key, str) and profile_key in self.profiles:
                self.active_profile_key = profile_key
            else:
                logger.warning("Ignoring invalid active profile in %s", CONFIG_FILE)

            for key, default in (
                ("is_enhanced", True),
                ("night_mode", False),
                ("auto_app_enabled", True),
                ("use_vst", True),
                ("force_full_range", False),
            ):
                value = data.get(key, default)
                if type(value) is bool:
                    setattr(self, key, value)
                else:
                    logger.warning("Ignoring invalid setting '%s' in %s", key, CONFIG_FILE)

            assignments = data.get("sense_profile_assignments", {})
            if isinstance(assignments, dict):
                for category in self.sense_profile_assignments:
                    profile = assignments.get(category)
                    if isinstance(profile, str) and profile in self.profiles:
                        self.sense_profile_assignments[category] = profile
                    elif category in assignments:
                        logger.warning(
                            "Ignoring invalid Soniq Sense %s profile in %s",
                            category,
                            CONFIG_FILE,
                        )
            elif "sense_profile_assignments" in data:
                logger.warning("Ignoring invalid Soniq Sense profile assignments in %s", CONFIG_FILE)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            logger.warning("Could not load settings from %s: %s", CONFIG_FILE, error)

    @staticmethod
    def _write_json_atomically(path, data):
        directory = os.path.dirname(os.path.abspath(path))
        fd, temp_path = tempfile.mkstemp(prefix=".soniq-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def save_persisted_profile(self):
        data = {
            "active_profile": self.active_profile_key,
            "is_enhanced": self.is_enhanced,
            "night_mode": self.night_mode,
            "auto_app_enabled": self.auto_app_enabled,
            "force_full_range": getattr(self, "force_full_range", False),
            "sense_profile_assignments": self.sense_profile_assignments,
        }
        try:
            self._write_json_atomically(CONFIG_FILE, data)
        except OSError as error:
            logger.exception("Could not save settings to %s", CONFIG_FILE)
            if hasattr(self, "lbl_status"):
                self.lbl_status.configure(
                    text=f"Could not save settings: {error}",
                    text_color=THEME["clip_red"],
                )

    def load_custom_presets(self):
        if not os.path.exists(CUSTOM_PRESETS_FILE):
            return
        try:
            with open(CUSTOM_PRESETS_FILE, "r", encoding="utf-8") as stream:
                custom = json.load(stream)
            if not isinstance(custom, dict):
                raise ValueError("Custom presets file must contain a JSON object.")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            logger.warning("Could not load custom presets from %s: %s", CUSTOM_PRESETS_FILE, error)
            return

        for key, profile in custom.items():
            if not isinstance(key, str) or key in DEFAULT_PROFILES:
                logger.warning("Ignoring invalid or built-in custom preset key: %r", key)
                continue
            try:
                self.profiles[key] = copy.deepcopy(validate_profile_data(profile))
            except ValueError as error:
                logger.warning("Ignoring invalid custom preset '%s': %s", key, error)

    def save_custom_preset_to_disk(self, key, profile_data):
        if not isinstance(key, str) or not key.strip() or key in DEFAULT_PROFILES:
            raise ValueError("Custom preset key must be non-empty and cannot replace a built-in preset.")
        profile_data = copy.deepcopy(validate_profile_data(profile_data))
        custom_only = {
            preset_key: preset
            for preset_key, preset in self.profiles.items()
            if preset_key not in DEFAULT_PROFILES
        }
        custom_only[key] = profile_data
        self._write_json_atomically(CUSTOM_PRESETS_FILE, custom_only)
        self.profiles[key] = profile_data
        if getattr(self, "tab_smart", None):
            self.tab_smart.refresh_profile_choices()

    def delete_custom_preset_from_disk(self, key):
        if key in DEFAULT_PROFILES:
            raise ValueError("Built-in presets cannot be deleted.")
        if key not in self.profiles:
            return
        del self.profiles[key]
        custom_only = {
            preset_key: preset
            for preset_key, preset in self.profiles.items()
            if preset_key not in DEFAULT_PROFILES
        }
        self._write_json_atomically(CUSTOM_PRESETS_FILE, custom_only)
        if getattr(self, "tab_smart", None):
            self.tab_smart.refresh_profile_choices()
        self.select_profile("laptop_lifesaver", apply_system=True)
        if getattr(self, "tab_audio", None):
            self.tab_audio.render_profiles(self.profiles, self.active_profile_key)
        self.lbl_status.configure(
            text="✓ Custom preset deleted.",
            text_color=THEME["accent_bronze"]
        )

    # =========================================================================
    # Main UI Construction
    # =========================================================================
    def build_ui(self):
        # 1. Header (Warm Bronze & Dark Roast)
        header = ctk.CTkFrame(self, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        header.pack(fill="x", padx=16, pady=(12, 6))

        h_content = ctk.CTkFrame(header, fg_color="transparent")
        h_content.pack(fill="x", padx=16, pady=10)

        # Left: Logo & Subtitle
        logo_box = ctk.CTkFrame(h_content, fg_color="transparent")
        logo_box.pack(side="left")

        title_row = ctk.CTkFrame(logo_box, fg_color="transparent")
        title_row.pack(anchor="w")

        app_title = ctk.CTkLabel(
            title_row, 
            text="SONIQ MAX", 
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=THEME["accent_gold"]
        )
        app_title.pack(side="left", padx=(0, 8))

        suite_badge = ctk.CTkLabel(
            title_row,
            text="PRO AUDIO SUITE",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            fg_color=THEME["pill_bg"],
            text_color=THEME["accent_gold"],
            corner_radius=6,
            padx=7,
            pady=2
        )
        suite_badge.pack(side="left")

        app_sub = ctk.CTkLabel(
            logo_box, 
            text="Adaptive audio engine • Personalized sound profiles",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=THEME["text_dim"]
        )
        app_sub.pack(anchor="w", pady=(2, 0))

        # Center: Dynamic Device Pill & Status (Clickable to override Anti-Rattle for external 4.1 / subwoofers)
        center_box = ctk.CTkFrame(h_content, fg_color="transparent")
        center_box.pack(side="left", expand=True)

        self.device_pill = ctk.CTkFrame(center_box, fg_color=THEME["pill_bg"], corner_radius=20, border_width=1, border_color=THEME["pill_border"], cursor="hand2")
        self.device_pill.pack(pady=(0, 4))

        eff_hp = self.effective_is_headphone
        dot_col = THEME["accent_green"] if eff_hp else THEME["accent_gold"]
        self.dev_dot = ctk.CTkLabel(self.device_pill, text="●", font=ctk.CTkFont(size=11), text_color=dot_col, cursor="hand2")
        self.dev_dot.pack(side="left", padx=(10, 4), pady=3)

        if self.force_full_range:
            dev_text = "⚡ Creative / Ext (Full Bass)"
        elif self.is_headphone:
            dev_text = f"🎧 {self.current_device_name[:24]}"
        else:
            dev_text = f"🔊 {self.current_device_name[:24]}"

        self.dev_lbl = ctk.CTkLabel(
            self.device_pill, 
            text=dev_text, 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME["text_main"],
            cursor="hand2"
        )
        self.dev_lbl.pack(side="left", padx=(0, 12), pady=3)
        self.lbl_device_pill = self.dev_lbl

        self.device_pill.bind("<Button-1>", self.toggle_speaker_headphone_override)
        self.dev_dot.bind("<Button-1>", self.toggle_speaker_headphone_override)
        self.dev_lbl.bind("<Button-1>", self.toggle_speaker_headphone_override)

        self.lbl_active_app = ctk.CTkLabel(
            center_box,
            text="Soniq Sense automatic profile control",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=THEME["accent_gold"]
        )
        self.lbl_active_app.pack(pady=(1, 0))

        FluentTooltip(self.dev_lbl, title="Audio Endpoint (Click to Toggle)", text="Click to switch between Laptop Speakers (120Hz Anti-Rattle) and External 4.1/Subwoofer (Full 20Hz Sub-Bass).")
        FluentTooltip(
            self.lbl_active_app,
            title="Soniq Sense",
            text="Automatically adapts your assigned audio presets to playback. Profile switching stays in the background.",
        )

        # Right: Tray Minimize & Master Power Switch
        h_right = ctk.CTkFrame(h_content, fg_color="transparent")
        h_right.pack(side="right")

        self.btn_tray_min = ctk.CTkButton(
            h_right,
            text="⬇ Tray",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME["pill_bg"],
            text_color=THEME["text_dim"],
            hover_color=THEME["btn_secondary_hover"],
            width=65,
            height=32,
            command=self.hide_to_tray
        )
        self.btn_tray_min.pack(side="left", padx=(0, 12))
        FluentTooltip(self.btn_tray_min, title="Minimize to Tray", text="Runs silently in the Windows system tray with minimal memory and active hotkeys.")

        self.master_switch = ctk.CTkSwitch(
            h_right,
            text="EFFECTS: ON",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=THEME["accent_gold"],
            progress_color=THEME["accent_bronze"],
            button_color=THEME["text_main"],
            button_hover_color="#ffffff",
            command=self.toggle_master_switch
        )
        if self.is_enhanced:
            self.master_switch.select()
        else:
            self.master_switch.deselect()
            self.master_switch.configure(text="EFFECTS: OFF", text_color=THEME["text_dim"])
        self.master_switch.pack(side="right")
        FluentTooltip(
            self.master_switch,
            title="Master Effects Switch",
            text="Toggle SONIQ MAX's generated filters. Other Equalizer APO filters remain active.",
        )

        # 2. Signature Tabview
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=THEME["bg_dark"],
            segmented_button_fg_color=THEME["pill_bg"],
            segmented_button_selected_color=THEME["accent_bronze"],
            segmented_button_selected_hover_color=THEME["btn_primary_hover"],
            segmented_button_unselected_color=THEME["card_bg"],
            segmented_button_unselected_hover_color=THEME["btn_secondary_hover"],
            corner_radius=10
        )
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(4, 6))

        tab_audio_parent = self.tabview.add("🎵 AUDIO")
        tab_eq_parent = self.tabview.add("🎚️ EQUALIZER")
        tab_smart_parent = self.tabview.add("⚡ SONIQ SENSE")
        tab_settings_parent = self.tabview.add("⚙️ SETTINGS")

        # Instantiate Primary Tab (Audio) Immediately for Instant Display
        self.tab_audio = AudioTab(tab_audio_parent, self)
        self.tab_audio.render_profiles(self.profiles, self.active_profile_key)

        # Defer Secondary Tabs (Equalizer, Soniq Sense, Settings)
        self.tab_eq = None
        self.tab_smart = None
        self.tab_settings = None
        self.tab_eq_parent = tab_eq_parent
        self.tab_smart_parent = tab_smart_parent
        self.tab_settings_parent = tab_settings_parent

        self.tabview.configure(command=self.on_tab_changed)
        self.after(80, self.build_secondary_tabs)

        # Floating Fluent Toast Notification Banner (Slide down from top)
        self.toast = ToastNotificationBanner(self)

        # Footer Status Banner
        apo_available = os.path.isdir(os.path.dirname(APO_DEFAULT_PATH))
        status_text = (
            "Equalizer APO config folder found · ready to apply SONIQ filters."
            if apo_available
            else "Equalizer APO not detected · only local filters can be generated."
        )
        status_color = THEME["accent_gold"] if apo_available else "#df8f44"

        self.lbl_status = ctk.CTkLabel(
            self,
            text="Ready.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=THEME["text_dim"]
        )
        self.lbl_status.pack(side="bottom", pady=(0, 2))
        self.lbl_apo_health = ctk.CTkLabel(
            self,
            text=status_text,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=status_color,
        )
        self.lbl_apo_health.pack(side="bottom", pady=(0, 5))

    def update_apo_health(self, message, healthy):
        if hasattr(self, "lbl_apo_health"):
            self.lbl_apo_health.configure(
                text=message,
                text_color=THEME["accent_green"] if healthy else THEME["accent_bronze"],
            )

    def show_toast(self, title, message="", icon="✓", duration_ms=2200):
        """Displays a floating Windows 11 Fluent toast notification at window top."""
        if hasattr(self, "toast") and self.toast:
            self.toast.show(title, message, icon, duration_ms)

    def on_tab_changed(self):
        """Build requested secondary tab on demand and trigger staggered cascade entrance."""
        sel = self.tabview.get()
        if "EQUALIZER" in sel:
            if self.tab_eq is None:
                self.tab_eq = EqualizerTab(self.tab_eq_parent, self)
                p = self.profiles.get(self.active_profile_key, {})
                self.tab_eq.update_eq_sliders(p.get("eq", [0.0] * 10))
            else:
                self.tab_eq.animate_staggered_entrance()
        elif "SONIQ SENSE" in sel:
            if self.tab_smart is None:
                self.tab_smart = SmartAppTab(self.tab_smart_parent, self)
                self.tab_smart.update_endpoint_display(self.current_device_name, self.is_headphone)
            else:
                self.tab_smart.animate_staggered_entrance()
        elif "SETTINGS" in sel:
            if self.tab_settings is None:
                self.tab_settings = SettingsTab(self.tab_settings_parent, self)
            else:
                self.tab_settings.animate_staggered_entrance()
        elif "AUDIO" in sel and hasattr(self, "tab_audio"):
            self.tab_audio.animate_staggered_entrance()

    def build_secondary_tabs(self):
        """Asynchronously build secondary tabs in the background so window is visible immediately."""
        try:
            if self.tab_eq is None:
                self.tab_eq = EqualizerTab(self.tab_eq_parent, self)
                p = self.profiles.get(self.active_profile_key, {})
                self.tab_eq.update_eq_sliders(p.get("eq", [0.0] * 10))
            if self.tab_smart is None:
                self.tab_smart = SmartAppTab(self.tab_smart_parent, self)
                self.tab_smart.update_endpoint_display(self.current_device_name, self.is_headphone)
            if self.tab_settings is None:
                self.tab_settings = SettingsTab(self.tab_settings_parent, self)
        except Exception:
            logger.exception("Could not build the secondary application tabs")
            if hasattr(self, "lbl_status"):
                self.lbl_status.configure(
                    text="Could not initialize one or more tabs. See the SONIQ MAX log for details.",
                    text_color=THEME["clip_red"],
                )

    # =========================================================================
    # Profile & Controller Actions
    # =========================================================================
    def get_current_eq_gains(self):
        return self.profiles.get(self.active_profile_key, {}).get("eq", [0.0] * 10)

    def sense_profile_for_detected_target(self, target):
        return resolve_sense_profile(target, self.sense_profile_assignments)

    def select_profile(self, key, apply_system=True):
        if key not in self.profiles:
            return
        self._auto_applied_profile_key = None
        self._auto_apply_pending_profile_key = None
        self._auto_apply_retry_after = 0.0
        self.active_profile_key = key
        p = self.profiles[key]

        if hasattr(self, "tab_audio"):
            self.tab_audio.highlight_profile_button(key)
            if getattr(self, "is_window_visible", True):
                self.tab_audio.animate_sliders_to_profile(p)
            else:
                self.tab_audio.update_sliders_from_profile(p)

        if getattr(self, "tab_eq", None):
            self.tab_eq.update_eq_sliders(p.get("eq", [0.0] * 10))

        self.save_persisted_profile()

        if apply_system:
            self.apply_to_system_audio(profile=p)
            if getattr(self, "is_window_visible", True):
                self.show_toast(f"Profile: {p['title']}", p.get('badge', 'ACTIVE PRESET'), icon=p.get('icon', '🎵'))

    def on_card_switch_toggled(self, card_name):
        self.apply_to_system_audio()
        p = self.profiles[self.active_profile_key]
        self.lbl_status.configure(
            text=f"Updated {card_name.upper()} state for '{p['title']}'.",
            text_color=THEME["accent_gold"]
        )

    def reset_profile_defaults(self):
        if self.active_profile_key in DEFAULT_PROFILES:
            default_p = copy.deepcopy(DEFAULT_PROFILES[self.active_profile_key])
            self.profiles[self.active_profile_key] = default_p
            self.select_profile(self.active_profile_key, apply_system=True)
            self.lbl_status.configure(
                text=f"↺ Restored factory defaults for '{default_p['title']}'.", 
                text_color=THEME["accent_gold"]
            )
            self.show_toast("↺ Restored Defaults", f"Factory settings for {default_p['title']}", icon="↺")

    def apply_eq_preset(self, preset_name):
        from constants import EQ_CURVES
        curve = EQ_CURVES.get(preset_name)
        if not curve:
            return
        p = self.profiles[self.active_profile_key]
        p["eq"] = curve.copy()
        if getattr(self, "tab_eq", None):
            self.tab_eq.update_eq_sliders(curve)
        self.apply_to_system_audio()
        self.lbl_status.configure(
            text=f"Applied EQ curve '{preset_name}' to {p['title']}", 
            text_color=THEME["accent_green"]
        )
        self.show_toast(f"EQ: {preset_name}", f"Target curve applied to {p['title']}", icon="🎚️")

    def queue_system_audio_apply(self, delay_ms=50):
        """
        Debounces file writes to Equalizer APO configuration file (50ms).
        Allows sliders to update at 60 FPS smoothly without disk I/O stutter or pops.
        """
        if hasattr(self, "_apply_audio_timer") and self._apply_audio_timer:
            try:
                self.after_cancel(self._apply_audio_timer)
            except Exception:
                pass
        self._apply_audio_timer = self.after(delay_ms, self.apply_to_system_audio)

    def on_eq_slider_changed(self, band_idx, value):
        p = self.profiles[self.active_profile_key]
        if "eq" not in p:
            p["eq"] = [0.0] * 10
        val = round(value, 1)
        p["eq"][band_idx] = val
        if getattr(self, "tab_eq", None) and band_idx < len(self.tab_eq.eq_labels):
            sign = "+" if val > 0 else ""
            self.tab_eq.eq_labels[band_idx].configure(text=f"{sign}{val:.1f}")
        self.queue_system_audio_apply()

    def on_slider_bass(self, val):
        if hasattr(self, "tab_audio"):
            self.tab_audio.cancel_slider_animation()
            self.tab_audio.lbl_bass.configure(text=f"Bass EQ: {int(val)}%")
        self.queue_system_audio_apply()

    def on_slider_clarity(self, val):
        if hasattr(self, "tab_audio"):
            self.tab_audio.cancel_slider_animation()
            self.tab_audio.lbl_clarity.configure(text=f"Vocal Clarity: {int(val)}%")
        self.queue_system_audio_apply()

    def on_slider_spatial(self, val):
        if hasattr(self, "tab_audio"):
            self.tab_audio.cancel_slider_animation()
            self.tab_audio.lbl_spatial.configure(text=f"Stereo Width: {(val/100.0):.2f}x")
        self.queue_system_audio_apply()

    def on_slider_volume(self, val):
        if hasattr(self, "tab_audio"):
            self.tab_audio.cancel_slider_animation()
            self.tab_audio.lbl_volume.configure(text=f"Output Level Trim: +{(val/10.0):.1f} dB")
        self.queue_system_audio_apply()

    def toggle_master_switch(self):
        self.is_enhanced = bool(self.master_switch.get())
        if self.is_enhanced:
            self.master_switch.configure(text="EFFECTS: ON", text_color=THEME["accent_gold"])
            self.lbl_status.configure(text="SONIQ MAX Equalizer APO filters are enabled.", text_color=THEME["accent_green"])
            self.show_toast("Master Effects ON", "SONIQ MAX Equalizer APO filters enabled", icon="⚡")
        else:
            self.master_switch.configure(text="EFFECTS: OFF", text_color=THEME["accent_bronze"])
            self.lbl_status.configure(text="SONIQ MAX filters bypassed; other Equalizer APO filters remain active.", text_color=THEME["accent_bronze"])
            self.show_toast("Master Effects OFF", "SONIQ MAX filters bypassed", icon="⚠️")

        self.save_persisted_profile()
        self.apply_to_system_audio()

    def toggle_night_mode(self):
        self.night_mode = bool(self.tab_audio.switch_night_mode.get())
        self.save_persisted_profile()
        self.apply_to_system_audio()
        if self.night_mode:
            self.lbl_status.configure(
                text="Night Mode subtracts 2 dB from the output target when Output Level is enabled.",
                text_color=THEME["accent_gold"],
            )
            self.show_toast("Night Mode Active", "Static output target adjustment enabled", icon="🌙")
        else:
            self.lbl_status.configure(text="Night Mode disabled. Standard preamp target restored.", text_color=THEME["text_dim"])
            self.show_toast("Night Mode Disabled", "Standard output trim restored", icon="🌙")

    def toggle_auto_app(self):
        self.auto_app_enabled = bool(self.tab_smart.switch_auto_app.get())
        self._auto_applied_profile_key = None
        self._auto_apply_pending_profile_key = None
        self._auto_apply_retry_after = 0.0
        self.save_persisted_profile()
        if self.auto_app_enabled:
            self.lbl_status.configure(text="Soniq Sense is active.", text_color=THEME["accent_green"])
            if hasattr(self, "tab_audio"):
                self.tab_audio.update_auto_mode_indicator(True)
            self.show_toast("Soniq Sense Active", "Automatic profile switching is on", icon="⚡")
        else:
            self._set_sense_content_analysis(False)
            self.lbl_active_app.configure(text="Stream: Manual")
            self.apply_to_system_audio(profile=self.profiles[self.active_profile_key])
            self.lbl_status.configure(text="Soniq Sense is off. Manual profile mode.", text_color=THEME["text_dim"])
            if hasattr(self, "tab_audio"):
                self.tab_audio.update_auto_mode_indicator(False)
            self.show_toast("Soniq Sense Off", "Manual sound profile selection mode", icon="⚙️")

    def _set_sense_content_analysis(self, enabled):
            if enabled == self._sense_content_monitor_active:
                return
            self._sense_content_monitor_active = enabled
            if enabled:
                self.audio_content_monitor.start()
            else:
                self.audio_content_monitor.stop()

    def reset_sense_profile_assignments(self):
        self.sense_profile_assignments = DEFAULT_SENSE_PROFILE_ASSIGNMENTS.copy()
        self._auto_applied_profile_key = None
        self._auto_apply_pending_profile_key = None
        self._auto_apply_retry_after = 0.0
        self.save_persisted_profile()
        if getattr(self, "tab_smart", None):
            self.tab_smart.refresh_profile_choices()
        if hasattr(self, "lbl_status"):
            self.lbl_status.configure(
                text="Soniq Sense preset assignments restored to defaults.",
                text_color=THEME["accent_green"],
            )

    def set_sense_profile_assignment(self, category, profile_key):
        if category not in self.sense_profile_assignments or profile_key not in self.profiles:
            logger.warning(
                "Ignoring invalid Soniq Sense preset assignment: %s -> %s",
                category,
                profile_key,
            )
            return
        self.sense_profile_assignments[category] = profile_key
        self._auto_applied_profile_key = None
        self._auto_apply_pending_profile_key = None
        self._auto_apply_retry_after = 0.0
        self.save_persisted_profile()
        if hasattr(self, "lbl_status"):
            category_label = {
                "gaming": "Gaming",
                "music": "Music",
                "speech": "Speech / calls",
                "other": "Other audio",
            }[category]
            profile_title = self.profiles[profile_key]["title"]
            self.lbl_status.configure(
                text=f"Soniq Sense {category_label} preset set to '{profile_title}'.",
                text_color=THEME["accent_green"],
            )

    def apply_to_system_audio(self, profile=None, update_status=True):
        automatic_profile_active = (
            profile is None
            and self.auto_app_enabled
            and self._auto_applied_profile_key is not None
        )
        if automatic_profile_active:
            update_status = False

        if profile is None:
            effective_key = (
                self._auto_applied_profile_key
                if self.auto_app_enabled and self._auto_applied_profile_key
                else self.active_profile_key
            )
            p = self.profiles[effective_key]
        else:
            p = profile

        enabled_effects = {
            "bass": bool(self.tab_audio.switch_card_bass.get()) if hasattr(self, "tab_audio") else True,
            "clarity": bool(self.tab_audio.switch_card_clarity.get()) if hasattr(self, "tab_audio") else True,
            "spatial": bool(self.tab_audio.switch_card_spatial.get()) if hasattr(self, "tab_audio") else True,
            "volume": bool(self.tab_audio.switch_card_volume.get()) if hasattr(self, "tab_audio") else True,
        }
        if profile is not None:
            profile_values = profile_filter_values(profile, enabled_effects)
        else:
            profile_values = {
                "bass_boost": self.tab_audio.slider_bass.get() / 100 if enabled_effects["bass"] else 0.0,
                "clarity": self.tab_audio.slider_clarity.get() / 100 if enabled_effects["clarity"] else 0.0,
                "spatial_width": self.tab_audio.slider_spatial.get() / 100 if enabled_effects["spatial"] else 1.0,
                "volume_boost_db": self.tab_audio.slider_volume.get() / 10 if enabled_effects["volume"] else 0.0,
            }

        vst_plugins = None
        if getattr(self, "use_vst", True):
            active_vst = self.get_active_vst_path()
            if active_vst:
                vst_plugins = [active_vst]

        if not self.is_enhanced:
            apo_text = "# SONIQ MAX: BYPASSED (other APO config remains active)\nPreamp: 0.0 dB\n"
        else:
            apo_text = generate_apo_config(
                preset_name=p["title"],
                eq_gains=p.get("eq", [0.0]*10),
                **profile_values,
                night_mode=(self.night_mode and enabled_effects["volume"]),
                is_headphone=self.effective_is_headphone,
                vst_plugins=vst_plugins,
            )

        local_cfg = os.path.join(get_base_dir(), "SONIQ_APO_Config.txt")
        local_error = None
        applied_successfully = False
        try:
            export_to_file(local_cfg, apo_text)
        except OSError as error:
            logger.exception("Could not write local SONIQ MAX config")
            local_error = error

        config_dir = os.path.dirname(APO_DEFAULT_PATH)
        if not os.path.isdir(config_dir):
            self.update_apo_health(
                "Equalizer APO not detected · local config only.",
                False,
            )
            if local_error:
                applied_msg = f"Local save failed: {local_error}; Equalizer APO was not found."
                status_color = THEME["clip_red"]
            else:
                applied_msg = f"Saved locally. Equalizer APO config folder not found: {config_dir}"
                status_color = THEME["accent_bronze"]
        else:
            try:
                install_apo_config(APO_DEFAULT_PATH, apo_text)
                applied_successfully = True
                self.update_apo_health(
                    "Equalizer APO connected · SONIQ filters applied.",
                    True,
                )
                ep_type = "Headphones / Full-Range" if self.effective_is_headphone else "Laptop Speakers"
                applied_msg = (
                    f"Applied '{p['title']}' to Equalizer APO ({ep_type}); "
                    "existing config was preserved."
                )
                if local_error:
                    applied_msg += f" Local save failed: {local_error}"
                    status_color = THEME["accent_bronze"]
                else:
                    status_color = THEME["accent_green"]
            except (OSError, ValueError) as error:
                logger.exception("Could not install SONIQ MAX Equalizer APO config")
                self.update_apo_health(
                    "Equalizer APO update failed · check config permissions.",
                    False,
                )
                if local_error:
                    applied_msg = f"Both local and Equalizer APO saves failed: {local_error}; {error}"
                    status_color = THEME["clip_red"]
                else:
                    applied_msg = f"Saved locally; Equalizer APO update failed: {error}"
                    status_color = THEME["clip_red"]

        if update_status:
            self.lbl_status.configure(text=applied_msg, text_color=status_color)
        elif not applied_successfully:
            logger.warning("Automatic Soniq Sense profile was not applied: %s", applied_msg)
        return applied_successfully

    def on_endpoint_hardware_event(self):
        """
        Triggered asynchronously by Windows Core Audio IMMNotificationClient callback
        the exact moment an audio device is plugged, unplugged, or changed by Windows.
        Zero polling overhead.
        """
        self.after(0, self.refresh_audio_endpoint_ui)

    def toggle_speaker_headphone_override(self, event=None):
        self.force_full_range = not self.force_full_range
        self.save_persisted_profile()
        self.update_endpoint_pill(self.current_device_name, self.is_headphone)
        if self.force_full_range:
            self.show_toast(
                "⚡ Full Sub-Bass Mode (20Hz)",
                "Anti-Rattle 120Hz filter bypassed for Creative 4.1 / External Subwoofer.",
                icon="⚡",
            )
        else:
            self.show_toast(
                "🔊 Laptop Speakers Mode",
                "Anti-Rattle 120Hz protection re-engaged for internal laptop cones.",
                icon="🔊",
            )

    def refresh_audio_endpoint_ui(self):
        dev_name, is_hp = get_active_windows_output_device()
        self.update_endpoint_pill(dev_name, is_hp)

    def update_endpoint_pill(self, dev_name, is_hp):
        self.current_device_name = dev_name
        self.is_headphone = is_hp
        eff_hp = self.effective_is_headphone

        if hasattr(self, "audio_content_monitor") and self.auto_app_enabled:
            self.audio_content_monitor.reconnect()

        if self.force_full_range:
            mode_desc = "External 4.1 / Subwoofer (Full 20Hz Sub-Bass)"
            pill_text = "⚡ Creative / Ext (Full Bass)"
            dot_color = THEME["accent_green"]
        elif is_hp:
            mode_desc = "Headphones (Full 20Hz Sub-Bass)"
            pill_text = f"🎧 {dev_name[:22]}"
            dot_color = THEME["accent_green"]
        else:
            mode_desc = "Laptop Speakers (Anti-Rattle 120Hz)"
            pill_text = f"🔊 {dev_name[:24]}"
            dot_color = THEME["accent_gold"]

        if getattr(self, "is_window_visible", True):
            if hasattr(self, "lbl_device_pill"):
                self.lbl_device_pill.configure(text=pill_text)
            if hasattr(self, "dev_dot"):
                self.dev_dot.configure(text_color=dot_color)
            if hasattr(self, "tab_smart") and self.tab_smart:
                self.tab_smart.update_endpoint_display(dev_name, eff_hp, self.force_full_range)
            if hasattr(self, "lbl_status"):
                self.lbl_status.configure(text=f"Endpoint: {dev_name} → {mode_desc}", text_color=THEME["accent_gold"])

        self.apply_to_system_audio()

    def prompt_save_custom_preset(self):
        cur_state = {
            "bass": self.tab_audio.slider_bass.get(),
            "clarity": self.tab_audio.slider_clarity.get(),
            "spatial": self.tab_audio.slider_spatial.get(),
            "volume": self.tab_audio.slider_volume.get() / 10.0,
            "eq": self.profiles[self.active_profile_key].get("eq", [0.0]*10)
        }
        def on_saved(key, new_profile):
            try:
                self.save_custom_preset_to_disk(key, new_profile)
            except (OSError, ValueError) as error:
                logger.exception("Could not save custom preset '%s'", key)
                self.lbl_status.configure(
                    text=f"Could not save custom preset: {error}",
                    text_color=THEME["clip_red"],
                )
                return
            self.tab_audio.render_profiles(self.profiles, key)
            self.select_profile(key, apply_system=True)
            self.lbl_status.configure(text=f"✓ Custom preset '{new_profile['title']}' saved and applied!", text_color=THEME["accent_green"])
            self.show_toast(f"Preset Saved: {new_profile['title']}", "Applied to system audio", icon="💾")

        prompt_save_custom_preset_dialog(self, cur_state, on_saved)

    def initial_endpoint_detect(self):
        def _bg():
            try:
                dev_name, is_hp = get_active_windows_output_device()
                self.after(0, lambda: self.update_endpoint_pill(dev_name, is_hp))
            except Exception:
                logger.exception("Initial Windows audio endpoint detection failed")
        threading.Thread(target=_bg, daemon=True).start()

    def get_active_vst_path(self):
        """Returns relative APO path if in VSTPlugins folder, or absolute path to local build."""
        if os.path.isfile(APO_VST_PLUGIN_PATH):
            return f"VSTPlugins\\{APO_VST_PLUGIN_NAME}"
        if os.path.isfile(LOCAL_VST_PLUGIN_PATH):
            return LOCAL_VST_PLUGIN_PATH
        internal_vst = os.path.abspath(os.path.join(get_asset_dir(), "vst", "bin", APO_VST_PLUGIN_NAME))
        if os.path.isfile(internal_vst):
            return internal_vst
        parent_vst = os.path.abspath(os.path.join(get_base_dir(), "..", "vst", "bin", APO_VST_PLUGIN_NAME))
        if os.path.isfile(parent_vst):
            return parent_vst
        root_vst = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vst", "bin", APO_VST_PLUGIN_NAME))
        if os.path.isfile(root_vst):
            return root_vst
        return None

    def is_vst_installed(self):
        return self.get_active_vst_path() is not None

    def toggle_vst(self):
        self.use_vst = not getattr(self, "use_vst", True)
        self.save_persisted_profile()
        self.apply_to_system_audio()
        if hasattr(self, "tab_settings"):
            self.tab_settings.update_vst_ui()

    def build_vst_plugin(self):
        vst_bat = os.path.join(get_base_dir(), "vst", "build_vst.bat")
        if os.path.isfile(vst_bat):
            try:
                os.startfile(vst_bat)
            except Exception as e:
                logger.error("Failed to launch build_vst.bat: %s", e)

    def open_sound_cpl(self):
        open_sound_control_panel()

    def open_driver_setup(self):
        open_system_driver_setup_dialog(self)

    # =========================================================================
    # Instant Headphone Detection & Stream Auto-Adapt Loop (~300ms)
    # =========================================================================
    def auto_app_monitor_loop(self):
        """
        Rock-Solid Decoupled Auto-Adapt Stream Classifier:
        - Priority 1 (3D Gaming): Active fullscreen / borderless 3D game locks Battlefield 360 immediately.
        - Calls remain app-classified; local content analysis selects broad speech/music profiles otherwise.
        - Stability Debounce (Hysteresis): The target must persist across cycles before switching.
        - Idle Hold: When playback pauses, the last sound profile is retained.
        """
        pending_target = None
        pending_counter = 0
        last_error_log = 0.0

        # Cached active audio source persisting across background check cycles
        cached_active_src = None
        cached_active_sources = []
        bg_check_counter = 0

        while self.running:
            is_vis = getattr(self, "is_window_visible", True)
            try:
                if not self.auto_app_enabled:
                    self._set_sense_content_analysis(False)
                    time.sleep(1.0)
                    continue

                # 1. Fast Foreground Active Window Check (~300ms)
                user32 = ctypes.windll.user32
                fg_hwnd = user32.GetForegroundWindow()
                fg_proc = None
                fg_pid = 0
                if fg_hwnd:
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(pid))
                    if pid.value > 0:
                        fg_pid = pid.value
                        fg_proc = get_process_name_by_pid(fg_pid)

                # Skip self process
                if fg_proc and fg_proc.lower() in ("soniq_max.exe", "python.exe", "pythonw.exe"):
                    fg_proc = None
                    fg_hwnd = None

                fg_target = None
                if fg_proc:
                    fg_target, _ = classify_audio_stream_dynamically(
                        fg_pid, fg_hwnd, fg_proc
                    )

                # 2. Background Audio Session Query (periodic ~900ms check)
                bg_check_counter += 1
                bg_threshold = 3 if is_vis else 1
                if bg_check_counter >= bg_threshold:
                    bg_check_counter = 0
                    audio_sources = get_dynamic_windows_audio_sources()
                    # Filter for real audio output (peak volume > 0.0005 or active state)
                    real_sources = [s for s in audio_sources if s.get("peak", 0) > 0.0005 or s.get("active")]
                    if real_sources:
                        cached_active_src = real_sources[0]
                        cached_active_sources = real_sources
                    else:
                        cached_active_src = None
                        cached_active_sources = []
                    browser_playback = should_classify_browser_audio(
                        source.get("name", "") for source in cached_active_sources
                    )
                    self._set_sense_content_analysis(browser_playback)

                chosen_target = None
                analysis = self.audio_content_monitor.latest_result
                content_target = None
                local_music_playing = any(
                    source.get("name", "").casefold() in SENSE_LOCAL_MUSIC_PROCESSES
                    for source in cached_active_sources
                )
                if local_music_playing:
                    content_target = self.sense_profile_assignments["music"]
                elif analysis and analysis.category == "gaming":
                    content_target = self.sense_profile_assignments["gaming"]
                elif analysis and analysis.category == "cinema":
                    content_target = self.sense_profile_for_detected_target("cinema_dialogue")
                elif analysis and analysis.category == "speech":
                    content_target = self.sense_profile_assignments["speech"]
                elif analysis and analysis.category == "music":
                    content_target = self.sense_profile_assignments["music"]

                # HIERARCHY EVALUATION:
                # -------------------------------------------------------------
                # Check for active voice communication stream in background
                active_voice_src = any(
                    s.get("name", "").casefold() in SENSE_VOICE_PROCESSES
                    for s in cached_active_sources
                )

                # Priority 1: Active Voice Call (Discord, Zoom, Teams, Skype, WhatsApp)
                # Voice intelligibility for live calls always takes precedence
                if active_voice_src or fg_target == "voice_meeting":
                    chosen_target = self.sense_profile_assignments["speech"]

                # Priority 2: Active 3D Fullscreen / Borderless Game or Dedicated Game Engine
                elif fg_target == "fps_gaming":
                    chosen_target = self.sense_profile_assignments["gaming"]

                # Priority 3: Active Media Player or Browser Media Stream
                elif cached_active_src:
                    src_proc = cached_active_src["name"]
                    src_pid = cached_active_src["pid"]
                    # If foreground window is the same app (e.g. Chrome with YouTube tab open in foreground)
                    if fg_proc and fg_proc.lower() == src_proc.lower():
                        chosen_hwnd = fg_hwnd
                    else:
                        chosen_hwnd = get_hwnd_for_process_family(src_pid, src_proc)

                    bg_target, _ = classify_audio_stream_dynamically(
                        src_pid, chosen_hwnd, src_proc
                    )
                    if local_music_playing:
                        chosen_target = self.sense_profile_assignments["music"]
                    elif bg_target == "fps_gaming":
                        chosen_target = self.sense_profile_assignments["gaming"]
                    elif bg_target in ("cinema_dialogue", "bass_beast", "voice_meeting"):
                        chosen_target = self.sense_profile_for_detected_target(bg_target)
                    elif content_target:
                        chosen_target = content_target
                    elif bg_target:
                        chosen_target = self.sense_profile_for_detected_target(bg_target)

                # Priority 4: AI Loopback Content Classifier (YAMNet unclassified streams)
                elif content_target:
                    chosen_target = content_target

                # Priority 5: Foreground dedicated media app
                elif fg_target and fg_target in ("cinema_dialogue", "bass_beast"):
                    chosen_target = self.sense_profile_for_detected_target(fg_target)

                elif analysis and analysis.category == "other" and cached_active_src:
                    chosen_target = resolve_sense_profile(
                        "other", self.sense_profile_assignments
                    )

                # Stability Debounce / Hysteresis Filter:
                # Target must be consistently observed for at least 2 consecutive cycles (~600ms)
                # before applying to prevent rapid flipping during tab switching or song pauses.
                if chosen_target and chosen_target in self.profiles:
                    if chosen_target == pending_target:
                        pending_counter += 1
                    else:
                        pending_target = chosen_target
                        pending_counter = 1

                    if pending_counter >= 2:
                        if (
                            chosen_target != self._auto_applied_profile_key
                            and chosen_target != self._auto_apply_pending_profile_key
                            and time.monotonic() >= self._auto_apply_retry_after
                        ):
                            self._auto_apply_pending_profile_key = chosen_target
                            self.after(
                                0,
                                lambda p=chosen_target: self.apply_auto_profile_silently(p),
                            )
                else:
                    # When audio pauses, hold current state without resetting or flapping
                    pending_target = None
                    pending_counter = 0

            except Exception:
                now = time.monotonic()
                if now - last_error_log >= 60:
                    logger.exception("Auto-adapt monitor iteration failed")
                    last_error_log = now

            # Decoupled sleep: 0.30s when visible for quick cues, 1.50s when minimized in tray
            # Decoupled sleep with laptop battery awareness:
            # When on battery power, relax polling to conserve power.
            poll_sleep = 0.30 if is_vis else 1.50
            try:
                battery = psutil.sensors_battery()
                if battery and not battery.power_plugged:
                    poll_sleep = 0.70 if is_vis else 2.20
            except Exception:
                pass
            time.sleep(poll_sleep)

    def apply_auto_profile_silently(self, target_profile):
        if (
            not self.auto_app_enabled
            or target_profile != self._auto_apply_pending_profile_key
            or target_profile not in self.profiles
        ):
            return

        try:
            applied = self.apply_to_system_audio(
                profile=self.profiles[target_profile],
                update_status=False,
            )
        except Exception:
            logger.exception(
                "Could not apply automatic Soniq Sense profile %s",
                target_profile,
            )
            applied = False
        if applied:
            self._auto_applied_profile_key = target_profile
            self._auto_apply_retry_after = 0.0
        else:
            self._auto_apply_retry_after = time.monotonic() + 10.0
        if self._auto_apply_pending_profile_key == target_profile:
            self._auto_apply_pending_profile_key = None

    # =========================================================================
    # Hotkey Dispatcher & Actions
    # =========================================================================
    def on_hotkey_triggered(self, action):
        """Thread-safe handler for registered Win32 global hotkeys."""
        profile_keys = [
            "laptop_lifesaver",
            "cinema_dialogue",
            "bass_beast",
            "fps_gaming",
            "voice_meeting",
            "audiophile_flat"
        ]

        if action == "toggle_bypass":
            self.after(0, self.hotkey_toggle_bypass)
        elif action == "toggle_night_mode":
            self.after(0, self.hotkey_toggle_night_mode)
        elif action == "restore_window":
            self.after(0, self._restore_window)
        elif action.startswith("select_preset_"):
            idx = int(action.split("_")[-1])
            if idx < len(profile_keys):
                pkey = profile_keys[idx]
                self.after(0, lambda k=pkey: self.hotkey_select_profile(k))

    def hotkey_toggle_bypass(self):
        if hasattr(self, "master_switch"):
            if self.is_enhanced:
                self.master_switch.deselect()
            else:
                self.master_switch.select()
            self.toggle_master_switch()
            state = "ENHANCED (ON)" if self.is_enhanced else "BYPASSED (OFF)"
            self.lbl_status.configure(text=f"⌨️ Global Hotkey: Effects {state}", text_color=THEME["accent_gold"])
            self.show_toast("Hotkey: Master Switch", f"Effects {state}", icon="⌨️")

    def hotkey_toggle_night_mode(self):
        if hasattr(self, "tab_audio"):
            self.tab_audio.switch_night_mode.toggle()
            self.toggle_night_mode()
            state = "ENABLED" if self.night_mode else "DISABLED"
            self.lbl_status.configure(text=f"⌨️ Global Hotkey: Night Mode {state}", text_color=THEME["accent_gold"])
            self.show_toast("Hotkey: Night Mode", f"Dialogue Leveler {state}", icon="🌙")

    def hotkey_select_profile(self, pkey):
        if pkey in self.profiles:
            self.select_profile(pkey, apply_system=True)
            title = self.profiles[pkey]["title"]
            self.lbl_status.configure(text=f"⌨️ Global Hotkey: Profile switched to '{title}'", text_color=THEME["accent_green"])
            self.show_toast(f"Hotkey: {title}", self.profiles[pkey].get("badge", "PRESET ACTIVE"), icon="⌨️")

    # =========================================================================
    # System Startup & System Tray Integration
    # =========================================================================
    def is_startup_registered(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            value = winreg.QueryValueEx(key, "SONIQ_MAX")[0]
            winreg.CloseKey(key)
            if not value:
                return False
            # Verify registered binary actually exists on disk
            match = re.match(r'^\s*"?([^"]+)"?', value)
            if match:
                return os.path.isfile(match.group(1).strip())
            return bool(value)
        except Exception:
            return False

    def toggle_startup(self):
        enable = bool(self.tab_settings.switch_startup.get())
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
            if enable:
                if getattr(sys, 'frozen', False):
                    val = f'"{sys.executable}" --minimized'
                else:
                    dist_exe = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "SONIQ_MAX", "SONIQ_MAX.exe"))
                    if not os.path.isfile(dist_exe):
                        dist_exe = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "SONIQ_MAX.exe"))
                    if os.path.isfile(dist_exe):
                        val = f'"{dist_exe}" --minimized'
                    else:
                        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
                        val = f'"{pythonw}" "{os.path.abspath(__file__)}" --minimized'
                winreg.SetValueEx(key, "SONIQ_MAX", 0, winreg.REG_SZ, val)
                self.lbl_status.configure(text="✓ Added to Windows Startup. Will run silently in tray on boot.", text_color=THEME["accent_green"])
            else:
                try:
                    winreg.DeleteValue(key, "SONIQ_MAX")
                except FileNotFoundError:
                    pass
                self.lbl_status.configure(text="Removed from Windows Startup.", text_color=THEME["accent_bronze"])
            winreg.CloseKey(key)
        except Exception as e:
            self.lbl_status.configure(text=f"Startup registry error: {e}", text_color=THEME["clip_red"])

    def hide_to_tray(self):
        self.withdraw()
        self.is_window_visible = False
        # Windows RAM Working Set flush: Trims physical memory footprint down to ~15 MB
        try:
            ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
        except Exception:
            pass
        self.tray_service.notify("SONIQ MAX is running in the background", "Sound Enhancer Active")

    def show_from_tray(self):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.is_window_visible = True
        self.deiconify()
        self.lift()
        self.focus_force()

    def tray_switch_profile(self, key):
        self.after(0, lambda: self.select_profile(key, apply_system=True))

    def tray_toggle_bypass(self):
        self.after(0, lambda: self.master_switch.toggle())

    def tray_toggle_auto_adapt(self):
        self.after(0, lambda: self.tab_smart.switch_auto_app.toggle())

    def quit_application(self):
        self.running = False
        self.audio_content_monitor.shutdown()
        if hasattr(self, "endpoint_watcher"):
            self.endpoint_watcher.stop()
        self.hotkey_service.stop()
        self.tray_service.stop()
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

if __name__ == "__main__":
    app = SoniqDesktopApp()
    app.mainloop()
