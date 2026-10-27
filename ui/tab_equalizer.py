"""
SONIQ MAX PRO — Equalizer Tab View Component.
Renders genre curve presets with Fluent tooltips, 10-band graphic sliders with haptic tactile
scaling feedback.
"""
import customtkinter as ctk
from constants import THEME, EQ_FREQS, EQ_CURVES
from ui.fluent_effects import FluentTooltip, attach_haptic_slider_feedback

CURVE_TOOLTIPS = {
    "Flat": "Neutral EQ curve. Other filters, including the speaker-mode high-pass filter, may still be active.",
    "Bass Punch": "+6dB boost on sub and mid-bass (32Hz-125Hz) for EDM, hip-hop, and club music.",
    "Vocal Clear": "+4dB speech articulation lift (1kHz-2kHz) with low-end rumble cut for podcasts and calls.",
    "Rock / V-Curve": "Classic aggressive V-curve: boosted punchy lows and sparkling crisp highs (8kHz-16kHz).",
    "Cinema": "Warm theatrical low-end with dialogue clarity elevation for immersive movie streaming.",
    "Gaming": "Footstep and positional cues exciter (2kHz-4kHz) with attenuated masking frequencies."
}

class EqualizerTab(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.eq_sliders = []
        self.eq_labels = []

        self.pack(fill="both", expand=True)
        self.build_content()

    def build_content(self):
        self.eq_card = ctk.CTkFrame(self, fg_color=THEME["card_bg"], corner_radius=12, border_width=1, border_color=THEME["card_border"])
        self.eq_card.pack(fill="both", expand=True, padx=8, pady=8)

        # Top title row with quick Flat reset
        top_row = ctk.CTkFrame(self.eq_card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(14, 4))

        eq_lbl = ctk.CTkLabel(
            top_row,
            text="🎚️ 10-Band Graphic Equalizer Studio",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=THEME["accent_gold"],
        )
        eq_lbl.pack(side="left")

        btn_reset_flat = ctk.CTkButton(
            top_row,
            text="↺ Reset to Flat (0 dB)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=THEME["pill_bg"],
            text_color=THEME["text_dim"],
            hover_color=THEME["btn_secondary_hover"],
            border_width=1,
            border_color=THEME["pill_border"],
            height=26,
            command=lambda: self.controller.apply_eq_preset("Flat")
        )
        btn_reset_flat.pack(side="right")
        FluentTooltip(btn_reset_flat, title="Reset Equalizer", text="Resets all 10 frequency band gains to 0.0 dB (neutral response).")

        self.curves_bar = ctk.CTkScrollableFrame(
            self.eq_card,
            orientation="horizontal",
            height=42,
            fg_color="transparent",
            scrollbar_button_color=THEME["pill_border"],
            scrollbar_button_hover_color=THEME["accent_bronze"],
        )
        self.curves_bar.pack(fill="x", padx=16, pady=(0, 10))

        for curve_name in EQ_CURVES.keys():
            btn = ctk.CTkButton(
                self.curves_bar,
                text=curve_name,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=THEME["btn_secondary"],
                text_color=THEME["accent_gold"],
                hover_color=THEME["btn_secondary_hover"],
                border_width=1,
                border_color=THEME["card_border"],
                height=26,
                width=112,
                command=lambda cn=curve_name: self.controller.apply_eq_preset(cn)
            )
            btn.pack(side="left", padx=3)

            # Tooltip explaining EQ curve shaping
            tip_desc = CURVE_TOOLTIPS.get(curve_name, "Custom 10-band target curve.")
            FluentTooltip(btn, title=f"EQ Preset: {curve_name}", text=tip_desc)

        # Sliders Container: 10 Vertical Bands
        self.sliders_frame = ctk.CTkFrame(self.eq_card, fg_color=THEME["bg_dark"], corner_radius=10, border_width=1, border_color=THEME["card_border"])
        self.sliders_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        for i in range(10):
            self.sliders_frame.grid_columnconfigure(i, weight=1, uniform="eq_col")
        self.sliders_frame.grid_rowconfigure(1, weight=1)

        self.eq_sliders = []
        self.eq_labels = []

        initial_eq = self.controller.get_current_eq_gains()

        for i, freq in enumerate(EQ_FREQS):
            val = initial_eq[i] if i < len(initial_eq) else 0.0

            # Value Label (row 0)
            sign = "+" if val > 0 else ""
            lbl_val = ctk.CTkLabel(self.sliders_frame, text=f"{sign}{val:.1f}", font=ctk.CTkFont(family="Consolas", size=10), text_color=THEME["accent_gold"])
            lbl_val.grid(row=0, column=i, pady=(8, 2))
            self.eq_labels.append(lbl_val)

            # Vertical Slider (row 1)
            slider = ctk.CTkSlider(
                self.sliders_frame,
                orientation="vertical",
                from_=-12.0,
                to=12.0,
                number_of_steps=48,
                progress_color=THEME["accent_bronze"],
                button_color=THEME["accent_gold"],
                button_hover_color=THEME["text_main"],
                command=lambda v, idx=i: self.controller.on_eq_slider_changed(idx, v)
            )
            slider.set(val)
            slider.grid(row=1, column=i, pady=2, sticky="ns")
            self.eq_sliders.append(slider)

            # Haptic Tactile Handle Scaling & Spring Bounce Feedback
            attach_haptic_slider_feedback(slider, expand_len=16)

            # Frequency Label (row 2)
            lbl_freq = ctk.CTkLabel(self.sliders_frame, text=freq, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=THEME["text_dim"])
            lbl_freq.grid(row=2, column=i, pady=(2, 8))

    def update_eq_sliders(self, eq_gains):
        """Updates the position and labels of all 10 sliders."""
        for i, val in enumerate(eq_gains):
            if i < len(self.eq_sliders):
                self.eq_sliders[i].set(val)
                sign = "+" if val > 0 else ""
                self.eq_labels[i].configure(text=f"{sign}{val:.1f}")

    def animate_staggered_entrance(self):
        """Sequential waterfall entrance for EQ studio."""
        try:
            self.sliders_frame.pack_forget()
            self.after(30, lambda: self.sliders_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14)) if self.sliders_frame.winfo_exists() else None)
        except Exception:
            pass
