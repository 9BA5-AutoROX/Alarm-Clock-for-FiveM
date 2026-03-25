"""
Timer Core Module
=================
Pure timer logic without any GUI dependencies.
Uses a snapshot-based approach for accurate time tracking.
"""

import time


class TimerCore:
    """
    A simple, stateful timer that supports start, pause, resume, and stop.
    
    Uses system timestamps instead of threading for accuracy and simplicity.
    The timer operates as a state machine with three states: IDLE, RUNNING, PAUSED.
    """
    
    # Timer states
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    
    def __init__(self):
        """Initialize the timer in IDLE state."""
        self._state = self.IDLE
        self._initial_duration = 0.0      # Total seconds for this timer session
        self._start_timestamp = 0.0       # When the current run started
        self._remaining_at_pause = 0.0    # Snapshot of remaining time when paused
    
    @property
    def state(self) -> str:
        """Return the current state of the timer."""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """Return True if timer is currently running."""
        return self._state == self.RUNNING
    
    @property
    def is_paused(self) -> bool:
        """Return True if timer is currently paused."""
        return self._state == self.PAUSED
    
    @property
    def is_idle(self) -> bool:
        """Return True if timer is idle (not started or stopped)."""
        return self._state == self.IDLE
    
    def start(self, seconds: float) -> None:
        """
        Start the timer with the specified duration.
        
        If called while already running, restarts with the new duration.
        If called while paused, stops first then starts fresh.
        
        Args:
            seconds: The countdown duration in seconds. Must be positive.
        
        Raises:
            ValueError: If seconds is not positive.
        """
        if seconds <= 0:
            raise ValueError("Duration must be a positive number.")
        
        self._initial_duration = float(seconds)
        self._start_timestamp = time.time()
        self._remaining_at_pause = 0.0
        self._state = self.RUNNING
    
    def pause(self) -> None:
        """
        Pause the timer if it's currently running.
        
        Takes a snapshot of the remaining time for later resumption.
        Does nothing if not in RUNNING state.
        """
        if self._state != self.RUNNING:
            return  # Silent no-op
        
        # Snapshot the remaining time
        self._remaining_at_pause = self._calculate_remaining()
        self._state = self.PAUSED
    
    def resume(self) -> None:
        """
        Resume the timer if it's currently paused.
        
        Restarts the countdown using the snapshot taken at pause.
        Does nothing if not in PAUSED state.
        """
        if self._state != self.PAUSED:
            return  # Silent no-op
        
        # Use the paused snapshot as the new duration
        self._initial_duration = self._remaining_at_pause
        self._start_timestamp = time.time()
        self._remaining_at_pause = 0.0
        self._state = self.RUNNING
    
    def stop(self) -> None:
        """
        Stop the timer and reset to IDLE state.
        
        Can be called from any state. Clears all internal tracking data.
        """
        self._state = self.IDLE
        self._initial_duration = 0.0
        self._start_timestamp = 0.0
        self._remaining_at_pause = 0.0
    
    def get_remaining_time(self) -> float:
        """
        Get the remaining time in seconds.
        
        Returns:
            float: Remaining seconds. Returns 0 if expired or idle.
                   When paused, returns the snapshot value.
                   When running, calculates from the system clock.
        """
        if self._state == self.IDLE:
            return 0.0
        
        if self._state == self.PAUSED:
            return max(0.0, self._remaining_at_pause)
        
        # RUNNING state: calculate from timestamps
        return max(0.0, self._calculate_remaining())
    
    def is_expired(self) -> bool:
        """
        Check if the timer has expired (remaining time <= 0).
        
        Returns:
            bool: True if timer was running and has reached zero.
        """
        if self._state != self.RUNNING:
            return False
        return self._calculate_remaining() <= 0
    
    def _calculate_remaining(self) -> float:
        """
        Internal method to calculate remaining time from timestamps.
        
        Returns:
            float: Remaining seconds (can be negative if expired).
        """
        elapsed = time.time() - self._start_timestamp
        return self._initial_duration - elapsed
    
    def __repr__(self) -> str:
        """Return a string representation for debugging."""
        return (
            f"TimerCore(state={self._state}, "
            f"remaining={self.get_remaining_time():.1f}s)"
        )
