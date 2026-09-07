"""
Safety Alert & Safe Stopping Navigation Engine
Manages acoustic alarm beeps, voice notifications, driver GPS coordinate tracking,
and locating nearest petrol pumps / rest areas with live Google Maps routes.
"""

import math
import os
import sys
import threading
import time
from typing import Callable, Dict, List, Optional

from core.gps_locator import driver_gps
from core.mock_data import RestStopCatalog

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


class AlertManager:
    """
    Coordinates non-blocking acoustic alarm beeps, voice warning alerts,
    driver GPS location detection, and petrol pump / rest area routing.
    """

    LEVEL_NORMAL = 0
    LEVEL_CAUTION = 1
    LEVEL_WARNING = 2
    LEVEL_CRITICAL = 3

    def __init__(self, enable_sound: bool = True, enable_voice: bool = True):
        self.enable_sound = enable_sound
        self.enable_voice = enable_voice
        self.current_level = self.LEVEL_NORMAL
        self.is_alarm_ringing = False
        self.stop_requested = False

        # Siren loop thread
        self._siren_thread: Optional[threading.Thread] = None
        self.last_voice_alert_time = 0.0
        self.voice_cooldown_sec = 8.0  # Avoid overlapping spoken alerts

        # Rest stop guidance state
        self.recommended_rest_stop: Optional[Dict] = None
        self.alarm_trigger_timestamp: float = 0.0

    def trigger_critical_alarm(self, reason: str = "Critical fatigue detected"):
        """
        Triggers the full emergency alarm:
        1. Locates driver GPS coordinates.
        2. Locates nearest petrol pump or rest area with live driving directions.
        3. Fires high-frequency siren beeps and spoken voice warning.
        """
        self.current_level = self.LEVEL_CRITICAL

        # Query driver GPS & locate nearest petrol pump / rest area
        self.recommended_rest_stop = driver_gps.locate_nearest_petrol_pump_or_rest_area()
        self.alarm_trigger_timestamp = time.time()

        if not self.is_alarm_ringing:
            self.is_alarm_ringing = True
            self.stop_requested = False
            self._siren_thread = threading.Thread(target=self._run_siren_loop, daemon=True)
            self._siren_thread.start()

        # Speak voice alert with actual located place
        now = time.time()
        if self.enable_voice and (now - self.last_voice_alert_time >= self.voice_cooldown_sec):
            self.last_voice_alert_time = now
            stop_name = self.recommended_rest_stop.get("name", "nearest petrol pump")
            dist = self.recommended_rest_stop.get("distance_km", 1.5)
            _, _, city = driver_gps.get_driver_coordinates()
            city_clause = f"near {city}" if city and city != "Current Location" else "on highway"
            message = f"Warning! Driver drowsiness detected. Driver located {city_clause}. Nearest petrol pump and rest area is {stop_name}, {dist} kilometers ahead. Please pull over safely."
            self._speak_async(message)

    def trigger_warning_beep(self):
        """Emits a short warning beep sequence for moderate fatigue."""
        if self.current_level == self.LEVEL_CRITICAL and self.is_alarm_ringing:
            return  # Critical alarm already active
        self.current_level = self.LEVEL_WARNING
        threading.Thread(target=self._play_warning_pulse, daemon=True).start()

    def silence_alarm(self):
        """Silences the alarm when driver acknowledges or returns to alert state."""
        self.is_alarm_ringing = False
        self.stop_requested = True
        self.current_level = self.LEVEL_NORMAL

    def _run_siren_loop(self):
        """Continuous high-urgency alternating tone emergency siren loop."""
        while self.is_alarm_ringing and not self.stop_requested:
            if not self.enable_sound:
                time.sleep(0.2)
                continue
            if HAS_WINSOUND:
                try:
                    # Alternating urgent high-frequency dual tone
                    winsound.Beep(1250, 160)
                    time.sleep(0.04)
                    if not self.is_alarm_ringing or self.stop_requested:
                        break
                    winsound.Beep(1750, 160)
                    time.sleep(0.08)
                except Exception:
                    time.sleep(0.2)
            else:
                time.sleep(0.3)

    def _play_warning_pulse(self):
        """Single two-pulse caution chime."""
        if not self.enable_sound:
            return
        if HAS_WINSOUND:
            try:
                winsound.Beep(900, 120)
                time.sleep(0.05)
                winsound.Beep(1100, 140)
            except Exception:
                pass

    def _speak_async(self, text: str):
        """Speaks voice alert asynchronously via Windows Speech."""
        def worker():
            try:
                escaped = text.replace('"', '`"')
                cmd = f'powershell -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{escaped}\');"'
                os.system(cmd)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def get_status(self) -> Dict[str, any]:
        """Returns current alert status, driver GPS coordinates, and nearest petrol pump / rest area."""
        nearest = self.recommended_rest_stop or driver_gps.locate_nearest_petrol_pump_or_rest_area()
        lat, lon, label = driver_gps.get_driver_coordinates()
        return {
            "level": self.current_level,
            "is_alarm_ringing": self.is_alarm_ringing,
            "driver_gps": {
                "lat": lat,
                "lon": lon,
                "label": label
            },
            "nearest_stop": nearest,
            "action_text": (
                f"STOP AT: {nearest['name']} ({nearest['distance_km']} km, ETA: {nearest['eta_mins']} mins)"
                if self.is_alarm_ringing else "Driver Attentive"
            )
        }
