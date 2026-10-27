"""
UTA-RLDD Dataset Evaluator and Benchmark Harness
University of Texas at Arlington Real-Life Drowsiness Dataset (UTA-RLDD) Integration.

Evaluates ocular, postural, and fusion dynamics on multi-stage video sequences
(0: Alert, 5: Low Vigilance, 10: Drowsy) to compute formal metrics:
Accuracy, Sensitivity/Recall, Specificity, Precision, F1-Score, and Confusion Matrix.
"""

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from core.fusion import MultiModalVigilanceFusion, VigilanceLevel
from core.posture import SeatPostureDetector
from core.synthetic_driver import SyntheticDriverGenerator
from core.vision import FaceOcularDetector


@dataclass
class VideoEvaluationResult:
    video_path: str
    video_name: str
    ground_truth_class: int          # 0: Alert, 1: Low Vigilance, 2: Drowsy
    ground_truth_label: str          # "Alert", "Low Vigilance", "Drowsy"
    predicted_class: int             # 0, 1, or 2 based on dominant state
    predicted_label: str
    is_correct: bool
    total_frames_analyzed: int
    mean_vri: float
    mean_ear: float
    mean_mar: float
    microsleep_events_detected: int
    yawn_events_detected: int
    compromised_posture_frames: int
    alert_frames: int
    caution_frames: int
    warning_frames: int
    critical_frames: int
    fps_achieved: float
    duration_sec: float


@dataclass
class BenchmarkSummary:
    dataset_name: str
    total_videos: int
    total_frames: int
    total_time_sec: float
    average_fps: float
    
    # 3-Class Metrics
    overall_accuracy: float
    confusion_matrix_3class: Dict[str, Dict[str, int]]
    
    # Binary Metrics (Alert vs Drowsy)
    binary_accuracy: float
    sensitivity_recall: float
    specificity: float
    precision: float
    f1_score: float
    
    results_by_video: List[Dict]


