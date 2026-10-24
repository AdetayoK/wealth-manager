"""Point-in-time machine-learning evaluation for externally supplied labelled rows.

No preloaded market dataset, no auto-training. This is an experiment evaluator:
it learns a binary outcome from numeric historical features, uses only past
data for fitting, purges a user-declared future label horizon, and compares
against a constant-probability baseline on a chronologically later holdout.
"""
from __future__ import annotations

from datetime import date

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def evaluate_classifier(
    feature_names: list[str],
    dates: list[date],
    features: list[list[float]],
    labels: list[int],
    label_horizon: int = 5,
    holdout_fraction: float = .25,
) -> dict:
    rows = len(labels)
    if not 100 <= rows <= 30000:
        raise ValueError("ML evaluation requires 100–30000 dated labelled observations")
    if len(feature_names) < 1 or len(feature_names) > 30:
        raise ValueError("Provide 1–30 named features")
    if len(set(feature_names)) != len(feature_names):
        raise ValueError("Feature names must be distinct")
    if len(dates) != rows or len(features) != rows:
        raise ValueError("Dates, features and outcomes must contain exactly the same rows")
    if any(dates[i] >= dates[i + 1] for i in range(rows - 1)):
        raise ValueError("Dates must be unique and strictly increasing")
    if not 1 <= label_horizon <= 60 or not .15 <= holdout_fraction <= .4:
        raise ValueError("Label horizon must be 1–60 observations and holdout fraction .15–.40")
    x = np.asarray(features, dtype=float)
    y = np.asarray(labels, dtype=int)
    if x.shape != (rows, len(feature_names)):
        raise ValueError("Feature matrix must have exactly one numeric value for every named feature")
    if not np.all(np.isfinite(x)) or not set(y).issubset({0, 1}):
        raise ValueError("Features must be finite numbers and labels strictly 0/1")
    cut = int(rows * (1 - holdout_fraction))
    train_end = cut - label_horizon
    if train_end < 60 or rows - cut < 20:
        raise ValueError("Too few rows remain after chronological holdout and future-label embargo")
    if len(np.unique(y[:train_end])) != 2 or len(np.unique(y[cut:])) != 2:
        raise ValueError("Both classes are needed in development and holdout periods")

    model = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000, class_weight=None, random_state=42)),
    ])
    model.fit(x[:train_end], y[:train_end])
    held_prob = model.predict_proba(x[cut:])[:, 1]
    base_prob = float(np.mean(y[:train_end]))
    baseline = np.full(rows - cut, base_prob)
    truth = y[cut:]
    brier_model = float(brier_score_loss(truth, held_prob))
    brier_base = float(brier_score_loss(truth, baseline))
    acc = float(accuracy_score(truth, held_prob >= .5))
    base_acc = float(accuracy_score(truth, baseline >= .5))
    auc = float(roc_auc_score(truth, held_prob))

    coefficients = model.named_steps["classifier"].coef_[0]
    ranked = sorted(zip(feature_names, map(float, coefficients)), key=lambda z: -abs(z[1]))
    return {
        "rows": rows,
        "train_rows": train_end,
        "embargo_rows": label_horizon,
        "holdout_rows": rows - cut,
        "development_ends": dates[train_end - 1].isoformat(),
        "holdout_starts": dates[cut].isoformat(),
        "metrics": {
            "model_brier": round(brier_model, 5),
            "baseline_brier": round(brier_base, 5),
            "model_accuracy": round(acc, 4),
            "baseline_accuracy": round(base_acc, 4),
            "holdout_roc_auc": round(auc, 4),
        },
        "beats_baseline_on_brier": bool(brier_model < brier_base),
        "standardized_coefficients": [
            {"feature": name, "coefficient": round(value, 4)} for name, value in ranked
        ],
        "model_family": "standardized logistic regression (scikit-learn)",
        "warnings": [
            "This is a chronological holdout diagnostic, not evidence of investment alpha.",
            "Feature timestamps and point-in-time availability must be verified outside this API; leaked future information can invalidate the test.",
            "Adjacent time-series observations may be highly dependent. The embargo only protects the declared label horizon, not every dependency.",
            "Single split results are sensitive to regime changes, class imbalance and sample selection.",
            "No automatic investment decisions, live quotes, portfolio forecasts, or persistent model deployment.",
        ],
    }
