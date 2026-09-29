# Kamai AIML Module

This module trains an India-focused delivery-time regression model and exposes predictions through a small local HTTP service.

## Set up

From the `kamai/ml` directory:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The dataset is included at `data/raw/zomato_cleaned.csv` so the university demonstration is reproducible offline.

## Train and evaluate

```powershell
.venv\Scripts\python.exe train.py
```

Generated outputs:

- `artifacts/delivery_time_model.joblib`
- `artifacts/model_metadata.json`
- `reports/training_report.json`
- `reports/test_predictions.csv`
- `reports/model_evaluation.html` (self-contained visual report)

## Run tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Start the prediction service

```powershell
.venv\Scripts\python.exe serve_model.py
```

The service listens on `http://127.0.0.1:8000` and provides:

- `GET /health`
- `GET /model-info`
- `POST /predict`
- `POST /recommend`
- `POST /rank` (ranks up to 20 darkstore or shift scenarios)

`/predict` and `/recommend` optionally accept `personal_duration_history`. After five valid `{predicted_minutes, actual_minutes}` pairs, Kamai applies a conservative median-residual calibration capped at ±5 minutes and reports the adjustment explicitly.

Example request:

```json
{
  "distance_km": 5.2,
  "order_hour": 19,
  "pickup_delay_minutes": 10,
  "order_weekday": 4,
  "weather_conditions": "Cloudy",
  "road_traffic_density": "High",
  "vehicle_condition": 1,
  "type_of_order": "Meal",
  "type_of_vehicle": "motorcycle",
  "multiple_deliveries": 1,
  "festival": "No",
  "city_type": "Metropolitan",
  "rider_rating": 4.7,
  "gross_per_order": 55,
  "commission_pct": 10,
  "scarcity_score": 6,
  "minimum_wage_hourly": 90
}
```
