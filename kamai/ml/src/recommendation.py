"""Transparent earnings and opportunity calculations using an ML ETA."""

from __future__ import annotations

from typing import Any


def _money(value: float) -> float:
    return round(float(value), 2)


def calculate_opportunity(predicted_minutes: float, inputs: dict[str, Any], model_mae: float) -> dict[str, Any]:
    """Convert predicted duration into a transparent net-hourly opportunity."""
    if predicted_minutes <= 0:
        raise ValueError("predicted_minutes must be positive")

    gross_per_order = float(inputs.get("gross_per_order", 45.0))
    commission_pct = float(inputs.get("commission_pct", 0.0))
    if commission_pct >= 1:
        commission_pct /= 100.0
    commission_pct = min(max(commission_pct, 0.0), 0.5)
    tds_pct = float(inputs.get("tds_pct", 1.0))
    if tds_pct >= 1:
        tds_pct /= 100.0
    tds_pct = min(max(tds_pct, 0.0), 0.1)

    distance_km = float(inputs.get("distance_km", 5.0))
    fuel_price = float(inputs.get("fuel_price_per_litre", 102.0))
    mileage = max(float(inputs.get("vehicle_mileage_kmpl", 45.0)), 1.0)
    app_fee_hourly = max(float(inputs.get("app_fee_hourly", 2.0)), 0.0)
    minimum_wage_hourly = max(float(inputs.get("minimum_wage_hourly", 90.0)), 1.0)
    scarcity_score = min(max(float(inputs.get("scarcity_score", 4.0)), 0.0), 8.0)

    deliveries_per_hour = min(max(60.0 / predicted_minutes, 0.5), 4.0)
    gross_hourly = deliveries_per_hour * gross_per_order
    commission_hourly = gross_hourly * commission_pct
    gst_on_commission = commission_hourly * 0.18
    tds_hourly = gross_hourly * tds_pct
    fuel_hourly = (distance_km * deliveries_per_hour / mileage) * fuel_price
    net_hourly = gross_hourly - commission_hourly - gst_on_commission - tds_hourly - fuel_hourly - app_fee_hourly

    wage_ratio = net_hourly / minimum_wage_hourly
    if wage_ratio >= 1.1:
        fair_wage_status = "ABOVE"
    elif wage_ratio >= 0.9:
        fair_wage_status = "NEAR"
    else:
        fair_wage_status = "BELOW"

    wage_component = min(max(wage_ratio, 0.0), 1.5) / 1.5 * 60.0
    scarcity_component = scarcity_score / 8.0 * 30.0
    confidence_component = max(0.0, 1.0 - model_mae / max(predicted_minutes, 1.0)) * 10.0
    opportunity_score = round(min(max(wage_component + scarcity_component + confidence_component, 0.0), 100.0), 1)
    if fair_wage_status == "BELOW":
        opportunity_score = min(opportunity_score, 49.0)

    if opportunity_score >= 75:
        opportunity_label = "BEST"
    elif opportunity_score >= 55:
        opportunity_label = "GOOD"
    elif opportunity_score >= 35:
        opportunity_label = "MODERATE"
    else:
        opportunity_label = "AVOID"

    reasons = []
    if scarcity_score >= 5:
        reasons.append("High rider scarcity increases the chance of receiving orders.")
    if inputs.get("road_traffic_density", "Medium") in {"High", "Jam"}:
        reasons.append("Heavy traffic increases the predicted delivery time.")
    if distance_km >= 10:
        reasons.append("Longer delivery distance increases time and fuel cost.")
    if fair_wage_status == "ABOVE":
        reasons.append("Predicted take-home pay is above the selected wage benchmark.")
    elif fair_wage_status == "BELOW":
        reasons.append("Predicted take-home pay is below the selected wage benchmark.")
    if not reasons:
        reasons.append("The estimate reflects average traffic, distance, payout, and rider availability.")

    return {
        "predicted_delivery_minutes": round(predicted_minutes, 1),
        "prediction_interval_minutes": [
            round(max(5.0, predicted_minutes - model_mae), 1),
            round(predicted_minutes + model_mae, 1),
        ],
        "deliveries_per_hour": round(deliveries_per_hour, 2),
        "gross_hourly": _money(gross_hourly),
        "deductions": {
            "commission": _money(commission_hourly),
            "gst_on_commission": _money(gst_on_commission),
            "tds": _money(tds_hourly),
            "fuel": _money(fuel_hourly),
            "app_fee": _money(app_fee_hourly),
        },
        "net_hourly": _money(net_hourly),
        "minimum_wage_hourly": _money(minimum_wage_hourly),
        "fair_wage_status": fair_wage_status,
        "opportunity_score": opportunity_score,
        "opportunity_label": opportunity_label,
        "reasons": reasons,
        "method": "ML delivery-time prediction plus transparent earnings calculation",
    }
