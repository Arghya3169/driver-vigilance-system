"""
Seat Posture & Ergonomics Detector
Monitors driver sitting posture, spinal alignment, slouching, head dropping forward (chin to chest),
and lateral leaning to determine if posture matches active driving conditions.
"""

import math
import numpy as np
import time
from typing import Dict, List, Optional, Tuple


class PostureState:
    ACTIVE = "ACTIVE_ATTENTIVE"
    SLOUCHING = "SLOUCHING"
    HEAD_DROPPED = "HEAD_DROPPED_FORWARD"
    LATERAL_LEAN = "LATERAL_LEAN"
    UNKNOWN = "UNKNOWN"


class SeatPostureDetector:
    """
    Evaluates driver ergonomics and posture alerts based on skeletal and facial geometry.
    Computes posture risk score (0 - 100%) and detects inactive sleeping postures.
    """

    def __init__(
        self,
        lateral_tilt_thresh_deg: float = 14.0,
        head_pitch_down_thresh_deg: float = 18.0,
        slouch_compression_ratio_thresh: float = 0.78
    ):
        self.lateral_tilt_thresh_deg = lateral_tilt_thresh_deg
        self.head_pitch_down_thresh_deg = head_pitch_down_thresh_deg
        self.slouch_compression_ratio_thresh = slouch_compression_ratio_thresh

        # Calibration for active driving baseline
        self.is_calibrated = False
        self.baseline_shoulder_width = None
        self.baseline_neck_head_dist = None
        self.calibration_samples = []

        # Current state
        self.current_state = PostureState.ACTIVE
        self.posture_risk_score = 0.0  # 0 to 100%
        self.compromised_duration = 0.0
        self.first_compromised_time = None

        # Posture metrics
        self.shoulder_tilt_deg = 0.0
        self.head_pitch_deg = 0.0
        self.compression_ratio = 1.0

    def calibrate(self, shoulder_width: float, neck_head_dist: float):
        """Sets the baseline active posture metrics for the current driver."""
        if shoulder_width > 10 and neck_head_dist > 10:
            self.baseline_shoulder_width = shoulder_width
            self.baseline_neck_head_dist = neck_head_dist
            self.is_calibrated = True

    def evaluate_posture(
        self,
        nose_pt: Optional[Tuple[float, float]],
        left_shoulder_pt: Optional[Tuple[float, float]],
        right_shoulder_pt: Optional[Tuple[float, float]],
        head_pitch_deg: float = 0.0,
        head_roll_deg: float = 0.0
    ) -> Dict[str, any]:
        """
        Evaluates current driver posture from keypoints and head angles.
        Keypoints are in pixel or normalized coordinates.
        """
        now = time.time()
        self.head_pitch_deg = head_pitch_deg

        # If full shoulder tracking is available
        has_shoulders = (
            left_shoulder_pt is not None and right_shoulder_pt is not None and
            len(left_shoulder_pt) == 2 and len(right_shoulder_pt) == 2
        )

        if has_shoulders:
            dx = right_shoulder_pt[0] - left_shoulder_pt[0]
            dy = right_shoulder_pt[1] - left_shoulder_pt[1]
            shoulder_width = math.hypot(dx, dy)

            # Shoulder tilt angle relative to horizontal
            shoulder_angle = math.degrees(math.atan2(abs(dy), max(1e-5, abs(dx))))
            self.shoulder_tilt_deg = round(shoulder_angle, 1)

            # Neck / Head vertical distance
            shoulder_mid_x = (left_shoulder_pt[0] + right_shoulder_pt[0]) / 2.0
            shoulder_mid_y = (left_shoulder_pt[1] + right_shoulder_pt[1]) / 2.0

            if nose_pt is not None:
                curr_dist = shoulder_mid_y - nose_pt[1]  # positive if head is above shoulders
                if not self.is_calibrated and shoulder_width > 10 and curr_dist > 10:
                    self.calibration_samples.append((shoulder_width, curr_dist))
                    if len(self.calibration_samples) >= 20:
                        med_w = float(np.median([s[0] for s in self.calibration_samples]))
                        med_d = float(np.median([s[1] for s in self.calibration_samples]))
                        self.calibrate(med_w, med_d)

                if self.is_calibrated and self.baseline_neck_head_dist and self.baseline_neck_head_dist > 0:
                    # Normalize against changes in camera distance
                    scale = shoulder_width / max(1e-5, self.baseline_shoulder_width)
                    norm_dist = curr_dist / max(1e-5, scale)
                    self.compression_ratio = norm_dist / self.baseline_neck_head_dist
                else:
                    self.compression_ratio = 1.0
        else:
            # Fallback based on head pose alone (roll & pitch)
            self.shoulder_tilt_deg = abs(head_roll_deg)
            self.compression_ratio = 1.0

        # Posture Classification Logic
        # 1. Head Dropped Forward (Chin sinking towards chest, classic sleep onset nodding)
        is_head_dropped = (self.head_pitch_deg > self.head_pitch_down_thresh_deg) or (self.compression_ratio < 0.70)

        # 2. Lateral Lean (Driver slumping against car door, pillar, or passenger seat)
        is_lateral_lean = (self.shoulder_tilt_deg > self.lateral_tilt_thresh_deg) or (abs(head_roll_deg) > 18.0)

        # 3. Slouching / Collapsed posture
        is_slouching = (self.compression_ratio < self.slouch_compression_ratio_thresh) and not is_head_dropped

        # Determine state
        if is_head_dropped:
            new_state = PostureState.HEAD_DROPPED
        elif is_lateral_lean:
            new_state = PostureState.LATERAL_LEAN
        elif is_slouching:
            new_state = PostureState.SLOUCHING
        else:
            new_state = PostureState.ACTIVE

        self.current_state = new_state

        # Compute duration of compromised posture
        is_compromised = (self.current_state != PostureState.ACTIVE)
        if is_compromised:
            if self.first_compromised_time is None:
                self.first_compromised_time = now
            self.compromised_duration = now - self.first_compromised_time
        else:
            self.first_compromised_time = None
            self.compromised_duration = 0.0

        # Posture Risk Score (0 - 100%)
        # Head drop has the highest immediate danger
        if self.current_state == PostureState.HEAD_DROPPED:
            risk = 65.0 + min(35.0, self.compromised_duration * 12.0)
        elif self.current_state == PostureState.LATERAL_LEAN:
            risk = 45.0 + min(40.0, self.compromised_duration * 8.0)
        elif self.current_state == PostureState.SLOUCHING:
            risk = 30.0 + min(35.0, self.compromised_duration * 5.0)
        else:
            risk = 0.0

        self.posture_risk_score = round(min(100.0, max(0.0, risk)), 1)

        return {
            "state": self.current_state,
            "is_active_posture": (self.current_state == PostureState.ACTIVE),
            "is_compromised": is_compromised,
            "compromised_duration_sec": round(self.compromised_duration, 1),
            "risk_score": self.posture_risk_score,
            "shoulder_tilt_deg": self.shoulder_tilt_deg,
            "head_pitch_deg": round(self.head_pitch_deg, 1),
            "compression_ratio": round(self.compression_ratio, 2)
        }