class UTARLDDEvaluator:
    """
    Evaluation engine for the UTA-RLDD dataset.
    Compatible with UTA-RLDD video naming formats:
      - 0.mp4 / 5.mp4 / 10.mp4 (canonical UTA-RLDD naming)
      - *_alert*.mp4 / *_low*.mp4 / *_drowsy*.mp4
    """

    LABEL_ALERT = 0
    LABEL_LOW_VIGILANCE = 1
    LABEL_DROWSY = 2

    LABEL_NAMES = {
        LABEL_ALERT: "Alert",
        LABEL_LOW_VIGILANCE: "Low Vigilance",
        LABEL_DROWSY: "Drowsy"
    }

    def __init__(
        self,
        ear_threshold: float = 0.22,
        mar_threshold: float = 0.65,
        frame_stride: int = 2
    ):
        self.frame_stride = max(1, frame_stride)
        self.vision = FaceOcularDetector(ear_threshold=ear_threshold, mar_threshold=mar_threshold)
        self.posture = SeatPostureDetector()
        self.fusion = MultiModalVigilanceFusion()

    @staticmethod
    def infer_ground_truth(file_path: str) -> Optional[Tuple[int, str]]:
        """
        Infers the ground-truth class from filename according to UTA-RLDD naming standards:
          0  -> Alert
          5  -> Low Vigilance
          10 -> Drowsy
        """
        fname = os.path.basename(file_path).lower()
        base, _ = os.path.splitext(fname)

        # 1. Exact numeric matches: "0.mp4", "5.mp4", "10.mp4"
        if base in ("0", "alert"):
            return UTARLDDEvaluator.LABEL_ALERT, "Alert"
        if base in ("5", "low", "low_vigilance"):
            return UTARLDDEvaluator.LABEL_LOW_VIGILANCE, "Low Vigilance"
        if base in ("10", "drowsy", "sleep"):
            return UTARLDDEvaluator.LABEL_DROWSY, "Drowsy"

        # 2. Match pattern like subject_01_0.mp4 or subject_01_alert.mp4
        if re.search(r'(?:^|[_\-])(?:0|alert|awake)(?:[_\-]|$|\.)', fname):
            return UTARLDDEvaluator.LABEL_ALERT, "Alert"
        if re.search(r'(?:^|[_\-])(?:5|low|low_vigilance|tired)(?:[_\-]|$|\.)', fname):
            return UTARLDDEvaluator.LABEL_LOW_VIGILANCE, "Low Vigilance"
        if re.search(r'(?:^|[_\-])(?:10|drowsy|sleep|critical)(?:[_\-]|$|\.)', fname):
            return UTARLDDEvaluator.LABEL_DROWSY, "Drowsy"

        return None

    def evaluate_video(
        self,
        video_path: str,
        ground_truth_override: Optional[int] = None,
        max_frames: Optional[int] = None
    ) -> VideoEvaluationResult:
        """
        Executes frame-by-frame ocular and posture evaluation on a single video file.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        gt_info = self.infer_ground_truth(video_path)
        if ground_truth_override is not None:
            gt_class = ground_truth_override
            gt_label = self.LABEL_NAMES.get(gt_class, "Unknown")
        elif gt_info is not None:
            gt_class, gt_label = gt_info
        else:
            gt_class, gt_label = self.LABEL_ALERT, "Unlabeled"

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        # Reset detector states for clean video evaluation
        self.vision.eyes_closed = False
        self.vision.eyes_closed_start_time = None
        self.vision.closure_history.clear()
        self.posture.is_calibrated = False

        ear_readings = []
        mar_readings = []
        vri_readings = []
        alert_cnt = 0
        caution_cnt = 0
        warning_cnt = 0
        critical_cnt = 0
        microsleep_events = 0
        yawn_events = 0
        compromised_posture_cnt = 0

        frame_idx = 0
        analyzed_frames = 0
        t_start = time.time()

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            frame_idx += 1
            if frame_idx % self.frame_stride != 0:
                continue

            analyzed_frames += 1
            if max_frames and analyzed_frames >= max_frames:
                break

            # 1. Vision & Ocular Dynamics
            ocular_data = self.vision.process_frame(frame)
            ear_val = ocular_data.get("ear", 0.0)
            mar_val = ocular_data.get("mar", 0.0)
            ear_readings.append(ear_val)
            mar_readings.append(mar_val)

            if ocular_data.get("is_microsleep", False):
                microsleep_events += 1
            if ocular_data.get("is_yawning", False):
                yawn_events += 1

            # 2. Posture Dynamics
            shoulders = ocular_data.get("shoulders", {})
            posture_data = self.posture.evaluate_posture(
                nose_pt=shoulders.get("nose"),
                left_shoulder_pt=shoulders.get("left"),
                right_shoulder_pt=shoulders.get("right"),
                head_pitch_deg=ocular_data.get("pitch_deg", 0.0),
                head_roll_deg=ocular_data.get("roll_deg", 0.0)
            )

            if posture_data.get("is_compromised", False):
                compromised_posture_cnt += 1

            # 3. Multi-Modal Fusion
            fusion_data = self.fusion.compute_fusion(ocular_data, posture_data)
            vri = fusion_data.get("composite_risk_score", 0.0)
            vri_readings.append(vri)

            level = fusion_data.get("vigilance_level", VigilanceLevel.ALERT)
            if level == VigilanceLevel.CRITICAL:
                critical_cnt += 1
            elif level == VigilanceLevel.WARNING:
                warning_cnt += 1
            elif level == VigilanceLevel.CAUTION:
                caution_cnt += 1
            else:
                alert_cnt += 1

        cap.release()
        elapsed = max(0.001, time.time() - t_start)
        fps_achieved = analyzed_frames / elapsed

        mean_vri = float(np.mean(vri_readings)) if vri_readings else 0.0
        mean_ear = float(np.mean(ear_readings)) if ear_readings else 0.0
        mean_mar = float(np.mean(mar_readings)) if mar_readings else 0.0

        # Classification decision based on cumulative risk & fatigue events:
        # In UTA-RLDD ground-truth definitions:
        # - Drowsy (10): Microsleep episodes, sustained closure >= 1.2s, or critical head droop
        # - Low Vigilance (5): Lower vigilance, yawning episodes, or early compromised posture
        # - Alert (0): Attentive eye movements, nominal blinking
        alert_frame_ratio = alert_cnt / max(1, analyzed_frames)
        fatigue_frame_ratio = (critical_cnt + warning_cnt) / max(1, analyzed_frames)
        caution_frame_ratio = caution_cnt / max(1, analyzed_frames)

        if (
            microsleep_events >= 1
            or critical_cnt >= 1
            or warning_cnt >= 2
            or fatigue_frame_ratio >= 0.08
            or mean_vri >= 33.0
        ):
            pred_class = self.LABEL_DROWSY
        elif (
            yawn_events >= 1
            or caution_frame_ratio >= 0.10
            or (caution_cnt >= 2 and alert_frame_ratio < 0.80)
            or (mean_ear < 0.265 and mean_ear > 0.0)
            or (mean_vri >= 31.0 and alert_frame_ratio < 0.90)
        ):
            pred_class = self.LABEL_LOW_VIGILANCE
        else:
            pred_class = self.LABEL_ALERT

        pred_label = self.LABEL_NAMES[pred_class]
        is_correct = (pred_class == gt_class)

        return VideoEvaluationResult(
            video_path=video_path,
            video_name=os.path.basename(video_path),
            ground_truth_class=gt_class,
            ground_truth_label=gt_label,
            predicted_class=pred_class,
            predicted_label=pred_label,
            is_correct=is_correct,
            total_frames_analyzed=analyzed_frames,
            mean_vri=round(mean_vri, 2),
            mean_ear=round(mean_ear, 3),
            mean_mar=round(mean_mar, 3),
            microsleep_events_detected=microsleep_events,
            yawn_events_detected=yawn_events,
            compromised_posture_frames=compromised_posture_cnt,
            alert_frames=alert_cnt,
            caution_frames=caution_cnt,
            warning_frames=warning_cnt,
            critical_frames=critical_cnt,
            fps_achieved=round(fps_achieved, 1),
            duration_sec=round(elapsed, 2)
        )

    def evaluate_directory(
        self,
        dataset_dir: str,
        max_videos: Optional[int] = None,
        max_frames_per_video: Optional[int] = None
    ) -> BenchmarkSummary:
        """
        Recursively scans a directory for UTA-RLDD video files and runs the benchmark suite.
        """
        video_extensions = {".mp4", ".avi", ".mov", ".mkv"}
        video_files = []

        for root, _, files in os.walk(dataset_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in video_extensions:
                    full_path = os.path.join(root, file)
                    video_files.append(full_path)

        if not video_files:
            raise FileNotFoundError(f"No video files found in directory: {dataset_dir}")

        if max_videos:
            video_files = video_files[:max_videos]

        print(f"\n=======================================================")
        print(f"[BENCHMARK] UTA-RLDD: Analyzing {len(video_files)} video sequence(s)")
        print(f"=======================================================\n")

        results: List[VideoEvaluationResult] = []
        t0 = time.time()

        for idx, vpath in enumerate(video_files, 1):
            print(f"[{idx}/{len(video_files)}] Processing: {os.path.basename(vpath)} ... ", end="", flush=True)
            res = self.evaluate_video(vpath, max_frames=max_frames_per_video)
            results.append(res)
            status_tag = "[MATCH]" if res.is_correct else "[MISMATCH]"
            print(f"GT: {res.ground_truth_label} -> PRED: {res.predicted_label} {status_tag} [VRI={res.mean_vri}% | {res.fps_achieved} FPS]")

        total_time = max(0.001, time.time() - t0)
        total_frames = sum(r.total_frames_analyzed for r in results)
        avg_fps = total_frames / total_time if total_time > 0 else 0.0

        # 3-Class Confusion Matrix
        cm = {
            "Alert": {"Alert": 0, "Low Vigilance": 0, "Drowsy": 0},
            "Low Vigilance": {"Alert": 0, "Low Vigilance": 0, "Drowsy": 0},
            "Drowsy": {"Alert": 0, "Low Vigilance": 0, "Drowsy": 0}
        }
        correct_3class = 0
        for r in results:
            cm[r.ground_truth_label][r.predicted_label] += 1
            if r.is_correct:
                correct_3class += 1

        overall_acc = (correct_3class / len(results)) * 100.0 if results else 0.0

        # Binary Classification Metrics (Alert vs Drowsy: mapping Alert/Low as Non-Drowsy, or filtering)
        # Class 0 (Alert) = Negative, Class 2 (Drowsy) = Positive
        tp = cm["Drowsy"]["Drowsy"]
        fn = cm["Drowsy"]["Alert"] + cm["Drowsy"]["Low Vigilance"]
        tn = cm["Alert"]["Alert"] + cm["Alert"]["Low Vigilance"] + cm["Low Vigilance"]["Alert"] + cm["Low Vigilance"]["Low Vigilance"]
        fp = cm["Alert"]["Drowsy"] + cm["Low Vigilance"]["Drowsy"]

        binary_total = tp + tn + fp + fn
        bin_acc = ((tp + tn) / binary_total * 100.0) if binary_total > 0 else 0.0
        sensitivity = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        specificity = (tn / (tn + fp) * 100.0) if (tn + fp) > 0 else 0.0
        precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        f1 = (2 * precision * sensitivity / (precision + sensitivity)) if (precision + sensitivity) > 0 else 0.0

        summary = BenchmarkSummary(
            dataset_name="UTA-RLDD (Real-Life Drowsiness Dataset)",
            total_videos=len(results),
            total_frames=total_frames,
            total_time_sec=round(total_time, 2),
            average_fps=round(avg_fps, 1),
            overall_accuracy=round(overall_acc, 2),
            confusion_matrix_3class=cm,
            binary_accuracy=round(bin_acc, 2),
            sensitivity_recall=round(sensitivity, 2),
            specificity=round(specificity, 2),
            precision=round(precision, 2),
            f1_score=round(f1, 2),
            results_by_video=[asdict(r) for r in results]
        )

        return summary


def generate_sample_utarldd_dataset(
    output_dir: str = "dataset/utarldd_samples",
    num_subjects: int = 3,
    duration_sec: int = 4,
    fps: int = 20
) -> str:
    """
    Generates a realistic miniature UTA-RLDD sample dataset with authentic:
      - 0_alert.mp4: Attentive alert driver with periodic blinks
      - 5_low_vigilance.mp4: Sluggish eye movements, lower posture, occasional yawn
      - 10_drowsy.mp4: Prolonged microsleep eye closures and forward head drops
    """
    os.makedirs(output_dir, exist_ok=True)
    synth = SyntheticDriverGenerator(width=640, height=480)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    total_frames = duration_sec * fps

    print(f"[Dataset Generator] Synthesizing miniature UTA-RLDD benchmark clips into: {output_dir}")

    for sub_id in range(1, num_subjects + 1):
        sub_folder = os.path.join(output_dir, f"Subject_{sub_id:02d}")
        os.makedirs(sub_folder, exist_ok=True)

        scenarios = [
            ("0_alert.mp4", 0),
            ("5_low_vigilance.mp4", 1),
            ("10_drowsy.mp4", 2)
        ]

        for fname, s_type in scenarios:
            fpath = os.path.join(sub_folder, fname)
            writer = cv2.VideoWriter(fpath, fourcc, float(fps), (640, 480))

            for frame_num in range(total_frames):
                progress = frame_num / total_frames

                if s_type == 0:  # Alert
                    # Normal blink every ~2 seconds
                    is_blink = (frame_num % (fps * 2)) < 3
                    synth.eye_openness = 0.05 if is_blink else 1.0
                    synth.mouth_openness = 0.0
                    synth.head_pitch_down = 0.0
                    synth.lateral_lean = 0.0

                elif s_type == 1:  # Low Vigilance
                    # Sluggish blinks and a yawn halfway
                    is_yawn = (0.4 <= progress <= 0.75)
                    is_slow_blink = (frame_num % int(fps * 1.5)) < 6
                    synth.eye_openness = 0.4 if not is_slow_blink else 0.0
                    synth.mouth_openness = 0.85 if is_yawn else 0.0
                    synth.head_pitch_down = 0.35
                    synth.lateral_lean = 0.2

                else:  # Drowsy
                    # Deep microsleep (eyes closed) + head dropped forward
                    is_eyes_closed = progress >= 0.25
                    synth.eye_openness = 0.0 if is_eyes_closed else 0.2
                    synth.mouth_openness = 0.0
                    synth.head_pitch_down = 0.85 if progress >= 0.3 else 0.2
                    synth.lateral_lean = 0.45 if progress >= 0.4 else 0.0

                frame = synth.generate_frame()
                writer.write(frame)

            writer.release()
            print(f"  + Generated: {os.path.relpath(fpath, output_dir)}")

    print(f"[Dataset Generator] Sample dataset generation complete.\n")
    return output_dir
