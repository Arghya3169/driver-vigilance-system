"""
Mock Data & Highway Safety Telemetry
Includes real-world highway rest-stops catalog and safe stopping havens.
"""

import math
import random
import time
from typing import Dict, List, Optional


class RestStopCatalog:
    """
    Catalog of emergency safe stopping places, highway rest areas, and service plazas.
    Calculates distances, estimated time of arrival (ETA), and recommended pull-offs.
    """

    DEFAULT_REST_STOPS = [
        {
            "id": "RS-101",
            "name": "Highway Oasis Plaza (Exit 42)",
            "type": "Full Service Plaza",
            "distance_km": 1.2,
            "eta_mins": 2,
            "amenities": ["24/7 Restrooms", "Coffee Shop", "Truck & Car Parking", "EV Chargers"],
            "address": "Interstate Exit 42, Northbound",
            "urgency": "Immediate Safe Haven"
        },
        {
            "id": "RS-102",
            "name": "State Highway Rest Area #14",
            "type": "Designated Rest Stop",
            "distance_km": 2.8,
            "eta_mins": 4,
            "amenities": ["Picnic Area", "Restrooms", "Lighted Parking Lot", "Emergency Callbox"],
            "address": "Mile Marker 128 Eastbound",
            "urgency": "High Recommendation"
        },
        {
            "id": "RS-103",
            "name": "Shell Express Travel Center",
            "type": "Fuel & Convenience",
            "distance_km": 4.5,
            "eta_mins": 6,
            "amenities": ["Fuel / EV", "Convenience Mart", "Coffee", "Restrooms"],
            "address": "Route 9 Junction, Westside",
            "urgency": "Secondary"
        },
        {
            "id": "RS-104",
            "name": "Comfort Inn & Suites Traveler Parking",
            "type": "Lodging / Long Rest",
            "distance_km": 6.1,
            "eta_mins": 8,
            "amenities": ["Overnight Rooms", "24/7 Lobby", "Secure Parking"],
            "address": "400 Hospitality Lane",
            "urgency": "Extended Sleep"
        },
        {
            "id": "RS-105",
            "name": "Scenic Valley Turnout & Safe Pull-off",
            "type": "Emergency Pull-off",
            "distance_km": 0.8,
            "eta_mins": 1,
            "amenities": ["Wide Shoulder", "Paved Pull-off Bay", "Cellular Service"],
            "address": "Highway Curve KM 14.2",
            "urgency": "Emergency Immediate"
        }
    ]

    @classmethod
    def get_nearest_rest_stop(cls, current_speed_kmh: float = 80.0) -> Dict:
        """Returns the single closest safe rest area with dynamic ETA."""
        stops = sorted(cls.DEFAULT_REST_STOPS, key=lambda s: s["distance_km"])
        nearest = dict(stops[0])
        # Update dynamic ETA based on speed
        speed = max(20.0, current_speed_kmh)
        nearest["eta_mins"] = max(1, math.ceil((nearest["distance_km"] / speed) * 60))
        return nearest

    @classmethod
    def get_all_recommendations(cls, current_speed_kmh: float = 80.0) -> List[Dict]:
        """Returns all nearby safe stopping areas sorted by proximity."""
        results = []
        speed = max(20.0, current_speed_kmh)
        for stop in sorted(cls.DEFAULT_REST_STOPS, key=lambda s: s["distance_km"]):
            copy_s = dict(stop)
            copy_s["eta_mins"] = max(1, math.ceil((copy_s["distance_km"] / speed) * 60))
            results.append(copy_s)
        return results

