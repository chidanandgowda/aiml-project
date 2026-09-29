"""Dataset cleaning and feature engineering shared by training and inference."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


TARGET_COLUMN = "delivery_minutes"

NUMERIC_FEATURES = [
    "distance_km",
    "order_hour",
    "pickup_delay_minutes",
    "order_weekday",
    "is_weekend",
    "vehicle_condition",
    "multiple_deliveries",
    "rider_rating",
]

CATEGORICAL_FEATURES = [
    "weather_conditions",
    "road_traffic_density",
    "type_of_order",
    "type_of_vehicle",
    "festival",
    "city_type",
]

MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def _parse_minutes(value: Any) -> float:
    """Convert an HH:MM time to minutes from midnight."""
    if value is None or pd.isna(value):
        return np.nan
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return np.nan
    try:
        hour_text, minute_text = text.split(":", maxsplit=1)
        hour = int(float(hour_text))
        minute = int(float(minute_text))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return float(hour * 60 + minute)
    except (TypeError, ValueError):
        pass
    return np.nan


def _pickup_delay(order_time: Any, pickup_time: Any) -> float:
    ordered = _parse_minutes(order_time)
    picked = _parse_minutes(pickup_time)
    if np.isnan(ordered) or np.isnan(picked):
        return np.nan
    delay = picked - ordered
    if delay < 0:
        delay += 24 * 60
    return delay if 0 <= delay <= 180 else np.nan


def prepare_training_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict[str, Any]]:
    """Create a leakage-safe model frame from the public delivery dataset."""
    required = {
        "Delivery_person_ID",
        "Delivery_person_Ratings",
        "Order_Date",
        "Time_Orderd",
        "Time_Order_picked",
        "Weather_conditions",
        "Road_traffic_density",
        "Vehicle_condition",
        "Type_of_order",
        "Type_of_vehicle",
        "multiple_deliveries",
        "Festival",
        "City",
        "Time_taken (min)",
        "distance_km",
    }
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")

    frame = pd.DataFrame(index=raw.index)
    frame["distance_km"] = pd.to_numeric(raw["distance_km"], errors="coerce")
    frame["order_hour"] = raw["Time_Orderd"].map(_parse_minutes) / 60.0
    frame["pickup_delay_minutes"] = [
        _pickup_delay(order_time, pickup_time)
        for order_time, pickup_time in zip(raw["Time_Orderd"], raw["Time_Order_picked"])
    ]

    order_dates = pd.to_datetime(raw["Order_Date"], format="%d-%m-%Y", errors="coerce")
    frame["order_weekday"] = order_dates.dt.weekday.astype("float")
    frame["is_weekend"] = frame["order_weekday"].isin([5, 6]).astype("float")
    frame.loc[frame["order_weekday"].isna(), "is_weekend"] = np.nan

    frame["vehicle_condition"] = pd.to_numeric(raw["Vehicle_condition"], errors="coerce")
    frame["multiple_deliveries"] = pd.to_numeric(raw["multiple_deliveries"], errors="coerce")
    frame["rider_rating"] = pd.to_numeric(raw["Delivery_person_Ratings"], errors="coerce")
    frame["weather_conditions"] = raw["Weather_conditions"].astype("string").str.strip()
    frame["road_traffic_density"] = raw["Road_traffic_density"].astype("string").str.strip()
    frame["type_of_order"] = raw["Type_of_order"].astype("string").str.strip()
    frame["type_of_vehicle"] = raw["Type_of_vehicle"].astype("string").str.strip()
    frame["festival"] = raw["Festival"].astype("string").str.strip()
    frame["city_type"] = raw["City"].astype("string").str.strip().replace({"Metropolitian": "Metropolitan"})

    target = pd.to_numeric(raw["Time_taken (min)"], errors="coerce").rename(TARGET_COLUMN)
    groups = raw["Delivery_person_ID"].astype("string").fillna("unknown-rider")

    valid = (
        target.between(5, 180)
        & frame["distance_km"].between(0.1, 50)
        & frame["pickup_delay_minutes"].between(0, 180)
    )
    dropped = int((~valid).sum())
    frame = frame.loc[valid, MODEL_FEATURES].reset_index(drop=True)
    target = target.loc[valid].reset_index(drop=True)
    groups = groups.loc[valid].reset_index(drop=True)

    audit = {
        "raw_rows": int(len(raw)),
        "training_rows": int(len(frame)),
        "dropped_rows": dropped,
        "excluded_leakage_columns": ["delivery_speed"],
        "excluded_sensitive_columns": ["Delivery_person_Age"],
        "feature_count": len(MODEL_FEATURES),
    }
    return frame, target, groups, audit


def normalize_prediction_payload(payload: dict[str, Any]) -> pd.DataFrame:
    """Validate and normalize one API prediction payload."""
    defaults: dict[str, Any] = {
        "distance_km": 5.0,
        "order_hour": 19.0,
        "pickup_delay_minutes": 10.0,
        "order_weekday": float(datetime.now().weekday()),
        "vehicle_condition": 1.0,
        "multiple_deliveries": 1.0,
        "rider_rating": 4.7,
        "weather_conditions": "Sunny",
        "road_traffic_density": "Medium",
        "type_of_order": "Meal",
        "type_of_vehicle": "motorcycle",
        "festival": "No",
        "city_type": "Metropolitan",
    }
    values = {**defaults, **payload}

    numeric_ranges = {
        "distance_km": (0.1, 50.0),
        "order_hour": (0.0, 23.99),
        "pickup_delay_minutes": (0.0, 180.0),
        "order_weekday": (0.0, 6.0),
        "vehicle_condition": (0.0, 2.0),
        "multiple_deliveries": (0.0, 3.0),
        "rider_rating": (1.0, 5.0),
    }
    for name, (minimum, maximum) in numeric_ranges.items():
        try:
            values[name] = float(values[name])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if not minimum <= values[name] <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")

    values["is_weekend"] = float(int(values["order_weekday"]) in {5, 6})
    values["festival"] = "Yes" if str(values["festival"]).lower() in {"yes", "true", "1"} else "No"
    values["city_type"] = str(values["city_type"]).replace("Metropolitian", "Metropolitan")

    return pd.DataFrame([{name: values[name] for name in MODEL_FEATURES}])

