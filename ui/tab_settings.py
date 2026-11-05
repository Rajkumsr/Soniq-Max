"""
SONIQ MAX PRO — Settings Tab View Component.
Unified System Audio Pipeline Engine selector (Direct Soniq Engine vs Equalizer APO),
native VST engine controls, global system hotkeys, diagnostics, Windows startup toggle,
and application info with zero duplication.
"""
import os
import webbrowser
import customtkinter as ctk
from constants import THEME, APO_DEFAULT_PATH, APP_GITHUB_URL, APP_ORGANIZATION
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

        # Card 1: Unified System Audio Pipeline Engine & VST DSP
        self.c_engine = ctk.CTkFrame(
            self.container, fg_color=THEME["card_bg"],
            corner_radius=12, border_width=1, border_color=THEME["card_border"]
        )
        self.c_engine.pack(fill="x", pady=6)

        eng_top = ctk.CTkFrame(self.c_engine, fg_color="transparent")
        eng_top.pack(fill="x", padx=16, pady=(12, 6))

        eng_title = ctk.CTkLabel(
            eng_top, text="⚡ System Audio Pipeline Engine",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=THEME["accent_gold"]
        )
        eng_title.pack(side="left")

        self.lbl_engine_badge = ctk.CTkLabel(
            eng_top, text="● DIRECT VST ACTIVE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=THEME["accent_green"],
            fg_color=THEME["pill_bg"],
            corner_radius=6,
            padx=8, pady=2
        )
        self.lbl_engine_badge.pack(side="right")

        # Engine Mode Segmented Button
        sel_row = ctk.CTkFrame(self.c_engine, fg_color="transparent")
        sel_row.pack(fill="x", padx=16, pady=(0, 10))

        self.seg_engine = ctk.CTkSegmentedButton(
            sel_row,
            values=["🛠️ Equalizer APO Driver (Native VST)", "🚀 Direct Soniq Engine (No APO)"],
            command=self.on_engine_mode_selected,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            selected_color=THEME["accent_green"],
            selected_hover_color=THEME["accent_green"],
            unselected_color=THEME["bg_dark"],
            unselected_hover_color=THEME["pill_bg"],
            corner_radius=8
        )
        self.seg_engine.pack(fill="x")

        # Direct Soniq Engine Box
        self.box_direct = ctk.CTkFrame(self.c_engine, fg_color=THEME["bg_dark"], corner_radius=8, border_width=1, border_color=THEME["card_border"])
        self.box_direct.pack(fill="x", padx=16, pady=(0, 12))

        lbl_direct_desc = ctk.CTkLabel(
            self.box_direct,
            text=(
                "• Intercepts Windows audio directly in RAM and passes samples through SoniqMaxDSP.dll.\n"
                "• Equalizer APO is completely bypassed (no driver installation, reboots, or config file writes required).\n"
                "• Psychoacoustic sub-harmonic bass, 2.8 kHz vocal presence, Haas 3D stereo, and peak brickwall limiting."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=THEME["text_dim"], justify="left"
        )
        lbl_direct_desc.pack(anchor="w", padx=12, pady=(10, 6))

        self.lbl_pipeline_flow = ctk.CTkLabel(
            self.box_direct,
            text="Pipeline: [Detecting Endpoints...]",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color=THEME["accent_gold"]
        )
        self.lbl_pipeline_flow.pack(anchor="w", padx=12, pady=(0, 8))

        # Direct Engine DSP Toggle & Status Row
        vst_toggle_row = ctk.CTkFrame(self.box_direct, fg_color="transparent")
        vst_toggle_row.pack(fill="x", padx=12, pady=(0, 10))

        self.switch_vst = ctk.CTkSwitch(
            vst_toggle_row,
            text="Enable Native VST Processing",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME["text_main"],
            progress_color=THEME["accent_green"],
            command=self.controller.toggle_vst
        )
        self.switch_vst.pack(side="left", padx=(0, 12))
        FluentTooltip(self.switch_vst, title="Toggle VST Processing", text="Instantly enables or bypasses the real-time C++17 DSP plugin.")

        self.vst_status_lbl = ctk.CTkLabel(
            vst_toggle_row, text="✓ Active (SoniqMaxDSP.dll)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME["accent_green"]
        )
        self.vst_status_lbl.pack(side="left")

        # Direct Engine Buttons
        direct_btns = ctk.CTkFrame(self.box_direct, fg_color="transparent")
        direct_btns.pack(fill="x", padx=12, pady=(0, 12))

        btn_restart_engine = ctk.CTkButton(
            direct_btns,
            text="⚡ Restart Pipeline",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME["btn_primary"],
            text_color=THEME["bg_dark"],
            hover_color=THEME["btn_primary_hover"],
            command=self.controller.restart_direct_engine
        )
        btn_restart_engine.pack(side="left", padx=(0, 8))
        FluentTooltip(btn_restart_engine, title="Restart Stream", text="Restarts the real-time audio pipeline and reconnects endpoints.")

        self.btn_compile_vst = ctk.CTkButton(
            direct_btns,
            text="🔨 Recompile VST",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=THEME["btn_secondary"],
            text_color=THEME["accent_gold"],
            hover_color=THEME["btn_secondary_hover"],
            border_width=1,
            border_color=THEME["card_border"],
            command=self.controller.build_vst_plugin
        )
        self.btn_compile_vst.pack(side="left", padx=(0, 8))
        FluentTooltip(self.btn_compile_vst, title="Build VST Plugin", text="Compiles SoniqMaxDSP.dll via vst/build_vst.bat.")

        btn_sound_cpl_direct = ctk.CTkButton(
            direct_btns,
            text="🔊 Windows Sound Settings",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=THEME["pill_bg"],
            text_color=THEME["text_dim"],
            hover_color=THEME["btn_secondary_hover"],
            border_width=1,
            border_color=THEME["pill_border"],
            command=self.controller.open_sound_cpl
        )
        btn_sound_cpl_direct.pack(side="left")
        FluentTooltip(btn_sound_cpl_direct, title="Windows Sound Control Panel", text="Set your default playback device to Virtual Cable for 100% system routing.")

        # Equalizer APO Box (shown only when APO mode is selected)
        self.box_apo = ctk.CTkFrame(self.c_engine, fg_color=THEME["bg_dark"], corner_radius=8, border_width=1, border_color=THEME["card_border"])

        apo_desc = ctk.CTkLabel(
            self.box_apo,
            text=(
                f"• System Audio Driver: Equalizer APO ({APO_DEFAULT_PATH})\n"
                "• Native Psychoacoustic DSP: SoniqMaxDSP.dll loaded directly in Realtek audio driver.\n"
                "• Zero latency, zero virtual audio cables required, works system-wide across all apps & games."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=THEME["text_dim"], justify="left"
        )
        apo_desc.pack(anchor="w", padx=12, pady=(10, 6))

        # APO VST DSP Mode Toggle Row
        vst_apo_row = ctk.CTkFrame(self.box_apo, fg_color="transparent")
        vst_apo_row.pack(fill="x", padx=12, pady=(0, 10))

        self.switch_vst_apo = ctk.CTkSwitch(
            vst_apo_row,
            text="Enable Native VST Processing",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME["text_main"],
            progress_color=THEME["accent_green"],
            command=self.controller.toggle_vst
        )
        self.switch_vst_apo.pack(side="left", padx=(0, 12))
        FluentTooltip(self.switch_vst_apo, title="Toggle VST Processing", text="When ON: VST owns harmonics, clarity, spatializer, and limiter with zero duplicate filters. When OFF: falls back cleanly to APO-only filters.")

        self.vst_status_lbl_apo = ctk.CTkLabel(
            vst_apo_row, text="✓ Active (SoniqMaxDSP.dll)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME["accent_green"]
        )
        self.vst_status_lbl_apo.pack(side="left", padx=(0, 12))

        self.btn_compile_vst_apo = ctk.CTkButton(
            vst_apo_row,
            text="🔨 Recompile VST",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=THEME["btn_secondary"],
            text_color=THEME["accent_gold"],
            hover_color=THEME["btn_secondary_hover"],
            border_width=1,
            border_color=THEME["card_border"],
            command=self.controller.build_vst_plugin
        )
        self.btn_compile_vst_apo.pack(side="left")

        apo_btn_row = ctk.CTkFrame(self.box_apo, fg_color="transparent")
        apo_btn_row.pack(fill="x", padx=12, pady=(0, 12))

        btn_sync = ctk.CTkButton(
            apo_btn_row, 
            text="⚡ Re-sync System Audio", 
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), 
            fg_color=THEME["btn_primary"], 
            text_color=THEME["bg_dark"], 
            hover_color=THEME["btn_primary_hover"], 
            command=self.controller.apply_to_system_audio
        )
        btn_sync.pack(side="left", padx=(0, 8))
        FluentTooltip(btn_sync, title="Synchronize Equalizer APO", text="Updates the SONIQ MAX managed filter file and ensures the main config includes it.")

        btn_guide = ctk.CTkButton(
            apo_btn_row, 
            text="📘 Driver Setup Guide", 
            font=ctk.CTkFont(family="Segoe UI", size=11), 
            fg_color=THEME["btn_secondary"], 
            text_color=THEME["accent_gold"], 
            hover_color=THEME["btn_secondary_hover"], 
            border_width=1, 
            border_color=THEME["card_border"], 
            command=self.controller.open_driver_setup
        )
        btn_guide.pack(side="left", padx=(0, 8))
        FluentTooltip(btn_guide, title="APO Setup Wizard", text="Opens step-by-step instructions for installing Equalizer APO on your sound card.")

        btn_sound_cpl_apo = ctk.CTkButton(
            apo_btn_row, 
            text="🔊 Windows Sound Settings", 
            font=ctk.CTkFont(family="Segoe UI", size=11), 
            fg_color=THEME["pill_bg"], 
            text_color=THEME["text_dim"], 
            hover_color=THEME["btn_secondary_hover"], 
            border_width=1, 
            border_color=THEME["pill_border"], 
            command=self.controller.open_sound_cpl
        )
        btn_sound_cpl_apo.pack(side="left")

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
            title="⚙️ Diagnostics & Engine Details",
            subtitle="Audio routing and configuration details",
            is_expanded=False,
            badge="POWER USER"
        )
        self.c_advanced.pack(fill="x", pady=6)

        adv_box = ctk.CTkFrame(self.c_advanced.content_frame, fg_color=THEME["bg_dark"], corner_radius=8, border_width=1, border_color=THEME["card_border"])
        adv_box.pack(fill="x", pady=4)

        adv_details = (
            f"• APO Primary File: {APO_DEFAULT_PATH}\n"
            "• Local Fallback Config: SONIQ_APO_Config.txt\n"
            "• Direct VST Binary: vst/bin/SoniqMaxDSP.dll (Static x64 C++17)\n"
            "• Processing Latency: ~10ms (WASAPI 48kHz Stereo)\n"
            "• DWM Accent Hook: Live Win32 HKCU\\Software\\Microsoft\\Windows\\DWM\\AccentColor\n"
            "• Audio Pipeline Engine: Standalone Direct Soniq Engine / Equalizer APO switchable"
        )
        self.lbl_adv = ctk.CTkLabel(
            adv_box, text=adv_details,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=THEME["text_dim"], justify="left"
        )
        self.lbl_adv.pack(anchor="w", padx=12, pady=10)

        # Card 4: Windows Startup Configuration
        self.c_boot = ctk.CTkFrame(self.container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        self.c_boot.pack(fill="x", pady=6)

        boot_row = ctk.CTkFrame(self.c_boot, fg_color="transparent")
        boot_row.pack(fill="x", padx=16, pady=12)

        self.switch_startup = ctk.CTkSwitch(
            boot_row,
            text="Launch SONIQ MAX on Windows Startup",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=THEME["text_main"],
            progress_color=THEME["accent_green"],
            command=self.controller.toggle_startup
        )
        self.switch_startup.pack(side="left")
        if self.controller.is_startup_registered():
            self.switch_startup.select()
        else:
            self.switch_startup.deselect()

        # Card 5: Application Info & Build
        self.c_about = ctk.CTkFrame(self.container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        self.c_about.pack(fill="x", pady=6)

        about_box = ctk.CTkFrame(self.c_about, fg_color="transparent")
        about_box.pack(fill="x", padx=16, pady=12)

        lbl_abt_title = ctk.CTkLabel(about_box, text=f"SONIQ MAX PRO · {APP_ORGANIZATION}", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=THEME["accent_gold"])
        lbl_abt_title.pack(anchor="w")

        lbl_abt_body = ctk.CTkLabel(
            about_box,
            text=f"Engineered & Maintained by {APP_ORGANIZATION}.\nHardware-Optimized Psychoacoustic Audio Suite for Windows 11.\nDirect VST Pipeline & Intelligent Content-Aware Sound Shaping.",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=THEME["text_dim"], justify="left"
        )
        lbl_abt_body.pack(anchor="w", pady=(2, 6))

        btn_github = ctk.CTkButton(
            about_box,
            text=f"🌐 {APP_ORGANIZATION} on GitHub",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME["pill_bg"],
            text_color=THEME["accent_gold"],
            hover_color=THEME["btn_secondary_hover"],
            border_width=1,
            border_color=THEME["pill_border"],
            height=28,
            command=lambda: webbrowser.open(APP_GITHUB_URL)
        )
        btn_github.pack(anchor="w", pady=(2, 0))

        # Initial UI synchronization
        self.update_engine_ui()

    def on_engine_mode_selected(self, choice):
        mode = "apo" if "APO" in choice or "Equalizer" in choice else "direct"
        self.controller.set_engine_mode(mode)

    def update_engine_ui(self):
        mode = getattr(self.controller, "engine_mode", "apo")
        if mode == "apo":
            self.seg_engine.set("🛠️ Equalizer APO Driver (Native VST)")
            self.lbl_engine_badge.configure(text="● EQUALIZER APO ACTIVE", text_color=THEME["accent_green"])
            self.box_apo.pack(fill="x", padx=16, pady=(0, 12))
            self.box_direct.pack_forget()
        else:
            self.seg_engine.set("🚀 Direct Soniq Engine (No APO)")
            self.lbl_engine_badge.configure(text="● DIRECT VST ACTIVE", text_color=THEME["accent_green"])
            self.box_direct.pack(fill="x", padx=16, pady=(0, 12))
            self.box_apo.pack_forget()

            # Refresh pipeline status
            bridge = getattr(self.controller, "audio_bridge", None)
            if bridge and bridge.is_running:
                flow_text = f"Pipeline: [{bridge.last_status_msg}] · 48kHz Stereo Float32"
            elif bridge:
                flow_text = f"Pipeline: Standby ({bridge.last_status_msg})"
            else:
                flow_text = "Pipeline: Initializing..."
            self.lbl_pipeline_flow.configure(text=flow_text)

        self.update_vst_ui()

    def update_vst_ui(self):
        installed = self.controller.is_vst_installed()
        use_vst = getattr(self.controller, "use_vst", True)

        status_text = "✓ Active (SoniqMaxDSP.dll)" if (installed and use_vst) else (
            "○ Bypassed (APO Filters Mode)" if installed else "⚡ Source Ready (vst/src/)"
        )
        status_color = THEME["accent_green"] if (installed and use_vst) else (
            THEME["accent_gold"] if installed else THEME["accent_bronze"]
        )
        btn_text = "🔨 Recompile VST" if installed else "🔨 Compile VST"

        for lbl in (getattr(self, "vst_status_lbl", None), getattr(self, "vst_status_lbl_apo", None)):
            if lbl:
                lbl.configure(text=status_text, text_color=status_color)

        for btn in (getattr(self, "btn_compile_vst", None), getattr(self, "btn_compile_vst_apo", None)):
            if btn:
                btn.configure(text=btn_text)

        for sw in (getattr(self, "switch_vst", None), getattr(self, "switch_vst_apo", None)):
            if sw:
                if use_vst and installed:
                    sw.select()
                else:
                    sw.deselect()

    def animate_staggered_entrance(self):
        """Sequential waterfall entrance for Settings view."""
        cards = [self.c_engine, self.c_hk, self.c_advanced, self.c_boot, self.c_about]
        stagger_cascade_entrance(self.container, cards, step_delay_ms=22)
