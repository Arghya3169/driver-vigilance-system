"""
Synthetic Driver Face & Cockpit Simulation Generator
Generates realistic animated driver frames with controllable eyes (blinks/closure),
mouth (speaking/yawning), head pitch (nodding off), and shoulder position for testing.
"""

import math
import numpy as np
import time
from typing import Dict, Optional, Tuple

import cv2


class SyntheticDriverGenerator:
    """
    Renders an animated driver inside a vehicle cabin.
    Allows exact testing of EAR, MAR, head droop, and multi-modal fatigue.
    """

    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height

        # Driver state controls
        self.eye_openness = 1.0     # 1.0 = wide open, 0.0 = completely closed
        self.mouth_openness = 0.0   # 0.0 = closed, 1.0 = wide yawn
        self.head_pitch_down = 0.0  # 0.0 = upright, 1.0 = chin on chest
        self.lateral_lean = 0.0     # -1.0 = left, 0.0 = center, +1.0 = right

        # Natural biological micro-movements
        self.phase = 0.0

    def set_states(
        self,
        eye_openness: float = 1.0,
        mouth_openness: float = 0.0,
        head_pitch_down: float = 0.0,
        lateral_lean: float = 0.0
    ):
        self.eye_openness = max(0.0, min(1.0, eye_openness))
        self.mouth_openness = max(0.0, min(1.0, mouth_openness))
        self.head_pitch_down = max(0.0, min(1.0, head_pitch_down))
        self.lateral_lean = max(-1.0, min(1.0, lateral_lean))

    def get_ground_truth_telemetry(self) -> Dict[str, any]:
        """Calculates exact EAR, MAR, head pitch, and posture metrics matching the simulated states."""
        # Active EAR is ~0.34; closed eye EAR is ~0.10
        ear = 0.08 + 0.28 * self.eye_openness
        # Nominal MAR is ~0.18; wide yawn is ~0.78
        mar = 0.18 + 0.60 * self.mouth_openness

        pitch_deg = self.head_pitch_down * 32.0  # 0 to 32 degrees down
        tilt_deg = abs(self.lateral_lean) * 22.0  # 0 to 22 degrees tilt

        return {
            "ear": round(ear, 3),
            "mar": round(mar, 3),
            "pitch_deg": round(pitch_deg, 1),
            "tilt_deg": round(tilt_deg, 1),
            "eye_openness": self.eye_openness,
            "mouth_openness": self.mouth_openness,
            "head_pitch_down": self.head_pitch_down,
            "lateral_lean": self.lateral_lean
        }

    def get_synthetic_landmarks(self) -> Dict[int, Tuple[float, float]]:
        """Synthesizes Face Mesh landmark coordinates matching the rendered avatar."""
        w, h = self.width, self.height
        center_x = int(w * 0.5 + self.lateral_lean * 70.0)
        slump_y = int(self.head_pitch_down * 50.0)
        head_y = int(h * 0.45 + slump_y)
        brow_y = head_y - int(100 * 0.4) + 22
        eye_y = brow_y + 16
        eye_half_h = max(1, int(12 * self.eye_openness))
        nose_y = eye_y + 24
        mouth_y = nose_y + 28
        mouth_h = max(2, int(38 * self.mouth_openness))

        lms = {}
        # Nose (1) & Chin (152)
        lms[1] = (float(center_x), float(nose_y))
        lms[152] = (float(center_x), float(head_y + 90))

        # Left eye (driver right: 33, 160, 158, 133, 153, 144)
        lx = center_x - 32
        lms[33] = (float(lx - 16), float(eye_y))
        lms[133] = (float(lx + 16), float(eye_y))
        lms[160] = (float(lx - 6), float(eye_y - eye_half_h))
        lms[158] = (float(lx + 6), float(eye_y - eye_half_h))
        lms[144] = (float(lx - 6), float(eye_y + eye_half_h))
        lms[153] = (float(lx + 6), float(eye_y + eye_half_h))

        # Right eye (driver left: 362, 385, 387, 263, 373, 380)
        rx = center_x + 32
        lms[362] = (float(rx - 16), float(eye_y))
        lms[263] = (float(rx + 16), float(eye_y))
        lms[385] = (float(rx - 6), float(eye_y - eye_half_h))
        lms[387] = (float(rx + 6), float(eye_y - eye_half_h))
        lms[380] = (float(rx - 6), float(eye_y + eye_half_h))
        lms[373] = (float(rx + 6), float(eye_y + eye_half_h))

        # Mouth: left 78, right 308, top 13, bottom 14
        lms[78] = (float(center_x - 24), float(mouth_y))
        lms[308] = (float(center_x + 24), float(mouth_y))
        lms[13] = (float(center_x), float(mouth_y - mouth_h * 0.5))
        lms[14] = (float(center_x), float(mouth_y + mouth_h * 0.5))

        # Forehead (10, 67, 109, 297, 338)
        fy = head_y - int(100 * 0.4)
        lms[10] = (float(center_x), float(fy - 10))
        lms[67] = (float(center_x - 25), float(fy))
        lms[109] = (float(center_x - 12), float(fy - 5))
        lms[297] = (float(center_x + 25), float(fy))
        lms[338] = (float(center_x + 12), float(fy - 5))

        return lms

    def generate_frame(self) -> np.ndarray:
        """Draws one frame of the synthetic driver in car cockpit."""
        self.phase += 0.08
        w, h = self.width, self.height
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # 1. Car Cabin Background
        # Windshield view (night highway with distant streetlamps)
        frame[0:int(h * 0.75), :] = [30, 25, 20]
        # Road lane markings
        cv2.line(frame, (int(w * 0.3), h), (int(w * 0.45), int(h * 0.35)), (50, 60, 70), 2)
        cv2.line(frame, (int(w * 0.7), h), (int(w * 0.55), int(h * 0.35)), (50, 60, 70), 2)

        # Driver seat headrest & cabin pillars
        seat_color = (40, 42, 48)
        cv2.rectangle(frame, (int(w * 0.22), int(h * 0.20)), (int(w * 0.78), int(h * 0.70)), seat_color, -1)
        cv2.ellipse(frame, (int(w * 0.5), int(h * 0.20)), (int(w * 0.28), int(h * 0.12)), 0, 180, 360, seat_color, -1)

        # 2. Driver Torso & Shoulders
        center_x = int(w * 0.5 + self.lateral_lean * 70.0)
        # Sinking down if head dropped / slouching
        slump_y = int(self.head_pitch_down * 50.0)
        shoulder_y = int(h * 0.75 + slump_y)

        # Shoulders tilt with lateral lean
        tilt_dy = int(self.lateral_lean * 25.0)
        left_sh_x = center_x - 160
        left_sh_y = shoulder_y - tilt_dy
        right_sh_x = center_x + 160
        right_sh_y = shoulder_y + tilt_dy

        # Driver jacket
        jacket_color = (60, 50, 45)
        torso_pts = np.array([
            (left_sh_x, left_sh_y),
            (right_sh_x, right_sh_y),
            (right_sh_x + 30, h),
            (left_sh_x - 30, h)
        ], dtype=np.int32)
        cv2.fillPoly(frame, [torso_pts], jacket_color)

        # 3. Driver Neck & Head
        head_y = int(h * 0.45 + slump_y)
        head_x = center_x
        # Neck
        cv2.rectangle(frame, (head_x - 30, head_y), (head_x + 30, shoulder_y), (180, 160, 140), -1)

        # Head oval
        head_w = 75
        head_h = 100
        skin_color = (195, 175, 155)
        cv2.ellipse(frame, (head_x, head_y), (head_w, head_h), 0, 0, 360, skin_color, -1)

        # Hair
        cv2.ellipse(frame, (head_x, head_y - int(head_h * 0.45)), (head_w + 5, int(head_h * 0.6)), 0, 180, 360, (40, 35, 30), -1)

        # 4. Forehead region (for rPPG)
        forehead_y = head_y - int(head_h * 0.4)
        # Add subtle green channel pulsatile tint for rPPG simulation
        pulse_tint = int(math.sin(self.phase * 2.0) * 4)
        cv2.ellipse(frame, (head_x, forehead_y), (35, 18), 0, 0, 360, (195, 175 + pulse_tint, 155), -1)

        # Eyebrows
        brow_y = forehead_y + 22
        cv2.line(frame, (head_x - 48, brow_y), (head_x - 14, brow_y - 2), (50, 40, 35), 4)
        cv2.line(frame, (head_x + 14, brow_y - 2), (head_x + 48, brow_y), (50, 40, 35), 4)

        # 5. Eyes (EAR simulation)
        eye_y = brow_y + 16
        eye_half_w = 16
        eye_half_h = max(1, int(12 * self.eye_openness))

        # Eye sockets / eyelids
        cv2.ellipse(frame, (head_x - 32, eye_y), (eye_half_w + 2, 13), 0, 0, 360, (175, 155, 135), -1)
        cv2.ellipse(frame, (head_x + 32, eye_y), (eye_half_w + 2, 13), 0, 0, 360, (175, 155, 135), -1)

        # Left eye (driver right)
        if self.eye_openness > 0.15:
            cv2.ellipse(frame, (head_x - 32, eye_y), (eye_half_w, eye_half_h), 0, 0, 360, (240, 240, 240), -1)
            cv2.circle(frame, (head_x - 32, eye_y), min(eye_half_h, 6), (70, 50, 30), -1)
            cv2.circle(frame, (head_x - 32, eye_y), max(1, min(eye_half_h - 1, 3)), (0, 0, 0), -1)
        else:
            # Closed eyelids with crease and lashes
            cv2.ellipse(frame, (head_x - 32, eye_y + 1), (eye_half_w, 4), 0, 0, 180, (90, 70, 60), 2)
            cv2.line(frame, (head_x - 32 - eye_half_w, eye_y), (head_x - 32 + eye_half_w, eye_y), (100, 80, 70), 2)

        # Right eye (driver left)
        if self.eye_openness > 0.15:
            cv2.ellipse(frame, (head_x + 32, eye_y), (eye_half_w, eye_half_h), 0, 0, 360, (240, 240, 240), -1)
            cv2.circle(frame, (head_x + 32, eye_y), min(eye_half_h, 6), (70, 50, 30), -1)
            cv2.circle(frame, (head_x + 32, eye_y), max(1, min(eye_half_h - 1, 3)), (0, 0, 0), -1)
        else:
            # Closed eyelids with crease and lashes
            cv2.ellipse(frame, (head_x + 32, eye_y + 1), (eye_half_w, 4), 0, 0, 180, (90, 70, 60), 2)
            cv2.line(frame, (head_x + 32 - eye_half_w, eye_y), (head_x + 32 + eye_half_w, eye_y), (100, 80, 70), 2)

        # 6. Nose
        nose_y = eye_y + 24
        cv2.line(frame, (head_x, eye_y + 6), (head_x, nose_y), (160, 140, 120), 2)
        cv2.line(frame, (head_x - 6, nose_y + 2), (head_x + 6, nose_y + 2), (150, 130, 110), 2)

        # 7. Mouth (MAR simulation)
        mouth_y = nose_y + 28
        mouth_w = 24
        # Max mouth vertical opening: ~32 pixels for wide yawn
        mouth_h = max(2, int(30 * self.mouth_openness))

        if self.mouth_openness > 0.35:
            # Yawn: dark mouth cavity
            cv2.ellipse(frame, (head_x, mouth_y), (mouth_w, mouth_h), 0, 0, 360, (30, 20, 25), -1)
            cv2.ellipse(frame, (head_x, mouth_y), (mouth_w, mouth_h), 0, 0, 360, (140, 80, 80), 2)
        else:
            # Normal lips
            cv2.ellipse(frame, (head_x, mouth_y), (mouth_w, max(2, mouth_h)), 0, 0, 360, (150, 90, 90), -1)

        # 8. Steering Wheel Foreground
        cv2.circle(frame, (int(w * 0.5), int(h * 1.05)), 170, (45, 45, 50), 24)

        return frame
