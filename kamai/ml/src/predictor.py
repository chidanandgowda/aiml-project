"""Load the trained model and produce predictions and recommendations."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

import joblib

from .features import normalize_prediction_payload
from .recommendation import calculate_opportunity


class KamaiPredictor:
    def __init__(self, artifacts_dir: Path | str):
        artifacts_dir = Path(artifacts_dir)
        model_path = artifacts_dir / "delivery_time_model.joblib"
        metadata_path = artifacts_dir / "model_metadata.json"
        if not model_path.exists() or not metadata_path.exists():
            raise FileNotFoundError("Model artifacts are missing. Run train.py first.")
        self.model = joblib.load(model_path)
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    @staticmethod
    def _personal_adjustment(payload: dict[str, Any]) -> dict[str, Any]:
        history = payload.get("personal_duration_history", [])
        if not isinstance(history, list):
            raise ValueError("personal_duration_history must be a list")
        residuals = []
        for row in history[:100]:
            if not isinstance(row, dict):
                continue
            try:
                predicted = float(row["predicted_minutes"])
                actual = float(row["actual_minutes"])
            except (KeyError, TypeError, ValueError):
                continue
            if 5 <= predicted <= 180 and 5 <= actual <= 180:
                residuals.append(actual - predicted)
        if len(residuals) < 5:
            return {"applied": False, "samples": len(residuals), "adjustment_minutes": 0.0, "minimum_samples": 5}
        adjustment = min(max(float(median(residuals)), -5.0), 5.0)
        return {
            "applied": True,
            "samples": len(residuals),
            "adjustment_minutes": round(adjustment, 2),
            "method": "Median residual calibration, limited to ±5 minutes",
        }

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        frame = normalize_prediction_payload(payload)
        base_prediction = max(float(self.model.predict(frame)[0]), 5.0)
        personalization = self._personal_adjustment(payload)
        prediction = max(base_prediction + personalization["adjustment_minutes"], 5.0)
        mae = float(self.metadata["test_metrics"]["mae_minutes"])
        return {
            "predicted_delivery_minutes": round(prediction, 1),
            "base_prediction_minutes": round(base_prediction, 1),
            "prediction_interval_minutes": [round(max(5.0, prediction - mae), 1), round(prediction + mae, 1)],
            "personalization": personalization,
            "model_name": self.metadata["selected_model"],
            "model_mae_minutes": round(mae, 2),
            "training_rows": self.metadata["dataset"]["training_rows"],
            "disclaimer": "Estimate trained on an India-focused food-delivery dataset; it is not proprietary quick-commerce data.",
        }

    def recommend(self, payload: dict[str, Any]) -> dict[str, Any]:
        prediction = self.predict(payload)
        result = calculate_opportunity(
            prediction["predicted_delivery_minutes"],
            payload,
            float(prediction["model_mae_minutes"]),
        )
        result["model"] = {
            "name": prediction["model_name"],
            "mae_minutes": prediction["model_mae_minutes"],
            "training_rows": prediction["training_rows"],
            "disclaimer": prediction["disclaimer"],
        }
        result["personalization"] = prediction["personalization"]
        return result

    def rank(self, payload: dict[str, Any]) -> dict[str, Any]:
        shared = payload.get("shared", {})
        opportunities = payload.get("opportunities", [])
        if not isinstance(shared, dict) or not isinstance(opportunities, list):
            raise ValueError("shared must be an object and opportunities must be a list")
        if not 1 <= len(opportunities) <= 20:
            raise ValueError("opportunities must contain between 1 and 20 scenarios")

        ranked = []
        for index, opportunity in enumerate(opportunities):
            if not isinstance(opportunity, dict):
                raise ValueError("each opportunity must be an object")
            name = str(opportunity.get("name", f"Opportunity {index + 1}"))
            recommendation = self.recommend({**shared, **opportunity})
            ranked.append({"name": name, **recommendation})

        ranked.sort(key=lambda row: (row["opportunity_score"], row["net_hourly"]), reverse=True)
        for index, row in enumerate(ranked, start=1):
            row["rank"] = index
        return {"best": ranked[0], "ranked": ranked, "scenario_count": len(ranked)}
