# FunnelIQ

Marketing-funnel intelligence for **Northbound Media** — turning two years of raw
funnel data into models and recommendations a non-technical team can actually use.

> **Status: complete.** All 6 analytical packages are trained live and exposed as
> endpoints in the deployed app, behind real Supabase Auth + RLS, on Railway with
> CI gating every push. See [REPORT.md](REPORT.md) for the findings and business
> recommendations.

**Live app:** https://funneliq-production-1366.up.railway.app — sign in and try
live LTV/upsell/super-customer predictions and the budget allocation simulator,
all computed against Supabase at request time. Railway's GitHub App is
authorized on this repo, connected to `main`, and has an active deployment
trigger, so every push here redeploys automatically. GitHub Actions runs lint +
tests on every push too — see the badge below.

[![CI](https://github.com/YoranKa/funneliq/actions/workflows/ci.yml/badge.svg)](https://github.com/YoranKa/funneliq/actions/workflows/ci.yml)

---

## The problem

Northbound Media is a performance-marketing agency. They track every funnel step —
ad spend, leads, who answered the phone, who survived each follow-up call, who closed,
how long each client stayed, whether they upsold, and whether they referred someone.
It all sits in one spreadsheet nobody trusts.

The questions FunnelIQ is being built to answer:

| Question | Approach |
|---|---|
| How long will a new customer stay? | Regression on `ltv_months` |
| Who is likely to buy more? | Classification on `upsell` |
| Who becomes a "super customer"? | 0–100 score from `referred` |
| Where should the ad budget go? | Profit model + allocation simulation |
| Are late follow-ups a waste of time? | Funnel drop-out analysis |

---

## The dataset

`data/funnel_marketing_data.csv` — 3,500 records, one row per customer/campaign.

| Column | Meaning |
|---|---|
| `ad_budget` | Monthly ad spend (₪) |
| `num_leads` | Leads generated |
| `leads_answered` / `leads_not_answered` | Split by phone pickup |
| `followup_1` … `followup_5` | Leads remaining after each follow-up round |
| `not_closed` / `closed` | Funnel outcome counts |
| `calls_to_closed` / `calls_to_not_closed` | Avg. calls before closing / giving up |
| `customer_acquisition_cost` | Cost per acquired customer (₪) |
| `ltv_months` | Customer lifetime in months |
| `purchased` / `upsell` | Initial purchase / bought more (1/0) |
| `cumulative_profit` | Total profit from the customer (₪) |
| `referred` | Referred someone? (Yes/No) |

The raw CSV is committed on purpose: at 200 KB with no personal data, keeping it in
the repo is what makes the project reproducible by anyone who clones it.

---

## Repository layout

```
funneliq/
├── data/                  raw dataset
├── notebooks/             exploration and model development (messy on purpose)
├── app/                   production application code (clean, deployable)
├── db/                    Supabase schema + one-time data loading script
├── tests/                 pytest suite run by GitHub Actions on every push
├── .github/workflows/     CI: lint (ruff) + test (pytest)
├── docs/                  the project brief and written findings
├── REPORT.md              findings and business recommendations, package by package
├── requirements.txt       runtime dependencies (what the server installs)
└── requirements-dev.txt   development dependencies (notebooks, plots, tests)
```

`notebooks/` and `app/` are deliberately separate. Notebooks are for figuring things
out; anything that needs to run unattended on a server gets rewritten cleanly into `app/`.

---

## Local setup

Requires [conda](https://docs.conda.io/) (or any Python 3.11 environment manager).

```bash
git clone <repo-url>
cd funneliq

conda create -n funneliq python=3.11 pip -y
conda activate funneliq

pip install -r requirements-dev.txt
```

Python 3.11 is chosen deliberately over newer releases: it is the version with the
widest, most stable support across the gradient-boosting libraries and hosting platforms.

Packages are installed with `pip` rather than `conda install` so that the exact versions
running locally are the ones reproducible from `requirements.txt` on the server.

To use the environment in Jupyter, select the **Python (funneliq)** kernel.

### Running the app

Copy `.env.example` to `.env` and fill in your Supabase project's URL, anon key,
and (for `db/load_data.py` only) service-role key. Then, with the schema applied
(`supabase db query --linked -f db/schema.sql`, or paste it into the Supabase SQL
Editor) and the data loaded:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and sign in with a user created under
**Authentication → Users** in the Supabase dashboard. The login screen runs
entirely client-side against Supabase Auth; the API never sees a password, only
the session token it forwards to PostgREST so Row Level Security decides what
the signed-in user can read.

---

## Built with

Python 3.11 · pandas · scikit-learn · XGBoost · LightGBM · CatBoost · FastAPI · Supabase · Railway

---

## Progress

- [x] Project structure, git repository, pinned environment
- [x] Data exploration and cleaning
- [x] Deployed app (Railway, auto-deploy from GitHub)
- [x] Supabase database + data loading script
- [x] Supabase Auth login + RLS
- [x] Customer-lifetime model — exposed as `POST /api/predict/ltv`
- [x] Upsell model — exposed as `POST /api/predict/upsell`
- [x] Super-customer score — exposed as `POST /api/predict/super-customer-score`
- [x] Follow-up analysis — exposed as `GET /api/insights/followup-dropout`
- [x] Budget optimizer — exposed as `POST /api/simulate/budget-allocation`
- [x] CI workflow (GitHub Actions: lint + test on every push)
- [x] Findings write-up ([REPORT.md](REPORT.md))
