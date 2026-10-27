"""
SONIQ MAX PRO — UI Dialogs & External Tool Launchers.
Includes Equalizer APO driver setup walkthrough, Sound Control Panel launcher,
and custom preset saving dialog.
"""
import subprocess
import webbrowser
import customtkinter as ctk
from constants import THEME

def open_sound_control_panel():
    """Opens standard Windows Sound Control Panel (mmsys.cpl)."""
    subprocess.Popen(["control", "mmsys.cpl"])

def open_system_driver_setup_dialog(parent):
    """Displays the modal guide for setting up Equalizer APO system driver."""
    setup_win = ctk.CTkToplevel(parent)
    setup_win.title("System-Wide Audio Setup (VLC, YouTube & Games)")
    setup_win.geometry("640x520")
    setup_win.configure(fg_color=THEME["bg_dark"])
    setup_win.grab_set()

    lbl = ctk.CTkLabel(
        setup_win, 
        text="How to Apply SONIQ MAX System-Wide to VLC & Chrome", 
        font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        text_color=THEME["accent_gold"]
    )
    lbl.pack(padx=20, pady=(18, 6), anchor="w")

    intro = ctk.CTkLabel(
        setup_win,
        text="Windows requires a system-level audio bridge (Equalizer APO) to let third-party apps\n(like VLC, YouTube, Chrome, Netflix, and Games) be enhanced by SONIQ MAX.",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color=THEME["text_dim"],
        justify="left"
    )
    intro.pack(padx=20, pady=(0, 14), anchor="w")

    # Method 1 Card
    m1 = ctk.CTkFrame(setup_win, fg_color=THEME["card_bg"], corner_radius=8, border_width=1, border_color=THEME["card_border"])
    m1.pack(fill="x", padx=20, pady=6)

    m1_title = ctk.CTkLabel(m1, text="Method 1: Install Equalizer APO (Permanent System-Wide Audio)", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=THEME["accent_green"])
    m1_title.pack(padx=14, pady=(10, 2), anchor="w")

    m1_steps = ctk.CTkLabel(
        m1,
        text="1. Download and install Equalizer APO.\n2. In the configurator, select your playback device and restart if requested.\n3. SONIQ MAX adds its own filter file to the APO config; existing config lines are preserved.",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color=THEME["text_main"],
        justify="left"
    )
    m1_steps.pack(padx=14, pady=(0, 10), anchor="w")

    btn_dl = ctk.CTkButton(
        m1,
        text="⬇️ Open Equalizer APO Download Page",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        fg_color=THEME["btn_primary"],
        text_color=THEME["bg_dark"],
        hover_color=THEME["btn_primary_hover"],
        height=30,
    )
    btn_dl.pack(padx=14, pady=(0, 12), anchor="w")
    download_status = ctk.CTkLabel(
        m1,
        text="",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        text_color=THEME["clip_red"],
        wraplength=560,
    )
    download_status.pack(padx=14, pady=(0, 8), anchor="w")
    btn_dl.configure(command=lambda: open_apo_download_page(download_status))

    # Method 2 Card
    m2 = ctk.CTkFrame(setup_win, fg_color=THEME["card_bg"], corner_radius=8, border_width=1, border_color=THEME["card_border"])
    m2.pack(fill="x", padx=20, pady=6)

    m2_title = ctk.CTkLabel(m2, text="Method 2: Instant Windows Built-in Loudness (Zero Install)", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=THEME["accent_gold"])
    m2_title.pack(padx=14, pady=(10, 2), anchor="w")

    m2_steps = ctk.CTkLabel(
        m2,
        text="1. Open Windows Sound Control Panel.\n2. Open your playback device properties and inspect its available enhancements.\n3. Enhancement options vary by driver and Windows version; they may change loud/quiet balance but do not guarantee a volume increase.",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color=THEME["text_main"],
        justify="left"
    )
    m2_steps.pack(padx=14, pady=(0, 10), anchor="w")

    btn_mmsys = ctk.CTkButton(
        m2,
        text="🔊 Open Windows Sound Control Panel",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        fg_color=THEME["btn_secondary"],
        text_color=THEME["accent_gold"],
        hover_color=THEME["btn_secondary_hover"],
        border_width=1,
        border_color=THEME["card_border"],
        height=30,
        command=open_sound_control_panel
    )
    btn_mmsys.pack(padx=14, pady=(0, 12), anchor="w")

def prompt_save_custom_preset_dialog(parent, current_state, on_saved):
    """
    Opens input dialog to prompt user for a custom preset name,
    constructs the profile object, and calls on_saved(key, profile_dict).
    """
    dialog = ctk.CTkInputDialog(text="Enter a name for your custom sound profile:", title="Save Custom Preset")
    dialog.transient(parent)
    name = dialog.get_input()
    if not name or not name.strip():
        return

    clean_name = name.strip()
    key = "custom_" + clean_name.lower().replace(" ", "_")

    new_profile = {
        "title": clean_name,
        "icon": "⭐",
        "badge": "CUSTOM",
        "desc": "Custom user preset saved with tailored EQ and acoustic parameters.",
        "bass": int(current_state["bass"]),
        "clarity": int(current_state["clarity"]),
        "spatial": int(current_state["spatial"]),
        "volume": round(current_state["volume"], 1),
        "eq": current_state.get("eq", [0.0] * 10)
    }

    on_saved(key, new_profile)


def open_apo_download_page(status_label):
    """Open the Equalizer APO download page and show a useful fallback on failure."""
    try:
        opened = webbrowser.open("https://sourceforge.net/projects/equalizerapo/")
    except OSError as error:
        status_label.configure(text=f"Could not open browser: {error}")
        return
    if not opened:
        status_label.configure(text="Browser did not open; see README for the download link.")
