"""Rolling-origin, 90-day open-pipeline forecast; terminal history provides labels."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from reporting import render
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

FEATURES = ["stage_asof", "segment", "type", "lead_source", "age_days"]


def snapshot(opps, history, asof, with_labels=True):
    asof = pd.Timestamp(asof)
    end = asof + pd.Timedelta(days=90)
    h = history.copy()
    h["entered_at"] = pd.to_datetime(h.entered_at)
    o = opps.copy()
    o["created_at"] = pd.to_datetime(o.created_at)
    current = (
        h[h.entered_at <= asof]
        .sort_values(["entered_at", "stage"])
        .drop_duplicates("opportunity_id", keep="last")
    )
    current = current.rename(columns={"stage": "stage_asof"})[
        ["opportunity_id", "stage_asof"]
    ]
    rows = o[o.created_at <= asof].merge(current, on="opportunity_id")
    rows = rows[~rows.stage_asof.str.startswith("Closed")].copy()
    rows["age_days"] = (asof - rows.created_at).dt.days
    rows["asof"] = asof
    # Never use snapshot-final stage, forecast_category, is_won, close_date or amount as features.
    if with_labels:
        won = set(
            h[
                (h.stage == "Closed Won")
                & (h.entered_at > asof)
                & (h.entered_at <= end)
            ].opportunity_id
        )
        rows["won_90d"] = rows.opportunity_id.isin(won).astype(int)
    return rows


def fit(train):
    prep = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURES[:-1]),
            ("num", StandardScaler(), ["age_days"]),
        ]
    )
    return make_pipeline(prep, LogisticRegression(max_iter=2000, C=0.5)).fit(
        train[FEATURES], train.won_90d
    )


def main(data, out):
    o = pd.read_csv(data / "raw/opportunities.csv")
    a = pd.read_csv(data / "raw/accounts.csv")
    h = pd.read_csv(data / "raw/opportunity_stage_history.csv")
    o = o.merge(a[["account_id", "segment"]], on="account_id", validate="many_to_one")
    train = pd.concat(
        [
            snapshot(o, h, d)
            for d in pd.date_range("2023-06-30", "2025-09-30", freq="QE")
        ],
        ignore_index=True,
    )
    tests = [snapshot(o, h, d) for d in ["2026-03-31 23:59:59", "2026-06-30 23:59:59"]]
    # Prevent the same deal from occurring in both train and held-out periods.
    heldout_ids = set(pd.concat(tests).opportunity_id)
    train = train[~train.opportunity_id.isin(heldout_ids)]
    model = fit(train)
    base = float(train.won_90d.mean())
    results = []
    predictions = []
    for test in tests:
        prob = model.predict_proba(test[FEATURES])[:, 1]
        test = test.copy()
        test["win_probability_90d"] = prob
        test["baseline_probability"] = base
        # Amounts are latest exported values, not historically versioned. See limitations.
        amount = test.amount.fillna(0)
        actual = float((amount * test.won_90d).sum())
        forecast = float((amount * prob).sum())
        results.append(
            {
                "asof": str(test["asof"].iloc[0]),
                "deals": len(test),
                "base_rate": float(test.won_90d.mean()),
                "brier": brier_score_loss(test.won_90d, prob),
                "baseline_brier": brier_score_loss(
                    test.won_90d, np.full(len(test), base)
                ),
                "auc": roc_auc_score(test.won_90d, prob),
                "actual_won_value": actual,
                "predicted_won_value": forecast,
                "bias_usd": forecast - actual,
                "missing_amounts": int(test.amount.isna().sum()),
            }
        )
        predictions.append(
            test[
                [
                    "opportunity_id",
                    "asof",
                    "stage_asof",
                    "age_days",
                    "won_90d",
                    "win_probability_90d",
                    "baseline_probability",
                    "amount",
                ]
            ]
        )
    results = pd.DataFrame(results)
    current = snapshot(o, h, "2026-09-30 23:59:59", False)
    current["win_probability_90d"] = model.predict_proba(current[FEATURES])[:, 1]
    current["expected_value_90d"] = (
        current.amount.fillna(0) * current.win_probability_90d
    )
    metrics = {
        "heldout_deals": int(results.deals.sum()),
        "mean_brier": round(results.brier.mean(), 4),
        "baseline_brier": round(results.baseline_brier.mean(), 4),
        "open_deals": len(current),
        "current_expected_value_USD": round(current.expected_value_90d.sum(), 2),
        "training_rows": len(train),
    }
    render(
        out,
        "Sales forecast laboratory",
        metrics,
        {
            "backtests": results,
            "heldout_predictions": pd.concat(predictions),
            "current_pipeline": current[
                [
                    "opportunity_id",
                    "stage_asof",
                    "segment",
                    "age_days",
                    "amount",
                    "win_probability_90d",
                    "expected_value_90d",
                ]
            ],
        },
        "90-day win probability for deals open at each cutoff. Training labels mature before evaluation cutoffs. Sales amounts are latest exported values: dollar backtests illustrate valuation and are not historically audited revenue forecasts. Missing amounts contribute zero and are counted. New deals created after a cutoff are excluded.",
        (
            ["Model Brier", "Constant baseline Brier"],
            [metrics["mean_brier"], metrics["baseline_brier"]],
            "Brier score (lower is better)",
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("reports"))
    a = p.parse_args()
    main(a.data, a.out)
