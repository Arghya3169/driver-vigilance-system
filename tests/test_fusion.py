"""
Unit tests for Multi-Modal Vigilance Fusion Engine (Ocular & Seat Posture).
Verifies individual modality thresholds and joint "All Conditions Triggered" logic.
"""

import unittest
from core.fusion import MultiModalVigilanceFusion, VigilanceLevel
from core.posture import PostureState


class TestMultiModalFusion(unittest.TestCase):

    def setUp(self):
        self.fusion = MultiModalVigilanceFusion()

    def test_nominal_alert_state(self):
        """Active driver with normal eyes and active posture should remain ALERT_NORMAL."""
        ocular = {
            "risk_score": 0.0,
            "is_microsleep": False,
            "eyes_closed_sec": 0.0,
            "is_yawning": False
        }
        posture = {
            "state": PostureState.ACTIVE,
            "is_compromised": False,
            "risk_score": 0.0,
            "compromised_duration_sec": 0.0
        }

        res = self.fusion.compute_fusion(ocular, posture)
        self.assertEqual(res["level"], VigilanceLevel.ALERT)
        self.assertFalse(res["is_critical"])
        self.assertFalse(res["all_conditions_triggered"])
        self.assertLess(res["composite_risk_score"], 30.0)

    def test_all_conditions_triggered(self):
        """
        When Eyes are Closed/Microsleep + Posture is Inactive/Dropped,
        system must trigger CRITICAL_SLEEP_ONSET and set all_conditions_triggered=True.
        """
        ocular = {
            "risk_score": 80.0,
            "is_microsleep": True,
            "eyes_closed_sec": 1.6,
            "is_yawning": False
        }
        posture = {
            "state": PostureState.HEAD_DROPPED,
            "is_compromised": True,
            "risk_score": 80.0,
            "compromised_duration_sec": 1.8
        }

        res = self.fusion.compute_fusion(ocular, posture)
        self.assertTrue(res["all_conditions_triggered"])
        self.assertEqual(res["level"], VigilanceLevel.CRITICAL)
        self.assertTrue(res["is_critical"])
        self.assertGreaterEqual(len(res["trigger_reasons"]), 2)

    def test_extreme_eye_closure_override(self):
        """Eyes closed >= 2.0s should trigger instant critical alert even if posture is active."""
        ocular = {
            "risk_score": 90.0,
            "is_microsleep": True,
            "eyes_closed_sec": 2.2,
            "is_yawning": False
        }
        posture = {
            "state": PostureState.ACTIVE,
            "is_compromised": False,
            "risk_score": 0.0,
            "compromised_duration_sec": 0.0
        }

        res = self.fusion.compute_fusion(ocular, posture)
        self.assertEqual(res["level"], VigilanceLevel.CRITICAL)
        self.assertTrue(res["is_critical"])


if __name__ == "__main__":
    unittest.main()
