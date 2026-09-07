"""
Unit tests for GPS locator and nearest petrol pump / rest area routing.
"""

import unittest
from core.gps_locator import GPSLocator, haversine_distance_km


class TestGPSLocator(unittest.TestCase):

    def test_haversine_distance(self):
        """Validates great-circle distance calculation."""
        # Distance between two points ~ 1.5 km apart
        lat1, lon1 = 12.9695, 79.1455
        lat2, lon2 = 12.9800, 79.1550
        dist = haversine_distance_km(lat1, lon1, lat2, lon2)
        self.assertGreater(dist, 1.0)
        self.assertLess(dist, 2.5)

    def test_nearest_petrol_pump_lookup(self):
        """Validates that nearest petrol pump is retrieved with coordinates, distance, and maps URL."""
        locator = GPSLocator()
        nearest = locator.locate_nearest_petrol_pump_or_rest_area(vehicle_speed_kmh=60.0)

        self.assertIsNotNone(nearest)
        self.assertIn("name", nearest)
        self.assertIn("lat", nearest)
        self.assertIn("lon", nearest)
        self.assertIn("distance_km", nearest)
        self.assertIn("eta_mins", nearest)
        self.assertIn("maps_url", nearest)
        self.assertTrue(nearest["maps_url"].startswith("https://www.google.com/maps/dir/"))
        self.assertGreater(nearest["distance_km"], 0.0)
        self.assertGreaterEqual(nearest["eta_mins"], 1)

    def test_driver_coordinates(self):
        """Validates driver GPS coordinates retrieval."""
        locator = GPSLocator()
        lat, lon, label = locator.get_driver_coordinates()
        self.assertIsInstance(lat, float)
        self.assertIsInstance(lon, float)
        self.assertIsInstance(label, str)
        self.assertNotEqual(lat, 0.0)
        self.assertNotEqual(lon, 0.0)


if __name__ == "__main__":
    unittest.main()
