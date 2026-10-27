"""
SONIQ MAX PRO — Fluent Design UI/UX Effects Module.
Provides native Windows 11 Fluent micro-animations and components:
1. ToastNotificationBanner: Sleek floating slide-down toast auto-dismissing after 2s.
2. FluentTooltip: Dark-themed popover with delay on advanced DSP toggles.
3. CollapsibleSection: Accordion-style dropdown for dense/advanced settings.
4. attach_haptic_slider_feedback: Tactile thumb scaling and bounce on slider drag.
5. stagger_cascade_entrance: Fluid waterfall card reveals when switching tabs.
"""
import tkinter as tk
import customtkinter as ctk
from constants import THEME

# =============================================================================
# 1. Floating Fluent Toast Notification Banner
# =============================================================================
class ToastNotificationBanner(ctk.CTkFrame):
    """
    Floating Fluent Design toast banner placed at the top center of the application window.
    Slides down smoothly from y=-60 to y=16, holds for duration_ms, and glides back up.
    """
    def __init__(self, parent_window):
        super().__init__(
            parent_window,
            fg_color="#1e1e1e",
            corner_radius=10,
            border_width=1,
            border_color=THEME["accent_gold"],
            width=360,
            height=46
        )
        self.parent_window = parent_window
        self._slide_timer = None
        self._dismiss_timer = None
        self._is_active = False

        # Internal Layout
        self.grid_columnconfigure(1, weight=1)

        self.lbl_icon = ctk.CTkLabel(
            self,
            text="✓",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=THEME["accent_gold"],
            width=30
        )
        self.lbl_icon.grid(row=0, column=0, rowspan=2, padx=(12, 6), pady=6)

        self.lbl_title = ctk.CTkLabel(
            self,
            text="Notification Title",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME["text_main"],
            anchor="w"
        )
        self.lbl_title.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=(6, 0))

        self.lbl_message = ctk.CTkLabel(
            self,
            text="Detailed notification status description.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=THEME["text_dim"],
            anchor="w"
        )
        self.lbl_message.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(0, 6))

        # Optional dismiss close glyph
        self.btn_close = ctk.CTkLabel(
            self,
            text="✕",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=THEME["text_subtle"],
            cursor="hand2",
            width=24
        )
        self.btn_close.grid(row=0, column=2, rowspan=2, padx=(0, 10))
        self.btn_close.bind("<Button-1>", lambda e: self.hide_toast())

        # Initially positioned offscreen above window
        self.place(relx=0.5, y=-70, anchor="n")

    def show(self, title, message="", icon="✓", duration_ms=2200):
        """Displays toast with slide-down animation and auto-dismissal."""
        self._cancel_timers()
        self.lbl_title.configure(text=str(title)[:45])
        self.lbl_message.configure(text=str(message)[:65])
        self.lbl_icon.configure(text=str(icon))
        
        # Color accent based on icon or intent
        if icon in ("⚠️", "❌"):
            self.configure(border_color=THEME["clip_red"])
            self.lbl_icon.configure(text_color=THEME["clip_red"])
        elif icon in ("🎮", "💥"):
            self.configure(border_color=THEME["accent_bronze"])
            self.lbl_icon.configure(text_color=THEME["accent_gold"])
        else:
            self.configure(border_color=THEME["accent_gold"])
            self.lbl_icon.configure(text_color=THEME["accent_gold"])

        self.lift()
        self._is_active = True

        # Slide down sequence: y = -60 -> 16 in 6 ease-out steps
        steps = [(-50), (-25), (0), (12), (18), (16)]
        self._animate_slide(steps, 0, on_done=lambda: self._schedule_dismiss(duration_ms))

    def _animate_slide(self, y_steps, index, on_done=None):
        if not self._is_active or index >= len(y_steps):
            if on_done:
                on_done()
            return
        self.place(relx=0.5, y=y_steps[index], anchor="n")
        self._slide_timer = self.after(16, lambda: self._animate_slide(y_steps, index + 1, on_done))

    def _schedule_dismiss(self, duration_ms):
        self._dismiss_timer = self.after(duration_ms, self.hide_toast)

    def hide_toast(self):
        """Slides toast back offscreen and resets."""
        self._cancel_timers()
        if not self._is_active:
            return
        # Slide up sequence
        steps = [14, 4, -18, -45, -75]
        def _finish():
            self._is_active = False
            self.place(relx=0.5, y=-75, anchor="n")
        self._animate_slide(steps, 0, on_done=_finish)

    def _cancel_timers(self):
        if self._slide_timer:
            try:
                self.after_cancel(self._slide_timer)
            except Exception:
                pass
            self._slide_timer = None
        if self._dismiss_timer:
            try:
                self.after_cancel(self._dismiss_timer)
            except Exception:
                pass
            self._dismiss_timer = None


