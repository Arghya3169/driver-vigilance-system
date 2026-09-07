"""
Driver Vigilance System - Main Entry Point
Launches the Multi-Modal Driver Vigilance & Safety System.
Supports Cockpit Desktop GUI, high-speed OpenCV HUD, or Headless Telemetry modes.
"""

import argparse
import os
import sys
import time

# Add workspace directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_opencv_mode(args):
    """
    Runs high-performance OpenCV cockpit window with real-time interactive hotkeys:
      [q]: Quit
      [c]: Toggle Eye Closure (Microsleep)
      [y]: Toggle Yawning
      [h]: Toggle Heart Rate Deceleration (Sleep Bradycardia)
      [p]: Toggle Posture Collapse (Head Drop / Slouch)
      [a]: Trigger ALL CONDITIONS (Joint Sleep Onset Emergency)
      [r]: Recalibrate / Reset to Active Nominal State
      [m]: Toggle Sound Mute
    """
    print("=" * 70)
    print("🚘 DRIVER VIGILANCE SYSTEM - OPENCV COCKPIT MODE")
    print("=" * 70)
    print("Hotkeys:")
    print("  [q] Quit")
    print("  [c] Toggle Eye Closure (Microsleep)")
    print("  [y] Toggle Yawn")
    print("  [p] Toggle Inactive Posture (Head Drop / Slouch)")
    print("  [a] 🚨 TRIGGER ALL CONDITIONS (Eyes Closed + Inactive Posture)")
    print("  [r] Reset to Active Nominal")
    print("  [m] Toggle Mute Alarm Beeps")
    print("=" * 70)

    import cv2
    from core.alert import AlertManager
    from core.fusion import MultiModalVigilanceFusion, VigilanceLevel
    from core.posture import SeatPostureDetector, PostureState
    from core.synthetic_driver import SyntheticDriverGenerator
    from core.vision import FaceOcularDetector
    from ui.hud_renderer import HUDRenderer

    vision = FaceOcularDetector()
    posture = SeatPostureDetector()
    fusion = MultiModalVigilanceFusion()
    alert = AlertManager(enable_sound=not args.no_sound, enable_voice=not args.no_voice)
    hud = HUDRenderer()
    synth = SyntheticDriverGenerator()

    # Open camera if not forced synth
    cap = None
    use_synth = args.synth
    if not use_synth:
        cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY)
        if not cap.isOpened():
            print(f"[Notice] Camera {args.camera} unavailable. Starting Synthetic Driver Simulator.")
            use_synth = True

    # State toggles
    t_eyes_closed = False
    t_yawn = False
    t_bad_posture = False
    t_all_conds = False

    window_name = "Driver Vigilance System - Automotive Safety HUD"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1024, 768)

    last_time = time.time()
    fps = 30.0

    try:
        while True:
            now = time.time()
            dt = max(0.001, now - last_time)
            last_time = now
            fps = 0.9 * fps + 0.1 * (1.0 / dt)

            # 1. Acquire Frame
            frame = None
            if not use_synth and cap is not None and cap.isOpened():
                ret, c_frame = cap.read()
                if ret and c_frame is not None:
                    frame = cv2.flip(c_frame, 1)

            if frame is None:
                frame = synth.generate_frame()
                is_synth_frame = True
            else:
                is_synth_frame = False

            # 2. Vision & Ocular
            if not is_synth_frame:
                ocular_data = vision.process_frame(frame)
            else:
                # Synthetic Telemetry Injection
                synth_lms = synth.get_synthetic_landmarks()
                synth_tele = synth.get_ground_truth_telemetry()
                ocular_data = vision.process_frame(frame)
                ocular_data["ear"] = synth_tele["ear"]
                ocular_data["mar"] = synth_tele["mar"]
                ocular_data["pitch_deg"] = synth_tele["pitch_deg"]
                ocular_data["roll_deg"] = synth_tele["tilt_deg"]
                ocular_data["landmarks_dict"] = synth_lms
                ocular_data["face_detected"] = True

                is_closed = (ocular_data["ear"] < vision.ear_threshold)
                ocular_data["eyes_closed"] = is_closed
                if is_closed:
                    if not vision.eyes_closed:
                        vision.eyes_closed = True
                        vision.eyes_closed_start_time = now
                    ocular_data["eyes_closed_sec"] = now - vision.eyes_closed_start_time
                else:
                    vision.eyes_closed = False
                    vision.eyes_closed_start_time = None
                    ocular_data["eyes_closed_sec"] = 0.0

                ocular_data["is_microsleep"] = (ocular_data["eyes_closed_sec"] >= vision.microsleep_duration_sec)
                ocular_data["is_yawning"] = (ocular_data["mar"] > vision.mar_threshold)

                r = 0.0
                if ocular_data["eyes_closed_sec"] > 0.3:
                    r += min(75.0, (ocular_data["eyes_closed_sec"] / 1.2) * 75.0)
                if ocular_data["is_yawning"]:
                    r += 35.0
                ocular_data["risk_score"] = min(100.0, r)

            # 3. Posture
            shoulders = ocular_data.get("shoulders", {})
            posture_data = posture.evaluate_posture(
                nose_pt=shoulders.get("nose"),
                left_shoulder_pt=shoulders.get("left"),
                right_shoulder_pt=shoulders.get("right"),
                head_pitch_deg=ocular_data.get("pitch_deg", 0.0),
                head_roll_deg=ocular_data.get("roll_deg", 0.0)
            )

            # 4. Multi-Modal Fusion (Ocular + Posture)
            fusion_data = fusion.compute_fusion(ocular_data, posture_data)

            # 5. Safety Alert Actions
            if fusion_data.get("is_critical", False):
                alert.trigger_critical_alarm()
            elif fusion_data.get("is_warning", False):
                alert.trigger_warning_beep()
            else:
                if not t_all_conds and not t_eyes_closed:
                    alert.silence_alarm()

            alert_data = alert.get_status()

            # 6. Render HUD
            hud_frame = hud.draw_hud(
                frame=frame,
                ocular_data=ocular_data,
                posture_data=posture_data,
                fusion_data=fusion_data,
                alert_data=alert_data,
                fps=fps
            )

            cv2.imshow(window_name, hud_frame)

            # Process Hotkeys
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c'):
                t_eyes_closed = not t_eyes_closed
                synth.eye_openness = 0.0 if t_eyes_closed else 1.0
                print(f"[Sim] Eye Closure: {t_eyes_closed}")
            elif key == ord('y'):
                t_yawn = not t_yawn
                synth.mouth_openness = 1.0 if t_yawn else 0.0
                print(f"[Sim] Yawn: {t_yawn}")
            elif key == ord('p'):
                t_bad_posture = not t_bad_posture
                synth.head_pitch_down = 0.9 if t_bad_posture else 0.0
                synth.lateral_lean = 0.5 if t_bad_posture else 0.0
                print(f"[Sim] Compromised Posture: {t_bad_posture}")
            elif key == ord('a'):
                t_all_conds = True
                t_eyes_closed = True
                t_bad_posture = True
                synth.set_states(eye_openness=0.0, mouth_openness=0.0, head_pitch_down=0.9, lateral_lean=0.5)
                print("[Sim] 🚨 ALL CONDITIONS TRIGGERED: Sleep onset emergency activated!")
            elif key == ord('r'):
                t_eyes_closed = False
                t_yawn = False
                t_bad_posture = False
                t_all_conds = False
                synth.set_states(eye_openness=1.0, mouth_openness=0.0, head_pitch_down=0.0, lateral_lean=0.0)
                alert.silence_alarm()
                print("[Sim] Reset to Active Nominal.")
            elif key == ord('m'):
                alert.enable_sound = not alert.enable_sound
                print(f"[Audio] Sound beeps: {alert.enable_sound}")

    finally:
        alert.silence_alarm()
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Driver Vigilance & Multi-Modal Fatigue Safety System")
    parser.add_argument("--mode", choices=["gui", "opencv", "cli"], default="gui", help="Interface mode: 'gui' (Tkinter Dashboard), 'opencv' (direct HUD window), or 'cli'")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index (default: 0)")
    parser.add_argument("--synth", action="store_true", help="Force synthetic driver simulation feed")
    parser.add_argument("--no-sound", action="store_true", help="Disable acoustic beep alarm")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice speech alerts")
    args = parser.parse_args()

    if args.mode == "gui":
        from ui.dashboard import launch_dashboard
        launch_dashboard()
    elif args.mode == "opencv":
        run_opencv_mode(args)
    else:
        print("CLI Mode: running verification check...")
        run_opencv_mode(args)


if __name__ == "__main__":
    main()
