"""
Multi-Modal Vigilance Fusion Engine
Fuses Ocular (EAR/MAR, eye closure, yawning) and Seat Posture (head drop, slouching, leaning)
into a unified Vigilance Risk Index (VRI) and manages the fatigue state machine.
"""

import time
from typing import Dict, Optional, Tuple


class VigilanceLevel:
    ALERT = "ALERT_NORMAL"
    CAUTION = "CAUTION_MILD_FATIGUE"
    WARNING = "WARNING_MODERATE_FATIGUE"
    CRITICAL = "CRITICAL_SLEEP_ONSET"


class MultiModalVigilanceFusion:
    """
    Fuses multi-factor telemetry:
      - Ocular fatigue (EAR microsleeps, PERCLOS, MAR yawns)
      - Seat posture (head drop forward, slouching, lateral lean)
    Triggers emergency alert when all conditions align into sleep onset or risk becomes critical.
    """

    def __init__(
        self,
        weight_ocular: float = 0.60,
        weight_posture: float = 0.40,
        caution_threshold: float = 35.0,
        warning_threshold: float = 60.0,
        critical_threshold: float = 75.0
    ):
        self.weight_ocular = weight_ocular
        self.weight_posture = weight_posture

        self.caution_threshold = caution_threshold
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

        # Current state
        self.current_level = VigilanceLevel.ALERT
        self.composite_risk_score = 0.0  # 0 to 100%
        self.all_conditions_triggered = False
        self.trigger_reasons = []

        # Persistence timers
        self.critical_start_time: Optional[float] = None
        self.critical_sustained_sec = 0.0

    def compute_fusion(
        self,
        ocular_data: Dict[str, any],
        posture_data: Dict[str, any],
        cardio_data: Optional[Dict[str, any]] = None
    ) -> Dict[str, any]:
        """
        Executes multi-factor fusion on latest sensory snapshots (Ocular + Posture).
        """
        now = time.time()
        self.trigger_reasons = []

        # 1. Ocular Fatigue Score & Flag
        ocular_score = float(ocular_data.get("risk_score", 0.0))
        is_ocular_triggered = bool(
            ocular_data.get("is_microsleep", False) or
            ocular_data.get("eyes_closed_sec", 0.0) >= 1.2 or
            ocular_data.get("is_yawning", False) or
            ocular_score >= 65.0
        )
        if is_ocular_triggered:
            if ocular_data.get("is_microsleep", False) or ocular_data.get("eyes_closed_sec", 0.0) >= 1.2:
                self.trigger_reasons.append(f"Eyes Closed ({ocular_data.get('eyes_closed_sec', 0.0):.1f}s)")
            if ocular_data.get("is_yawning", False):
                self.trigger_reasons.append("Yawning Episode")

        # 2. Posture Score & Flag
        posture_score = float(posture_data.get("risk_score", 0.0))
        is_posture_triggered = bool(
            posture_data.get("is_compromised", False) and
            (posture_data.get("compromised_duration_sec", 0.0) >= 0.8 or posture_score >= 60.0)
        )
        if is_posture_triggered:
            self.trigger_reasons.append(f"Compromised Posture ({posture_data.get('state', 'Unknown')})")

        # Compute Composite Vigilance Risk Index (VRI)
        self.composite_risk_score = (
            self.weight_ocular * ocular_score +
            self.weight_posture * posture_score
        )
        self.composite_risk_score = round(min(100.0, max(0.0, self.composite_risk_score)), 1)

        # JOINT CONDITION: Check if ALL conditions triggered simultaneously!
        # (Ocular fatigue [eyes closed/microsleep/yawn] AND Inactive Seat Posture [head dropped/slouched])
        self.all_conditions_triggered = (is_ocular_triggered and is_posture_triggered)

        # Safety override: prolonged eye closure alone (>= 2.0s) is an instant emergency
        is_emergency_eye_closure = (ocular_data.get("eyes_closed_sec", 0.0) >= 2.0)

        # State Determination
        if self.all_conditions_triggered or is_emergency_eye_closure or self.composite_risk_score >= self.critical_threshold:
            self.current_level = VigilanceLevel.CRITICAL
            if self.critical_start_time is None:
                self.critical_start_time = now
            self.critical_sustained_sec = now - self.critical_start_time
        elif self.composite_risk_score >= self.warning_threshold:
            self.current_level = VigilanceLevel.WARNING
            self.critical_start_time = None
            self.critical_sustained_sec = 0.0
        elif self.composite_risk_score >= self.caution_threshold:
            self.current_level = VigilanceLevel.CAUTION
            self.critical_start_time = None
            self.critical_sustained_sec = 0.0
        else:
            self.current_level = VigilanceLevel.ALERT
            self.critical_start_time = None
            self.critical_sustained_sec = 0.0

        return {
            "level": self.current_level,
            "composite_risk_score": self.composite_risk_score,
            "all_conditions_triggered": self.all_conditions_triggered,
            "is_critical": (self.current_level == VigilanceLevel.CRITICAL),
            "is_warning": (self.current_level == VigilanceLevel.WARNING),
            "modalities": {
                "ocular": {
                    "score": ocular_score,
                    "triggered": is_ocular_triggered
                },
                "posture": {
                    "score": posture_score,
                    "triggered": is_posture_triggered
                }
            },
            "trigger_reasons": self.trigger_reasons,
            "critical_sustained_sec": round(self.critical_sustained_sec, 1)
        }
