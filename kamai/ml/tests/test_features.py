import unittest

from src.features import MODEL_FEATURES, normalize_prediction_payload
from src.predictor import KamaiPredictor


class FeatureTests(unittest.TestCase):
    def test_payload_defaults_create_complete_frame(self):
        frame = normalize_prediction_payload({"distance_km": 4.2})
        self.assertEqual(list(frame.columns), MODEL_FEATURES)
        self.assertEqual(float(frame.iloc[0]["distance_km"]), 4.2)

    def test_invalid_distance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "distance_km"):
            normalize_prediction_payload({"distance_km": -1})

    def test_weekend_is_derived(self):
        frame = normalize_prediction_payload({"order_weekday": 6})
        self.assertEqual(float(frame.iloc[0]["is_weekend"]), 1.0)

    def test_personal_calibration_requires_five_samples(self):
        adjustment = KamaiPredictor._personal_adjustment({
            "personal_duration_history": [
                {"predicted_minutes": 20, "actual_minutes": 22}
            ] * 4
        })
        self.assertFalse(adjustment["applied"])

    def test_personal_calibration_uses_capped_median_residual(self):
        adjustment = KamaiPredictor._personal_adjustment({
            "personal_duration_history": [
                {"predicted_minutes": 20, "actual_minutes": 30}
            ] * 5
        })
        self.assertTrue(adjustment["applied"])
        self.assertEqual(adjustment["adjustment_minutes"], 5.0)


if __name__ == "__main__":
    unittest.main()
