import pandas as pd
from run import FEATURES, snapshot


def test_history_respects_cutoff_and_forward_label_window():
    o = pd.DataFrame(
        [
            {
                "opportunity_id": "a",
                "created_at": "2024-01-01",
                "stage": "Closed Won",
                "is_won": True,
            },
            {
                "opportunity_id": "b",
                "created_at": "2024-01-01",
                "stage": "Closed Won",
                "is_won": True,
            },
        ]
    )
    h = pd.DataFrame(
        [
            ("a", "Discovery", "2024-01-01"),
            ("a", "Proposal", "2024-02-01"),
            ("a", "Closed Won", "2024-03-01"),
            ("b", "Discovery", "2024-01-01"),
            ("b", "Closed Won", "2024-12-01"),
        ],
        columns=["opportunity_id", "stage", "entered_at"],
    )
    s = snapshot(o, h, "2024-01-31").set_index("opportunity_id")
    assert (
        s.loc["a", "stage_asof"] == "Discovery"
        and s.loc["a", "won_90d"] == 1
        and s.loc["b", "won_90d"] == 0
    )
    assert not {"stage", "is_won", "amount", "close_date", "forecast_category"} & set(
        FEATURES
    )
    h.loc[len(h)] = ["a", "Closed Lost", "2025-01-01"]
    pd.testing.assert_frame_equal(
        s, snapshot(o, h, "2024-01-31").set_index("opportunity_id")
    )


def test_already_closed_and_not_yet_created_deals_are_excluded():
    o = pd.DataFrame(
        [("a", "2024-01-01"), ("b", "2024-03-01")],
        columns=["opportunity_id", "created_at"],
    )
    h = pd.DataFrame(
        [
            ("a", "Discovery", "2024-01-01"),
            ("a", "Closed Lost", "2024-01-15"),
            ("b", "Discovery", "2024-03-01"),
        ],
        columns=["opportunity_id", "stage", "entered_at"],
    )
    assert snapshot(o, h, "2024-01-31").empty
