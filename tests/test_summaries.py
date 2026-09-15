import json
import unittest
from unittest.mock import patch

from smartpak_inventory.summaries import (
    build_verified_observations,
    generate_verified_sku_summary,
)


SAMPLE_SKU = {
    "SKU_NUMBER": "12345",
    "SKU_NAME": "Sample supplement",
    "INVENTORY_SNAPSHOT_STATUS": "AVAILABLE",
    "TOTAL_OH": 240,
    "PLYMOUTH_OH": 180,
    "RENO_OH": 60,
    "PLYMOUTH_OOS": "IN STOCK",
    "RENO_OOS": "IN STOCK",
    "T30_AVG_DAILY_SALES": 12,
    "T90_AVG_DAILY_SALES": 11,
    "T180_AVG_DAILY_SALES": 10,
    "F30_AVG_DAILY_FORECAST": 15,
    "F90_AVG_DAILY_FORECAST": 13,
    "F180_AVG_DAILY_FORECAST": 12,
    "F30_DOS": 16,
    "F90_DOS": 18.5,
    "F180_DOS": 20,
}


class VerifiedObservationsTest(unittest.TestCase):
    def test_builds_deterministic_executive_callouts(self):
        observations = build_verified_observations(SAMPLE_SKU)
        by_id = {item["id"]: item["text"] for item in observations}

        self.assertIn("positive position", by_id["inventory"])
        self.assertIn("broadly stable", by_id["sales_trend"])
        self.assertIn("25.0% above", by_id["material_sales_forecast_gap"])
        self.assertIn("forecast review", by_id["material_sales_forecast_gap"])

    def test_oos_location_is_an_immediate_customer_opportunity(self):
        row = dict(SAMPLE_SKU)
        row["RENO_OH"] = 0
        row["RENO_OOS"] = "OOS"

        observations = build_verified_observations(row)
        inventory_text = next(
            item["text"] for item in observations if item["id"] == "inventory"
        )

        self.assertIn("Reno is OOS", inventory_text)
        self.assertIn("immediate opportunity", inventory_text)
        self.assertIn("speed-to-customer delivery", inventory_text)

    def test_no_snapshot_does_not_invent_location_status(self):
        row = dict(SAMPLE_SKU)
        row["INVENTORY_SNAPSHOT_STATUS"] = "NO SNAPSHOT"
        row["PLYMOUTH_OH"] = None
        row["RENO_OH"] = None

        observations = build_verified_observations(row)
        inventory_text = next(
            item["text"] for item in observations if item["id"] == "inventory"
        )

        self.assertIn("cannot be evaluated", inventory_text)
        self.assertNotIn("IN STOCK", inventory_text)

    @patch("smartpak_inventory.summaries._call_cortex")
    def test_rejects_ids_not_in_verified_observations(self, mock_cortex):
        observations = build_verified_observations(SAMPLE_SKU)
        mock_cortex.return_value = {
            "selected_ids": [
                "inventory",
                "invented_claim",
                "sales_trend",
                "inventory",
            ]
        }

        result = generate_verified_sku_summary.__wrapped__(
            "12345",
            json.dumps(observations),
        )

        self.assertEqual(len(result["observations"]), 3)
        self.assertIn("positive position", result["observations"][0])
        self.assertIn("25.0% above", result["observations"][1])
        self.assertIn("broadly stable", result["observations"][2])


if __name__ == "__main__":
    unittest.main()
