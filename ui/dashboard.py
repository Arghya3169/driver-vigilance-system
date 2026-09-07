"""
Driver Vigilance System - Interactive Cockpit Dashboard
A high-tech desktop GUI providing real-time camera video with HUD overlays,
ocular dynamics (EAR/MAR), seat posture ergonomics, multi-factor test controls,
emergency alarms, and nearest rest-stop navigation assistance.
"""

import math
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

from core.alert import AlertManager
from core.fusion import MultiModalVigilanceFusion, VigilanceLevel
from core.mock_data import RestStopCatalog
from core.posture import PostureState, SeatPostureDetector
from core.synthetic_driver import SyntheticDriverGenerator
from core.vision import FaceOcularDetector
from ui.hud_renderer import HUDRenderer


class VigilanceDashboard:
    """
    Main Cockpit GUI application (Ocular + Posture multi-factor vigilance).
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Driver Vigilance Safety System (EAR, MAR & Seat Posture)")
        self.root.geometry("1280x820")
        self.root.minsize(1100, 720)
        self.root.configure(bg="#121418")

        # Initialize Core Engines
        self.vision_detector = FaceOcularDetector()
        self.posture_detector = SeatPostureDetector()
        self.fusion_engine = MultiModalVigilanceFusion()
        self.alert_manager = AlertManager(enable_sound=True, enable_voice=True)
        self.hud_renderer = HUDRenderer()
        self.synthetic_driver = SyntheticDriverGenerator()

        # Video source state
        self.source_mode = "synthetic"  # "synthetic" or "webcam"
        self.cap: Optional[cv2.VideoCapture] = None
        self.webcam_index = 0
        self.is_running = True

        # FPS calculation
        self.last_frame_time = time.time()
        self.current_fps = 30.0

        # Simulation override state for testing
        self.override_eye_closed = False
        self.override_yawn = False
        self.override_bad_posture = False
        self.override_slouch = False
        self.override_all_conditions = False

        # Build GUI
        self._setup_styles()
        self._build_layout()

        # Try auto-detecting camera
        self._check_webcam_availability()

        # Start Video & Processing Loop
        self.root.after(20, self._process_frame_loop)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background="#121418")
        style.configure("Card.TFrame", background="#1a1d24", relief="flat")
        style.configure("TLabel", background="#121418", foreground="#e6e8ee", font=("Segoe UI", 9))
        style.configure("Header.TLabel", background="#1a1d24", foreground="#00e5ff", font=("Segoe UI", 11, "bold"))
        style.configure("Title.TLabel", background="#121418", foreground="#ffffff", font=("Segoe UI", 14, "bold"))
        style.configure("Muted.TLabel", background="#1a1d24", foreground="#9da3b4", font=("Segoe UI", 8))
        style.configure("Value.TLabel", background="#1a1d24", foreground="#ffffff", font=("Segoe UI", 10, "bold"))

        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=5)
        style.configure("Emergency.TButton", background="#d32f2f", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.configure("Reset.TButton", background="#388e3c", foreground="#ffffff", font=("Segoe UI", 9, "bold"))

    def _build_layout(self):
        # Header banner
        header_frame = tk.Frame(self.root, bg="#181b22", height=50)
        header_frame.pack(side=tk.TOP, fill=tk.X)

        title_lbl = tk.Label(
            header_frame,
            text="🚘 DRIVER VIGILANCE SYSTEM (EAR, MAR & SEAT POSTURE)",
            bg="#181b22",
            fg="#00f0ff",
            font=("Segoe UI", 13, "bold")
        )
        title_lbl.pack(side=tk.LEFT, padx=16, pady=10)

        self.status_pill = tk.Label(
            header_frame,
            text="SYSTEM READY | SENSORS NOMINAL",
            bg="#2e7d32",
            fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=4
        )
        self.status_pill.pack(side=tk.RIGHT, padx=16, pady=8)

        # Main Split Content
        main_container = tk.Frame(self.root, bg="#121418")
        main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Left Column: Video Feed Canvas
        left_frame = tk.Frame(main_container, bg="#121418")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Video Canvas
        self.video_canvas = tk.Canvas(left_frame, bg="#0d0e12", highlightthickness=1, highlightbackground="#2d3342")
        self.video_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Video Controls Bar
        vid_ctrls = tk.Frame(left_frame, bg="#181b22", height=42)
        vid_ctrls.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 0))

        tk.Label(vid_ctrls, text="Video Stream Source:", bg="#181b22", fg="#c4c9d8", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=10, pady=8)

        self.source_var = tk.StringVar(value="synthetic")
        self.source_cb = ttk.Combobox(
            vid_ctrls,
            textvariable=self.source_var,
            values=["Synthetic Driver Simulator", "Live Webcam 0", "Live Webcam 1"],
            state="readonly",
            width=26
        )
        self.source_cb.pack(side=tk.LEFT, padx=6, pady=8)
        self.source_cb.bind("<<ComboboxSelected>>", self._on_source_change)

        self.btn_recalibrate = tk.Button(
            vid_ctrls,
            text="Recalibrate Posture Baseline",
            bg="#263238",
            fg="#eceff1",
            relief="groove",
            font=("Segoe UI", 8, "bold"),
            command=self._on_recalibrate
        )
        self.btn_recalibrate.pack(side=tk.RIGHT, padx=10, pady=8)

        # Right Column: Telemetry, Test Bench & Rest Stop Navigation
        right_frame = tk.Frame(main_container, bg="#121418", width=420)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(12, 0))
        right_frame.pack_propagate(False)

        # 1. Multi-Factor Risk & Status Card
        card_risk = tk.Frame(right_frame, bg="#1a1d24", bd=1, relief="solid")
        card_risk.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        tk.Label(card_risk, text="OCULAR & SEAT POSTURE METRICS", bg="#1a1d24", fg="#00f0ff", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        metrics_grid = tk.Frame(card_risk, bg="#1a1d24")
        metrics_grid.pack(fill=tk.X, padx=12, pady=4)

        # EAR Row
        tk.Label(metrics_grid, text="Eye Ratio (EAR):", bg="#1a1d24", fg="#9da3b4").grid(row=0, column=0, sticky="w", pady=2)
        self.lbl_ear_val = tk.Label(metrics_grid, text="0.320 (Open)", bg="#1a1d24", fg="#00e676", font=("Segoe UI", 9, "bold"))
        self.lbl_ear_val.grid(row=0, column=1, sticky="e", pady=2)

        # MAR Row
        tk.Label(metrics_grid, text="Mouth Ratio (MAR):", bg="#1a1d24", fg="#9da3b4").grid(row=1, column=0, sticky="w", pady=2)
        self.lbl_mar_val = tk.Label(metrics_grid, text="0.180 (Normal)", bg="#1a1d24", fg="#00e676", font=("Segoe UI", 9, "bold"))
        self.lbl_mar_val.grid(row=1, column=1, sticky="e", pady=2)

        # PERCLOS Row
        tk.Label(metrics_grid, text="PERCLOS (% Eye Closure):", bg="#1a1d24", fg="#9da3b4").grid(row=2, column=0, sticky="w", pady=2)
        self.lbl_perclos_val = tk.Label(metrics_grid, text="0.0%", bg="#1a1d24", fg="#00e676", font=("Segoe UI", 9, "bold"))
        self.lbl_perclos_val.grid(row=2, column=1, sticky="e", pady=2)

        # Posture Row
        tk.Label(metrics_grid, text="Seat Posture:", bg="#1a1d24", fg="#9da3b4").grid(row=3, column=0, sticky="w", pady=2)
        self.lbl_posture_val = tk.Label(metrics_grid, text="ACTIVE ATTENTIVE", bg="#1a1d24", fg="#00e676", font=("Segoe UI", 9, "bold"))
        self.lbl_posture_val.grid(row=3, column=1, sticky="e", pady=2)

        # Angles Row
        tk.Label(metrics_grid, text="Head Pitch / Shoulder Tilt:", bg="#1a1d24", fg="#9da3b4").grid(row=4, column=0, sticky="w", pady=2)
        self.lbl_angles_val = tk.Label(metrics_grid, text="Pitch: 0.0° | Tilt: 0.0°", bg="#1a1d24", fg="#e0e0e0", font=("Segoe UI", 8))
        self.lbl_angles_val.grid(row=4, column=1, sticky="e", pady=2)

        # Composite Risk Gauge
        tk.Label(metrics_grid, text="Overall Fatigue Risk:", bg="#1a1d24", fg="#ffffff", font=("Segoe UI", 9, "bold")).grid(row=5, column=0, sticky="w", pady=(8, 4))
        self.lbl_risk_val = tk.Label(metrics_grid, text="0.0% (NORMAL)", bg="#1a1d24", fg="#00e676", font=("Segoe UI", 10, "bold"))
        self.lbl_risk_val.grid(row=5, column=1, sticky="e", pady=(8, 4))

        # 2. Multi-Modal Fatigue Test Bench (Quick Injection Buttons)
        card_test = tk.Frame(right_frame, bg="#1a1d24", bd=1, relief="solid")
        card_test.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))

        tk.Label(card_test, text="SIMULATION & FATIGUE INJECTION BENCH", bg="#1a1d24", fg="#ffb300", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 6))

        btn_grid = tk.Frame(card_test, bg="#1a1d24")
        btn_grid.pack(fill=tk.X, padx=12, pady=(0, 10))

        self.btn_norm = tk.Button(btn_grid, text="Awake / Active", bg="#1e3a24", fg="#a5d6a7", font=("Segoe UI", 8, "bold"), command=self._sim_normal)
        self.btn_norm.grid(row=0, column=0, padx=3, pady=3, sticky="ew")

        self.btn_eyes = tk.Button(btn_grid, text="Toggle Eye Closure", bg="#37474f", fg="#eceff1", font=("Segoe UI", 8), command=self._sim_toggle_eyes)
        self.btn_eyes.grid(row=0, column=1, padx=3, pady=3, sticky="ew")

        self.btn_yawn = tk.Button(btn_grid, text="Trigger Yawning", bg="#37474f", fg="#eceff1", font=("Segoe UI", 8), command=self._sim_toggle_yawn)
        self.btn_yawn.grid(row=1, column=0, padx=3, pady=3, sticky="ew")

        self.btn_posture = tk.Button(btn_grid, text="Head Dropped (Chin on Chest)", bg="#37474f", fg="#eceff1", font=("Segoe UI", 8), command=self._sim_toggle_posture)
        self.btn_posture.grid(row=1, column=1, padx=3, pady=3, sticky="ew")

        self.btn_slouch = tk.Button(btn_grid, text="Slouch / Lateral Lean", bg="#37474f", fg="#eceff1", font=("Segoe UI", 8), command=self._sim_toggle_slouch)
        self.btn_slouch.grid(row=2, column=0, columnspan=2, padx=3, pady=3, sticky="ew")

        # Big "TRIGGER ALL CONDITIONS" Button
        self.btn_all_conds = tk.Button(
            btn_grid,
            text="🚨 TRIGGER ALL CONDITIONS (Eyes Closed + Inactive Posture)",
            bg="#b71c1c",
            fg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            relief="raised",
            command=self._sim_trigger_all_conditions
        )
        self.btn_all_conds.grid(row=3, column=0, columnspan=2, padx=3, pady=(6, 2), sticky="ew")

        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # 3. Emergency Alarm & Safe Stop Guidance Card
        card_alarm = tk.Frame(right_frame, bg="#1a1d24", bd=1, relief="solid")
        card_alarm.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        tk.Label(card_alarm, text="ALARM & NEAREST PETROL PUMP / REST STOP", bg="#1a1d24", fg="#ff5252", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))

        self.lbl_gps_status = tk.Label(
            card_alarm,
            text="📍 Driver GPS: Resolving location...",
            bg="#1a1d24",
            fg="#80d8ff",
            font=("Segoe UI", 8, "bold")
        )
        self.lbl_gps_status.pack(anchor="w", padx=12, pady=(0, 4))

        # Audio toggles
        audio_frame = tk.Frame(card_alarm, bg="#1a1d24")
        audio_frame.pack(fill=tk.X, padx=12, pady=2)

        self.sound_enabled_var = tk.BooleanVar(value=True)
        self.chk_sound = tk.Checkbutton(
            audio_frame,
            text="Acoustic Beeps",
            variable=self.sound_enabled_var,
            bg="#1a1d24",
            fg="#e0e0e0",
            selectcolor="#263238",
            command=self._on_toggle_sound
        )
        self.chk_sound.pack(side=tk.LEFT)

        self.voice_enabled_var = tk.BooleanVar(value=True)
        self.chk_voice = tk.Checkbutton(
            audio_frame,
            text="Voice Speech Alerts",
            variable=self.voice_enabled_var,
            bg="#1a1d24",
            fg="#e0e0e0",
            selectcolor="#263238",
            command=self._on_toggle_voice
        )
        self.chk_voice.pack(side=tk.LEFT, padx=12)

        self.btn_silence = tk.Button(
            audio_frame,
            text="Silence Alarm",
            bg="#455a64",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            command=self._on_silence_alarm
        )
        self.btn_silence.pack(side=tk.RIGHT)

        # Recommended Nearest Petrol Pump / Rest Stop Info Box
        self.rest_box = tk.Frame(card_alarm, bg="#14171d", bd=1, relief="groove")
        self.rest_box.pack(fill=tk.X, padx=12, pady=6)

        self.lbl_rest_name = tk.Label(self.rest_box, text="Locating nearest petrol pump / rest stop...", bg="#14171d", fg="#ffeb3b", font=("Segoe UI", 9, "bold"))
        self.lbl_rest_name.pack(anchor="w", padx=8, pady=(6, 2))

        self.lbl_rest_meta = tk.Label(
            self.rest_box,
            text="Distance: -- km  |  ETA: -- mins",
            bg="#14171d",
            fg="#ffffff",
            font=("Segoe UI", 8)
        )
        self.lbl_rest_meta.pack(anchor="w", padx=8, pady=1)

        self.lbl_rest_amenities = tk.Label(
            self.rest_box,
            text="Amenities: Fuel, Restrooms, Emergency Parking",
            bg="#14171d",
            fg="#90a4ae",
            font=("Segoe UI", 8)
        )
        self.lbl_rest_amenities.pack(anchor="w", padx=8, pady=1)

        # Live Google Maps Directions Button
        self.btn_open_maps = tk.Button(
            self.rest_box,
            text="📍 Open Live Route in Google Maps",
            bg="#1565c0",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
            relief="raised",
            command=self._on_navigate_maps
        )
        self.btn_open_maps.pack(fill=tk.X, padx=8, pady=(4, 6))

        # Rest Stops Listbox
        tk.Label(card_alarm, text="Nearby Safe Havens & Fuel Plazas:", bg="#1a1d24", fg="#9da3b4", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(4, 2))

        self.rest_listbox = tk.Listbox(card_alarm, bg="#0f1115", fg="#cfd8dc", selectbackground="#1e88e5", font=("Segoe UI", 8), height=3)
        self.rest_listbox.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self._populate_rest_stops()

    def _populate_rest_stops(self):
        self.rest_listbox.delete(0, tk.END)
        for stop in RestStopCatalog.get_all_recommendations():
            text = f"• {stop['name']} ({stop['distance_km']} km, ETA: {stop['eta_mins']}m) - {stop['type']}"
            self.rest_listbox.insert(tk.END, text)

    def _check_webcam_availability(self):
        """Checks if a webcam is physically connected and working."""
        try:
            test_cap = cv2.VideoCapture(0)
            if test_cap is not None and test_cap.isOpened():
                ret, _ = test_cap.read()
                test_cap.release()
                if ret:
                    self.source_cb.current(1)  # Select Live Webcam 0
                    self._on_source_change(None)
                    return
        except Exception:
            pass
        self.source_cb.current(0)
        self._on_source_change(None)

    def _on_source_change(self, event):
        val = self.source_var.get()
        if "Webcam 0" in val:
            self._set_webcam(0)
        elif "Webcam 1" in val:
            self._set_webcam(1)
        else:
            self._set_synthetic()

    def _set_webcam(self, idx: int):
        if self.cap is not None:
            self.cap.release()
        try:
            self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
            if self.cap.isOpened():
                self.source_mode = "webcam"
                self.webcam_index = idx
                return
        except Exception:
            pass
        messagebox.showwarning("Webcam Notice", f"Camera {idx} could not be opened. Falling back to Synthetic Simulator.")
        self.source_cb.current(0)
        self._set_synthetic()

    def _set_synthetic(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.source_mode = "synthetic"

    def _on_recalibrate(self):
        self.posture_detector.is_calibrated = False
        messagebox.showinfo("Recalibrated", "Posture baseline reset for current driver.")

    def _on_toggle_sound(self):
        self.alert_manager.enable_sound = self.sound_enabled_var.get()

    def _on_toggle_voice(self):
        self.alert_manager.enable_voice = self.voice_enabled_var.get()

    def _on_silence_alarm(self):
        self.alert_manager.silence_alarm()
        self.override_all_conditions = False
        self._sim_normal()

    # Simulation Controls
    def _sim_normal(self):
        self.override_eye_closed = False
        self.override_yawn = False
        self.override_bad_posture = False
        self.override_slouch = False
        self.override_all_conditions = False

        self.synthetic_driver.set_states(eye_openness=1.0, mouth_openness=0.0, head_pitch_down=0.0, lateral_lean=0.0)
        self.alert_manager.silence_alarm()

        self.btn_eyes.configure(bg="#37474f", fg="#eceff1")
        self.btn_yawn.configure(bg="#37474f", fg="#eceff1")
        self.btn_posture.configure(bg="#37474f", fg="#eceff1")
        self.btn_slouch.configure(bg="#37474f", fg="#eceff1")

    def _sim_toggle_eyes(self):
        self.override_eye_closed = not self.override_eye_closed
        self.synthetic_driver.eye_openness = 0.0 if self.override_eye_closed else 1.0
        self.btn_eyes.configure(bg="#c62828" if self.override_eye_closed else "#37474f", fg="#ffffff")

    def _sim_toggle_yawn(self):
        self.override_yawn = not self.override_yawn
        self.synthetic_driver.mouth_openness = 1.0 if self.override_yawn else 0.0
        self.btn_yawn.configure(bg="#ef6c00" if self.override_yawn else "#37474f", fg="#ffffff")

    def _sim_toggle_posture(self):
        self.override_bad_posture = not self.override_bad_posture
        if self.override_bad_posture:
            self.synthetic_driver.head_pitch_down = 0.90
            self.synthetic_driver.lateral_lean = 0.2
        else:
            self.synthetic_driver.head_pitch_down = 0.0
            self.synthetic_driver.lateral_lean = 0.0
        self.btn_posture.configure(bg="#6a1b9a" if self.override_bad_posture else "#37474f", fg="#ffffff")

    def _sim_toggle_slouch(self):
        self.override_slouch = not self.override_slouch
        if self.override_slouch:
            self.synthetic_driver.head_pitch_down = 0.4
            self.synthetic_driver.lateral_lean = 0.6
        else:
            self.synthetic_driver.head_pitch_down = 0.0
            self.synthetic_driver.lateral_lean = 0.0
        self.btn_slouch.configure(bg="#4a148c" if self.override_slouch else "#37474f", fg="#ffffff")

    def _sim_trigger_all_conditions(self):
        """Simulates all conditions simultaneously: Eye closure + Head drop / Inactive Posture."""
        self.override_all_conditions = True
        self.override_eye_closed = True
        self.override_yawn = False
        self.override_bad_posture = True

        self.synthetic_driver.set_states(eye_openness=0.0, mouth_openness=0.0, head_pitch_down=0.9, lateral_lean=0.5)

        self.btn_eyes.configure(bg="#c62828", fg="#ffffff")
        self.btn_posture.configure(bg="#6a1b9a", fg="#ffffff")

    def _process_frame_loop(self):
        """Main real-time frame acquisition, computer vision, fusion, and rendering loop."""
        if not self.is_running:
            return

        now = time.time()
        dt = max(0.001, now - self.last_frame_time)
        self.last_frame_time = now
        self.current_fps = 0.9 * self.current_fps + 0.1 * (1.0 / dt)

        # 1. Acquire Frame
        frame = None
        if self.source_mode == "webcam" and self.cap is not None and self.cap.isOpened():
            ret, cam_frame = self.cap.read()
            if ret and cam_frame is not None:
                frame = cv2.flip(cam_frame, 1)

        if frame is None:
            frame = self.synthetic_driver.generate_frame()

        # 2. Vision & Ocular Processing
        if self.source_mode == "webcam":
            ocular_data = self.vision_detector.process_frame(frame)
        else:
            # Synthetic simulation mode
            synth_lms = self.synthetic_driver.get_synthetic_landmarks()
            synth_tele = self.synthetic_driver.get_ground_truth_telemetry()
            ocular_data = self.vision_detector.process_frame(frame)
            ocular_data["ear"] = synth_tele["ear"]
            ocular_data["mar"] = synth_tele["mar"]
            ocular_data["pitch_deg"] = synth_tele["pitch_deg"]
            ocular_data["roll_deg"] = synth_tele["tilt_deg"]
            ocular_data["landmarks_dict"] = synth_lms
            ocular_data["face_detected"] = True

            # Closure logic
            is_closed = (ocular_data["ear"] < self.vision_detector.ear_threshold)
            ocular_data["eyes_closed"] = is_closed
            if is_closed:
                if not self.vision_detector.eyes_closed:
                    self.vision_detector.eyes_closed = True
                    self.vision_detector.eyes_closed_start_time = now
                ocular_data["eyes_closed_sec"] = now - self.vision_detector.eyes_closed_start_time
            else:
                self.vision_detector.eyes_closed = False
                self.vision_detector.eyes_closed_start_time = None
                ocular_data["eyes_closed_sec"] = 0.0

            ocular_data["is_microsleep"] = (ocular_data["eyes_closed_sec"] >= self.vision_detector.microsleep_duration_sec)
            ocular_data["is_yawning"] = (ocular_data["mar"] > self.vision_detector.mar_threshold)

            # Risk score
            r = 0.0
            if ocular_data["eyes_closed_sec"] > 0.3:
                r += min(75.0, (ocular_data["eyes_closed_sec"] / 1.2) * 75.0)
            if ocular_data["is_yawning"]:
                r += 35.0
            ocular_data["risk_score"] = min(100.0, r)

        # 3. Posture Processing
        shoulders = ocular_data.get("shoulders", {})
        posture_data = self.posture_detector.evaluate_posture(
            nose_pt=shoulders.get("nose"),
            left_shoulder_pt=shoulders.get("left"),
            right_shoulder_pt=shoulders.get("right"),
            head_pitch_deg=ocular_data.get("pitch_deg", 0.0),
            head_roll_deg=ocular_data.get("roll_deg", 0.0)
        )

        # 4. Multi-Factor Fusion Decision Engine (Ocular + Posture)
        fusion_data = self.fusion_engine.compute_fusion(ocular_data, posture_data)

        # 5. Safety Alarm & Navigation Advisor
        if fusion_data.get("is_critical", False):
            self.alert_manager.trigger_critical_alarm()
        elif fusion_data.get("is_warning", False):
            self.alert_manager.trigger_warning_beep()
        else:
            if not self.override_all_conditions and not self.override_eye_closed:
                self.alert_manager.silence_alarm()

        alert_data = self.alert_manager.get_status()

        # 6. Render Cockpit HUD directly onto Frame
        hud_frame = self.hud_renderer.draw_hud(
            frame=frame,
            ocular_data=ocular_data,
            posture_data=posture_data,
            fusion_data=fusion_data,
            alert_data=alert_data,
            fps=self.current_fps
        )

        # 7. Update GUI Displays
        self._update_gui_telemetry(ocular_data, posture_data, fusion_data, alert_data)
        self._render_video_canvas(hud_frame)

        # Schedule next iteration (~30 FPS)
        self.root.after(30, self._process_frame_loop)

    def _update_gui_telemetry(
        self,
        ocular: Dict[str, any],
        posture: Dict[str, any],
        fusion: Dict[str, any],
        alert: Dict[str, any]
    ):
        level = fusion.get("level", VigilanceLevel.ALERT)
        risk = fusion.get("composite_risk_score", 0.0)

        if level == VigilanceLevel.CRITICAL:
            if fusion.get("all_conditions_triggered", False):
                self.status_pill.configure(text="🚨 EMERGENCY: ALL CONDITIONS TRIGGERED!", bg="#d50000")
            else:
                self.status_pill.configure(text=f"🚨 CRITICAL FATIGUE DETECTED ({risk}%)", bg="#b71c1c")
        elif level == VigilanceLevel.WARNING:
            self.status_pill.configure(text=f"⚠️ WARNING: FATIGUE ELEVATED ({risk}%)", bg="#e65100")
        elif level == VigilanceLevel.CAUTION:
            self.status_pill.configure(text=f"CAUTION: MILD TIREDNESS ({risk}%)", bg="#f57f17")
        else:
            self.status_pill.configure(text="DRIVER ALERT & ATTENTIVE", bg="#2e7d32")

        # EAR
        ear = ocular.get("ear", 0.3)
        eyes_sec = ocular.get("eyes_closed_sec", 0.0)
        ear_str = f"{ear:.3f}" + (f" (CLOSED {eyes_sec:.1f}s!)" if eyes_sec > 0 else " (Open)")
        ear_col = "#ff1744" if eyes_sec >= 1.0 else ("#ffea00" if eyes_sec > 0 else "#00e676")
        self.lbl_ear_val.configure(text=ear_str, fg=ear_col)

        # MAR
        mar = ocular.get("mar", 0.2)
        is_yawn = ocular.get("is_yawning", False)
        mar_str = f"{mar:.3f}" + (" (YAWNING!)" if is_yawn else " (Normal)")
        mar_col = "#ff9100" if is_yawn else "#00e676"
        self.lbl_mar_val.configure(text=mar_str, fg=mar_col)

        # PERCLOS
        perclos = ocular.get("perclos_pct", 0.0)
        self.lbl_perclos_val.configure(text=f"{perclos:.1f}%")

        # Posture
        p_state = posture.get("state", PostureState.ACTIVE)
        p_col = "#00e676" if p_state == PostureState.ACTIVE else "#ff5252"
        self.lbl_posture_val.configure(text=p_state.replace("_", " "), fg=p_col)

        pitch = posture.get("head_pitch_deg", 0.0)
        tilt = posture.get("shoulder_tilt_deg", 0.0)
        self.lbl_angles_val.configure(text=f"Pitch: {pitch:+.1f}° | Tilt: {tilt:.1f}°")

        # Risk
        self.lbl_risk_val.configure(text=f"{risk}% ({level.replace('_', ' ')})", fg=self._get_risk_color(level))

        # Rest stop update (Nearest Petrol Pump / Rest Area)
        stop = alert.get("nearest_stop", {})
        if stop:
            self.lbl_rest_name.configure(text=stop.get("name", "Nearest Petrol Pump / Rest Stop"))
            self.lbl_rest_meta.configure(text=f"Distance: {stop.get('distance_km')} km  |  ETA: {stop.get('eta_mins')} mins")
            self.lbl_rest_amenities.configure(text="Services: " + ", ".join(stop.get("amenities", [])[:3]))

        # Driver GPS update
        driver_gps = alert.get("driver_gps", {})
        if driver_gps:
            lat = driver_gps.get("lat", 12.9695)
            lon = driver_gps.get("lon", 79.1455)
            city = driver_gps.get("label", "Current Location")
            self.lbl_gps_status.configure(
                text=f"📍 Driver GPS: {lat:.4f}°N, {lon:.4f}°E ({city})"
            )

    def _on_navigate_maps(self):
        """Opens live driving route to the nearest petrol pump or rest area in Google Maps."""
        status = self.alert_manager.get_status()
        nearest = status.get("nearest_stop", {})
        url = nearest.get("maps_url")
        if not url:
            gps = status.get("driver_gps", {})
            lat = gps.get("lat", 12.9695)
            lon = gps.get("lon", 79.1455)
            url = f"https://www.google.com/maps/search/petrol+pump+or+rest+area/@{lat},{lon},14z"
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"[Dashboard] Error opening maps: {e}")

    def _render_video_canvas(self, frame_bgr: np.ndarray):
        """Converts OpenCV BGR image to Tkinter Canvas PhotoImage."""
        canvas_w = self.video_canvas.winfo_width()
        canvas_h = self.video_canvas.winfo_height()
        if canvas_w < 50 or canvas_h < 50:
            canvas_w, canvas_h = 720, 520

        img_h, img_w = frame_bgr.shape[:2]
        scale = min(canvas_w / img_w, canvas_h / img_h)
        new_w, new_h = max(10, int(img_w * scale)), max(10, int(img_h * scale))

        resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        rgb_img = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)
        self.tk_photo = ImageTk.PhotoImage(image=pil_img)

        self.video_canvas.delete("all")
        pos_x = (canvas_w - new_w) // 2
        pos_y = (canvas_h - new_h) // 2
        self.video_canvas.create_image(pos_x, pos_y, anchor=tk.NW, image=self.tk_photo)

    @staticmethod
    def _get_risk_color(level: str) -> str:
        if level == VigilanceLevel.CRITICAL:
            return "#ff1744"
        elif level == VigilanceLevel.WARNING:
            return "#ff9100"
        elif level == VigilanceLevel.CAUTION:
            return "#ffea00"
        return "#00e676"

    def on_close(self):
        """Cleans up threads, camera, and audio on window close."""
        self.is_running = False
        self.alert_manager.silence_alarm()
        if self.cap is not None:
            self.cap.release()
        self.root.destroy()


def launch_dashboard():
    root = tk.Tk()
    app = VigilanceDashboard(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    launch_dashboard()
