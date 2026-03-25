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


class Controller:
    """
    Coordinates the timer and provides an interface for the GUI.
    
    The Controller owns the TimerCore instance and provides:
    - Methods to control the timer (start, pause, resume, stop)
    - Formatted time output for display
    - Callback system for GUI updates
    
    The GUI should call tick() periodically to check for timer completion.
    """
    
    def __init__(self):
        """Initialize the controller with a fresh TimerCore."""
        self._timer = TimerCore()
        self._on_tick_callback: Optional[Callable[[], None]] = None
        self._on_complete_callback: Optional[Callable[[], None]] = None
        self._completed_fired = False  # Prevents multiple complete callbacks
        # Smart Countdown thresholds (seconds)
        self.WARNING_THRESHOLD = 10 * 60   # 10 minutes
        self.DANGER_THRESHOLD  = 5 * 60    # 5 minutes
        self._alarm_time: datetime | None = None
        self._alarm_warning_delta = timedelta(minutes=10)
        self.selected_alarm_presets = set()
        self.current_alarm = None
        self.countdown_presets = self._load_presets("presets/countdown_presets.json")
        self.alarm_presets = self._load_presets("presets/alarm_presets.json")

        # --- Default: use all alarm presets ---
        for p in self.alarm_presets:
            self.selected_alarm_presets.add(p["name"])

        self.resolve_next_alarm()

    # =========================================================================
    # Callback Registration
    # =========================================================================
    
    def set_on_tick(self, callback: Optional[Callable[[], None]]) -> None:
        """
        Register a callback to be fired on each tick.
        
        The GUI should use this to update the display.
        
        Args:
            callback: Function with no arguments, or None to clear.
        """
        self._on_tick_callback = callback
    
    def set_on_complete(self, callback: Optional[Callable[[], None]]) -> None:
        """
        Register a callback to be fired when timer completes.
        
        The GUI should use this to play sounds, show notifications, etc.
        
        Args:
            callback: Function with no arguments, or None to clear.
        """
        self._on_complete_callback = callback
    
    # =========================================================================
    # Timer Control Methods
    # =========================================================================
    
    def start_timer(self, seconds: float) -> None:
        """
        Start the timer with the specified duration.
        
        Args:
            seconds: Duration in seconds. Must be positive.
        
        Raises:
            ValueError: If seconds is not positive.
        """
        if seconds <= 0:
            raise ValueError("Duration must be a positive number.")
        
        self._completed_fired = False  # Reset completion flag
        self._timer.start(seconds)
        self._fire_tick_callback()
    
    def pause_timer(self) -> None:
        """
        Pause the timer if it's running.
        
        Does nothing if timer is not in RUNNING state.
        """
        self._timer.pause()
        self._fire_tick_callback()
    
    def resume_timer(self) -> None:
        """
        Resume the timer if it's paused.
        
        Does nothing if timer is not in PAUSED state.
        """
        self._timer.resume()
        self._fire_tick_callback()
    
    def stop_timer(self) -> None:
        """
        Stop the timer and reset to idle state.
        
        Can be called from any state.
        """
        self._timer.stop()
        self._completed_fired = False
        self._fire_tick_callback()
    
    # =========================================================================
    # Display Methods
    # =========================================================================
    
    def get_display_time(self) -> str:
        """
        Get the remaining time formatted as MM:SS.
        
        Returns:
            str: Time in "MM:SS" format (e.g., "05:30", "00:00").
        """
        remaining = self._timer.get_remaining_time()
        total_seconds = max(0, int(remaining + 0.999))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def get_remaining_seconds(self) -> float:
        """
        Get the raw remaining time in seconds.
        
        Returns:
            float: Remaining seconds (0 if idle or expired).
        """
        return self._timer.get_remaining_time()
    
    def get_urgency_level(self) -> str:
        """
        Return urgency level based on remaining time:
        'normal', 'warning', 'danger'
        """
        remaining = self.get_remaining_seconds()

        if remaining <= self.DANGER_THRESHOLD:
            return "danger"
        if remaining <= self.WARNING_THRESHOLD:
            return "warning"
        return "normal"
        
    def set_alarm(self, hour: int, minute: int):
        """Set next alarm using real world clock."""
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        self._alarm_time = target

    def get_alarm_remaining(self) -> timedelta | None:
        if not self._alarm_time:
            return None
        return self._alarm_time - datetime.now()

    def is_alarm_warning(self) -> bool:
        remaining = self.get_alarm_remaining()
        if not remaining:
            return False
        return remaining <= self._alarm_warning_delta

    def is_alarm_due(self) -> bool:
        remaining = self.get_alarm_remaining()
        if not remaining:
            return False
        return remaining.total_seconds() <= 0

    def _load_presets(self, path):
        try:
            with open(resolve(path), "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def apply_countdown_preset(self, preset):
        h, m, s = preset["time"]
        self.start_timer(h*3600 + m*60 + s)

    def apply_alarm_preset(self, preset):
        h, m = map(int, preset["time"].split(":"))
        self.set_alarm(h, m)
    
    def select_alarm_preset(self, name: str):
        self.selected_alarm_presets.add(name)

    def unselect_alarm_preset(self, name: str):
        self.selected_alarm_presets.discard(name)

    def resolve_next_alarm(self):
        now = datetime.now()
        candidates = []

        for preset in self.alarm_presets:
            if preset["name"] not in self.selected_alarm_presets:
                continue

            times = preset.get("time", [])
            for t in times:
                hour, minute = map(int, t.split(":"))

                alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if alarm_time < now:
                    alarm_time += timedelta(days=1)

                candidates.append((alarm_time, preset["name"]))

        if not candidates:
            self.current_alarms = []
            self.current_alarm = None
            return

        candidates.sort(key=lambda x: x[0])
        next_time = candidates[0][0]

        same_time = [c for c in candidates if c[0] == next_time]

        self.current_alarms = same_time

        # ⬇️ ตัวเดียวสำหรับ UI legacy
        alarm_time, name = same_time[0]
        self.current_alarm = (alarm_time, name)

    #def get_alarm_status(self):
        #if not self.current_alarms:
            #return "idle", []

        #now = datetime.now()
        #alarm_time = self.current_alarms[0][0]
        #remaining = alarm_time - now

        #if remaining <= timedelta(seconds=-60):
            #self.resolve_next_alarm()
            #return "advance", []

        #if remaining <= timedelta(seconds=0):
            #return "active", self.current_alarms

        #if remaining <= timedelta(minutes=3):
            #return "danger", self.current_alarms

        #if remaining <= timedelta(minutes=10):
            #return "warning", self.current_alarms

        #return "normal", self.current_alarms
    
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

    def get_current_alarm(self):
        return self.current_alarm

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
    
    @property
    def is_running(self) -> bool:
        """Return True if timer is currently running."""
        return self._timer.is_running
    
    @property
    def is_paused(self) -> bool:
        """Return True if timer is currently paused."""
        return self._timer.is_paused
    
    @property
    def is_idle(self) -> bool:
        """Return True if timer is idle."""
        return self._timer.is_idle
    
    @property
    def state(self) -> str:
        """Return the current timer state string."""
        return self._timer.state
    
    # =========================================================================
    # Tick Method (Called by GUI)
    # =========================================================================
    
    def tick(self) -> None:
        """
        Called periodically by the GUI to update display and check completion.
        
        This method:
        1. Fires the tick callback to update the display
        2. Checks if timer has expired and fires complete callback (once)
        """
        self._fire_tick_callback()
        
        # Check for completion (only fire once per timer session)
        if self._timer.is_expired() and not self._completed_fired:
            self._completed_fired = True
            self._timer.stop()  # Transition to IDLE
            self._fire_complete_callback()
        
        # ----- Auto advance alarm -----
        if self.current_alarm:
            time_obj, name = self.current_alarm
            if datetime.now() > time_obj + timedelta(minutes=1):
                self.resolve_next_alarm()

    # =========================================================================
    # Private Callback Methods
    # =========================================================================
    
    def _fire_tick_callback(self) -> None:
        """Fire the tick callback if registered."""
        if self._on_tick_callback is not None:
            self._on_tick_callback()
    
    def _fire_complete_callback(self) -> None:
        """Fire the complete callback if registered."""
        if self._on_complete_callback is not None:
            self._on_complete_callback()
    
    # =========================================================================
    # Debug
    # =========================================================================
    
    def __repr__(self) -> str:
        """Return a string representation for debugging."""
        return (
            f"Controller(state={self.state}, "
            f"display={self.get_display_time()})"
        )
