"""
Sound Service Module
====================
Provides asynchronous sound playback for alerts and warnings.
Uses winsound for zero-dependency playback on Windows.
"""

import winsound
import threading
from pathlib import Path
from typing import Optional
import time
from core.paths import resolve


class SoundService:
    """
    Manages audio alerts. Prevents overlapping sounds of the same type
    and handles missing files gracefully.
    """
    
    _instance = None
    _lock = threading.Lock()
    _last_play_time = {}  # type: dict[str, float]
    COOLDOWN = 1.0  # Seconds between repeats of the same sound
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SoundService, cls).__new__(cls)
        return cls._instance

    def play(self, sound_name: Optional[str], category: str = "general"):
        """
        Play a sound file from the sounds/ directory.
        
        Args:
            sound_name: Filename (e.g., 'alert.wav') or None/empty to skip.
            category: Used for cooldown tracking.
        """
        if not sound_name:
            return

        # Simple cooldown check
        now = time.time()
        if now - self._last_play_time.get(category, 0) < self.COOLDOWN:
            return
        self._last_play_time[category] = now

        # Resolve path
        sound_path = resolve(f"sounds/{sound_name}")
        
        if not sound_path.exists():
            print(f"[SoundService] Warning: Sound file not found: {sound_path}")
            return

        # Play asynchronously
        try:
            # winsound.SND_ASYNC | winsound.SND_FILENAME
            threading.Thread(
                target=lambda: winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[SoundService] Error playing sound {sound_name}: {e}")

    def play_warning(self, stage: int):
        """Play a warning sound (5, 3, or 1 minute remaining)."""
        filename = f"warning_{stage}m.wav"
        self.play(filename, category=f"warning_{stage}")

    def play_complete(self, preset_sound: Optional[str] = None):
        """Play the completion sound (specific preset or default)."""
        if preset_sound:
            self.play(preset_sound, category="complete")
        else:
            self.play("default_complete.wav", category="complete")
