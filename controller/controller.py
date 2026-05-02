"""
Controller Module
=================
Central coordinator between timer logic and UI.
Manages TimerCore instance and provides formatted output for display.
"""

import json
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime, timedelta
from core.timer_core import TimerCore
from core.paths import resolve
from services.sound_service import SoundService


class Controller:
    """
    Coordinates the timers and provides an interface for the GUI.
    
    The Controller manages multiple TimerCore instances:
    - main: General countdown presets
    - mushroom: Feed Mushroom specifically
    - cow: Cow presets (5m, 25m)
    """
    
    def __init__(self):
        self._timers = {
            "main": TimerCore(),
            "mushroom": TimerCore(),
            "cow": TimerCore()
        }
        self._sound_service = SoundService()
        self._on_tick_callback: Optional[Callable[[], None]] = None
        self._on_complete_callback: Optional[Callable[[str], None]] = None
        
        self._completed_fired = {"main": False, "mushroom": False, "cow": False}
        self._active_preset_sounds = {"main": None, "mushroom": None, "cow": None}
        self._milestones_played = {"main": set(), "mushroom": set(), "cow": set()}
        self._milestones_played["alarm"] = set()
        
        # Smart Countdown thresholds (seconds)
        self.WARNING_THRESHOLD = 10 * 60   # 10 minutes
        self.DANGER_THRESHOLD  = 5 * 60    # 5 minutes
        
        self._alarm_time: datetime | None = None
        self._alarm_warning_delta = timedelta(minutes=10)
        self.selected_alarm_presets = set()
        self.current_alarm = None
        
        self.countdown_presets = self._load_presets("presets/countdown_presets.json")
        self.alarm_presets = self._load_presets("presets/alarm_presets.json")

        for p in self.alarm_presets:
            self.selected_alarm_presets.add(p["name"])

        self.resolve_next_alarm()

    # =========================================================================
    # Callback Registration
    # =========================================================================
    
    def set_on_tick(self, callback: Optional[Callable[[], None]]) -> None:
        self._on_tick_callback = callback
    
    def set_on_complete(self, callback: Optional[Callable[[str], None]]) -> None:
        """Callback takes a string identifying which timer completed."""
        self._on_complete_callback = callback
    
    # =========================================================================
    # Timer Control Methods
    # =========================================================================
    
    def start_timer(self, timer_id: str, seconds: float, sound: Optional[str] = None) -> None:
        if seconds <= 0:
            raise ValueError("Duration must be a positive number.")
        if timer_id not in self._timers:
            return
            
        self._completed_fired[timer_id] = False
        self._active_preset_sounds[timer_id] = sound
        self._milestones_played[timer_id].clear()
        
        self._timers[timer_id].start(seconds)
        self._fire_tick_callback()
    
    def stop_timer(self, timer_id: str) -> None:
        if timer_id not in self._timers:
            return
        self._timers[timer_id].stop()
        self._completed_fired[timer_id] = False
        self._active_preset_sounds[timer_id] = None
        self._milestones_played[timer_id].clear()
        self._fire_tick_callback()
    
    # =========================================================================
    # Display Methods
    # =========================================================================
    
    def get_display_time(self, timer_id: str) -> str:
        if timer_id not in self._timers:
            return "00:00"
        remaining = self._timers[timer_id].get_remaining_time()
        total_seconds = max(0, int(remaining + 0.999))
        
        # Format as HH:MM:SS if >= 1 hour, else MM:SS
        if total_seconds >= 3600:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
    
    def get_remaining_seconds(self, timer_id: str) -> float:
        if timer_id not in self._timers:
            return 0.0
        return self._timers[timer_id].get_remaining_time()
    
    def get_urgency_level(self, timer_id: str) -> str:
        remaining = self.get_remaining_seconds(timer_id)
        if remaining <= self.DANGER_THRESHOLD:
            return "danger"
        if remaining <= self.WARNING_THRESHOLD:
            return "warning"
        return "normal"
        
    def set_alarm(self, hour: int, minute: int, sound: Optional[str] = None):
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        self._alarm_time = target
        self._active_preset_sounds["alarm"] = sound
        self._milestones_played["alarm"].clear()

    def get_alarm_remaining(self) -> timedelta | None:
        if not self._alarm_time:
            return None
        return self._alarm_time - datetime.now()

    def _load_presets(self, path):
        try:
            with open(resolve(path), "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def apply_countdown_preset(self, preset):
        # By default apply to main
        h, m, s = preset["time"]
        sound = preset.get("sound")
        self.start_timer("main", h*3600 + m*60 + s, sound=sound)

    def apply_alarm_preset(self, preset):
        h, m = map(int, preset["time"].split(":"))
        sound = preset.get("sound")
        self.set_alarm(h, m, sound=sound)
    
    def resolve_next_alarm(self):
        now = datetime.now()
        candidates = []

        for preset in self.alarm_presets:
            if preset["name"] not in self.selected_alarm_presets:
                continue

            times = preset.get("time", [])
            if not times and "times" in preset:
                times = preset["times"]
            sound = preset.get("sound")

            for t in times:
                hour, minute = map(int, t.split(":"))
                alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if alarm_time < now:
                    alarm_time += timedelta(days=1)
                candidates.append((alarm_time, preset["name"], sound))

        if not candidates:
            self.current_alarms = []
            self.current_alarm = None
            return

        candidates.sort(key=lambda x: x[0])
        next_time = candidates[0][0]
        same_time = [c for c in candidates if c[0] == next_time]
        self.current_alarms = same_time
        
        alarm_time, name, sound = same_time[0]
        self.current_alarm = (alarm_time, name)
        
        self._active_preset_sounds["alarm"] = sound
        self._milestones_played["alarm"].clear()
    
    def get_alarm_status(self):
        if not self.current_alarms:
            return "idle", []
        from datetime import datetime, timedelta
        now = datetime.now()
        alarm_time = self.current_alarms[0][0]
        remaining = alarm_time - now

        if remaining <= timedelta(seconds=0):
            return "active", self.current_alarms
        elif remaining <= timedelta(minutes=3):
            return "danger", self.current_alarms
        elif remaining <= timedelta(minutes=10):
            return "warning", self.current_alarms
        else:
            return "normal", self.current_alarms

    def get_next_alarm_display(self):
        if not self.current_alarm:
            return None
        time_obj, name = self.current_alarm
        return f"{name} {time_obj.strftime('%H:%M')}"
    
    def reload_countdown_presets(self):
        self.countdown_presets = self._load_presets("presets/countdown_presets.json")

    def reload_alarm_presets(self):
        self.alarm_presets = self._load_presets("presets/alarm_presets.json")

    # =========================================================================
    # State Properties
    # =========================================================================
    
    def is_running(self, timer_id: str) -> bool:
        if timer_id not in self._timers: return False
        return self._timers[timer_id].is_running
    
    def is_idle(self, timer_id: str) -> bool:
        if timer_id not in self._timers: return True
        return self._timers[timer_id].is_idle
    
    def get_state(self, timer_id: str) -> str:
        if timer_id not in self._timers: return "IDLE"
        return self._timers[timer_id].state
    
    # =========================================================================
    # Tick Method (Called by GUI)
    # =========================================================================
    
    def tick(self) -> None:
        self._fire_tick_callback()
        
        # Check completion for each timer instance
        for t_id, timer in self._timers.items():
            if timer.is_expired() and not self._completed_fired[t_id]:
                self._completed_fired[t_id] = True
                timer.stop()
                
                # Play specific sound if exists, else default target sound (if we want different defaults)
                # SoundService will handle fallbacks if not found
                self._sound_service.play_complete(self._active_preset_sounds[t_id])
                
                if self._on_complete_callback:
                    self._on_complete_callback(t_id)

            # Milestones for timers
            if timer.is_running:
                rem_sec = timer.get_remaining_time()
                for ms in [5, 3, 1]:
                    if rem_sec <= ms * 60 and ms not in self._milestones_played[t_id]:
                        self._milestones_played[t_id].add(ms)
                        self._sound_service.play_warning(ms)
                        
        # Milestones for alarms
        if self.current_alarm:
            time_obj, name = self.current_alarm
            diff = time_obj - datetime.now()
            rem_sec = diff.total_seconds()
            if rem_sec > 0:
                for ms in [5, 3, 1]:
                    if rem_sec <= ms * 60 and ms not in self._milestones_played["alarm"]:
                        self._milestones_played["alarm"].add(ms)
                        self._sound_service.play_warning(ms)
                        
            # Advance logic
            if datetime.now() > time_obj + timedelta(minutes=1):
                self.resolve_next_alarm()

    def _fire_tick_callback(self) -> None:
        if self._on_tick_callback is not None:
            self._on_tick_callback()
