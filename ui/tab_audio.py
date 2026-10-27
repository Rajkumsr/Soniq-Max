"""SONIQ MAX audio controls and manually selected sound profiles.
Renders a horizontally scrollable profile selector, selected-profile hero card,
4 modular effect cards (Surround Sound, Bass Boost, Voices/Dialogue, Volume Stabilizer + Night Mode),
haptic-style slider feedback, custom dark tooltips, and bottom action bar.
"""
import customtkinter as ctk
from constants import THEME, DEFAULT_PROFILES
from ui.fluent_effects import FluentTooltip, attach_haptic_slider_feedback

class AudioTab(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.profile_buttons = {}
        self._anim_timer = None
        self._anim_step = 0
        self._hero_pulse_timer = None

        self.pack(fill="both", expand=True)
        self.build_content()

    def build_content(self):
        # 1. Scrollable profile selector so custom presets remain usable.
        self.prof_container = ctk.CTkFrame(self, fg_color="transparent")
        self.prof_container.pack(fill="x", padx=4, pady=(2, 4))

        self.profile_bar = ctk.CTkScrollableFrame(
            self.prof_container,
            orientation="horizontal",
            height=48,
            fg_color="transparent",
            scrollbar_button_color=THEME["pill_border"],
            scrollbar_button_hover_color=THEME["accent_bronze"],
        )
        self.profile_bar.pack(fill="x")

        # 2. Manually selected profile, distinct from Soniq Sense's background choice.
        self.active_hero_card = ctk.CTkFrame(
            self,
            fg_color=THEME["card_bg"],
            corner_radius=12,
            border_width=2,
            border_color=THEME["accent_gold"]
        )
        self.active_hero_card.pack(fill="x", padx=4, pady=(2, 6))

        hero_left = ctk.CTkFrame(self.active_hero_card, fg_color="transparent")
        hero_left.pack(side="left", padx=14, pady=8)

        self.hero_icon = ctk.CTkLabel(
            hero_left,
            text="💻",
            font=ctk.CTkFont(family="Segoe UI", size=22)
        )
        self.hero_icon.pack(side="left", padx=(0, 10))

        hero_title_box = ctk.CTkFrame(hero_left, fg_color="transparent")
        hero_title_box.pack(side="left")

        hero_row = ctk.CTkFrame(hero_title_box, fg_color="transparent")
        hero_row.pack(anchor="w")

        self.hero_title = ctk.CTkLabel(
            hero_row,
            text="LAPTOP LIFESAVER",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=THEME["text_main"]
        )
        self.hero_title.pack(side="left", padx=(0, 8))

        self.hero_badge = ctk.CTkLabel(
            hero_row,
            text="SELECTED",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color=THEME["pill_bg"],
            text_color=THEME["accent_gold"],
            corner_radius=5,
            padx=8,
            pady=1
        )
        self.hero_badge.pack(side="left")

        self.hero_desc = ctk.CTkLabel(
            hero_title_box,
            text="A laptop-focused EQ with a low-frequency cut, added upper-bass energy, and clearer vocal frequencies.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=THEME["text_dim"],
            anchor="w"
        )
        self.hero_desc.pack(anchor="w", pady=(1, 0))
        self.hero_auto_note = ctk.CTkLabel(
            hero_title_box,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=THEME["accent_gold"],
            anchor="w",
        )
        self.hero_auto_note.pack(anchor="w", pady=(3, 0))
        self.update_auto_mode_indicator(self.controller.auto_app_enabled)

        # 3. The 4 Signature Effect Cards (2x2 Grid)
        self.deck_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.deck_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.deck_frame.grid_columnconfigure((0, 1), weight=1, uniform="c")
        self.deck_frame.grid_rowconfigure((0, 1), weight=1, uniform="r")

        # Card 1: Surround Sound
        self.c1 = ctk.CTkFrame(self.deck_frame, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["accent_bronze"])
        self.c1.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        c1_top = ctk.CTkFrame(self.c1, fg_color="transparent")
        c1_top.pack(fill="x", padx=14, pady=(10, 2))

        c1_title = ctk.CTkLabel(c1_top, text="🌐 STEREO WIDTH", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=THEME["accent_gold"])
        c1_title.pack(side="left")

        self.switch_card_spatial = ctk.CTkSwitch(
            c1_top, text="ON", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=THEME["accent_gold"], progress_color=THEME["accent_bronze"], width=42,
            command=lambda: self.on_effect_card_toggled("spatial", self.switch_card_spatial, self.c1)
        )
        self.switch_card_spatial.select()
        self.switch_card_spatial.pack(side="right")

        c1_desc = ctk.CTkLabel(self.c1, text="Adjusts a simple left/right channel mix; results vary by recording and device.", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=THEME["text_dim"], justify="left")
        c1_desc.pack(anchor="w", padx=14, pady=(0, 4))

        self.lbl_spatial = ctk.CTkLabel(self.c1, text="Stereo Width: 1.65x", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=THEME["text_main"])
        self.lbl_spatial.pack(anchor="w", padx=14)

        self.slider_spatial = ctk.CTkSlider(self.c1, from_=100, to=250, number_of_steps=150, progress_color=THEME["accent_bronze"], button_color=THEME["accent_gold"], command=self.controller.on_slider_spatial)
        self.slider_spatial.pack(fill="x", padx=14, pady=(2, 4))
        attach_haptic_slider_feedback(self.slider_spatial, expand_len=18)

        c1_badge = ctk.CTkLabel(self.c1, text="Stereo Channel Mix • No Haas Delay Processing", font=ctk.CTkFont(family="Consolas", size=9), text_color=THEME["text_subtle"])
        c1_badge.pack(anchor="w", padx=14, pady=(0, 8))

        # Tooltip on Spatial Audio
        FluentTooltip(
            self.switch_card_spatial,
            title="Stereo Width Mix",
            text="Adjusts the amount of opposite-channel signal mixed into each stereo channel. This is not binaural or Haas-delay processing."
        )

        # Card 2: Bass Boost
        self.c2 = ctk.CTkFrame(self.deck_frame, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["accent_bronze"])
        self.c2.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        c2_top = ctk.CTkFrame(self.c2, fg_color="transparent")
        c2_top.pack(fill="x", padx=14, pady=(10, 2))

        c2_title = ctk.CTkLabel(c2_top, text="⚡ BASS BOOST", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=THEME["accent_gold"])
        c2_title.pack(side="left")

        self.switch_card_bass = ctk.CTkSwitch(
            c2_top, text="ON", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=THEME["accent_gold"], progress_color=THEME["accent_bronze"], width=42,
            command=lambda: self.on_effect_card_toggled("bass", self.switch_card_bass, self.c2)
        )
        self.switch_card_bass.select()
        self.switch_card_bass.pack(side="right")

        c2_desc = ctk.CTkLabel(self.c2, text="Adds upper-bass EQ. The actual low-frequency response depends on your speakers.", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=THEME["text_dim"], justify="left")
        c2_desc.pack(anchor="w", padx=14, pady=(0, 4))

        self.lbl_bass = ctk.CTkLabel(self.c2, text="Bass EQ: 75%", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=THEME["text_main"])
        self.lbl_bass.pack(anchor="w", padx=14)

        self.slider_bass = ctk.CTkSlider(self.c2, from_=0, to=100, number_of_steps=100, progress_color=THEME["accent_bronze"], button_color=THEME["accent_gold"], command=self.controller.on_slider_bass)
        self.slider_bass.pack(fill="x", padx=14, pady=(2, 4))
        attach_haptic_slider_feedback(self.slider_bass, expand_len=18)

        c2_badge = ctk.CTkLabel(self.c2, text="Static EQ Filters • No Harmonic Synthesis", font=ctk.CTkFont(family="Consolas", size=9), text_color=THEME["text_subtle"])
        c2_badge.pack(anchor="w", padx=14, pady=(0, 8))

        # Tooltip on Bass Boost
        FluentTooltip(
            self.switch_card_bass,
            title="Bass EQ",
            text="Applies static bass shelving and peak EQ. It does not synthesize missing bass harmonics."
        )

        # Card 3: Voices / Dialogue Clarity
        self.c3 = ctk.CTkFrame(self.deck_frame, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["accent_bronze"])
        self.c3.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")

        c3_top = ctk.CTkFrame(self.c3, fg_color="transparent")
        c3_top.pack(fill="x", padx=14, pady=(10, 2))

        c3_title = ctk.CTkLabel(c3_top, text="🗣️ VOICES (DIALOGUE)", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=THEME["accent_gold"])
        c3_title.pack(side="left")

        self.switch_card_clarity = ctk.CTkSwitch(
            c3_top, text="ON", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=THEME["accent_gold"], progress_color=THEME["accent_bronze"], width=42,
            command=lambda: self.on_effect_card_toggled("clarity", self.switch_card_clarity, self.c3)
        )
        self.switch_card_clarity.select()
        self.switch_card_clarity.pack(side="right")

        c3_desc = ctk.CTkLabel(self.c3, text="Adds fixed presence EQ; it does not isolate voices or suppress background noise.", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=THEME["text_dim"], justify="left")
        c3_desc.pack(anchor="w", padx=14, pady=(0, 4))

        self.lbl_clarity = ctk.CTkLabel(self.c3, text="Vocal Clarity: 80%", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=THEME["text_main"])
        self.lbl_clarity.pack(anchor="w", padx=14)

        self.slider_clarity = ctk.CTkSlider(self.c3, from_=0, to=100, number_of_steps=100, progress_color=THEME["accent_bronze"], button_color=THEME["accent_gold"], command=self.controller.on_slider_clarity)
        self.slider_clarity.pack(fill="x", padx=14, pady=(2, 4))
        attach_haptic_slider_feedback(self.slider_clarity, expand_len=18)

        c3_badge = ctk.CTkLabel(self.c3, text="2.8 kHz Presence Peak • 7.0 kHz High Shelf", font=ctk.CTkFont(family="Consolas", size=9), text_color=THEME["text_subtle"])
        c3_badge.pack(anchor="w", padx=14, pady=(0, 8))

        # Tooltip on Voices
        FluentTooltip(
            self.switch_card_clarity,
            title="Dialogue Presence EQ",
            text="Applies static presence and high-shelf EQ. It may improve perceived speech clarity but does not isolate dialogue or suppress noise."
        )

        # Card 4: Output Level & Night Mode
        self.c4 = ctk.CTkFrame(self.deck_frame, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["accent_bronze"])
        self.c4.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")

        c4_top = ctk.CTkFrame(self.c4, fg_color="transparent")
        c4_top.pack(fill="x", padx=14, pady=(10, 2))

        c4_title = ctk.CTkLabel(c4_top, text="🔊 OUTPUT LEVEL", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=THEME["accent_gold"])
        c4_title.pack(side="left")

        self.switch_card_volume = ctk.CTkSwitch(
            c4_top, text="ON", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=THEME["accent_gold"], progress_color=THEME["accent_bronze"], width=42,
            command=lambda: self.on_effect_card_toggled("volume", self.switch_card_volume, self.c4)
        )
        self.switch_card_volume.select()
        self.switch_card_volume.pack(side="right")

        c4_desc = ctk.CTkFrame(self.c4, fg_color="transparent")
        c4_desc.pack(fill="x", padx=14, pady=(0, 4))

        c4_text = ctk.CTkLabel(c4_desc, text="Sets output trim with estimated EQ headroom compensation; this is not a hard limiter.", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=THEME["text_dim"], justify="left")
        c4_text.pack(side="left")

        self.switch_night_mode = ctk.CTkSwitch(
            c4_desc, text="🌙 Night Mode", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=THEME["text_main"], progress_color=THEME["accent_bronze"], width=40,
            command=self.controller.toggle_night_mode
        )
        if self.controller.night_mode:
            self.switch_night_mode.select()
        self.switch_night_mode.pack(side="right")

        self.lbl_volume = ctk.CTkLabel(self.c4, text="Output Level Trim: +5.5 dB", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=THEME["text_main"])
        self.lbl_volume.pack(anchor="w", padx=14)

        self.slider_volume = ctk.CTkSlider(self.c4, from_=0, to=120, number_of_steps=120, progress_color=THEME["accent_bronze"], button_color=THEME["accent_gold"], command=self.controller.on_slider_volume)
        self.slider_volume.pack(fill="x", padx=14, pady=(2, 4))
        attach_haptic_slider_feedback(self.slider_volume, expand_len=18)

        c4_badge = ctk.CTkLabel(self.c4, text="Static Preamp Trim • No Limiter or Compressor", font=ctk.CTkFont(family="Consolas", size=9), text_color=THEME["text_subtle"])
        c4_badge.pack(anchor="w", padx=14, pady=(0, 8))

        # Tooltip on Volume & Night Mode
        FluentTooltip(
            self.switch_card_volume,
            title="Output Preamp Trim",
            text="Raises or lowers the output target. Static headroom compensation estimates filter peaks but cannot guarantee protection from clipping."
        )
        FluentTooltip(
            self.switch_night_mode,
            title="Night Mode Output Trim",
            text="Subtracts 2 dB from the requested output-level target before headroom compensation. It does not compress dynamic range."
        )

        # 4. Bottom Action Bar
        self.action_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.action_bar.pack(fill="x", padx=6, pady=(4, 2))

        self.btn_reset = ctk.CTkButton(
            self.action_bar,
            text="↺ Reset Profile",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=THEME["pill_bg"],
            text_color=THEME["text_dim"],
            hover_color=THEME["btn_secondary_hover"],
            height=32,
            command=self.controller.reset_profile_defaults
        )
        self.btn_reset.pack(side="left", padx=(0, 8))

        self.btn_apply = ctk.CTkButton(
            self.action_bar,
            text="⚡ Apply to System Audio",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=THEME["btn_primary"],
            text_color=THEME["text_main"],
            hover_color=THEME["btn_primary_hover"],
            height=32,
            command=self.controller.apply_to_system_audio
        )
        self.btn_apply.pack(side="right")

        self.btn_save_custom = ctk.CTkButton(
            self.action_bar,
            text="💾 Save Custom Preset",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=THEME["pill_bg"],
            text_color=THEME["accent_gold"],
            hover_color=THEME["btn_secondary_hover"],
            height=32,
            command=self.controller.prompt_save_custom_preset
        )
        self.btn_save_custom.pack(side="right", padx=(0, 8))

        self.btn_delete_custom = ctk.CTkButton(
            self.action_bar,
            text="🗑️ Delete Preset",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=THEME["pill_bg"],
            text_color=THEME["clip_red"],
            hover_color=THEME["btn_secondary_hover"],
            height=32,
            command=self.on_delete_custom_clicked
        )

    def on_effect_card_toggled(self, card_name, switch_widget, card_frame):
        """Updates effect card border styling dynamically based on toggle state."""
        is_on = bool(switch_widget.get())
        if is_on:
            card_frame.configure(border_color=THEME["accent_bronze"])
        else:
            card_frame.configure(border_color=THEME["card_border"])
        self.controller.on_card_switch_toggled(card_name)

    def render_profiles(self, profiles, active_key):
        """Renders the horizontal capsule buttons for all profiles."""
        for w in self.profile_bar.winfo_children():
            w.destroy()
        self.profile_buttons = {}

        for index, (key, p) in enumerate(profiles.items()):
            is_active = (key == active_key)
            btn = ctk.CTkButton(
                self.profile_bar,
                text=f"{p.get('icon', '🎵')} {p['title'].upper()}",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=THEME["btn_primary"] if is_active else THEME["pill_bg"],
                border_color=THEME["accent_gold"] if is_active else THEME["pill_border"],
                border_width=2 if is_active else 1,
                text_color=THEME["text_main"] if is_active else THEME["text_dim"],
                hover_color=THEME["btn_primary_hover"] if is_active else THEME["btn_secondary_hover"],
                height=34,
                width=190,
                corner_radius=10,
                command=lambda k=key: self.controller.select_profile(k)
            )
            btn.pack(side="left", padx=(0 if index == 0 else 6, 0), pady=(2, 4))
            self.profile_buttons[key] = btn

            # Tooltip for each preset
            FluentTooltip(
                btn,
                title=f"{p.get('icon', '🎵')} {p['title']}",
                text=p.get("desc", "Optimized sound profile.")
            )

        self.update_active_hero_card(active_key, profiles.get(active_key, {}))

    def update_active_hero_card(self, key, profile):
        """Update the manually selected profile, not the automatic processing state."""
        if not profile:
            return
        self.hero_icon.configure(text=profile.get("icon", "🎵"))
        self.hero_title.configure(text=profile.get("title", "CUSTOM").upper())
        self.hero_badge.configure(text="SELECTED")
        self.hero_desc.configure(text=profile.get("desc", "Optimized sound profile."))

        if key not in DEFAULT_PROFILES and hasattr(self, "btn_delete_custom"):
            self.btn_delete_custom.pack(side="right", padx=(0, 8))
        elif hasattr(self, "btn_delete_custom"):
            self.btn_delete_custom.pack_forget()

        # Soft Accent Glow Pulse on the hero card
        self.active_hero_card.configure(
            border_color="#ffffff",
            fg_color=THEME["pill_bg"]
        )
        if self._hero_pulse_timer:
            try:
                self.after_cancel(self._hero_pulse_timer)
            except Exception:
                pass

        def _settle():
            if self.active_hero_card.winfo_exists():
                self.active_hero_card.configure(
                    border_color=THEME["accent_gold"],
                    fg_color=THEME["card_bg"]
                )

        self._hero_pulse_timer = self.after(200, _settle)

    def update_auto_mode_indicator(self, enabled):
        if enabled:
            note = "Auto-Adapt is on. Assigned presets apply quietly; your manual selection stays visible."
        else:
            note = "Auto-Adapt is off. Your selected preset is used for playback."
        self.hero_auto_note.configure(text=note)

    def highlight_profile_button(self, active_key):
        """Updates active button visual styling and synchronizes hero card."""
        for k, btn in self.profile_buttons.items():
            if k == active_key:
                btn.configure(
                    fg_color=THEME["btn_primary_hover"],
                    border_color=THEME["accent_gold"],
                    border_width=2,
                    text_color="#ffffff"
                )
                self.after(220, lambda b=btn: b.configure(
                    fg_color=THEME["btn_primary"],
                    border_color=THEME["accent_gold"],
                    border_width=2,
                    text_color=THEME["text_main"]
                ) if b.winfo_exists() else None)
            else:
                btn.configure(
                    fg_color=THEME["pill_bg"],
                    border_color=THEME["pill_border"],
                    border_width=1,
                    text_color=THEME["text_dim"]
                )

        p = self.controller.profiles.get(active_key, {})
        self.update_active_hero_card(active_key, p)

    def on_delete_custom_clicked(self):
        active_key = self.controller.active_profile_key
        if active_key in DEFAULT_PROFILES:
            return
        p = self.controller.profiles.get(active_key, {})
        title = p.get("title", active_key)
        self.controller.delete_custom_preset_from_disk(active_key)
        self.controller.show_toast("Preset Deleted", f"'{title}' was removed", icon="🗑️")

    def animate_staggered_entrance(self):
        """Cascades effect cards smoothly upon view activation."""
        for idx, c in enumerate([self.c1, self.c2, self.c3, self.c4]):
            try:
                c.grid_remove()
                self.after(idx * 24, lambda card=c: card.grid() if card.winfo_exists() else None)
            except Exception:
                pass

    def cancel_slider_animation(self):
        """Immediately halts any in-progress slider interpolation."""
        if hasattr(self, "_anim_timer") and self._anim_timer:
            try:
                self.after_cancel(self._anim_timer)
            except Exception:
                pass
            self._anim_timer = None

    def animate_sliders_to_profile(self, profile, duration_ms=160, steps=6):
        """
        Smoothly interpolates audio sliders and labels to target profile values.
        Uses a lightweight cubic ease-out curve (~160ms). Zero disk I/O occurs during animation.
        """
        self.cancel_slider_animation()

        try:
            start_bass = float(self.slider_bass.get())
            start_clarity = float(self.slider_clarity.get())
            start_spatial = float(self.slider_spatial.get())
            start_vol = float(self.slider_volume.get())
        except Exception:
            self.update_sliders_from_profile(profile)
            return

        target_bass = float(profile["bass"])
        target_clarity = float(profile["clarity"])
        target_spatial = float(profile["spatial"])
        target_vol = float(profile["volume"] * 10)

        if (abs(start_bass - target_bass) < 0.5 and
            abs(start_clarity - target_clarity) < 0.5 and
            abs(start_spatial - target_spatial) < 0.5 and
            abs(start_vol - target_vol) < 0.5):
            self.update_sliders_from_profile(profile)
            return

        interval = max(15, duration_ms // steps)
        self._anim_step = 0

        def step_frame():
            self._anim_step += 1
            t = min(1.0, self._anim_step / steps)
            ease = 1.0 - (1.0 - t) ** 3

            cur_b = start_bass + (target_bass - start_bass) * ease
            cur_c = start_clarity + (target_clarity - start_clarity) * ease
            cur_s = start_spatial + (target_spatial - start_spatial) * ease
            cur_v = start_vol + (target_vol - start_vol) * ease

            if self.winfo_exists():
                self.slider_bass.set(cur_b)
                self.lbl_bass.configure(text=f"Bass EQ: {int(cur_b)}%")

                self.slider_clarity.set(cur_c)
                self.lbl_clarity.configure(text=f"Vocal Clarity: {int(cur_c)}%")

                self.slider_spatial.set(cur_s)
                self.lbl_spatial.configure(text=f"Stereo Width: {(cur_s/100.0):.2f}x")

                self.slider_volume.set(cur_v)
                self.lbl_volume.configure(text=f"Output Level Trim: +{(cur_v/10.0):.1f} dB")

            if self._anim_step < steps:
                self._anim_timer = self.after(interval, step_frame)
            else:
                self._anim_timer = None
                self.update_sliders_from_profile(profile)

        self._anim_timer = self.after(interval, step_frame)

    def update_sliders_from_profile(self, profile):
        """Instant non-animated slider snapshot update."""
        self.cancel_slider_animation()
        self.slider_bass.set(profile["bass"])
        self.lbl_bass.configure(text=f"Bass EQ: {profile['bass']}%")

        self.slider_clarity.set(profile["clarity"])
        self.lbl_clarity.configure(text=f"Vocal Clarity: {profile['clarity']}%")

        self.slider_spatial.set(profile["spatial"])
        self.lbl_spatial.configure(text=f"Stereo Width: {(profile['spatial']/100.0):.2f}x")

        self.slider_volume.set(profile["volume"] * 10)
        self.lbl_volume.configure(text=f"Output Level Trim: +{profile['volume']:.1f} dB")
