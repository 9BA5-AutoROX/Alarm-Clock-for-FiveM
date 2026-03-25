"""
Preset Editor Module
====================
Standalone window for managing countdown / alarm presets.
"""


import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
from typing import List, Dict, Any
from core.paths import resolve


class PresetEditor:
    """
    A standalone window for managing countdown presets.
    
    Features:
    - Display presets in a list (name + HH:MM:SS format)
    - Add, Edit, Delete presets
    - Save changes back to JSON file
    """
    
    # Path to the presets JSON file
    BASE_PRESET_PATH = None  # Resolved at __init__ time
    
    def __init__(self, parent: tk.Tk = None, mode="countdown"):
        self.mode = mode
        """
        Initialize the Preset Editor window.
        
        Args:
            parent: Optional parent window. If None, creates a root window.
        """
        # Create window
        if parent is None:
            self.root = tk.Tk()
            self.is_standalone = True
        else:
            self.root = tk.Toplevel(parent)
            self.is_standalone = False
        
        if self.mode == "countdown":
            self.PRESETS_FILE = resolve("presets/countdown_presets.json")
            self.root.title("Countdown Preset Editor")
        else:
            self.PRESETS_FILE = resolve("presets/alarm_presets.json")
            self.root.title("Alarm Preset Editor")

        self.root.geometry("420x400")
        self.root.resizable(False, False)
        
        # Configure style
        self._configure_style()
        
        # Data storage
        self.presets: List[Dict[str, Any]] = []
        
        # Build UI
        self._create_widgets()
        
        # Load presets
        self._load_presets()
    
    def _configure_style(self):
        """Configure ttk styles for a clean look."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        self.colors = {
            'bg': '#2b2b2b',
            'fg': '#ffffff',
            'accent': '#4a9eff',
            'input_bg': '#3c3c3c',
            'list_bg': '#1e1e1e',
            'button_bg': '#3c3c3c',
            'button_hover': '#4a4a4a',
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # Style configurations
        style.configure('TFrame', background=self.colors['bg'])
        style.configure('TLabel', background=self.colors['bg'], foreground=self.colors['fg'])
        style.configure('TButton', padding=6)
        style.configure('Header.TLabel', font=('Segoe UI', 12, 'bold'))
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Label(main_frame, text="Countdown Presets", style='Header.TLabel')
        header.pack(anchor=tk.W, pady=(0, 10))
        
        # === Preset List Section ===
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Listbox with scrollbar
        self.listbox = tk.Listbox(
            list_frame,
            font=('Consolas', 11),
            bg=self.colors['list_bg'],
            fg=self.colors['fg'],
            selectbackground=self.colors['accent'],
            selectforeground='#ffffff',
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=self.colors['accent'],
            highlightbackground=self.colors['input_bg'],
            activestyle='none',
            height=8
        )
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.listbox.bind('<<ListboxSelect>>', self._on_select)
        
        # === Edit Section ===
        edit_frame = ttk.Frame(main_frame)
        edit_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Name input
        name_frame = ttk.Frame(edit_frame)
        name_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(name_frame, text="Name:", width=6).pack(side=tk.LEFT)
        self.name_entry = tk.Entry(
            name_frame,
            font=('Segoe UI', 10),
            bg=self.colors['input_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=self.colors['accent'],
            highlightbackground=self.colors['input_bg']
        )
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(5, 0))
        
        # Time input (HH:MM:SS)
        time_frame = ttk.Frame(edit_frame)
        time_frame.pack(fill=tk.X)
        
        ttk.Label(time_frame, text="Time:", width=6).pack(side=tk.LEFT)
        
        # Hours
        self.hours_var = tk.StringVar(value="00")
        self.hours_entry = tk.Entry(
            time_frame,
            textvariable=self.hours_var,
            font=('Consolas', 12),
            width=3,
            justify=tk.CENTER,
            bg=self.colors['input_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=self.colors['accent'],
            highlightbackground=self.colors['input_bg']
        )
        self.hours_entry.pack(side=tk.LEFT, ipady=3, padx=(5, 0))
        
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=3)
        
        # Minutes
        self.minutes_var = tk.StringVar(value="00")
        self.minutes_entry = tk.Entry(
            time_frame,
            textvariable=self.minutes_var,
            font=('Consolas', 12),
            width=3,
            justify=tk.CENTER,
            bg=self.colors['input_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=self.colors['accent'],
            highlightbackground=self.colors['input_bg']
        )
        self.minutes_entry.pack(side=tk.LEFT, ipady=3)
        
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=3)
        
        # Seconds
        self.seconds_var = tk.StringVar(value="00")
        self.seconds_entry = tk.Entry(
            time_frame,
            textvariable=self.seconds_var,
            font=('Consolas', 12),
            width=3,
            justify=tk.CENTER,
            bg=self.colors['input_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            borderwidth=0,
            highlightthickness=1,
            highlightcolor=self.colors['accent'],
            highlightbackground=self.colors['input_bg']
        )
        self.seconds_entry.pack(side=tk.LEFT, ipady=3)
        
        ttk.Label(time_frame, text="(HH:MM:SS)", foreground='#888888').pack(side=tk.LEFT, padx=(10, 0))
        
        # === Button Section ===
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Create buttons with consistent styling
        button_config = {
            'font': ('Segoe UI', 9),
            'bg': self.colors['button_bg'],
            'fg': self.colors['fg'],
            'activebackground': self.colors['button_hover'],
            'activeforeground': self.colors['fg'],
            'borderwidth': 0,
            'padx': 15,
            'pady': 6,
            'cursor': 'hand2'
        }
        
        self.add_btn = tk.Button(button_frame, text="Add", command=self._add_preset, **button_config)
        self.add_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.update_btn = tk.Button(button_frame, text="Update", command=self._update_preset, **button_config)
        self.update_btn.pack(side=tk.LEFT, padx=5)
        
        self.delete_btn = tk.Button(button_frame, text="Delete", command=self._delete_preset, **button_config)
        self.delete_btn.pack(side=tk.LEFT, padx=5)
        
        # Save button on the right with accent color
        self.save_btn = tk.Button(
            button_frame,
            text="Save",
            command=self._save_presets,
            font=('Segoe UI', 9, 'bold'),
            bg=self.colors['accent'],
            fg='#ffffff',
            activebackground='#3d8be0',
            activeforeground='#ffffff',
            borderwidth=0,
            padx=20,
            pady=6,
            cursor='hand2'
        )
        self.save_btn.pack(side=tk.RIGHT)
        
        # Clear button
        self.clear_btn = tk.Button(button_frame, text="Clear", command=self._clear_fields, **button_config)
        self.clear_btn.pack(side=tk.RIGHT, padx=(0, 10))
    
    def _load_presets(self):
        """Load presets from JSON file."""
        try:
            if self.PRESETS_FILE.exists():
                with open(self.PRESETS_FILE, 'r', encoding='utf-8') as f:
                    self.presets = json.load(f)
            else:
                self.presets = []
        except (json.JSONDecodeError, IOError) as e:
            messagebox.showerror("Error", f"Failed to load presets: {e}")
            self.presets = []
        
        self._refresh_listbox()
    
    def _save_presets(self):
        """Save presets to JSON file."""
        try:
            # Ensure directory exists
            self.PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)

            if self.mode == "alarm":
                for p in self.presets:
                    if "times" not in p and "time" in p:
                        p["times"] = [p.pop("time")]

            with open(self.PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, indent=4)
            
            messagebox.showinfo("Success", "Presets saved successfully!")
        except IOError as e:
            messagebox.showerror("Error", f"Failed to save presets: {e}")
    
    def _refresh_listbox(self):
        """Refresh the listbox with current presets."""
        self.listbox.delete(0, tk.END)
        
        for preset in self.presets:
            name = preset.get('name', 'Unnamed')
            if self.mode == "countdown":
                time = preset.get('time', [0, 0, 0])
                time_str = f"{time[0]:02d}:{time[1]:02d}:{time[2]:02d}"
            else:
                times = preset.get("times", [])
                time_str = ", ".join(times)
            display = f"{name:<20} {time_str}"
            self.listbox.insert(tk.END, display)
            
    def _on_select(self, event):
        """Handle listbox selection - populate edit fields."""
        selection = self.listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        preset = self.presets[index]
        
        # Populate fields
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, preset.get('name', ''))
        
        time = preset.get('time', [0, 0, 0])
        self.hours_var.set(f"{time[0]:02d}")
        self.minutes_var.set(f"{time[1]:02d}")
        self.seconds_var.set(f"{time[2]:02d}")
    
    def _get_time_values(self) -> tuple:
        """Parse and validate time values from entries."""
        try:
            hours = int(self.hours_var.get() or 0)
            minutes = int(self.minutes_var.get() or 0)
            seconds = int(self.seconds_var.get() or 0)
            
            # Validation
            if hours < 0 or hours > 99:
                raise ValueError("Hours must be 0-99")
            if minutes < 0 or minutes > 59:
                raise ValueError("Minutes must be 0-59")
            if seconds < 0 or seconds > 59:
                raise ValueError("Seconds must be 0-59")
            
            return hours, minutes, seconds
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError("Time values must be numbers")
            raise
    
    def _add_preset(self):
        """Add a new preset from current field values."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a preset name.")
            return
        
        try:
            hours, minutes, seconds = self._get_time_values()
        except ValueError as e:
            messagebox.showwarning("Warning", str(e))
            return
        
        # Check for duplicate name
        for preset in self.presets:
            if preset['name'].lower() == name.lower():
                messagebox.showwarning("Warning", f"A preset named '{name}' already exists.")
                return
        
        # Add preset
        if self.mode == "countdown":
            self.presets.append({
                'name': name,
                'time': [hours, minutes, seconds]
            })
        else:
            self.presets.append({
                'name': name,
                'times': [f"{hours:02d}:{minutes:02d}"]
            })
                
        self._refresh_listbox()
        self._clear_fields()
        
        # Select the new item
        self.listbox.selection_set(len(self.presets) - 1)
        self.listbox.see(len(self.presets) - 1)
    
    def _update_preset(self):
        """Update the selected preset with current field values."""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a preset to update.")
            return
        
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Please enter a preset name.")
            return
        
        try:
            hours, minutes, seconds = self._get_time_values()
        except ValueError as e:
            messagebox.showwarning("Warning", str(e))
            return
        
        index = selection[0]
        
        # Check for duplicate name (excluding current)
        for i, preset in enumerate(self.presets):
            if i != index and preset['name'].lower() == name.lower():
                messagebox.showwarning("Warning", f"A preset named '{name}' already exists.")
                return
        
        # Update preset
        if self.mode == "countdown":
            self.presets[index] = {
                'name': name,
                'time': [hours, minutes, seconds]
            }
        else:
            self.presets[index]['name'] = name
                
        self._refresh_listbox()
        self.listbox.selection_set(index)
    
    def _delete_preset(self):
        """Delete the selected preset."""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a preset to delete.")
            return
        
        index = selection[0]
        preset_name = self.presets[index]['name']
        
        if messagebox.askyesno("Confirm Delete", f"Delete preset '{preset_name}'?"):
            del self.presets[index]
            self._refresh_listbox()
            self._clear_fields()
    
    def _clear_fields(self):
        """Clear all input fields."""
        self.name_entry.delete(0, tk.END)
        self.hours_var.set("00")
        self.minutes_var.set("00")
        self.seconds_var.set("00")
        self.listbox.selection_clear(0, tk.END)
    
    def run(self):
        """Start the editor window and enter the main loop."""
        if self.is_standalone:
            self.root.mainloop()
    
    def show(self, on_close=None):
        """Show the editor window (for use as a dialog)."""
        self._on_close = on_close
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _handle_close(self):
        if self._on_close:
            self._on_close()
        self.root.destroy()

# Allow running standalone for testing
if __name__ == "__main__":
    editor = PresetEditor()
    editor.run()
