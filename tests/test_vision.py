"""
Unit tests for Vision module (EAR, MAR, and microsleep logic).
"""

import unittest
from core.synthetic_driver import SyntheticDriverGenerator
from core.vision import FaceOcularDetector


class TestVisionMetrics(unittest.TestCase):

    def setUp(self):
        self.detector = FaceOcularDetector()
        self.synth = SyntheticDriverGenerator()

    def test_ear_calculation_awake_vs_closed(self):
        """Validates EAR drops dramatically when eyes close."""
        # 1. Wide open eyes
        self.synth.set_states(eye_openness=1.0, mouth_openness=0.0)
        lms_open = self.synth.get_synthetic_landmarks()
        ear_open, _, _ = self.detector.calculate_ear(lms_open)

        # 2. Closed eyes
        self.synth.set_states(eye_openness=0.0, mouth_openness=0.0)
        lms_closed = self.synth.get_synthetic_landmarks()
        ear_closed, _, _ = self.detector.calculate_ear(lms_closed)

        self.assertGreater(ear_open, self.detector.ear_threshold)
        self.assertLess(ear_closed, self.detector.ear_threshold)
        self.assertGreater(ear_open, ear_closed * 3.0)

    def test_mar_calculation_normal_vs_yawn(self):
        """Validates MAR rises dramatically during a yawn."""
        # 1. Closed mouth
        self.synth.set_states(eye_openness=1.0, mouth_openness=0.0)
        lms_closed = self.synth.get_synthetic_landmarks()
        mar_closed = self.detector.calculate_mar(lms_closed)

        # 2. Wide yawn
        self.synth.set_states(eye_openness=1.0, mouth_openness=1.0)
        lms_yawn = self.synth.get_synthetic_landmarks()
        mar_yawn = self.detector.calculate_mar(lms_yawn)

        self.assertLess(mar_closed, self.detector.mar_threshold)
        self.assertGreater(mar_yawn, self.detector.mar_threshold)
        self.assertGreater(mar_yawn, mar_closed * 4.0)


if __name__ == "__main__":
    unittest.main()
