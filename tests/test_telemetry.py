"""
Unit tests for Seat Posture Detector and Rest Stop Catalog.
"""

import unittest
from core.mock_data import RestStopCatalog
from core.posture import SeatPostureDetector, PostureState


class TestPostureAndRestStops(unittest.TestCase):

    def test_seat_posture_classification(self):
        """Validates detection of active vs head-drop vs lateral lean postures."""
        detector = SeatPostureDetector()
        detector.calibrate(shoulder_width=300.0, neck_head_dist=120.0)

        # 1. Active attentive posture
        res_active = detector.evaluate_posture(
            nose_pt=(320.0, 180.0),
            left_shoulder_pt=(170.0, 300.0),
            right_shoulder_pt=(470.0, 300.0),
            head_pitch_deg=2.0,
            head_roll_deg=1.0
        )
        self.assertEqual(res_active["state"], PostureState.ACTIVE)
        self.assertTrue(res_active["is_active_posture"])

        # 2. Head drop forward (pitch down 26 degrees)
        res_head_drop = detector.evaluate_posture(
            nose_pt=(320.0, 240.0),
            left_shoulder_pt=(170.0, 300.0),
            right_shoulder_pt=(470.0, 300.0),
            head_pitch_deg=26.0,
            head_roll_deg=1.0
        )
        self.assertEqual(res_head_drop["state"], PostureState.HEAD_DROPPED)
        self.assertTrue(res_head_drop["is_compromised"])

        # 3. Lateral lean (head roll 22 degrees)
        res_lean = detector.evaluate_posture(
            nose_pt=(380.0, 200.0),
            left_shoulder_pt=(160.0, 270.0),
            right_shoulder_pt=(460.0, 330.0),
            head_pitch_deg=4.0,
            head_roll_deg=22.0
        )
        self.assertEqual(res_lean["state"], PostureState.LATERAL_LEAN)
        self.assertTrue(res_lean["is_compromised"])

    def test_rest_stop_catalog(self):
        """Validates nearest safe stop and ETA calculation."""
        nearest = RestStopCatalog.get_nearest_rest_stop(current_speed_kmh=80.0)
        self.assertIsNotNone(nearest)
        self.assertIn("name", nearest)
        self.assertIn("distance_km", nearest)
        self.assertIn("eta_mins", nearest)
        self.assertGreater(nearest["distance_km"], 0.0)
        self.assertGreaterEqual(nearest["eta_mins"], 1)

        all_stops = RestStopCatalog.get_all_recommendations()
        self.assertGreaterEqual(len(all_stops), 3)
        # Must be sorted by distance
        distances = [s["distance_km"] for s in all_stops]
        self.assertEqual(distances, sorted(distances))


if __name__ == "__main__":
    unittest.main()
