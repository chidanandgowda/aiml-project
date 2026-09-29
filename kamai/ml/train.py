"""Train, compare, evaluate, and save Kamai's delivery-time regression model."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.linear_model import Ridge

from src.features import CATEGORICAL_FEATURES, MODEL_FEATURES, NUMERIC_FEATURES, prepare_training_frame
from src.reporting import generate_evaluation_report


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "data" / "raw" / "zomato_cleaned.csv"
ARTIFACTS_DIR = ROOT / "artifacts"
REPORTS_DIR = ROOT / "reports"


def regression_metrics(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae_minutes": round(float(mean_absolute_error(actual, predicted)), 4),
        "rmse_minutes": round(float(np.sqrt(mean_squared_error(actual, predicted))), 4),
        "r2": round(float(r2_score(actual, predicted)), 4),
    }


def split_by_rider(features: pd.DataFrame, target: pd.Series, groups: pd.Series):
    outer = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)
    train_val_idx, test_idx = next(outer.split(features, target, groups))
    train_val_x = features.iloc[train_val_idx]
    train_val_y = target.iloc[train_val_idx]
    train_val_groups = groups.iloc[train_val_idx]

    inner = GroupShuffleSplit(n_splits=1, test_size=0.1765, random_state=43)
    train_rel, validation_rel = next(inner.split(train_val_x, train_val_y, train_val_groups))

    return (
        features.iloc[train_val_idx[train_rel]],
        target.iloc[train_val_idx[train_rel]],
        features.iloc[train_val_idx[validation_rel]],
        target.iloc[train_val_idx[validation_rel]],
        features.iloc[test_idx],
        target.iloc[test_idx],
    )


def linear_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC_FEATURES),
            ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL_FEATURES),
        ]
    )


def tree_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("numeric", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
            (
                "categorical",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("encode", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        sparse_threshold=0,
    )


def build_candidates() -> dict[str, Pipeline]:
    categorical_indexes = list(range(len(NUMERIC_FEATURES), len(MODEL_FEATURES)))
    return {
        "median_baseline": Pipeline([("model", DummyRegressor(strategy="median"))]),
        "ridge_regression": Pipeline([("preprocess", linear_preprocessor()), ("model", Ridge(alpha=1.0))]),
        "random_forest": Pipeline(
            [
                ("preprocess", tree_preprocessor()),
                ("model", RandomForestRegressor(n_estimators=180, min_samples_leaf=3, max_features=0.8, n_jobs=-1, random_state=42)),
            ]
        ),
        "hist_gradient_boosting": Pipeline(
            [
                ("preprocess", tree_preprocessor()),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        max_iter=220,
                        learning_rate=0.08,
                        max_leaf_nodes=31,
                        l2_regularization=0.2,
                        categorical_features=categorical_indexes,
                        random_state=42,
                    ),
                ),
            ]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args()

    raw = pd.read_csv(args.data)
    features, target, groups, audit = prepare_training_frame(raw)
    train_x, train_y, validation_x, validation_y, test_x, test_y = split_by_rider(features, target, groups)

    candidates = build_candidates()
    validation_results: dict[str, dict[str, float]] = {}
    for name, candidate in candidates.items():
        candidate.fit(train_x, train_y)
        validation_results[name] = regression_metrics(validation_y, candidate.predict(validation_x))
        print(f"{name}: {validation_results[name]}")

    eligible = {name: metrics for name, metrics in validation_results.items() if name != "median_baseline"}
    selected_name = min(eligible, key=lambda name: eligible[name]["mae_minutes"])
    selected = candidates[selected_name]

    combined_x = pd.concat([train_x, validation_x], ignore_index=True)
    combined_y = pd.concat([train_y, validation_y], ignore_index=True)
    selected.fit(combined_x, combined_y)
    test_predictions = selected.predict(test_x)
    test_metrics = regression_metrics(test_y, test_predictions)

    baseline = DummyRegressor(strategy="median").fit(combined_x, combined_y)
    baseline_metrics = regression_metrics(test_y, baseline.predict(test_x))
    improvement = 100.0 * (baseline_metrics["mae_minutes"] - test_metrics["mae_minutes"]) / baseline_metrics["mae_minutes"]

    sample_size = min(2000, len(test_x))
    importance = permutation_importance(
        selected,
        test_x.sample(sample_size, random_state=42),
        test_y.loc[test_x.sample(sample_size, random_state=42).index],
        scoring="neg_mean_absolute_error",
        n_repeats=3,
        random_state=42,
        n_jobs=-1,
    )
    feature_importance = sorted(
        [
            {"feature": feature, "importance": round(float(score), 4)}
            for feature, score in zip(MODEL_FEATURES, importance.importances_mean)
        ],
        key=lambda row: row["importance"],
        reverse=True,
    )

    evaluation = test_x.copy()
    evaluation["actual_minutes"] = test_y.to_numpy()
    evaluation["predicted_minutes"] = np.round(test_predictions, 3)
    evaluation["absolute_error"] = np.round(np.abs(test_predictions - test_y.to_numpy()), 3)

    traffic_slices = {}
    for traffic, rows in evaluation.groupby("road_traffic_density"):
        traffic_slices[str(traffic)] = {
            "rows": int(len(rows)),
            "mae_minutes": round(float(rows["absolute_error"].mean()), 3),
        }

    metadata = {
        "model_version": "1.0.0",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_model": selected_name,
        "target": "Time_taken (min)",
        "features": MODEL_FEATURES,
        "test_metrics": test_metrics,
        "baseline_test_metrics": baseline_metrics,
        "mae_improvement_over_baseline_pct": round(improvement, 2),
        "validation_results": validation_results,
        "feature_importance": feature_importance,
        "traffic_error_slices": traffic_slices,
        "dataset": {
            **audit,
            "source_file": args.data.name,
            "train_rows": int(len(train_x)),
            "validation_rows": int(len(validation_x)),
            "test_rows": int(len(test_x)),
            "split_strategy": "Group split by delivery-person ID (70/15/15)",
        },
        "limitations": [
            "The public data represents Indian food delivery, not proprietary quick-commerce operations.",
            "The dataset city field contains city types rather than explicit city names.",
            "Traffic and weather are categorical snapshots rather than live feeds.",
            "The prediction interval is a simple MAE-based range, not a calibrated probabilistic interval.",
        ],
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected, ARTIFACTS_DIR / "delivery_time_model.joblib")
    (ARTIFACTS_DIR / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (REPORTS_DIR / "training_report.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    evaluation.to_csv(REPORTS_DIR / "test_predictions.csv", index=False)
    generate_evaluation_report(metadata, evaluation, REPORTS_DIR / "model_evaluation.html")

    print(f"Selected model: {selected_name}")
    print(f"Test metrics: {test_metrics}")
    print(f"MAE improvement over median baseline: {improvement:.2f}%")
    print(f"Saved model to {ARTIFACTS_DIR / 'delivery_time_model.joblib'}")


if __name__ == "__main__":
    main()
