# Dataset Card: Kamai Delivery-Time Training Data

## Dataset

Kamai uses `zomato_cleaned.csv`, a cleaned copy of the public Zomato delivery-operations dataset. The checked-in copy contains 38,964 Indian food-delivery records and 22 source columns.

- Public mirror: https://huggingface.co/datasets/allenborochin/zomato_delivery_EDA
- Stated upstream source: https://www.kaggle.com/datasets/gauravmalik26/food-delivery-dataset
- Retrieval date: 2026-09-29
- Local file: `data/raw/zomato_cleaned.csv`
- Local SHA-256: `A76ED049CD698B189797B180FFCE60DCDAD7B45B99729CD171B5562EC585EB0C`

## Intended use

The dataset is used for a supervised regression task: predicting delivery duration in minutes from operational context available before a delivery finishes. It supplies an India-focused academic baseline for Kamai's opportunity estimator.

## Features used

- Delivery distance
- Order hour, weekday, and weekend status
- Pickup delay
- Weather and road-traffic categories
- Vehicle type and condition
- Order type
- Number of simultaneous deliveries
- Festival indicator
- City type
- Rider rating

## Exclusions

- `delivery_speed` is excluded because it is calculated using the target delivery duration and would leak the answer into training.
- `Delivery_person_Age` is excluded to avoid ranking work opportunities using age.
- Raw IDs and exact latitude/longitude fields are excluded from the model.

## Known limitations

- The data is food-delivery data, not proprietary Zepto, Blinkit, or Instamart quick-commerce data.
- The public mirror describes the records as operational data, but Kamai cannot independently verify how the upstream dataset was collected.
- The `City` column contains city categories such as Metropolitan and Urban, not explicit city names.
- Weather and traffic values are historical categorical labels, not live conditions.
- Public copies of the broader dataset have documented coordinate-quality problems. Kamai uses the cleaned distance field and enforces plausible distance bounds.

## Ethical use

Predictions are decision support for riders, not a guarantee of orders or income. They must not be used by a platform to penalize, deactivate, or allocate work unfairly to a rider.
