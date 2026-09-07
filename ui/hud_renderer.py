"""
Automotive Heads-Up Display (HUD) Renderer
Draws high-tech cockpit telemetry overlays, landmark tracking highlights,
ocular metrics (EAR, MAR, PERCLOS), seat posture ergonomics, risk meters,
and emergency rest-stop recommendation cards.
"""

import math
import numpy as np
import time
from typing import Dict, List, Optional, Tuple

import cv2

from core.fusion import VigilanceLevel
from core.posture import PostureState


class HUDRenderer:
    """
    Renders an automotive telemetry HUD directly onto the video frame.
    """

    # Color definitions (BGR)
    COLOR_BG_DARK = (20, 20, 24)
    COLOR_CARD_BG = (28, 30, 36)
    COLOR_BORDER = (55, 60, 72)
    COLOR_TEXT_WHITE = (245, 245, 250)
    COLOR_TEXT_DIM = (160, 165, 175)
    COLOR_GREEN = (50, 205, 50)
    COLOR_YELLOW = (0, 215, 255)
    COLOR_ORANGE = (0, 140, 255)
    COLOR_RED = (40, 40, 240)
    COLOR_CYAN = (240, 200, 0)
    COLOR_PURPLE = (220, 80, 180)

    def __init__(self):
        self.flash_phase = 0.0

    def draw_hud(
        self,
        frame: np.ndarray,
        ocular_data: Dict[str, any],
        posture_data: Dict[str, any],
        fusion_data: Dict[str, any],
        alert_data: Dict[str, any],
        fps: float = 30.0,
        cardio_data: Optional[Dict[str, any]] = None
    ) -> np.ndarray:
        """
        Renders the complete cockpit HUD onto the provided frame (Ocular + Posture).
        """
        canvas = frame.copy()
        h, w = canvas.shape[:2]
        now = time.time()
        self.flash_phase += 0.2

        # 1. Draw facial & skeletal overlays
        self._draw_landmarks_overlay(canvas, ocular_data, posture_data)

        # 2. Draw Top Status Bar
        self._draw_top_bar(canvas, fusion_data, fps)

        # 3. Draw Left Ocular Telemetry Panel (EAR, MAR, PERCLOS, Yawns)
        self._draw_ocular_panel(canvas, ocular_data)

        # 4. Draw Right Seat Posture & Ergonomics Panel (Head Pitch, Tilt, Slouch)
        self._draw_posture_panel(canvas, posture_data)

        # 5. Draw Bottom Emergency Alarm Banner & Rest Stop Card if critical
        if fusion_data.get("is_critical", False) or alert_data.get("is_alarm_ringing", False):
            self._draw_critical_alarm_modal(canvas, fusion_data, alert_data)
        elif fusion_data.get("is_warning", False):
            self._draw_warning_banner(canvas, fusion_data)

        return canvas

    def _draw_landmarks_overlay(
        self,
        canvas: np.ndarray,
        ocular_data: Dict[str, any],
        posture_data: Dict[str, any]
    ):
        """Highlights eyes, lips, and posture alignment."""
        landmarks = ocular_data.get("landmarks_dict", {})
        if not landmarks:
            return

        # Eyes color based on closure
        eyes_closed = ocular_data.get("eyes_closed", False)
        eye_color = self.COLOR_RED if eyes_closed else self.COLOR_CYAN

        # Draw eye contours
        right_eye_pts = [np.array(landmarks[idx], dtype=np.int32) for idx in [33, 160, 158, 133, 153, 144] if idx in landmarks]
        left_eye_pts = [np.array(landmarks[idx], dtype=np.int32) for idx in [362, 385, 387, 263, 373, 380] if idx in landmarks]

        if len(right_eye_pts) == 6:
            cv2.polylines(canvas, [np.array(right_eye_pts)], isClosed=True, color=eye_color, thickness=2)
        if len(left_eye_pts) == 6:
            cv2.polylines(canvas, [np.array(left_eye_pts)], isClosed=True, color=eye_color, thickness=2)

        # Draw mouth contour
        is_yawn = ocular_data.get("is_yawning", False)
        mouth_color = self.COLOR_ORANGE if is_yawn else self.COLOR_GREEN
        mouth_pts = [np.array(landmarks[idx], dtype=np.int32) for idx in [78, 13, 308, 14] if idx in landmarks]
        if len(mouth_pts) == 4:
            cv2.polylines(canvas, [np.array(mouth_pts)], isClosed=True, color=mouth_color, thickness=2)

        # Draw shoulder posture line
        shoulders = ocular_data.get("shoulders", {})
        if shoulders.get("left") and shoulders.get("right"):
            lx, ly = int(shoulders["left"][0]), int(shoulders["left"][1])
            rx, ry = int(shoulders["right"][0]), int(shoulders["right"][1])
            is_active = posture_data.get("is_active_posture", True)
            posture_col = self.COLOR_GREEN if is_active else self.COLOR_ORANGE
            cv2.line(canvas, (lx, ly), (rx, ry), posture_col, 2)
            cv2.circle(canvas, (lx, ly), 5, posture_col, -1)
            cv2.circle(canvas, (rx, ry), 5, posture_col, -1)

    def _draw_top_bar(self, canvas: np.ndarray, fusion_data: Dict[str, any], fps: float):
        """Draws the top status header bar."""
        w = canvas.shape[1]
        cv2.rectangle(canvas, (0, 0), (w, 42), self.COLOR_BG_DARK, -1)
        cv2.line(canvas, (0, 42), (w, 42), self.COLOR_BORDER, 1)

        # App title
        cv2.putText(canvas, "DRIVER VIGILANCE SYSTEM", (14, 28), cv2.FONT_HERSHEY_DUPLEX, 0.65, self.COLOR_TEXT_WHITE, 1)

        # Risk score badge
        level = fusion_data.get("level", VigilanceLevel.ALERT)
        risk_score = fusion_data.get("composite_risk_score", 0.0)

        if level == VigilanceLevel.CRITICAL:
            badge_color = self.COLOR_RED
            status_str = f"CRITICAL DROWSINESS | RISK: {risk_score}%"
        elif level == VigilanceLevel.WARNING:
            badge_color = self.COLOR_ORANGE
            status_str = f"WARNING: FATIGUE | RISK: {risk_score}%"
        elif level == VigilanceLevel.CAUTION:
            badge_color = self.COLOR_YELLOW
            status_str = f"CAUTION | RISK: {risk_score}%"
        else:
            badge_color = self.COLOR_GREEN
            status_str = f"ALERT & ATTENTIVE | RISK: {risk_score}%"

        # Badge rect
        badge_w = 280
        badge_x = (w - badge_w) // 2
        cv2.rectangle(canvas, (badge_x, 8), (badge_x + badge_w, 34), badge_color, -1)
        cv2.putText(canvas, status_str, (badge_x + 12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)

        # FPS counter
        fps_text = f"FPS: {fps:.1f}"
        cv2.putText(canvas, fps_text, (w - 90, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.COLOR_TEXT_DIM, 1)

    def _draw_ocular_panel(self, canvas: np.ndarray, ocular_data: Dict[str, any]):
        """Renders Ocular telemetry card on left side."""
        card_x, card_y, card_w, card_h = 14, 52, 230, 200
        self._draw_translucent_card(canvas, card_x, card_y, card_w, card_h)

        cv2.putText(canvas, "OCULAR METRICS", (card_x + 10, card_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_CYAN, 1)

        # EAR Meter
        ear = ocular_data.get("ear", 0.30)
        eyes_closed_sec = ocular_data.get("eyes_closed_sec", 0.0)
        ear_text = f"EAR: {ear:.3f}"
        if eyes_closed_sec > 0:
            ear_text += f" (CLOSED {eyes_closed_sec:.1f}s)"
        ear_color = self.COLOR_RED if eyes_closed_sec >= 1.0 else (self.COLOR_YELLOW if eyes_closed_sec > 0 else self.COLOR_GREEN)
        cv2.putText(canvas, ear_text, (card_x + 10, card_y + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.4, ear_color, 1)
        self._draw_bar(canvas, card_x + 10, card_y + 50, 200, 8, min(1.0, ear / 0.45), ear_color)

        # MAR Meter
        mar = ocular_data.get("mar", 0.20)
        is_yawn = ocular_data.get("is_yawning", False)
        yawns_count = ocular_data.get("recent_yawns_count", 0)
        mar_text = f"MAR: {mar:.3f}"
        if is_yawn:
            mar_text += " (YAWNING!)"
        mar_color = self.COLOR_ORANGE if is_yawn else self.COLOR_GREEN
        cv2.putText(canvas, mar_text, (card_x + 10, card_y + 76), cv2.FONT_HERSHEY_SIMPLEX, 0.4, mar_color, 1)
        self._draw_bar(canvas, card_x + 10, card_y + 82, 200, 8, min(1.0, mar / 0.9), mar_color)

        # PERCLOS & Yawns info
        cv2.putText(canvas, f"Yawns (last 2m): {yawns_count}", (card_x + 10, card_y + 108), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_TEXT_DIM, 1)
        perclos = ocular_data.get("perclos_pct", 0.0)
        cv2.putText(canvas, f"PERCLOS: {perclos:.1f}%", (card_x + 10, card_y + 130), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_TEXT_DIM, 1)

        # Ocular Risk contribution
        risk = ocular_data.get("risk_score", 0.0)
        cv2.putText(canvas, f"Ocular Risk: {risk:.0f}%", (card_x + 10, card_y + 160), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLOR_TEXT_WHITE, 1)
        self._draw_bar(canvas, card_x + 10, card_y + 168, 200, 8, min(1.0, risk / 100.0), self.COLOR_CYAN)

    def _draw_posture_panel(self, canvas: np.ndarray, posture_data: Dict[str, any]):
        """Renders Driver Seat Posture & Ergonomics on right side."""
        w = canvas.shape[1]
        card_w, card_h = 230, 200
        card_x = w - card_w - 14
        card_y = 52

        self._draw_translucent_card(canvas, card_x, card_y, card_w, card_h)

        cv2.putText(canvas, "SEAT POSTURE", (card_x + 10, card_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLOR_PURPLE, 1)

        p_state = posture_data.get("state", PostureState.ACTIVE)
        p_dur = posture_data.get("compromised_duration_sec", 0.0)
        p_color = self.COLOR_GREEN if p_state == PostureState.ACTIVE else self.COLOR_RED

        state_label = p_state.replace("_", " ")
        if p_dur > 0:
            state_label += f" ({p_dur:.1f}s)"

        cv2.putText(canvas, "CURRENT POSITION:", (card_x + 10, card_y + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.COLOR_TEXT_DIM, 1)
        cv2.putText(canvas, state_label, (card_x + 10, card_y + 64), cv2.FONT_HERSHEY_SIMPLEX, 0.42, p_color, 1)

        # Head Pitch (drooping forward)
        pitch = posture_data.get("head_pitch_deg", 0.0)
        pitch_color = self.COLOR_RED if pitch > 18.0 else self.COLOR_GREEN
        cv2.putText(canvas, f"Head Pitch: {pitch:+.1f} deg", (card_x + 10, card_y + 92), cv2.FONT_HERSHEY_SIMPLEX, 0.38, pitch_color, 1)
        self._draw_bar(canvas, card_x + 10, card_y + 98, 200, 6, min(1.0, max(0.0, pitch / 30.0)), pitch_color)

        # Shoulder Tilt
        tilt = posture_data.get("shoulder_tilt_deg", 0.0)
        tilt_color = self.COLOR_ORANGE if tilt > 14.0 else self.COLOR_GREEN
        cv2.putText(canvas, f"Shoulder Tilt: {tilt:.1f} deg", (card_x + 10, card_y + 124), cv2.FONT_HERSHEY_SIMPLEX, 0.38, tilt_color, 1)
        self._draw_bar(canvas, card_x + 10, card_y + 130, 200, 6, min(1.0, max(0.0, tilt / 25.0)), tilt_color)

        # Posture Risk contribution
        p_risk = posture_data.get("risk_score", 0.0)
        cv2.putText(canvas, f"Posture Risk: {p_risk:.0f}%", (card_x + 10, card_y + 160), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.COLOR_TEXT_WHITE, 1)
        self._draw_bar(canvas, card_x + 10, card_y + 168, 200, 8, min(1.0, p_risk / 100.0), self.COLOR_PURPLE)

    def _draw_critical_alarm_modal(
        self,
        canvas: np.ndarray,
        fusion_data: Dict[str, any],
        alert_data: Dict[str, any]
    ):
        """Draws flashing emergency alert banner and recommended rest stop guidance card."""
        h, w = canvas.shape[:2]
        modal_w = min(680, w - 40)
        modal_h = 135
        modal_x = (w - modal_w) // 2
        modal_y = h - modal_h - 18

        is_flash = int(self.flash_phase) % 2 == 0
        bg_color = (25, 25, 180) if is_flash else (15, 15, 100)
        border_color = (0, 0, 255) if is_flash else (50, 50, 220)

        cv2.rectangle(canvas, (modal_x, modal_y), (modal_x + modal_w, modal_y + modal_h), bg_color, -1)
        cv2.rectangle(canvas, (modal_x, modal_y), (modal_x + modal_w, modal_y + modal_h), border_color, 3)

        # Emergency Title
        all_triggered = fusion_data.get("all_conditions_triggered", False)
        title_str = "CRITICAL: SLEEP ONSET DETECTED - ALL CONDITIONS TRIGGERED!" if all_triggered else "CRITICAL DROWSINESS ALERT - PULL OVER SAFELY"
        cv2.putText(canvas, title_str, (modal_x + 14, modal_y + 28), cv2.FONT_HERSHEY_DUPLEX, 0.58, (255, 255, 255), 2)

        # Active triggers list
        reasons = fusion_data.get("trigger_reasons", [])
        reasons_str = "Triggers: " + " | ".join(reasons[:2]) if reasons else "Severe microsleep / fatigue detected."
        cv2.putText(canvas, reasons_str, (modal_x + 14, modal_y + 54), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 255), 1)

        # Safe Stop Guidance (Nearest Petrol Pump / Rest Area)
        stop = alert_data.get("nearest_stop", {})
        stop_name = stop.get("name", "Nearest Petrol Pump & Rest Area")
        dist = stop.get("distance_km", 1.2)
        eta = stop.get("eta_mins", 2)
        amenities = ", ".join(stop.get("amenities", [])[:3])

        # Driver GPS info
        gps_info = alert_data.get("driver_gps", {})
        lat = gps_info.get("lat", 12.9695)
        lon = gps_info.get("lon", 79.1455)
        city = gps_info.get("label", "Current Location")
        gps_str = f"DRIVER GPS: [{lat:.4f}°N, {lon:.4f}°E] ({city})"

        cv2.putText(canvas, f"NEAREST PETROL PUMP / REST: {stop_name}", (modal_x + 14, modal_y + 80), cv2.FONT_HERSHEY_DUPLEX, 0.48, (50, 255, 255), 1)
        cv2.putText(canvas, f"Distance: {dist} km  |  ETA: {eta} min  |  {gps_str}", (modal_x + 14, modal_y + 104), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
        cv2.putText(canvas, f"Services: {amenities}", (modal_x + 14, modal_y + 122), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 220, 255), 1)

        # Siren indicator
        cv2.putText(canvas, "ALARM SOUNDING", (modal_x + modal_w - 180, modal_y + 28), cv2.FONT_HERSHEY_DUPLEX, 0.48, (0, 255, 255), 1)

    def _draw_warning_banner(self, canvas: np.ndarray, fusion_data: Dict[str, any]):
        """Draws amber caution banner at bottom."""
        h, w = canvas.shape[:2]
        banner_h = 36
        banner_y = h - banner_h - 10
        cv2.rectangle(canvas, (40, banner_y), (w - 40, banner_y + banner_h), (0, 100, 160), -1)
        cv2.rectangle(canvas, (40, banner_y), (w - 40, banner_y + banner_h), self.COLOR_ORANGE, 2)
        cv2.putText(canvas, "FATIGUE WARNING: Driver is showing early signs of drowsiness. Plan a rest break.", (55, banner_y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

    def _draw_translucent_card(self, canvas: np.ndarray, x: int, y: int, w: int, h: int):
        """Draws card with semi-transparent dark background."""
        sub_img = canvas[y:y+h, x:x+w]
        if sub_img.shape[0] == h and sub_img.shape[1] == w:
            card_fill = np.full((h, w, 3), self.COLOR_CARD_BG, dtype=np.uint8)
            cv2.addWeighted(card_fill, 0.85, sub_img, 0.15, 0, sub_img)
            cv2.rectangle(canvas, (x, y), (x + w, y + h), self.COLOR_BORDER, 1)

    @staticmethod
    def _draw_bar(canvas: np.ndarray, x: int, y: int, w: int, h: int, ratio: float, color: Tuple[int, int, int]):
        """Draws progress / meter bar."""
        cv2.rectangle(canvas, (x, y), (x + w, y + h), (45, 48, 56), -1)
        fill_w = max(0, min(w, int(w * ratio)))
        if fill_w > 0:
            cv2.rectangle(canvas, (x, y), (x + fill_w, y + h), color, -1)
