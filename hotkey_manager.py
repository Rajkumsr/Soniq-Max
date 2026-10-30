"""
SONIQ MAX PRO — Global System-Wide Keyboard Hotkey Service.
Registers native Win32 system-wide hotkeys (MOD_CONTROL | MOD_ALT) so users can
control audio profiles, bypass mode, and night mode from inside games or fullscreen apps.
"""
import ctypes
from ctypes import wintypes
import threading
import time

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

class GlobalHotkeyManager:
    """Manages Win32 global hotkeys using RegisterHotKey and a thread message pump."""
    def __init__(self, callback_dispatcher=None):
        self.running = False
        self._thread = None
        self.callback_dispatcher = callback_dispatcher
        self.registered_hotkeys = {}

    def start(self):
        """Starts background hotkey listening thread."""
        if self._thread and self._thread.is_alive():
            return
        self.running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops background hotkey listening thread."""
        self.running = False

    def _worker_loop(self):
        user32 = ctypes.windll.user32

        # Define hotkeys: ID -> (Virtual Key Code, Action Name)
        hotkey_definitions = {
            101: (ord('B'), "toggle_bypass"),
            102: (ord('N'), "toggle_night_mode"),
            103: (ord('S'), "restore_window"),
            104: (ord('1'), "select_preset_0"),
            105: (ord('2'), "select_preset_1"),
            106: (ord('3'), "select_preset_2"),
            107: (ord('4'), "select_preset_3"),
            108: (ord('5'), "select_preset_4"),
            109: (ord('6'), "select_preset_5"),
        }

        # Force thread message queue creation
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        # Register hotkeys
        for hk_id, (vk, action) in hotkey_definitions.items():
            try:
                res = user32.RegisterHotKey(None, hk_id, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, vk)
                if res:
                    self.registered_hotkeys[hk_id] = action
            except Exception:
                pass

        while self.running:
            try:
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1): # PM_REMOVE = 1
                    if msg.message == WM_HOTKEY:
                        hk_id = msg.wParam
                        action = self.registered_hotkeys.get(hk_id)
                        if action and self.callback_dispatcher:
                            self.callback_dispatcher(action)
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            except Exception:
                pass
            time.sleep(0.04)

        # Clean unregistration
        for hk_id in list(self.registered_hotkeys.keys()):
            try:
                user32.UnregisterHotKey(None, hk_id)
            except Exception:
                pass
        self.registered_hotkeys.clear()
