# FunnelIQ

Marketing-funnel intelligence for **Northbound Media** — turning two years of raw
funnel data into models and recommendations a non-technical team can actually use.

> **Status: in progress.** This README describes what exists today, not what is planned.
> Sections are added as each part is built and verified.

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
├── docs/                  the project brief and written findings
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

---

## Built with

Python 3.11 · pandas · scikit-learn · XGBoost · LightGBM · CatBoost · FastAPI · Supabase · Railway

---

## Progress

- [x] Project structure, git repository, pinned environment
- [ ] Data exploration and cleaning
- [ ] Deployed skeleton app (Railway)
- [ ] Supabase database + data loading script
- [ ] Supabase Auth login
- [ ] Customer-lifetime model
- [ ] Upsell model
- [ ] Super-customer score
- [ ] Follow-up analysis
- [ ] Budget optimizer
- [ ] CI workflow
