# FunnelIQ — Findings & Recommendations

Short write-up of what each work package found and what it means for Northbound
Media. Full analysis and code live in `notebooks/`; live numbers are served by
the deployed app (see README for the URL).

## Executive summary

- **Ad spend has a sweet spot, not a "more is better" curve.** Campaigns sized
  ₪2,000–5,000 convert best (Package 1) and generate far more profit per campaign
  (Package 6) than either very small or very large campaigns. Restructuring the
  ₪50,000/month budget into ~10–25 campaigns in this range (e.g. 25×₪2,000) is
  projected to roughly **double** profit versus the current even split.
- **"Less effort to close" predicts almost everything good.** Fewer calls needed
  to close a deal (`calls_to_closed`) is the top driver of longer customer
  lifetime (Package 2), higher upsell probability (Package 3), and becoming a
  "super customer" (Package 4) — the same signal, independently, three times.
- **The sales manager's "stop after call 3" instinct is half right.** Profit per
  deal does fall sharply after call 3, but ~21% of closed deals only close on
  call 5 — a blanket cutoff would forfeit a fifth of revenue (Package 5). The
  fix is to prioritize *who* gets chased past call 3 using the models below, not
  to cut everyone off.
- **Northbound's best customers are also its cheapest to acquire.** Super
  customers (18.3% of the base) generate 39.6% of total profit at a *lower*
  average acquisition cost than everyone else (Package 4) — they aren't being
  overpaid for, they're being under-recognized.

## Package 1 — Exploration & cleaning

Only 2 of 20 columns have missing values (`ltv_months`, `cumulative_profit`),
both targets, not features. **Conversion rate does not rise with budget** — it
peaks at the Mid tier (₪2,000–5,000, 8.5%) and is worse at High (>₪5,000, 5.4%),
direct evidence that ad spend isn't being allocated on evidence. See
`docs/package_1_findings.md` for the full write-up.

## Package 2 — Predicting customer lifetime (LTV)

CatBoost predicts `ltv_months` within ~3 months on average (RMSE 2.95, R²
0.944). `calls_to_closed` dominates feature importance; removing it roughly
doubles RMSE but the model doesn't collapse, confirming real (if concentrated)
signal rather than leakage. **Takeaway:** quality of close predicts customer
value far better than budget or lead volume — worth investigating *why* a fast
close correlates with a better-fit customer.

## Package 3 — Predicting upsell probability

CatBoost reaches ROC-AUC 0.781 on purchasers-only data (the honest version of
the problem, after catching that `purchased=0 ⇒ upsell=0` always, which let an
earlier version of the model solve an easier sub-question). A simple rule
(`calls_to_closed ≤ 3` and `customer_acquisition_cost ≤ 1250`) matches the
model on precision (72.0% vs. 69.8%) but misses a third of real upsell
opportunities (69.0% vs. 83.2% recall). **Recommendation:** rank purchasers by
predicted probability rather than calling everyone above a 0.5 cutoff — a
missed upsell likely costs more than one unproductive call.

## Package 4 — The "super customer" score

A tuned CatBoost model (ROC-AUC 0.813) scores any customer's likelihood of
becoming a super customer — someone who stays, upsells, and refers — from
early-funnel signals alone, before a purchase happens. Super customers are
18.3% of the base but generate 39.6% of total profit, at 0.69x the acquisition
cost of everyone else. The engineered `budget_tier` feature turned out fully
redundant with `ad_budget` (0% importance) — a useful negative result.

## Package 5 — The follow-up paradox

Dropout across the 5 follow-up stages is **not monotonic**: the 3rd→4th call is
the *lowest*-dropout stage of all five (10%), then 4th→5th spikes to the
*highest* (30%). Among closed deals, 31% close in 2 calls but a real second
cluster (21%, 690 deals) needs all 5 — a hard cutoff at call 3 would forfeit
that cluster, not just fringe cases. Profit per deal does fall 64% right after
call 3 (₪6,278 → ₪2,255). **Recommendation:** no blanket cutoff — use the
LTV/upsell/super-customer scores to decide which leads are worth chasing past
call 3.

## Package 6 — Budget optimization

LightGBM (RMSE 5,254, R² 0.775) predicts `cumulative_profit` from full
historical funnel outcomes, combined with a typical-funnel-profile-per-budget-
bucket lookup for simulating hypothetical campaigns. Of four ₪50,000/month
allocation strategies tested, **25×₪2,000 wins clearly** — ₪561k predicted
profit, 11.2x ROI, cross-checked against raw historical means (agreement within
~3%). The 2×₪20k+₪10k strategy is worst by a wide margin (₪14k, 0.28x ROI).
**One caveat carried honestly into the app:** the 100×₪500 prediction (₪394k)
is a known 3x overprediction (raw data implies ₪121k) — the "typical profile"
approximation breaks down at the extreme low end of the budget range, and the
app's simulator flags this explicitly rather than hiding it.

## What this means for Northbound, next month

Restructure the ₪50,000 monthly budget into ~10–25 campaigns of ₪2,000–5,000
each instead of the current even split. Use the deployed scoring models to
prioritize which leads get follow-up calls past the 3rd attempt and which
purchasers get upsell outreach, rather than applying the same rule to everyone.
Revisit the super-customer score periodically to catch high-value customers
earlier in their lifecycle, not after the fact.
