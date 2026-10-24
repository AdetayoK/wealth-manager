"""Evaluate the model under explicitly ordered, real-valued synthetic fixtures."""
from datetime import date, timedelta
import math
import pytest

from app.ml import evaluate_classifier


def fixture_rows(n=160):
    days = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    # Deterministic alternating binary outcomes with both holdout classes.
    features = [[math.sin(i / 5), math.cos(i / 9)] for i in range(n)]
    labels = [int(math.sin(i / 5) > 0) for i in range(n)]
    return days, features, labels


def test_ml_chronological_embargo_and_baseline():
    days, features, labels = fixture_rows()
    r = evaluate_classifier(["feature_a", "feature_b"], days, features, labels,
                            label_horizon=5, holdout_fraction=.25)
    assert r["rows"] == 160
    assert r["embargo_rows"] == 5
    assert r["train_rows"] == 115
    assert r["holdout_rows"] == 40
    assert r["development_ends"] < r["holdout_starts"]
    assert 0 <= r["metrics"]["model_brier"] <= 1
    assert 0 <= r["metrics"]["baseline_brier"] <= 1
    assert len(r["standardized_coefficients"]) == 2
    assert r["model_family"].startswith("standardized logistic")


def test_ml_rejects_insufficient_and_unsorted_history():
    days, features, labels = fixture_rows()
    with pytest.raises(ValueError, match="strictly increasing"):
        evaluate_classifier(["a", "b"], list(reversed(days)), features, labels)
    with pytest.raises(ValueError, match="100"):
        evaluate_classifier(["a", "b"], days[:50], features[:50], labels[:50])
    with pytest.raises(ValueError, match="both classes|Both classes"):
        evaluate_classifier(["a", "b"], days, features, [1] * 160)
