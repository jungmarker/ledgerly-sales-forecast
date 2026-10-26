# Design notes

## Decision and contract

How much of today’s open pipeline is likely to win in the next 90 days?

Stage event history → point-in-time open-deal snapshots → matured 90-day labels → logistic model → future-period backtests and current pipeline probabilities.

The input contract is the Ledgerly raw CSV/schema documented in the pinned source repository. Monetary values are USD, dates refer to the synthetic company calendar and the snapshot is September 30, 2026. Reads are local and source files are never modified. Missing or malformed required columns fail visibly rather than silently inventing input fields.

## Evaluation

Features are stage at cutoff, source, opportunity type, segment and age. Training snapshots end September 2025; outcomes mature before March/June 2026 evaluation. Held-out deal IDs are removed from training. Terminal stage, current forecast category, close date and amount are excluded from model features.

Brier score and ROC-AUC versus a constant historical win-rate baseline, plus indicative expected pipeline dollars.

The tests use small constructed examples to catch cutoff leakage, incorrect identity decisions, review bypasses or revenue reconciliation errors. They do not merely assert that the pipeline runs. The full seeded pipeline runs in CI to expose schema and integration failures.

## Operator workflow

Run the analysis, read metrics.json, inspect detailed CSV exceptions or predictions, and review the narrative before taking a business action. Reruns replace the reports in the selected output folder. Save previous output folders if you need historical runs. Data is regenerated from the pinned source; no credentials are required for local analysis.

## Production changes

Use source contracts and historical snapshots, least-privilege storage, access controls, execution logging, retry/idempotency policies and data freshness monitoring. Separate feature generation from labeled evaluation and version both data and model configuration. Validate on representative real data before setting business thresholds. This demo uses local files and full rebuilds at about a few thousand accounts; it is not a benchmark of distributed scale.

## Known limitations

Historical amount versions do not exist. Dollar backtests use latest exported amounts and cannot establish real historical revenue forecast accuracy. Segment/source are assumed stable. Repeated snapshots and synthetic dynamics limit inference. No post-cutoff new-pipeline generation forecast or prediction interval.

## Interview walkthrough

1. Explain the business question and the input table grain.
2. Reproduce the report and trace one result to its source rows.
3. Explain the baseline, failure cases and why the evaluation split is appropriate.
4. Show the adversarial unit test and make a small behavior change.
5. Describe the changes needed for reliable operation on real company data.
