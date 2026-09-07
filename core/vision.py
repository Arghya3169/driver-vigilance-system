"""
Facial & Ocular Dynamics Detector (EAR & MAR)
Uses MediaPipe FaceLandmarker and PoseLandmarker tasks for precision tracking.
Calculates Eye Aspect Ratio (EAR) for microsleep/closure detection,
Mouth Aspect Ratio (MAR) for yawning detection, 3D Head Pose estimation,
and crops forehead ROI for contactless rPPG blood flow analysis.
"""

import collections
import math
import os
import numpy as np
import time
from typing import Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class FaceOcularDetector:
    """
    Precision ocular and facial dynamics detector.
    Computes EAR, MAR, blink duration, yawn frequency, and head pose.
    """

    # Landmark indices according to canonical Face Mesh / Landmarker topology
    # Right eye
    RIGHT_EYE = [33, 160, 158, 133, 153, 144]
    # Left eye
    LEFT_EYE = [362, 385, 387, 263, 373, 380]
    # Mouth (Upper lip 13, lower lip 14, left corner 78, right corner 308)
    MOUTH_CORNERS = [78, 308]
    MOUTH_LIPS = [13, 14]
    MOUTH_VERTICAL_EXTRA = [(81, 178), (311, 402)]
    # Forehead ROI landmarks (upper forehead / brow region)
    FOREHEAD_LANDMARKS = [10, 67, 109, 297, 338]
    # 3D model points for Head Pose PnP estimation
    FACE_3D_MODEL = np.array([
        (0.0, 0.0, 0.0),          # Nose tip (index 1)
        (0.0, -330.0, -65.0),     # Chin (index 152)
        (-225.0, 170.0, -135.0),  # Left eye corner (index 33)
        (225.0, 170.0, -135.0),   # Right eye corner (index 263)
        (-150.0, -150.0, -125.0), # Left mouth corner (index 61)
        (150.0, -150.0, -125.0)   # Right mouth corner (index 291)
    ], dtype=np.float64)

    def __init__(
        self,
        face_model_path: str = "models/face_landmarker.task",
        pose_model_path: str = "models/pose_landmarker_lite.task",
        ear_threshold: float = 0.22,
        mar_threshold: float = 0.65,
        microsleep_duration_sec: float = 1.2,
        yawn_duration_sec: float = 1.0,
        perclos_window_size: int = 60
    ):
        self.ear_threshold = ear_threshold
        self.mar_threshold = mar_threshold
        self.microsleep_duration_sec = microsleep_duration_sec
        self.yawn_duration_sec = yawn_duration_sec

        # State tracking
        self.current_ear = 0.32
        self.current_mar = 0.15
        self.eyes_closed = False
        self.eyes_closed_start_time: Optional[float] = None
        self.eyes_closed_duration: float = 0.0
        self.is_microsleep = False

        # Yawn tracking
        self.is_yawning = False
        self.yawn_start_time: Optional[float] = None
        self.yawn_duration: float = 0.0
        self.yawn_events = collections.deque(maxlen=100)

        # Rolling buffers for PERCLOS
        self.closure_history = collections.deque(maxlen=perclos_window_size)

        # Head pose
        self.pitch_deg = 0.0
        self.yaw_deg = 0.0
        self.roll_deg = 0.0

        # Last detected landmarks and forehead ROI
        self.last_landmarks_2d: Optional[Dict[int, Tuple[float, float]]] = None
        self.forehead_roi_rect = None

        # Initialize MediaPipe Task Detectors
        self.face_landmarker = None
        self.pose_landmarker = None

        # Resolve paths relative to project root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        f_path = os.path.join(base_dir, face_model_path) if not os.path.isabs(face_model_path) else face_model_path
        p_path = os.path.join(base_dir, pose_model_path) if not os.path.isabs(pose_model_path) else pose_model_path

        if os.path.exists(f_path):
            try:
                base_options = python.BaseOptions(model_asset_path=f_path)
                options = vision.FaceLandmarkerOptions(
                    base_options=base_options,
                    output_face_blendshapes=False,
                    output_facial_transformation_matrixes=True,
                    num_faces=1
                )
                self.face_landmarker = vision.FaceLandmarker.create_from_options(options)
            except Exception as e:
                print(f"[Vision] Warning: Failed to init FaceLandmarker task: {e}")

        if os.path.exists(p_path):
            try:
                p_options = python.BaseOptions(model_asset_path=p_path)
                pose_opts = vision.PoseLandmarkerOptions(
                    base_options=p_options,
                    num_poses=1
                )
                self.pose_landmarker = vision.PoseLandmarker.create_from_options(pose_opts)
            except Exception as e:
                print(f"[Vision] Warning: Failed to init PoseLandmarker task: {e}")

        # Fallback OpenCV Haar cascades
        self.face_cascade = None
        self.eye_cascade = None
        self._init_cascades()

    def _init_cascades(self):
        try:
            cascade_path = cv2.data.haarcascades
            self.face_cascade = cv2.CascadeClassifier(cascade_path + 'haarcascade_frontalface_default.xml')
            self.eye_cascade = cv2.CascadeClassifier(cascade_path + 'haarcascade_eye.xml')
        except Exception:
            pass

    @staticmethod
    def _euclidean_dist(pt1: Tuple[float, float], pt2: Tuple[float, float]) -> float:
        return math.hypot(pt1[0] - pt2[0], pt1[1] - pt2[1])

    def calculate_ear(self, landmarks_2d: Dict[int, Tuple[float, float]]) -> Tuple[float, float, float]:
        """
        Calculates Eye Aspect Ratio:
        EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)
        """
        # Right Eye
        try:
            rp1 = landmarks_2d[self.RIGHT_EYE[0]]
            rp2 = landmarks_2d[self.RIGHT_EYE[1]]
            rp3 = landmarks_2d[self.RIGHT_EYE[2]]
            rp4 = landmarks_2d[self.RIGHT_EYE[3]]
            rp5 = landmarks_2d[self.RIGHT_EYE[4]]
            rp6 = landmarks_2d[self.RIGHT_EYE[5]]

            r_v1 = self._euclidean_dist(rp2, rp6)
            r_v2 = self._euclidean_dist(rp3, rp5)
            r_horiz = max(1e-5, self._euclidean_dist(rp1, rp4))
            ear_right = (r_v1 + r_v2) / (2.0 * r_horiz)
        except KeyError:
            ear_right = 0.30

        # Left Eye
        try:
            lp1 = landmarks_2d[self.LEFT_EYE[0]]
            lp2 = landmarks_2d[self.LEFT_EYE[1]]
            lp3 = landmarks_2d[self.LEFT_EYE[2]]
            lp4 = landmarks_2d[self.LEFT_EYE[3]]
            lp5 = landmarks_2d[self.LEFT_EYE[4]]
            lp6 = landmarks_2d[self.LEFT_EYE[5]]

            l_v1 = self._euclidean_dist(lp2, lp6)
            l_v2 = self._euclidean_dist(lp3, lp5)
            l_horiz = max(1e-5, self._euclidean_dist(lp1, lp4))
            ear_left = (l_v1 + l_v2) / (2.0 * l_horiz)
        except KeyError:
            ear_left = 0.30

        avg_ear = (ear_left + ear_right) / 2.0
        return float(avg_ear), float(ear_left), float(ear_right)

    def calculate_mar(self, landmarks_2d: Dict[int, Tuple[float, float]]) -> float:
        """
        Calculates Mouth Aspect Ratio for yawning detection.
        MAR = vertical lip opening / horizontal corner distance
        """
        try:
            c_left = landmarks_2d[self.MOUTH_CORNERS[0]]
            c_right = landmarks_2d[self.MOUTH_CORNERS[1]]
            lip_top = landmarks_2d[self.MOUTH_LIPS[0]]
            lip_bottom = landmarks_2d[self.MOUTH_LIPS[1]]

            horiz = max(1e-5, self._euclidean_dist(c_left, c_right))
            vert_main = self._euclidean_dist(lip_top, lip_bottom)

            vert_extra = 0.0
            extra_count = 0
            for idx_top, idx_bot in self.MOUTH_VERTICAL_EXTRA:
                if idx_top in landmarks_2d and idx_bot in landmarks_2d:
                    vert_extra += self._euclidean_dist(landmarks_2d[idx_top], landmarks_2d[idx_bot])
                    extra_count += 1

            if extra_count > 0:
                avg_vert = (vert_main + vert_extra) / (1.0 + extra_count)
            else:
                avg_vert = vert_main

            mar = avg_vert / horiz
            return float(mar)
        except KeyError:
            return 0.20

    def estimate_head_pose(
        self,
        landmarks_2d: Dict[int, Tuple[float, float]],
        frame_shape: Tuple[int, int]
    ) -> Tuple[float, float, float]:
        """Estimates Pitch, Yaw, Roll angles via cv2.solvePnP."""
        h, w = frame_shape[:2]
        try:
            image_points = np.array([
                landmarks_2d[1],
                landmarks_2d[152],
                landmarks_2d[33],
                landmarks_2d[263],
                landmarks_2d[61],
                landmarks_2d[291]
            ], dtype=np.float64)

            focal_length = w
            center = (w / 2.0, h / 2.0)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float64)
            dist_coeffs = np.zeros((4, 1), dtype=np.float64)

            success, rot_vec, trans_vec = cv2.solvePnP(
                self.FACE_3D_MODEL,
                image_points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )

            if success:
                rmat, _ = cv2.Rodrigues(rot_vec)
                sy = math.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
                singular = sy < 1e-6
                if not singular:
                    pitch = math.atan2(rmat[2, 1], rmat[2, 2])
                    yaw = math.atan2(-rmat[2, 0], sy)
                    roll = math.atan2(rmat[1, 0], rmat[0, 0])
                else:
                    pitch = math.atan2(-rmat[1, 2], rmat[1, 1])
                    yaw = math.atan2(-rmat[2, 0], sy)
                    roll = 0.0

                self.pitch_deg = round(math.degrees(pitch), 1)
                self.yaw_deg = round(math.degrees(yaw), 1)
                self.roll_deg = round(math.degrees(roll), 1)
                return self.pitch_deg, self.yaw_deg, self.roll_deg
        except Exception:
            pass

        return self.pitch_deg, self.yaw_deg, self.roll_deg

    def extract_forehead_roi(
        self,
        frame: np.ndarray,
        landmarks_2d: Dict[int, Tuple[float, float]]
    ) -> Optional[np.ndarray]:
        """Crops forehead region for contactless rPPG pulse extraction."""
        h, w = frame.shape[:2]
        try:
            xs = [landmarks_2d[idx][0] for idx in self.FOREHEAD_LANDMARKS if idx in landmarks_2d]
            ys = [landmarks_2d[idx][1] for idx in self.FOREHEAD_LANDMARKS if idx in landmarks_2d]
            if len(xs) >= 3:
                min_x = max(0, int(min(xs)))
                max_x = min(w, int(max(xs)))
                min_y = max(0, int(min(ys) - 20))
                max_y = min(h, int(max(ys) + 10))

                if max_x > min_x + 10 and max_y > min_y + 10:
                    self.forehead_roi_rect = (min_x, min_y, max_x - min_x, max_y - min_y)
                    return frame[min_y:max_y, min_x:max_x]
        except Exception:
            pass

        return None

    def process_frame(self, frame_bgr: np.ndarray) -> Dict[str, any]:
        """
        Runs full facial and ocular detection on a video frame.
        """
        now = time.time()
        h, w = frame_bgr.shape[:2]
        landmarks_dict = {}
        shoulders = {"left": None, "right": None, "nose": None}
        forehead_roi = None
        face_detected = False

        if self.face_landmarker is not None:
            try:
                rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                detection_result = self.face_landmarker.detect(mp_image)

                if detection_result.face_landmarks and len(detection_result.face_landmarks) > 0:
                    face_detected = True
                    lms = detection_result.face_landmarks[0]
                    for idx, lm in enumerate(lms):
                        landmarks_dict[idx] = (lm.x * w, lm.y * h)

                    if 1 in landmarks_dict:
                        shoulders["nose"] = landmarks_dict[1]

                    # Pose detection for shoulders
                    if self.pose_landmarker is not None:
                        try:
                            pose_res = self.pose_landmarker.detect(mp_image)
                            if pose_res.pose_landmarks and len(pose_res.pose_landmarks) > 0:
                                plm = pose_res.pose_landmarks[0]
                                # 11: left shoulder, 12: right shoulder
                                shoulders["left"] = (plm[11].x * w, plm[11].y * h)
                                shoulders["right"] = (plm[12].x * w, plm[12].y * h)
                        except Exception:
                            pass

                    # Extract forehead ROI
                    forehead_roi = self.extract_forehead_roi(frame_bgr, landmarks_dict)

                    # Head pose
                    self.estimate_head_pose(landmarks_dict, frame_bgr.shape)
            except Exception as e:
                face_detected = False

        # Fallback if no landmarks detected
        if not face_detected:
            landmarks_dict, forehead_roi, shoulders = self._fallback_cascade_detect(frame_bgr)
            face_detected = (len(landmarks_dict) > 0)

        # Compute EAR & MAR
        if face_detected and landmarks_dict:
            self.last_landmarks_2d = landmarks_dict
            ear_avg, ear_l, ear_r = self.calculate_ear(landmarks_dict)
            mar = self.calculate_mar(landmarks_dict)
            self.current_ear = round(ear_avg, 3)
            self.current_mar = round(mar, 3)
        else:
            self.current_ear = 0.30
            self.current_mar = 0.20

        # Eye Closure & Microsleep Logic
        is_closed_now = (self.current_ear < self.ear_threshold)
        self.closure_history.append(1 if is_closed_now else 0)

        if is_closed_now:
            if not self.eyes_closed:
                self.eyes_closed = True
                self.eyes_closed_start_time = now
            self.eyes_closed_duration = now - self.eyes_closed_start_time
        else:
            self.eyes_closed = False
            self.eyes_closed_start_time = None
            self.eyes_closed_duration = 0.0

        self.is_microsleep = (self.eyes_closed_duration >= self.microsleep_duration_sec)

        # Yawning Logic
        is_yawning_now = (self.current_mar > self.mar_threshold)
        if is_yawning_now:
            if not self.is_yawning:
                self.is_yawning = True
                self.yawn_start_time = now
            self.yawn_duration = now - self.yawn_start_time
            if self.yawn_duration >= self.yawn_duration_sec:
                if not self.yawn_events or (now - self.yawn_events[-1] > 3.0):
                    self.yawn_events.append(now)
        else:
            self.is_yawning = False
            self.yawn_start_time = None
            self.yawn_duration = 0.0

        while self.yawn_events and (now - self.yawn_events[0] > 120.0):
            self.yawn_events.popleft()
        recent_yawns_count = len(self.yawn_events)

        # PERCLOS
        perclos = (sum(self.closure_history) / max(1, len(self.closure_history))) * 100.0

        # Ocular Risk Score (0 - 100%)
        risk = 0.0
        if self.eyes_closed_duration > 0.25:
            risk += min(75.0, (self.eyes_closed_duration / self.microsleep_duration_sec) * 75.0)
        if self.is_yawning or recent_yawns_count > 0:
            risk += min(30.0, recent_yawns_count * 12.0 + (10.0 if self.is_yawning else 0.0))
        if perclos > 30.0:
            risk += min(20.0, (perclos - 30.0) * 0.5)

        ocular_risk_score = round(min(100.0, max(0.0, risk)), 1)

        return {
            "face_detected": face_detected,
            "ear": self.current_ear,
            "mar": self.current_mar,
            "eyes_closed": self.eyes_closed,
            "eyes_closed_sec": round(self.eyes_closed_duration, 2),
            "is_microsleep": self.is_microsleep,
            "is_yawning": self.is_yawning,
            "yawn_duration_sec": round(self.yawn_duration, 1),
            "recent_yawns_count": recent_yawns_count,
            "perclos_pct": round(perclos, 1),
            "pitch_deg": self.pitch_deg,
            "yaw_deg": self.yaw_deg,
            "roll_deg": self.roll_deg,
            "risk_score": ocular_risk_score,
            "landmarks_dict": landmarks_dict,
            "forehead_roi": forehead_roi,
            "forehead_rect": self.forehead_roi_rect,
            "shoulders": shoulders
        }

    def _fallback_cascade_detect(self, frame_bgr: np.ndarray) -> Tuple[Dict, Optional[np.ndarray], Dict]:
        landmarks = {}
        forehead_roi = None
        shoulders = {"left": None, "right": None, "nose": None}

        if self.face_cascade is None:
            return landmarks, forehead_roi, shoulders

        try:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.2, 4, minSize=(90, 90))
            if len(faces) > 0:
                fx, fy, fw, fh = faces[0]
                landmarks[1] = (fx + fw * 0.5, fy + fh * 0.55)
                landmarks[152] = (fx + fw * 0.5, fy + fh * 0.95)
                landmarks[33] = (fx + fw * 0.28, fy + fh * 0.38)
                landmarks[133] = (fx + fw * 0.44, fy + fh * 0.38)
                landmarks[160] = (fx + fw * 0.36, fy + fh * 0.35)
                landmarks[144] = (fx + fw * 0.36, fy + fh * 0.41)
                landmarks[158] = (fx + fw * 0.38, fy + fh * 0.35)
                landmarks[153] = (fx + fw * 0.38, fy + fh * 0.41)
                landmarks[362] = (fx + fw * 0.56, fy + fh * 0.38)
                landmarks[263] = (fx + fw * 0.72, fy + fh * 0.38)
                landmarks[385] = (fx + fw * 0.64, fy + fh * 0.35)
                landmarks[380] = (fx + fw * 0.64, fy + fh * 0.41)
                landmarks[387] = (fx + fw * 0.62, fy + fh * 0.35)
                landmarks[373] = (fx + fw * 0.62, fy + fh * 0.41)
                landmarks[78] = (fx + fw * 0.35, fy + fh * 0.78)
                landmarks[308] = (fx + fw * 0.65, fy + fh * 0.78)
                landmarks[13] = (fx + fw * 0.5, fy + fh * 0.75)
                landmarks[14] = (fx + fw * 0.5, fy + fh * 0.81)

                shoulders["nose"] = landmarks[1]
                shoulders["left"] = (max(0, fx - fw * 0.4), fy + fh * 1.3)
                shoulders["right"] = (min(frame_bgr.shape[1], fx + fw * 1.4), fy + fh * 1.3)

                fy_fh = max(0, int(fy + fh * 0.1))
                fy_fh_end = int(fy + fh * 0.3)
                fx_fh = int(fx + fw * 0.3)
                fx_fh_end = int(fx + fw * 0.7)
                forehead_roi = frame_bgr[fy_fh:fy_fh_end, fx_fh:fx_fh_end]
                self.forehead_roi_rect = (fx_fh, fy_fh, fx_fh_end - fx_fh, fy_fh_end - fy_fh)
        except Exception:
            pass

        return landmarks, forehead_roi, shoulders