# =============================================================================
# 2. Sleek Custom Dark Tooltip Popovers
# =============================================================================
class FluentTooltip:
    """
    Lightweight, dark-themed hover popover with a slight delay (~350ms).
    Provides technical insight for advanced DSP controls without cluttering the UI.
    """
    def __init__(self, widget, text, title=None, delay_ms=360):
        self.widget = widget
        self.text = text
        self.title = title
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip_window = None

        # Bind enter/leave events to widget and internal canvas/label if present
        targets = [self.widget]
        if hasattr(self.widget, "_canvas") and self.widget._canvas:
            targets.append(self.widget._canvas)
        if hasattr(self.widget, "_text_label") and self.widget._text_label:
            targets.append(self.widget._text_label)

        for target in targets:
            target.bind("<Enter>", self._on_enter, add="+")
            target.bind("<Leave>", self._on_leave, add="+")
            target.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        self._cancel_schedule()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, event=None):
        self._cancel_schedule()
        self._destroy_tip()

    def _cancel_schedule(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        self._destroy_tip()
        if not self.widget.winfo_exists():
            return

        try:
            # Calculate position on screen directly beneath the widget
            x = self.widget.winfo_rootx() + 4
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

            scr_w = self.widget.winfo_screenwidth()
            scr_h = self.widget.winfo_screenheight()

            # Create top-level borderless window
            self._tip_window = tk.Toplevel(self.widget)
            tw = self._tip_window
            tw.withdraw()
            tw.overrideredirect(True)
            tw.attributes("-topmost", True)
            tw.configure(bg="#3a3a3a")  # 1px Fluent border

            # Inner surface container
            inner = tk.Frame(tw, bg="#202020", padx=10, pady=7)
            inner.pack(padx=1, pady=1)

            if self.title:
                t_lbl = tk.Label(
                    inner,
                    text=self.title,
                    font=("Segoe UI", 9, "bold"),
                    fg=THEME["accent_gold"],
                    bg="#202020",
                    justify="left"
                )
                t_lbl.pack(anchor="w", pady=(0, 2))

            b_lbl = tk.Label(
                inner,
                text=self.text,
                font=("Segoe UI", 9),
                fg="#dcdcdc",
                bg="#202020",
                justify="left",
                wraplength=270
            )
            b_lbl.pack(anchor="w")

            tw.update_idletasks()
            tip_w = tw.winfo_width()
            tip_h = tw.winfo_height()

            # Clamp coordinates so tooltip never goes offscreen
            if x + tip_w > scr_w - 12:
                x = scr_w - tip_w - 12
            if y + tip_h > scr_h - 12:
                y = self.widget.winfo_rooty() - tip_h - 6  # Flip above widget

            tw.geometry(f"+{max(10, x)}+{max(10, y)}")
            tw.deiconify()
        except Exception:
            self._destroy_tip()

    def _destroy_tip(self):
        if self._tip_window:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None


# =============================================================================
# 3. Collapsible Advanced Sections (Accordion)
# =============================================================================
class CollapsibleSection(ctk.CTkFrame):
    """
    Sleek accordion dropdown with rotating arrow (▶ / ▼) and badge.
    Allows compact presentation of dense or power-user configuration panels.
    """
    def __init__(self, parent, title, subtitle="", is_expanded=False, badge="", **kwargs):
        super().__init__(
            parent,
            fg_color=THEME["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["card_border"],
            **kwargs
        )
        self.is_expanded = is_expanded
        self.title_text = title
        self.subtitle_text = subtitle
        self.badge_text = badge

        # Clickable Header Row
        self.header = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        self.header.pack(fill="x", padx=16, pady=11)

        self.lbl_arrow = ctk.CTkLabel(
            self.header,
            text="▼" if is_expanded else "▶",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=THEME["accent_gold"],
            width=18
        )
        self.lbl_arrow.pack(side="left", padx=(0, 6))

        self.lbl_title = ctk.CTkLabel(
            self.header,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=THEME["accent_gold"] if is_expanded else THEME["text_main"]
        )
        self.lbl_title.pack(side="left")

        if subtitle:
            self.lbl_sub = ctk.CTkLabel(
                self.header,
                text=f"•  {subtitle}",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=THEME["text_dim"]
            )
            self.lbl_sub.pack(side="left", padx=(8, 0))

        if badge:
            self.lbl_badge = ctk.CTkLabel(
                self.header,
                text=badge,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=THEME["pill_bg"],
                text_color=THEME["accent_green"],
                corner_radius=6,
                padx=8,
                pady=2
            )
            self.lbl_badge.pack(side="right")

        # Inner Content Container
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        if is_expanded:
            self.content_frame.pack(fill="x", padx=16, pady=(0, 14))

        # Bind clicks across header widgets
        for w in (self.header, self.lbl_arrow, self.lbl_title):
            w.bind("<Button-1>", lambda e: self.toggle())

    def toggle(self):
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        self.is_expanded = True
        self.lbl_arrow.configure(text="▼")
        self.lbl_title.configure(text_color=THEME["accent_gold"])
        self.configure(border_color=THEME["card_border"])
        self.content_frame.pack(fill="x", padx=16, pady=(0, 14))

    def collapse(self):
        self.is_expanded = False
        self.lbl_arrow.configure(text="▶")
        self.lbl_title.configure(text_color=THEME["text_main"])
        self.content_frame.pack_forget()


# =============================================================================
# 4. Haptic-Style Slider Tactile Feedback
# =============================================================================
def attach_haptic_slider_feedback(slider, expand_len=18):
    """
    Adds visual spring & thumb handle scaling to CTkSlider during drag.
    When the user grabs the slider handle, it expands horizontally/vertically
    with an illuminated highlight, then bounces back smoothly upon release.
    """
    if not hasattr(slider, "_canvas") or not slider._canvas:
        return

    def on_press(e):
        try:
            slider.configure(
                button_length=expand_len,
                button_color=THEME["text_main"]
            )
        except Exception:
            pass

    def on_release(e):
        try:
            # Micro-bounce return sequence: expand -> small bounce -> normal
            slider.configure(
                button_length=expand_len // 2,
                button_color=THEME["accent_gold"]
            )
            slider.after(35, lambda: slider.configure(button_length=0) if slider.winfo_exists() else None)
        except Exception:
            pass

    slider._canvas.bind("<Button-1>", on_press, add="+")
    slider._canvas.bind("<ButtonRelease-1>", on_release, add="+")


# =============================================================================
# 5. Staggered Cascade Entrance Animation
# =============================================================================
def stagger_cascade_entrance(parent_widget, cards, step_delay_ms=22, on_complete=None):
    """
    Populates tab or view cards sequentially with a microscopic staggered delay (~22ms).
    Creates a fluid waterfall entrance instead of jarring instant pops.
    """
    if not cards:
        if on_complete:
            on_complete()
        return

    for idx, card in enumerate(cards):
        if hasattr(card, "winfo_exists") and card.winfo_exists():
            # If using pack, temporarily unpack and cascade pack
            try:
                card.pack_forget()
            except Exception:
                pass

    def reveal(step):
        if step >= len(cards):
            if on_complete:
                on_complete()
            return
        c = cards[step]
        if hasattr(c, "winfo_exists") and c.winfo_exists():
            c.pack(fill="x", pady=6)
        parent_widget.after(step_delay_ms, lambda: reveal(step + 1))

    parent_widget.after(10, lambda: reveal(0))
