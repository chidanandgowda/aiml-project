# Model Card: Kamai Delivery-Time Regressor

## Purpose

Estimate delivery duration for an Indian last-mile delivery context. Kamai converts that estimate into an explainable net-hourly earnings calculation and fair-wage warning.

## Training design

- Supervised regression
- Delivery-person group split: 70% training, 15% validation, 15% testing
- Models compared: median baseline, Ridge regression, Random Forest, and Histogram Gradient Boosting
- Selection metric: validation mean absolute error (MAE)
- Final reporting: test MAE, RMSE, R2, baseline improvement, feature importance, and traffic-level error slices

The final model name and measured results are stored in `artifacts/model_metadata.json` after training.

## Inputs

Distance, order time, pickup delay, weekday, traffic, weather, vehicle information, multiple-delivery count, festival status, city type, and rider rating.

## Outputs

- Predicted delivery duration in minutes
- An indicative range of prediction ± test MAE
- Downstream estimated deliveries/hour and net earnings/hour
- Fair-wage status and opportunity score
- Plain-language reasons

After five valid personal predicted-versus-actual duration pairs, the service can apply an explicitly reported median-residual correction. The correction is capped at ±5 minutes so limited personal history cannot overwhelm the population model. The `/rank` endpoint applies the same model and earnings logic consistently to multiple darkstore or shift scenarios.

## Responsible-AI decisions

- Rider age is not used.
- A target-derived speed field is excluded to prevent leakage.
- Model performance is compared with a simple baseline.
- The UI identifies the source domain and does not claim platform-proprietary accuracy.
- The earnings calculation is kept separate and inspectable instead of being hidden inside an opaque score.

## Limitations

This is an academic prototype. Predictions can be wrong during unusual traffic, weather, demand spikes, platform policy changes, or in locations unlike the training data. The MAE range is not a formal statistical confidence interval.
