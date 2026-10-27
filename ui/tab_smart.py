"""SONIQ SENSE auto-adaptation and preset assignment controls."""
import customtkinter as ctk
from constants import THEME
from ui.fluent_effects import FluentTooltip, stagger_cascade_entrance

class SmartAppTab(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.pack(fill="both", expand=True)
        self.build_content()

    def build_content(self):
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=4, pady=4)

        self.c_brand = ctk.CTkFrame(
            self.container,
            fg_color=THEME["card_bg"],
            corner_radius=14,
            border_width=1,
            border_color=THEME["card_border"],
        )
        self.c_brand.pack(fill="x", pady=(2, 8))
        ctk.CTkLabel(
            self.c_brand,
            text="SONIQ SENSE",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=THEME["accent_gold"],
        ).pack(anchor="w", padx=18, pady=(16, 2))
        ctk.CTkLabel(
            self.c_brand,
            text="Adaptive audio profiles, tuned to what you play.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=THEME["text_dim"],
        ).pack(anchor="w", padx=18, pady=(0, 16))

        # Playback device used for output-mode profile tuning
        self.c_endpoint = ctk.CTkFrame(self.container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        self.c_endpoint.pack(fill="x", pady=6)

        ep_top = ctk.CTkFrame(self.c_endpoint, fg_color="transparent")
        ep_top.pack(fill="x", padx=16, pady=(12, 4))

        ep_title = ctk.CTkLabel(ep_top, text="🎧 Playback device", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=THEME["accent_gold"])
        ep_title.pack(side="left")

        hp_tag = "HEADPHONES" if self.controller.is_headphone else "SPEAKERS"
        hp_color = THEME["accent_green"] if self.controller.is_headphone else THEME["accent_bronze"]
        self.lbl_endpoint_badge = ctk.CTkLabel(ep_top, text=f"● {hp_tag}", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=hp_color)
        self.lbl_endpoint_badge.pack(side="right")

        self.lbl_endpoint_device = ctk.CTkLabel(
            self.c_endpoint,
            text=f"Device: {self.controller.current_device_name}",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=THEME["text_main"]
        )
        self.lbl_endpoint_device.pack(anchor="w", padx=16, pady=(2, 2))

        ep_mode_desc = (
            "• Headphones: no speaker high-pass filter is added.\n"
            "• Speakers: a 120 Hz high-pass filter is included; actual device response varies."
        )
        self.lbl_endpoint_details = ctk.CTkLabel(
            self.c_endpoint,
            text=ep_mode_desc,
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=THEME["text_dim"], justify="left"
        )
        self.lbl_endpoint_details.pack(anchor="w", padx=16, pady=(0, 10))

        ep_btn_row = ctk.CTkFrame(self.c_endpoint, fg_color="transparent")
        ep_btn_row.pack(fill="x", padx=16, pady=(0, 12))

        btn_refresh_ep = ctk.CTkButton(
            ep_btn_row,
            text="Refresh playback device",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME["btn_secondary"],
            text_color=THEME["accent_gold"],
            hover_color=THEME["btn_secondary_hover"],
            border_width=1,
            border_color=THEME["card_border"],
            height=28,
            command=self.controller.refresh_audio_endpoint_ui
        )
        btn_refresh_ep.pack(side="left")
        FluentTooltip(btn_refresh_ep, title="Playback device", text="Refreshes the active output device used to select speaker or headphone filter tuning.")

        # Card 2: Soniq Sense hybrid app and playback-content analysis
        self.c_stream = ctk.CTkFrame(self.container, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        self.c_stream.pack(fill="x", pady=6)

        s_top = ctk.CTkFrame(self.c_stream, fg_color="transparent")
        s_top.pack(fill="x", padx=16, pady=(12, 4))

        self.switch_auto_app = ctk.CTkSwitch(
            s_top,
            text="⚡ Automatic profile switching",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=THEME["text_main"],
            progress_color=THEME["accent_bronze"],
            command=self.controller.toggle_auto_app
        )
        if self.controller.auto_app_enabled:
            self.switch_auto_app.select()
        self.switch_auto_app.pack(side="left")

        FluentTooltip(
            self.switch_auto_app,
            title="Soniq Sense",
            text="Automatically selects your assigned presets for games, music, speech/calls, and other playback. Analysis is performed locally."
        )

        s_desc = ctk.CTkLabel(
            self.c_stream,
            text=(
                "Choose what Soniq Sense should apply for each type of listening. "
                "Switches happen quietly; your manual preset selection stays visible."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=THEME["text_dim"], justify="left"
        )
        s_desc.pack(anchor="w", padx=16, pady=(6, 14))

        self.c_assignments = ctk.CTkFrame(
            self.container,
            fg_color=THEME["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["card_border"],
        )
        self.c_assignments.pack(fill="x", pady=6)

        assignment_header = ctk.CTkFrame(self.c_assignments, fg_color="transparent")
        assignment_header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(
            assignment_header,
            text="Your listening presets",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=THEME["accent_gold"],
        ).pack(side="left", anchor="w")
        self.btn_reset_assignments = ctk.CTkButton(
            assignment_header,
            text="Restore defaults",
            width=112,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color=THEME["pill_bg"],
            text_color=THEME["text_dim"],
            hover_color=THEME["btn_secondary_hover"],
            command=self.controller.reset_sense_profile_assignments,
        )
        self.btn_reset_assignments.pack(side="right")

        ctk.CTkLabel(
            self.c_assignments,
            text=(
                "Choose the preset Soniq Sense applies to each category. Other audio is playback "
                "that does not match the game, music, or speech/call rules. Your choices save automatically."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=THEME["text_dim"],
            anchor="w",
            wraplength=740,
        ).pack(anchor="w", padx=16, pady=(0, 8))
        self.profile_assignment_menus = {}
        self.profile_choice_keys = {}
        self._profile_choice_values = []
        self._build_profile_assignment_controls()

    def update_endpoint_display(self, dev_name, is_hp):
        """Refreshes endpoint labels."""
        self.lbl_endpoint_device.configure(text=f"Device: {dev_name}")
        hp_tag = "HEADPHONES" if is_hp else "SPEAKERS"
        hp_color = THEME["accent_green"] if is_hp else THEME["accent_bronze"]
        self.lbl_endpoint_badge.configure(text=f"● {hp_tag}", text_color=hp_color)

    def refresh_profile_choices(self):
        counts = {}
        for profile in self.controller.profiles.values():
            title = profile.get("title", "Custom")
            counts[title] = counts.get(title, 0) + 1

        self.profile_choice_keys.clear()
        for key, profile in self.controller.profiles.items():
            title = profile.get("title", "Custom")
            display = f"{title} ({key})" if counts[title] > 1 else title
            self.profile_choice_keys[display] = key
        self._profile_choice_values = list(self.profile_choice_keys)

        for category, menu in self.profile_assignment_menus.items():
            menu.configure(values=self._profile_choice_values)
            assigned_key = self.controller.sense_profile_assignments[category]
            menu.set(self._display_value_for_profile(assigned_key))

    def _display_value_for_profile(self, profile_key):
        for display, key in self.profile_choice_keys.items():
            if key == profile_key:
                return display
        return self._profile_choice_values[0] if self._profile_choice_values else ""

    def _on_profile_assignment_changed(self, category, display_value):
        profile_key = self.profile_choice_keys.get(display_value)
        if profile_key:
            self.controller.set_sense_profile_assignment(category, profile_key)

    def _build_profile_assignment_controls(self):
        self.refresh_profile_choices()
        categories = (
            ("gaming", "Games"),
            ("music", "Music playback"),
            ("speech", "Speech / calls"),
            ("other", "Other detected audio"),
        )
        for category, label in categories:
            row = ctk.CTkFrame(self.c_assignments, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(
                row,
                text=label,
                width=190,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=THEME["text_main"],
                anchor="w",
            ).pack(side="left")
            menu = ctk.CTkOptionMenu(
                row,
                values=self._profile_choice_values,
                command=lambda value, key=category: self._on_profile_assignment_changed(key, value),
                fg_color=THEME["btn_secondary"],
                button_color=THEME["accent_bronze"],
                button_hover_color=THEME["btn_primary_hover"],
                dropdown_fg_color=THEME["card_bg"],
                text_color=THEME["text_main"],
                width=260,
                dynamic_resizing=False,
            )
            menu.pack(side="left", fill="x", expand=True)
            self.profile_assignment_menus[category] = menu
        self.refresh_profile_choices()

    def animate_staggered_entrance(self):
        """Sequential waterfall entrance for Soniq Sense controls."""
        cards = [self.c_endpoint, self.c_stream, self.c_assignments]
        cards.insert(0, self.c_brand)
        stagger_cascade_entrance(self.container, cards, step_delay_ms=22)
