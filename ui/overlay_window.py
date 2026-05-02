"""
Overlay Window Module
=====================
Floating, borderless, always-on-top timer display.
Integrates with Controller via callbacks - no direct TimerCore access.
"""

import tkinter as tk
from typing import TYPE_CHECKING
import json
from pathlib import Path
from ui.preset_editor import PresetEditor
from datetime import datetime
from core.paths import resolve
import ctypes
from ctypes import wintypes
import threading

# --- Win32 API Constants & Setup ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

# MOD modifiers for RegisterHotKey
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOTKEY_ID = 101  # Unique ID for our lock hotkey
PRESET_HOTKEY_BASE_ID = 1000  # Base ID for preset hotkeys
MUSHROOM_HOTKEY_ID = 2000
COW_5M_HOTKEY_ID = 2001
COW_V_HOTKEY_ID = 2002

if TYPE_CHECKING:
    from controller.controller import Controller


class OverlayWindow:
    """
    A floating borderless window that displays the timer.
    
    Features:
    - Always on top of other windows
    - Draggable with mouse
    - Updates display via Controller callbacks
    - Compact, minimal design
    """
    
    # Update interval in milliseconds
    TICK_INTERVAL_MS = 100
    
    # Styling constants
    BG_COLOR = "#1a1a2e"
    TEXT_COLOR = "#00ff88"
    TEXT_COLOR_PAUSED = "#ffaa00"
    TEXT_COLOR_IDLE = "#888888"
    TEXT_COLOR_WARNING = "#ffaa00"   # orange
    TEXT_COLOR_DANGER  = "#ff3333"   # red
    TEXT_COLOR_ALARM = "#ff4444"   
    TEXT_COLOR_LOCKED = "#00ffff"  # Bright cyan for better visibility when locked
    FONT_FAMILY = "Consolas"
    FONT_SIZE = 48
    PADDING = 20
    
    def __init__(self, controller: "Controller"):
        """
        Initialize the overlay window.
        
        Args:
            controller: The Controller instance to coordinate with.
        """
        self._controller = controller
        
        # Default initialization for widgets defined in _create_widgets
        self._root = None
        self._time_label = None 
        self._status_label = None
        self._alarm_label = None
        self._is_locked = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        self._is_flashing = {"main": False, "mushroom": False, "cow": False}
        
        # Build the window
        self._create_window()
        self._create_widgets()
        self._bind_events()
        self._register_callbacks()
        self._create_context_menu()

        # Start Global Hotkey Listener (Ctrl + Shift + L)
        self._start_hotkey_listener()
    
    def _create_context_menu(self):
        self._menu = tk.Menu(self._root, tearoff=0)

        self._menu.add_command(label="⏯ Pause / Resume", command=self._toggle_pause)
        self._menu.add_command(label="🔄 Reset Timer", command=self._reset_timer)
        self._menu.add_command(label="🔒 Lock/Unlock (Ctrl+Shift+L)", command=self._toggle_lock)
        self._menu.add_separator()
        self._menu.add_command(label="⏱ Set Countdown", command=self._set_countdown_dialog)
        self._menu.add_command(label="⏰ Set Alarm", command=self._set_alarm_dialog)
        self._menu.add_separator()
        self._menu.add_command(label="❌ Exit", command=self.close)

        countdown_menu = tk.Menu(self._menu, tearoff=0)
        for i, p in enumerate(self._controller.countdown_presets):
            # Show hotkey hint for first 9 presets
            hint = f" (CS{i+1})" if i < 9 else ""
            countdown_menu.add_command(
                label=f"{p['name']}{hint}",
                command=lambda p=p: self._controller.apply_countdown_preset(p)
            )

        self._alarm_vars = {}

        alarm_menu = tk.Menu(self._menu, tearoff=0)
        
        for p in self._controller.alarm_presets:
            var = tk.BooleanVar(value=(p["name"] in self._controller.selected_alarm_presets))
            self._alarm_vars[p["name"]] = var

            alarm_menu.add_checkbutton(
                label=p["name"],
                variable=var,
                command=lambda name=p["name"]: self._toggle_alarm_preset(name)
            )
            
        alarm_menu.add_separator()
        alarm_menu.add_command(label="Use All", command=self._use_all_alarms)
        alarm_menu.add_command(label="Clear All", command=self._clear_all_alarms)
        
        self._menu.add_cascade(label="⏳ Countdown Presets", menu=countdown_menu)
        self._menu.add_cascade(label="⏰ Alarm Presets", menu=alarm_menu)

        preset_manager = tk.Menu(self._menu, tearoff=0)
        preset_manager.add_command(label="⏳ Edit Countdown Presets", command=self._open_countdown_editor)
        preset_manager.add_command(label="⏰ Edit Alarm Presets", command=self._open_alarm_editor)

        self._menu.add_cascade(label="📋 Preset Manager", menu=preset_manager)

    # =========================================================================
    # Window Setup
    # =========================================================================
    
    def _create_window(self) -> None:
        """Create and configure the main window."""
        self._root = tk.Tk()
        self._root.title("Timer")
        
        # Borderless window
        self._root.overrideredirect(True)
        
        # Always on top
        self._root.attributes("-topmost", True)
        
        # Semi-transparent (optional, can be adjusted)
        self._root.attributes("-alpha", 0.95)
        
        # Background color
        self._root.configure(bg=self.BG_COLOR)
        
        # Initial position (top-right corner of screen)
        x, y = self._load_window_position()

        if x is not None and y is not None:
            self._root.geometry(f"+{x}+{y}")
        else:
            screen_width = self._root.winfo_screenwidth()
            window_width = 200
            x = (screen_width // 2) - (window_width // 2)
            y = 30
            self._root.geometry(f"+{x}+{y}")
   
    def _create_widgets(self) -> None:
        """Create the timer display labels."""
        # Main frame with padding
        self._frame = tk.Frame(
            self._root,
            bg=self.BG_COLOR,
            padx=self.PADDING,
            pady=self.PADDING // 2
        )
        self._frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Main Timer ---
        self._main_time_label = tk.Label(
            self._frame, text="00:00",
            font=(self.FONT_FAMILY, self.FONT_SIZE, "bold"),
            fg=self.TEXT_COLOR_IDLE, bg=self.BG_COLOR
        )
        self._main_time_label.pack()
        
        self._main_status_label = tk.Label(
            self._frame, text="IDLE",
            font=(self.FONT_FAMILY, 12),
            fg=self.TEXT_COLOR_IDLE, bg=self.BG_COLOR
        )
        self._main_status_label.pack()
        
        # --- Sub Timers Frame ---
        self._sub_frame = tk.Frame(self._frame, bg=self.BG_COLOR)
        self._sub_frame.pack(fill="x", pady=(5, 5))
        self._sub_frame.columnconfigure(0, weight=1)
        self._sub_frame.columnconfigure(1, weight=1)
        
        # Mushroom (Left)
        self._mushroom_time_label = tk.Label(
            self._sub_frame, text="🍄 00:00", font=(self.FONT_FAMILY, 14, "bold"),
            fg=self.TEXT_COLOR_IDLE, bg=self.BG_COLOR
        )
        self._mushroom_time_label.grid(row=0, column=0, sticky="n")
        self._mushroom_status_label = tk.Label(
            self._sub_frame, text="Mushroom", font=(self.FONT_FAMILY, 9),
            fg=self.TEXT_COLOR_IDLE, bg=self.BG_COLOR
        )
        self._mushroom_status_label.grid(row=1, column=0, sticky="n")

        # Cow (Right)
        self._cow_time_label = tk.Label(
            self._sub_frame, text="🐮 00:00", font=(self.FONT_FAMILY, 14, "bold"),
            fg=self.TEXT_COLOR_IDLE, bg=self.BG_COLOR
        )
        self._cow_time_label.grid(row=0, column=1, sticky="n")
        self._cow_status_label = tk.Label(
            self._sub_frame, text="Cow", font=(self.FONT_FAMILY, 9),
            fg=self.TEXT_COLOR_IDLE, bg=self.BG_COLOR
        )
        self._cow_status_label.grid(row=1, column=1, sticky="n")

        # --- Alarm status label ---
        self._alarm_label = tk.Label(
            self._frame, text="",
            font=(self.FONT_FAMILY, 12),
            fg=self.TEXT_COLOR_WARNING, bg=self.BG_COLOR
        )
        self._alarm_label.pack(pady=(2, 0), fill="x")
    
    def _bind_events(self) -> None:
        """Bind mouse events for dragging."""
        widgets = (
            self._root, self._frame, self._sub_frame,
            self._main_time_label, self._main_status_label,
            self._mushroom_time_label, self._mushroom_status_label,
            self._cow_time_label, self._cow_status_label, self._alarm_label
        )
        for widget in widgets:
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)
        
        # Right-click to close (escape hatch)
        self._root.bind("<Button-3>", self._show_menu)

    def _show_menu(self, event):
        self._menu.tk_popup(event.x_root, event.y_root)

    def _register_callbacks(self) -> None:
        """Register callbacks with the controller."""
        self._controller.set_on_tick(self._update_display)
        self._controller.set_on_complete(self._on_timer_complete)
    
    # =========================================================================
    # Window Positioning
    # =========================================================================
    
    def _load_window_position(self):
        path = resolve("settings/window.json")
        if not path.exists():
            return None, None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("x"), data.get("y")
        
    def _save_window_position(self, x, y):
        path = resolve("settings/window.json")
        path.parent.mkdir(exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump({"x": x, "y": y}, f)

    # =========================================================================
    # Drag Handling
    # =========================================================================
    
    def _start_drag(self, event: tk.Event) -> None:
        """Record mouse position when drag starts."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def _do_drag(self, event: tk.Event) -> None:
        """Move window to follow mouse during drag."""
        # Calculate new position
        new_x = self._root.winfo_x() + (event.x - self._drag_start_x)
        new_y = self._root.winfo_y() + (event.y - self._drag_start_y)
        
        # Move window
        self._root.geometry(f"+{new_x}+{new_y}")

        # Save position
        self._save_window_position(new_x, new_y)
    
    # =========================================================================
    # Display Updates
    # =========================================================================
    
    def _update_display(self):
        # Update Main Timer
        if not self._is_flashing["main"]:
            self._update_timer_block(
                "main", self._main_time_label, self._main_status_label, "", "IDLE"
            )
            
        # Update Mushroom Timer
        if not self._is_flashing["mushroom"]:
            self._update_timer_block(
                "mushroom", self._mushroom_time_label, self._mushroom_status_label, "🍄 ", "Mushroom"
            )
            
        # Update Cow Timer
        if not self._is_flashing["cow"]:
            self._update_timer_block(
                "cow", self._cow_time_label, self._cow_status_label, "🐮 ", "Cow"
            )

        # ---- Alarm section ----
        alarm_status, alarms = self._controller.get_alarm_status()

        if not alarms:
            self._alarm_label.config(text="")
        else:
            alarm_time = alarms[0][0].strftime("%H:%M")
            names = ", ".join(name for _, name, _ in alarms)
            text = f"{alarm_time} - {names}"

            if alarm_status == "active":
                self._alarm_label.config(text=f"🟢 {text}", fg="#00ff7f")
            elif alarm_status == "danger":
                self._alarm_label.config(text=f"🔴 {text}", fg=self.TEXT_COLOR_DANGER)
            elif alarm_status == "warning":
                self._alarm_label.config(text=f"🟠 {text}", fg=self.TEXT_COLOR_WARNING)
            else:
                color = self.TEXT_COLOR_LOCKED if self._is_locked else self.TEXT_COLOR_IDLE
                self._alarm_label.config(text=f"⏰ {text}", fg=color)

    def _update_timer_block(self, timer_id, time_lbl, stat_lbl, prefix, idle_text):
        display_time = self._controller.get_display_time(timer_id)
        time_lbl.config(text=f"{prefix}{display_time}")

        urgency = self._controller.get_urgency_level(timer_id)
        if urgency == "danger":
            color = self.TEXT_COLOR_DANGER
            status = "URGENT"
        elif urgency == "warning":
            color = self.TEXT_COLOR_WARNING
            status = "SOON"
        else:
            color = self.TEXT_COLOR
            if self._controller.get_state(timer_id) == "PAUSED":
                color = self.TEXT_COLOR_PAUSED
                status = "PAUSED"
            else:
                status = "RUNNING"

        if self._controller.is_idle(timer_id):
            color = self.TEXT_COLOR_IDLE
            status = idle_text

        time_lbl.config(fg=color)
        if not self._is_locked:
            stat_lbl.config(text=status, fg=color)
        else:
            stat_lbl.config(text="LOCKED", fg="#ff3333")
                
    def _on_timer_complete(self, timer_id: str) -> None:
        """Handle timer completion - flash the display."""
        self._is_flashing[timer_id] = True
        
        lbl = self._get_time_label(timer_id)
        stat = self._get_stat_label(timer_id)
        
        lbl.config(fg="#ff0000")
        stat.config(text="COMPLETE!", fg="#ff0000")
        
        # Start flash loop for this timer
        self._flash_display(timer_id, 0)
        
    def _get_time_label(self, timer_id: str):
        if timer_id == "mushroom": return self._mushroom_time_label
        elif timer_id == "cow": return self._cow_time_label
        return self._main_time_label
        
    def _get_stat_label(self, timer_id: str):
        if timer_id == "mushroom": return self._mushroom_status_label
        elif timer_id == "cow": return self._cow_status_label
        return self._main_status_label
    
    def _flash_display(self, timer_id: str, count: int) -> None:
        """Create a flashing effect when timer completes."""
        lbl = self._get_time_label(timer_id)
        stat = self._get_stat_label(timer_id)
        
        if count >= 10:  # Flash 5 times (on/off)
            self._is_flashing[timer_id] = False
            lbl.config(fg=self.TEXT_COLOR_IDLE)
            stat.config(fg=self.TEXT_COLOR_IDLE)
            return
        
        # Toggle visibility
        current_color = lbl.cget("fg")
        new_color = self.BG_COLOR if current_color != self.BG_COLOR else "#ff0000"
        lbl.config(fg=new_color)
        
        self._root.after(200, lambda: self._flash_display(timer_id, count + 1))
    
    def _toggle_pause(self):
        if self._controller.is_running:
            self._controller.pause_timer()
        else:
            self._controller.resume_timer()

    def _toggle_lock(self):
        """Toggle the window lock (click-through) state."""
        self._is_locked = not self._is_locked
        
        if self._is_locked:
            # 1. Visual change
            self._root.attributes("-alpha", 0.7)
            self._status_label = self._main_status_label  # Legacy map for _toggle_lock
            self._main_status_label.config(text="LOCKED", fg="#ff3333")
            self._mushroom_status_label.config(text="LOCKED", fg="#ff3333")
            self._cow_status_label.config(text="LOCKED", fg="#ff3333")
            
            # 2. Use Tkinter's native transparent color (makes background click-through)
            self._root.attributes("-transparentcolor", self.BG_COLOR)
            
            # 3. Unbind mouse events so Tkinter doesn't intercept clicks
            self._root.unbind("<Button-1>")
            self._root.unbind("<Button-3>")
            self._frame.unbind("<Button-1>")
            self._sub_frame.unbind("<Button-1>")
            
            widgets = (
                self._main_time_label, self._main_status_label,
                self._mushroom_time_label, self._mushroom_status_label,
                self._cow_time_label, self._cow_status_label, self._alarm_label
            )
            for widget in widgets:
                widget.unbind("<Button-1>")
        else:
            # 1. Restore visual
            self._root.attributes("-alpha", 0.95)
            self._root.attributes("-transparentcolor", "")
            
            # 2. Re-bind all mouse events
            self._bind_events()
            self._update_display()

        # 3. Apply Win32 style AFTER a short delay. 
        # This prevents Tkinter from overwriting the style immediately.
        # We also specifically use GetAncestor to reach the true top-level HWND.
        self._root.after(200, lambda: self._apply_lock_styles())

    def _apply_lock_styles(self):
        """Apply the click-through styles using Win32 API directly on the root window."""
        try:
            # GA_ROOT = 2 (Gets the actual window handle regardless of internal frames)
            hwnd = user32.GetAncestor(self._root.winfo_id(), 2)
            if not hwnd:
                hwnd = self._root.winfo_id()

            # Get current extended style
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            
            if self._is_locked:
                # Add TRANSPARENT and LAYERED flags
                # WS_EX_TRANSPARENT (0x20) | WS_EX_LAYERED (0x80000)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            else:
                # Remove TRANSPARENT but keep LAYERED (Tkinter usually needs LAYERED for alpha)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TRANSPARENT)
            
            # SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER (0x27)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
        except Exception as e:
            print(f"Error applying Win32 styles: {e}")

    def _set_click_through(self, enabled: bool):
        # This method is now replaced by _apply_lock_styles for better reliability
        pass

    # --- Global Hotkey Listener ---

    def _start_hotkey_listener(self):
        """Run the hotkey listener in a background thread."""
        thread = threading.Thread(target=self._hotkey_loop, daemon=True)
        thread.start()

    def _hotkey_loop(self):
        """Win32 Hotkey message loop."""
        VK_L = 0x4C
        VK_M = 0x4D
        VK_C = 0x43
        VK_V = 0x56
        
        # 1. Register Lock hotkey
        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_L):
            print("Failed to register lock hotkey.")

        # 2. Register special timer hotkeys
        user32.RegisterHotKey(None, MUSHROOM_HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_M)
        user32.RegisterHotKey(None, COW_5M_HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_C)
        user32.RegisterHotKey(None, COW_V_HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_V)

        # 3. Register Preset hotkeys (Ctrl+Shift+1...9)
        for i in range(min(9, len(self._controller.countdown_presets))):
            vk_key = 0x31 + i  # 0x31 is '1'
            user32.RegisterHotKey(None, PRESET_HOTKEY_BASE_ID + i, MOD_CONTROL | MOD_SHIFT, vk_key)

        try:
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == 0x0312: # WM_HOTKEY
                    hid = msg.wParam
                    if hid == HOTKEY_ID:
                        self._root.after(0, self._toggle_lock)
                    elif hid == MUSHROOM_HOTKEY_ID:
                        self._root.after(0, lambda: self._controller.start_timer("mushroom", 3600.0, "feed_mushroom.wav"))
                    elif hid == COW_5M_HOTKEY_ID:
                        self._root.after(0, lambda: self._controller.start_timer("cow", 300.0, "cow_normal.wav"))
                    elif hid == COW_V_HOTKEY_ID:
                        self._root.after(0, lambda: self._controller.start_timer("cow", 1500.0, "cow_vip.wav"))
                    elif PRESET_HOTKEY_BASE_ID <= hid < PRESET_HOTKEY_BASE_ID + 9:
                        idx = hid - PRESET_HOTKEY_BASE_ID
                        # Apply preset on main thread
                        self._root.after(0, lambda idx=idx: self._apply_preset_by_index(idx))
                        
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            user32.UnregisterHotKey(None, MUSHROOM_HOTKEY_ID)
            user32.UnregisterHotKey(None, COW_5M_HOTKEY_ID)
            user32.UnregisterHotKey(None, COW_V_HOTKEY_ID)
            for i in range(9):
                user32.UnregisterHotKey(None, PRESET_HOTKEY_BASE_ID + i)

    def _apply_preset_by_index(self, index: int):
        """Apply a countdown preset by its index in the list."""
        presets = self._controller.countdown_presets
        if 0 <= index < len(presets):
            self._controller.apply_countdown_preset(presets[index])

    def _reset_timer(self):
        self._controller.stop_timer()

    def _set_countdown_dialog(self):
        import tkinter.simpledialog as sd
        h = sd.askinteger("Countdown", "Hours:", minvalue=0)
        if h is None: return
        m = sd.askinteger("Countdown", "Minutes:", minvalue=0, maxvalue=59)
        if m is None: return
        s = sd.askinteger("Countdown", "Seconds:", minvalue=0, maxvalue=59)
        if s is None: return
        
        total = h*3600 + m*60 + s
        self._controller.start_timer(total)

    def _set_alarm_dialog(self):
        import tkinter.simpledialog as sd
        h = sd.askinteger("Alarm", "Hour (0-23):", minvalue=0, maxvalue=23)
        if h is None: return
        m = sd.askinteger("Alarm", "Minute (0-59):", minvalue=0, maxvalue=59)
        if m is None: return
        
        self._controller.set_alarm(h, m)

    def _toggle_alarm_preset(self, name):
        if self._alarm_vars[name].get():
            self._controller.select_alarm_preset(name)
        else:
            self._controller.unselect_alarm_preset(name)

        self._controller.resolve_next_alarm()

    def _use_all_alarms(self):
        for name in self._alarm_vars:
            self._alarm_vars[name].set(True)
            self._controller.select_alarm_preset(name)

        self._controller.resolve_next_alarm()

    def _clear_all_alarms(self):
        for name in self._alarm_vars:
            self._alarm_vars[name].set(False)
            self._controller.unselect_alarm_preset(name)

        self._controller.resolve_next_alarm()

    def _rebuild_preset_menus(self):
        self._menu.delete(0, "end")
        self._create_context_menu()

    # =========================================================================
    # Preset Management
    # =========================================================================
    
    def _open_countdown_editor(self):
        editor = PresetEditor(self._root, mode="countdown")
        editor.show(on_close=self._reload_presets)
    
    def _open_alarm_editor(self):
        editor = PresetEditor(self._root, mode="alarm")
        editor.show(on_close=self._reload_presets)

    def _reload_presets(self):
        self._controller.reload_countdown_presets()
        self._rebuild_preset_menus()

    # =========================================================================
    # Main Loop
    # =========================================================================
    
    def _tick_loop(self) -> None:
        """
        Periodic tick loop that drives the controller.
        
        This method:
        1. Calls controller.tick() to update state and fire callbacks
        2. Reschedules itself for the next tick
        """
        self._controller.tick()
        self._root.after(self.TICK_INTERVAL_MS, self._tick_loop)
        
        # Keep the UI responsive even when click-through is active
        # Layered windows sometimes fall behind on redraws.
        self._root.update_idletasks()
    
    def run(self) -> None:
        """
        Start the overlay window and enter the main loop.
        
        This method blocks until the window is closed.
        """
        # Initial display update
        self._update_display()
        
        # Start the tick loop
        self._root.after(self.TICK_INTERVAL_MS, self._tick_loop)
        
        # Enter tkinter main loop (blocking)
        self._root.mainloop()
    
    def close(self) -> None:
        """Close the overlay window."""
        self._root.destroy()
    
    # =========================================================================
    # Public Properties
    # =========================================================================
    
    @property
    def root(self) -> tk.Tk:
        """Return the root Tk window for external access if needed."""
        return self._root
