"""
Unit tests for UTA-RLDD Dataset Evaluator and Benchmark Harness.
"""

import os
import unittest
from core.dataset_evaluator import UTARLDDEvaluator


class TestUTARLDDEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = UTARLDDEvaluator(frame_stride=2)

    def test_infer_ground_truth(self):
        """Validates canonical UTA-RLDD filename mapping."""
        # Canonical UTA-RLDD numbering (0, 5, 10)
        gt0 = self.evaluator.infer_ground_truth("0.mp4")
        gt5 = self.evaluator.infer_ground_truth("5.mp4")
        gt10 = self.evaluator.infer_ground_truth("10.mp4")

        self.assertEqual(gt0, (0, "Alert"))
        self.assertEqual(gt5, (1, "Low Vigilance"))
        self.assertEqual(gt10, (2, "Drowsy"))

        # Semantic filename mapping
        gt_alert = self.evaluator.infer_ground_truth("subject_01_0_alert.mp4")
        gt_low = self.evaluator.infer_ground_truth("subject_02_5_low_vigilance.mp4")
        gt_drowsy = self.evaluator.infer_ground_truth("subject_03_10_drowsy.mp4")

        self.assertEqual(gt_alert[0], 0)
        self.assertEqual(gt_low[0], 1)
        self.assertEqual(gt_drowsy[0], 2)

    def test_evaluate_sample_clip(self):
        """Validates evaluation on a sample clip if present."""
        sample_path = "dataset/utarldd_samples/Subject_01/0_alert.mp4"
        if os.path.exists(sample_path):
            result = self.evaluator.evaluate_video(sample_path, max_frames=20)
            self.assertEqual(result.ground_truth_class, 0)
            self.assertGreater(result.fps_achieved, 10.0)
            self.assertGreater(result.total_frames_analyzed, 0)


if __name__ == "__main__":
    unittest.main()
