"""Generate a self-contained visual evaluation report without notebook state."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd


def _bar(label: str, value: float, maximum: float, suffix: str = "") -> str:
    width = 0 if maximum <= 0 else min(max(value / maximum * 100, 0), 100)
    return (
        f'<div class="bar-row"><span>{html.escape(label)}</span><div class="track">'
        f'<i style="width:{width:.1f}%"></i></div><b>{value:.3f}{suffix}</b></div>'
    )


def _scatter_svg(evaluation: pd.DataFrame) -> str:
    sample = evaluation.iloc[:: max(1, len(evaluation) // 450)].head(450)
    low = float(min(sample["actual_minutes"].min(), sample["predicted_minutes"].min()))
    high = float(max(sample["actual_minutes"].max(), sample["predicted_minutes"].max()))
    span = max(high - low, 1.0)

    def x(value: float) -> float:
        return 48 + (float(value) - low) / span * 520

    def y(value: float) -> float:
        return 315 - (float(value) - low) / span * 260

    points = "".join(
        f'<circle cx="{x(row.actual_minutes):.1f}" cy="{y(row.predicted_minutes):.1f}" r="2.4" />'
        for row in sample.itertuples()
    )
    return f"""
    <svg viewBox="0 0 620 350" role="img" aria-label="Actual versus predicted delivery minutes">
      <line x1="48" y1="315" x2="568" y2="55" class="ideal" />
      <line x1="48" y1="315" x2="580" y2="315" class="axis" />
      <line x1="48" y1="315" x2="48" y2="42" class="axis" />
      <g class="points">{points}</g>
      <text x="252" y="342">Actual minutes</text>
      <text x="16" y="200" transform="rotate(-90 16 200)">Predicted minutes</text>
      <text x="50" y="334">{low:.0f}</text><text x="552" y="334">{high:.0f}</text>
    </svg>"""


def generate_evaluation_report(metadata: dict[str, Any], evaluation: pd.DataFrame, output_path: Path) -> None:
    comparison = metadata["validation_results"]
    max_mae = max(row["mae_minutes"] for row in comparison.values())
    model_bars = "".join(
        _bar(name.replace("_", " ").title(), values["mae_minutes"], max_mae, " min")
        for name, values in comparison.items()
    )
    top_features = metadata["feature_importance"][:8]
    max_importance = max(row["importance"] for row in top_features)
    feature_bars = "".join(
        _bar(row["feature"].replace("_", " ").title(), max(row["importance"], 0), max_importance)
        for row in top_features
    )
    traffic_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{values['rows']:,}</td><td>{values['mae_minutes']:.3f} min</td></tr>"
        for name, values in metadata["traffic_error_slices"].items()
    )
    metrics = metadata["test_metrics"]

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kamai ML Evaluation Report</title>
<style>
:root{{--bg:#0b0c0b;--card:#151714;--line:#292d27;--text:#f6f7f4;--muted:#9ca39a;--green:#12d896;--red:#f0544a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 Arial,sans-serif}}main{{max-width:1080px;margin:auto;padding:48px 24px 80px}}h1{{font-size:42px;margin:0 0 8px}}h2{{margin-top:0}}p{{color:var(--muted)}}.tag{{color:var(--green);text-transform:uppercase;letter-spacing:.12em;font-size:12px}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:28px 0}}.metric,.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px}}.metric b{{display:block;color:var(--green);font-size:25px}}.metric span{{color:var(--muted);font-size:12px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:18px 0}}.bar-row{{display:grid;grid-template-columns:150px 1fr 85px;gap:10px;align-items:center;margin:12px 0;font-size:12px}}.track{{height:8px;background:var(--line);border-radius:8px;overflow:hidden}}.track i{{display:block;height:100%;background:var(--green)}}.bar-row b{{font-family:monospace;text-align:right}}svg{{width:100%;height:auto}}svg text{{fill:var(--muted);font-size:11px}}.axis{{stroke:var(--muted);stroke-width:1}}.ideal{{stroke:var(--green);stroke-width:2;stroke-dasharray:6}}.points circle{{fill:var(--green);opacity:.28}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted)}}.note{{font-size:12px;border-left:3px solid var(--red);padding-left:14px}}@media(max-width:760px){{.metrics{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="tag">Kamai · reproducible model evaluation</div><h1>Delivery-time regression</h1>
<p>Generated {html.escape(metadata['trained_at_utc'])}. The untouched test set is grouped by delivery-person ID to reduce rider leakage.</p>
<div class="metrics"><div class="metric"><b>{metrics['mae_minutes']:.2f} min</b><span>Test MAE</span></div><div class="metric"><b>{metrics['rmse_minutes']:.2f} min</b><span>Test RMSE</span></div><div class="metric"><b>{metrics['r2']:.3f}</b><span>Test R²</span></div><div class="metric"><b>{metadata['mae_improvement_over_baseline_pct']:.2f}%</b><span>MAE improvement over baseline</span></div></div>
<div class="grid"><section class="card"><h2>Validation comparison</h2><p>Lower MAE is better.</p>{model_bars}</section><section class="card"><h2>Permutation importance</h2><p>Increase in prediction error when a feature is shuffled.</p>{feature_bars}</section></div>
<section class="card"><h2>Actual vs predicted</h2><p>A sampled view of the held-out test predictions. The dashed diagonal is a perfect prediction.</p>{_scatter_svg(evaluation)}</section>
<div class="grid"><section class="card"><h2>Error by traffic</h2><table><thead><tr><th>Traffic</th><th>Rows</th><th>MAE</th></tr></thead><tbody>{traffic_rows}</tbody></table></section><section class="card"><h2>Dataset audit</h2><p><b>{metadata['dataset']['raw_rows']:,}</b> source rows → <b>{metadata['dataset']['training_rows']:,}</b> validated rows.</p><p>{html.escape(metadata['dataset']['split_strategy'])}</p><p class="note">Target-derived delivery speed and rider age were excluded. This public food-delivery dataset is an adjacent academic baseline, not proprietary quick-commerce data.</p></section></div>
</main></body></html>"""
    output_path.write_text(document, encoding="utf-8")

