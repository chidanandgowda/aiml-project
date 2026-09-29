import unittest

from src.recommendation import calculate_opportunity


class RecommendationTests(unittest.TestCase):
    def test_recommendation_contains_explainable_breakdown(self):
        result = calculate_opportunity(
            25.0,
            {
                "distance_km": 5,
                "gross_per_order": 55,
                "commission_pct": 10,
                "road_traffic_density": "Medium",
                "scarcity_score": 6,
                "minimum_wage_hourly": 90,
            },
            4.0,
        )
        self.assertGreater(result["gross_hourly"], result["net_hourly"])
        self.assertIn("fuel", result["deductions"])
        self.assertIn(result["fair_wage_status"], {"ABOVE", "NEAR", "BELOW"})
        self.assertTrue(result["reasons"])

    def test_one_percent_tds_is_not_treated_as_full_fraction(self):
        result = calculate_opportunity(30, {"gross_per_order": 50, "tds_pct": 1}, 4)
        self.assertEqual(result["deductions"]["tds"], 1.0)

    def test_below_wage_opportunity_is_not_labelled_good(self):
        result = calculate_opportunity(
            45,
            {"gross_per_order": 30, "minimum_wage_hourly": 100, "scarcity_score": 8},
            4,
        )
        self.assertEqual(result["fair_wage_status"], "BELOW")
        self.assertLess(result["opportunity_score"], 55)

    def test_slower_delivery_reduces_net_hourly(self):
        inputs = {"distance_km": 5, "gross_per_order": 50}
        fast = calculate_opportunity(20, inputs, 4)
        slow = calculate_opportunity(40, inputs, 4)
        self.assertGreater(fast["net_hourly"], slow["net_hourly"])


if __name__ == "__main__":
    unittest.main()
