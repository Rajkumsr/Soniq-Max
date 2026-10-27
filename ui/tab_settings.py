"""
SONIQ MAX PRO — Settings Tab View Component.
Displays Equalizer APO driver integration status, collapsible global system hotkeys accordion,
collapsible driver diagnostics & overrides, Windows startup toggle, and application info.
"""
import os
import customtkinter as ctk
from constants import THEME, APO_DEFAULT_PATH
from ui.fluent_effects import CollapsibleSection, FluentTooltip, stagger_cascade_entrance

class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.pack(fill="both", expand=True)
        self.build_content()

    def build_content(self):
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=4, pady=4)

        # Card 1: Equalizer APO System Audio Driver
        self.c_apo = ctk.CTkFrame(self.container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        self.c_apo.pack(fill="x", pady=6)

        apo_top = ctk.CTkFrame(self.c_apo, fg_color="transparent")
        apo_top.pack(fill="x", padx=16, pady=(12, 4))

        apo_title = ctk.CTkLabel(apo_top, text="🛠️ System Audio Driver (Equalizer APO)", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=THEME["accent_gold"])
        apo_title.pack(side="left")

        apo_available = os.path.isdir(os.path.dirname(APO_DEFAULT_PATH))
        apo_status = "✓ APO config folder found" if apo_available else "⚠️ APO config folder not detected"
        status_color = THEME["accent_green"] if apo_available else THEME["accent_bronze"]
        st_lbl = ctk.CTkLabel(apo_top, text=apo_status, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=status_color)
        st_lbl.pack(side="right")

        apo_desc = ctk.CTkLabel(
            self.c_apo,
            text=f"Equalizer APO main config: {APO_DEFAULT_PATH}\nSONIQ MAX writes a separate managed filter file and adds an Include line, preserving your existing config.",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=THEME["text_dim"], justify="left"
        )
        apo_desc.pack(anchor="w", padx=16, pady=(0, 10))

        btn_row = ctk.CTkFrame(self.c_apo, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 14))

        btn_sync = ctk.CTkButton(
            btn_row, 
            text="⚡ Re-sync System Audio", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), 
            fg_color=THEME["btn_primary"], 
            text_color=THEME["bg_dark"], 
            hover_color=THEME["btn_primary_hover"], 
            command=self.controller.apply_to_system_audio
        )
        btn_sync.pack(side="left", padx=(0, 10))
        FluentTooltip(btn_sync, title="Synchronize Equalizer APO", text="Updates the SONIQ MAX managed filter file and ensures the main config includes it.")

        btn_guide = ctk.CTkButton(
            btn_row, 
            text="📘 Driver Setup Guide", 
            font=ctk.CTkFont(family="Segoe UI", size=11), 
            fg_color=THEME["btn_secondary"], 
            text_color=THEME["accent_gold"], 
            hover_color=THEME["btn_secondary_hover"], 
            border_width=1, 
            border_color=THEME["card_border"], 
            command=self.controller.open_driver_setup
        )
        btn_guide.pack(side="left", padx=(0, 10))
        FluentTooltip(btn_guide, title="APO Setup Wizard", text="Opens step-by-step instructions for installing and enabling Equalizer APO on your sound card.")

        btn_sound_cpl = ctk.CTkButton(
            btn_row, 
            text="🔊 Windows Sound Control Panel", 
            font=ctk.CTkFont(family="Segoe UI", size=11), 
            fg_color=THEME["pill_bg"], 
            text_color=THEME["text_dim"], 
            hover_color=THEME["btn_secondary_hover"], 
            border_width=1, 
            border_color=THEME["pill_border"], 
            command=self.controller.open_sound_cpl
        )
        btn_sound_cpl.pack(side="right")
        FluentTooltip(btn_sound_cpl, title="Windows Sound Control Panel", text="Launches classic mmsys.cpl to configure default playback devices and sample rates.")

        # Card 2: Collapsible Accordion for Global System Hotkeys
        self.c_hk = CollapsibleSection(
            self.container,
            title="⌨️ Global System Hotkeys (Native Win32 Hooks)",
            subtitle="9 shortcuts active across apps & games",
            is_expanded=True,
            badge="ACTIVE"
        )
        self.c_hk.pack(fill="x", pady=6)

        hk_desc = ctk.CTkLabel(
            self.c_hk.content_frame,
            text="Control audio enhancements and switch sound profiles instantly without minimizing your games, videos, or workspace.",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=THEME["text_dim"], justify="left"
        )
        hk_desc.pack(anchor="w", pady=(0, 10))

        # Hotkeys Table / Grid
        hk_grid = ctk.CTkFrame(self.c_hk.content_frame, fg_color=THEME["bg_dark"], corner_radius=8, border_width=1, border_color=THEME["card_border"])
        hk_grid.pack(fill="x", pady=(0, 4))

        shortcuts = [
            ("Ctrl + Alt + B", "Toggle Master Bypass (Effects ON / OFF)"),
            ("Ctrl + Alt + N", "Toggle Night Mode (Dialogue Leveler)"),
            ("Ctrl + Alt + S", "Show / Restore SONIQ MAX from System Tray"),
            ("Ctrl + Alt + 1", "Preset 1: Laptop Lifesaver (Anti-Rattle)"),
            ("Ctrl + Alt + 2", "Preset 2: Cinema & Dialogue (Movies / OTT)"),
            ("Ctrl + Alt + 3", "Preset 3: Bass & EDM Beast (Club Sub-Bass)"),
            ("Ctrl + Alt + 4", "Preset 4: Battlefield 360 (Combat & Footsteps)"),
            ("Ctrl + Alt + 5", "Preset 5: Zoom & Meeting (Vocal Clarity)"),
            ("Ctrl + Alt + 6", "Preset 6: Acoustic Pure (Hi-Fi Flat)"),
        ]

        for idx, (combo, action) in enumerate(shortcuts):
            col = idx % 2
            row = idx // 2
            cell = ctk.CTkFrame(hk_grid, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="w", padx=12, pady=5)

            badge = ctk.CTkLabel(
                cell,
                text=combo,
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                fg_color=THEME["pill_bg"],
                text_color=THEME["accent_gold"],
                corner_radius=5,
                padx=8,
                pady=2
            )
            badge.pack(side="left")

            desc = ctk.CTkLabel(
                cell,
                text=action,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#d5c2b3"
            )
            desc.pack(side="left", padx=(8, 0))

        # Card 3: Collapsible Accordion for Advanced Driver Diagnostics & Overrides
        self.c_advanced = CollapsibleSection(
            self.container,
            title="⚙️ Equalizer APO Config Details",
            subtitle="Generated filters and APO config details",
            is_expanded=False,
            badge="POWER USER"
        )
        self.c_advanced.pack(fill="x", pady=6)

        adv_box = ctk.CTkFrame(self.c_advanced.content_frame, fg_color=THEME["bg_dark"], corner_radius=8, border_width=1, border_color=THEME["card_border"])
        adv_box.pack(fill="x", pady=4)

        adv_details = (
            f"• APO Primary File: {APO_DEFAULT_PATH}\n"
            "• Local Fallback Config: SONIQ_APO_Config.txt\n"
            "• Managed Equalizer APO Include: SONIQ_MAX_Config.txt\n"
            "• DWM Accent Hook: Live Win32 HKCU\\Software\\Microsoft\\Windows\\DWM\\AccentColor\n"
            "• Processing: Static Equalizer APO filters and stereo channel mixing"
        )
        adv_lbl = ctk.CTkLabel(
            adv_box,
            text=adv_details,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=THEME["text_dim"],
            justify="left"
        )
        adv_lbl.pack(anchor="w", padx=14, pady=10)

        # Card 4: Windows System Startup
        self.c_boot = ctk.CTkFrame(self.container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        self.c_boot.pack(fill="x", pady=6)

        boot_top = ctk.CTkFrame(self.c_boot, fg_color="transparent")
        boot_top.pack(fill="x", padx=16, pady=12)

        self.switch_startup = ctk.CTkSwitch(
            boot_top,
            text="🚀 Launch on Windows Boot (Silent in System Tray)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=THEME["text_main"],
            progress_color=THEME["accent_bronze"],
            command=self.controller.toggle_startup
        )
        if self.controller.is_startup_registered():
            self.switch_startup.select()
        self.switch_startup.pack(side="left")

        FluentTooltip(
            self.switch_startup,
            title="Silent Windows Boot",
            text="Registers in Windows Run registry key. Boots directly into system tray with empty working set memory."
        )

        # Card 5: About
        self.c_about = ctk.CTkFrame(self.container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        self.c_about.pack(fill="x", pady=6)

        ab_title = ctk.CTkLabel(self.c_about, text="SONIQ MAX PRO v2.5 (Windows 11 Native Fluent Edition)", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=THEME["accent_gold"])
        ab_title.pack(anchor="w", padx=16, pady=(12, 2))

        ab_text = ctk.CTkLabel(
            self.c_about,
            text="Windows audio profile manager using Equalizer APO filters.\nIncludes EQ curves, output trim, and optional stereo channel mixing.",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=THEME["text_dim"], justify="left"
        )
        ab_text.pack(anchor="w", padx=16, pady=(0, 14))

    def animate_staggered_entrance(self):
        """Sequential waterfall entrance for Settings view."""
        cards = [self.c_apo, self.c_hk, self.c_advanced, self.c_boot, self.c_about]
        stagger_cascade_entrance(self.container, cards, step_delay_ms=22)
