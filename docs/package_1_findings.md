# Package 1 — Exploration & cleaning: findings

Written findings note for the brief's Package 1 deliverable. Full analysis and code
live in `notebooks/01_explore.ipynb`; this is the short, readable summary.

## Missing values

Only two columns have gaps: `ltv_months` (4 rows) and `cumulative_profit` (29 rows).
Both are **targets** used in later packages (Package 2 and Package 6 respectively),
not features — no feature column in the dataset has any missing values.

**How they were handled:** a missing target is dropped at the point the specific
model that needs it is trained, not eagerly at the start — a row missing
`cumulative_profit` is still perfectly good training data for the upsell model in
Package 3, which never touches that column. A target with a missing value is always
dropped, never imputed: there is no valid stand-in for an unknown outcome, and
filling one in would mean training a model to predict a number we invented.

## Correlation against `cumulative_profit`

`ltv_months` (0.85) and `upsell` (0.65) correlate most strongly with profit — expected,
since both are mechanically part of how profit accumulates over a customer
relationship, not an independent discovery. This is exactly why they can't be used as
*features* to predict `cumulative_profit` in Package 6: at prediction time for a new
campaign, future LTV/upsell behavior isn't known yet. Using them would be data
leakage.

The more interesting signal: `ad_budget` correlates *negatively* (-0.21) with
per-customer profit, and `calls_to_closed` is the strongest negative correlate
overall (-0.55) — fewer calls needed to close predicts more profit, a pattern that
turned out to repeat across nearly every later package.

## `ad_budget` → `num_leads`: proportional, or diminishing returns?

The relationship is close to linear/proportional across most of the range, with only
a mild flattening at the top budget levels (₪15,000 → ₪20,000). **More budget does
buy roughly proportionally more leads** — the real story, as the next section shows,
is what happens to those leads afterward, not how many arrive.

## Conversion rate by budget tier

Conversion rate is `closed / num_leads` per row, averaged per tier (`pd.cut` on
`ad_budget`; the brief's tier boundaries — Low ≤1500, Mid 2000–5000, High >5000 —
leave ₪1,500–2,000 undefined, so those rows were kept in their own bucket rather than
silently folded into Low or Mid).

| Budget tier | Conversion rate |
|---|---|
| Low (≤1500) | 4.5% |
| **Mid (2000–5000)** | **8.5%** |
| High (>5000) | 5.4% |

**This is the headline result of Package 1:** conversion rate does **not** rise with
budget. Mid converts best, and High converts worse than Mid — barely better than Low.
Bigger ad spend buys proportionally more leads, but not proportionally better ones.
That's direct, data-driven evidence for the founder's suspicion that ad spend isn't
being optimized on evidence — a pattern Package 6 later confirms and sharpens at the
profit level (campaigns of ₪2,000–5,000 turned out to be a clear profit sweet spot).
