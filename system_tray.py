"""
SONIQ MAX PRO — System Tray Integration Service.
Manages Windows notification area icon, right-click context menu,
profile switching, and background minimization.
"""
import os
import threading
from PIL import Image
import pystray
from constants import get_asset_dir

class SystemTrayService:
    def __init__(self, app_callbacks):
        """
        app_callbacks dict:
        - "show": fn()
        - "quit": fn()
        - "toggle_bypass": fn()
        - "toggle_auto_adapt": fn()
        - "select_profile": fn(profile_key)
        - "get_profiles": fn() -> dict of profiles
        """
        self.cb = app_callbacks
        self.icon = None

    def start(self):
        """Builds and starts the system tray icon."""
        icon_path = os.path.join(get_asset_dir(), "soniq_icon.ico")
        if os.path.exists(icon_path):
            img = Image.open(icon_path)
        else:
            img = Image.new("RGBA", (64, 64), (212, 139, 70, 255))

        profiles = self.cb.get("get_profiles", lambda: {})()
        preset_items = []
        for k, p in profiles.items():
            preset_items.append(
                pystray.MenuItem(
                    f"{p.get('icon', '🎵')} {p['title']}",
                    lambda _, key=k: self.cb["select_profile"](key)
                )
            )

        menu = pystray.Menu(
            pystray.MenuItem("SONIQ MAX PRO", lambda: self.cb["show"](), default=True),
            pystray.MenuItem("Sound Profiles", pystray.Menu(*preset_items)),
            pystray.MenuItem("Toggle Enhanced / Bypass", lambda: self.cb["toggle_bypass"]()),
            pystray.MenuItem("Toggle Stream Auto-Adapt", lambda: self.cb["toggle_auto_adapt"]()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show Window", lambda: self.cb["show"]()),
            pystray.MenuItem("Quit", lambda: self.cb["quit"]())
        )

        self.icon = pystray.Icon("SONIQ_MAX", img, "SONIQ MAX — Sound Enhancer", menu=menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def notify(self, message, title="SONIQ MAX"):
        """Displays balloon notification if supported."""
        if self.icon and hasattr(self.icon, "notify"):
            try:
                self.icon.notify(message, title)
            except Exception:
                pass

    def stop(self):
        """Stops tray icon cleanly."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
