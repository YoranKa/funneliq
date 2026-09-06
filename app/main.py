"""
FunnelIQ API - serves the login/dashboard page and the data endpoints
behind it.

Auth model: the browser signs in directly against Supabase Auth with the
anon key (see static/app.js) and gets back the user's access token. Every
data request sends that token here in the Authorization header; this
server does nothing but forward it to Supabase's PostgREST as that user's
bearer token, so Row Level Security (db/schema.sql) is what actually
decides what the request can see - the service-role key never touches a
user-facing request.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from dotenv import load_dotenv
from lightgbm import LGBMRegressor
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from postgrest.exceptions import APIError
from pydantic import BaseModel
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Same feature list, target, and model as notebooks/02_ltv_regression.ipynb -
# see docs/package_1_findings.md-style reasoning there for why cumulative_profit
# / upsell / referred are excluded as leakage.
LTV_FEATURES = [
    "ad_budget", "num_leads", "leads_answered", "leads_not_answered",
    "followup_1", "followup_2", "followup_3", "followup_4", "followup_5",
    "not_closed", "closed", "calls_to_closed", "calls_to_not_closed",
    "customer_acquisition_cost", "purchased",
]

# notebooks/03_upsell_classification.ipynb's refined model: trained on
# purchasers only (upsell is meaningless before a purchase happens), so
# "purchased" is dropped - it would be constant (always 1) and uninformative.
UPSELL_FEATURES = [f for f in LTV_FEATURES if f != "purchased"]

# notebooks/04_super_customer_score.ipynb: early-funnel-only features, since
# the score must be computable before purchase/referral/upsell are known.
SUPER_CUSTOMER_BASE_FEATURES = [
    "ad_budget", "num_leads", "leads_answered", "leads_not_answered",
    "followup_1", "followup_2", "followup_3", "followup_4", "followup_5",
]
SUPER_CUSTOMER_FEATURES = SUPER_CUSTOMER_BASE_FEATURES + ["budget_tier"]
# Winning hyperparameters from the notebook's RandomizedSearchCV (ROC-AUC
# 0.813) - reused as fixed values here instead of re-tuning on every deploy.
SUPER_CUSTOMER_BEST_PARAMS = {"learning_rate": 0.01, "iterations": 100, "depth": 3}

_ltv_model: CatBoostRegressor | None = None
_upsell_model: CatBoostClassifier | None = None
_super_customer_model: CatBoostClassifier | None = None
_budget_tier_edges: list[float] | None = None
_budget_profit_model: LGBMRegressor | None = None
_budget_profile: pd.DataFrame | None = None


def _train_ltv_model() -> CatBoostRegressor:
    # Admin/bulk operation (trains on the whole table), like db/load_data.py -
    # uses the service-role key server-side only, never sent to the browser.
    admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    rows = _fetch_all_rows(admin_client, ",".join(LTV_FEATURES + ["ltv_months"]))
    df = pd.DataFrame(rows).dropna(subset=["ltv_months"])

    model = CatBoostRegressor(random_state=42, verbose=False)
    model.fit(df[LTV_FEATURES], df["ltv_months"])
    return model


def _train_upsell_model() -> CatBoostClassifier:
    admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    rows = _fetch_all_rows(
        admin_client, ",".join(UPSELL_FEATURES + ["upsell"]), purchased_only=True
    )
    df = pd.DataFrame(rows)

    model = CatBoostClassifier(random_state=42, verbose=False)
    model.fit(df[UPSELL_FEATURES], df["upsell"])
    return model


def _train_super_customer_model() -> tuple[CatBoostClassifier, list[float]]:
    admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    columns = SUPER_CUSTOMER_BASE_FEATURES + ["purchased", "referred", "upsell", "ltv_months"]
    df = pd.DataFrame(_fetch_all_rows(admin_client, ",".join(set(columns))))

    # Engineered label: a purchaser who referred someone, upsold, and stuck
    # around in the top third of tenure among purchasers. Unlike the
    # notebook's raw CSV (where referred is "Yes"/"No"), db/load_data.py
    # already converted it to a real boolean when loading into Supabase.
    tenure_threshold = df.loc[df["purchased"], "ltv_months"].quantile(2 / 3)
    super_customer = (
        df["purchased"]
        & df["referred"]
        & df["upsell"]
        & (df["ltv_months"] >= tenure_threshold)
    ).astype(int)

    # budget_tier: equal-sized tertiles of ad_budget. The bin edges are kept
    # (with the outer edges opened to +-inf) so a single new ad_budget value
    # can be bucketed the same way at prediction time.
    _, edges = pd.qcut(df["ad_budget"], q=3, retbins=True)
    edges = [-float("inf")] + list(edges[1:-1]) + [float("inf")]
    budget_tier = pd.cut(df["ad_budget"], bins=edges, labels=["Low", "Mid", "High"]).astype(str)

    X = df[SUPER_CUSTOMER_BASE_FEATURES].copy()
    X["budget_tier"] = budget_tier
    cat_feature_idx = [X.columns.get_loc("budget_tier")]

    model = CatBoostClassifier(random_state=42, verbose=False, **SUPER_CUSTOMER_BEST_PARAMS)
    model.fit(X, super_customer, cat_features=cat_feature_idx)
    return model, edges


def _train_budget_profit_model() -> tuple[LGBMRegressor, pd.DataFrame]:
    # Full historical features (same list as LTV_FEATURES) - unlike Packages
    # 2-4, the simulator only ever knows a hypothetical campaign's budget, so
    # training isn't restricted to early-funnel-only signals. See
    # notebooks/06_budget_optimization.ipynb for why LightGBM was the winner.
    admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    rows = _fetch_all_rows(admin_client, ",".join(LTV_FEATURES + ["cumulative_profit"]))
    df = pd.DataFrame(rows).dropna(subset=["cumulative_profit"])

    model = LGBMRegressor(random_state=42, verbose=-1)
    model.fit(df[LTV_FEATURES], df["cumulative_profit"])

    # Typical funnel profile per 500-wide budget bucket (median, since
    # several features are right-skewed) - the simulator overrides ad_budget
    # with the real value being tested but fills in everything else from here.
    df["budget_bucket"] = (df["ad_budget"] // 500 * 500).astype(int)
    profile = df.groupby("budget_bucket")[LTV_FEATURES].median()
    return model, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ltv_model, _upsell_model, _super_customer_model, _budget_tier_edges
    global _budget_profit_model, _budget_profile
    _ltv_model = _train_ltv_model()
    _upsell_model = _train_upsell_model()
    _super_customer_model, _budget_tier_edges = _train_super_customer_model()
    _budget_profit_model, _budget_profile = _train_budget_profit_model()
    yield


app = FastAPI(title="FunnelIQ", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    # Both values are meant to be public - this is the same anon key and
    # URL the assignment says are safe to ship to the browser.
    return {"supabase_url": SUPABASE_URL, "supabase_anon_key": SUPABASE_ANON_KEY}


def _client_for_user(access_token: str):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    return client


def _require_session(authorization: str | None):
    """Validate the bearer token the same way every endpoint does, and
    return a Supabase client scoped to that user's session."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]

    client = _client_for_user(token)
    try:
        client.table("funnel_records").select("id").limit(1).execute()
    except APIError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc
    return client


def _fetch_all_rows(client, columns: str, page_size: int = 1000, purchased_only: bool = False) -> list[dict]:
    # PostgREST caps rows per request (1000 by default), so a full-table
    # read needs paging via .range() rather than one .select().execute().
    rows: list[dict] = []
    start = 0
    while True:
        query = client.table("funnel_records").select(columns)
        if purchased_only:
            query = query.eq("purchased", True)
        batch = query.range(start, start + page_size - 1).execute().data
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        start += page_size


@app.get("/api/funnel-summary")
def funnel_summary(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]

    client = _client_for_user(token)
    try:
        response = (
            client.table("funnel_records")
            .select("ad_budget,num_leads,closed,ltv_months,upsell,cumulative_profit,referred", count="exact")
            .limit(500)
            .execute()
        )
    except APIError as exc:
        # PostgREST returns 401 for an invalid/expired JWT.
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc

    rows = response.data
    n = len(rows)
    upsell_rate = sum(1 for r in rows if r["upsell"]) / n if n else 0
    referred_rate = sum(1 for r in rows if r["referred"]) / n if n else 0
    avg_ltv = sum(r["ltv_months"] for r in rows if r["ltv_months"] is not None) / n if n else 0

    return {
        "visible_row_count": response.count,
        "sampled_rows": n,
        "avg_ltv_months": round(avg_ltv, 2),
        "upsell_rate": round(upsell_rate, 3),
        "referred_rate": round(referred_rate, 3),
    }


@app.get("/api/insights/conversion-by-budget-tier")
def conversion_by_budget_tier(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]

    client = _client_for_user(token)
    try:
        rows = _fetch_all_rows(client, "ad_budget,num_leads,closed")
    except APIError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc

    # Same bins/labels and mean-of-per-row-ratios as notebooks/01_explore.ipynb -
    # see docs/package_1_findings.md for why the 1500-2000 gap gets its own bucket.
    df = pd.DataFrame(rows)
    tier = pd.cut(
        df["ad_budget"],
        bins=[0, 1500, 2000, 5000, float("inf")],
        labels=["Low (<=1500)", "Unclassified (1500-2000)", "Mid (2000-5000)", "High (>5000)"],
    )
    conversion_rate = df["closed"] / df["num_leads"]
    by_tier = conversion_rate.groupby(tier, observed=True).mean().sort_index()

    return {
        "row_count": len(df),
        "tiers": [
            {"label": label, "conversion_rate": round(float(rate), 4)}
            for label, rate in by_tier.items()
        ],
    }


FOLLOWUP_STAGES = ["leads_answered", "followup_1", "followup_2", "followup_3", "followup_4", "followup_5"]


@app.get("/api/insights/followup-dropout")
def followup_dropout(authorization: str | None = Header(default=None)):
    # A genuine user-facing read (not model training), so it goes through
    # the signed-in user's own token like conversion-by-budget-tier does -
    # RLS decides what's visible, not the service-role key.
    client = _require_session(authorization)
    rows = _fetch_all_rows(client, ",".join(FOLLOWUP_STAGES + ["closed", "calls_to_closed", "cumulative_profit"]))
    df = pd.DataFrame(rows)

    # Dropout per stage, computed per row then averaged (weighs every
    # campaign equally) - see notebooks/05_followup_dropout.ipynb.
    stage_dropout = []
    for i in range(1, len(FOLLOWUP_STAGES)):
        prev_col, cur_col = FOLLOWUP_STAGES[i - 1], FOLLOWUP_STAGES[i]
        rate = ((df[prev_col] - df[cur_col]) / df[prev_col]).mean()
        stage_dropout.append({"stage": f"{prev_col} -> {cur_col}", "dropout_rate": round(float(rate), 4)})

    # closed==0 rows have calls_to_closed==0 as a placeholder (nothing to
    # average), not a real zero-call close - excluded, same as the notebook.
    closed_deals = df[df["closed"] > 0].copy()
    closed_deals["profit_per_deal"] = closed_deals["cumulative_profit"] / closed_deals["closed"]
    profit_by_calls = (
        closed_deals.groupby("calls_to_closed")["profit_per_deal"].agg(["mean", "count"]).sort_index()
    )

    return {
        "row_count": len(df),
        "stage_dropout": stage_dropout,
        "profit_by_calls": [
            {"calls_to_closed": float(calls), "avg_profit_per_deal": round(float(row["mean"]), 0), "count": int(row["count"])}
            for calls, row in profit_by_calls.iterrows()
        ],
        "recommendation": (
            "Don't cut off follow-ups after call 3 - dropout isn't monotonic (stage 3->4 is "
            "the lowest of all five, then 4->5 spikes) and ~21% of closed deals need all 5 "
            "calls. Profit per deal does fall sharply after call 3, so use the LTV/upsell/"
            "super-customer scores to prioritize who gets chased past call 3, rather than "
            "applying the same cutoff to everyone."
        ),
    }


class LtvPredictionRequest(BaseModel):
    ad_budget: float
    num_leads: float
    leads_answered: float
    leads_not_answered: float
    followup_1: float
    followup_2: float
    followup_3: float
    followup_4: float
    followup_5: float
    not_closed: float
    closed: float
    calls_to_closed: float
    calls_to_not_closed: float
    customer_acquisition_cost: float
    purchased: bool


@app.post("/api/predict/ltv")
def predict_ltv(payload: LtvPredictionRequest, authorization: str | None = Header(default=None)):
    # This endpoint doesn't read any RLS-scoped rows itself (the model
    # already lives in memory), but it still requires a real, valid session.
    _require_session(authorization)

    row = pd.DataFrame([payload.model_dump()])[LTV_FEATURES]
    predicted_months = float(_ltv_model.predict(row)[0])
    return {"predicted_ltv_months": round(predicted_months, 1)}


class UpsellPredictionRequest(BaseModel):
    ad_budget: float
    num_leads: float
    leads_answered: float
    leads_not_answered: float
    followup_1: float
    followup_2: float
    followup_3: float
    followup_4: float
    followup_5: float
    not_closed: float
    closed: float
    calls_to_closed: float
    calls_to_not_closed: float
    customer_acquisition_cost: float


@app.post("/api/predict/upsell")
def predict_upsell(payload: UpsellPredictionRequest, authorization: str | None = Header(default=None)):
    _require_session(authorization)

    row = pd.DataFrame([payload.model_dump()])[UPSELL_FEATURES]
    # Business takeaway from notebooks/03_upsell_classification.ipynb: ship
    # the probability, not a hard 0/1 label, so the sales team can rank
    # purchasers rather than only calling whoever crosses a 0.5 cutoff.
    probability = float(_upsell_model.predict_proba(row)[0][1])

    # Same simple business rule from the notebook, returned alongside the
    # model so the two can be compared directly on the same customer.
    rule_flag = bool(payload.calls_to_closed <= 3 and payload.customer_acquisition_cost <= 1250)

    return {"upsell_probability": round(probability, 4), "business_rule_flag": rule_flag}


class SuperCustomerScoreRequest(BaseModel):
    ad_budget: float
    num_leads: float
    leads_answered: float
    leads_not_answered: float
    followup_1: float
    followup_2: float
    followup_3: float
    followup_4: float
    followup_5: float


@app.post("/api/predict/super-customer-score")
def predict_super_customer_score(
    payload: SuperCustomerScoreRequest, authorization: str | None = Header(default=None)
):
    _require_session(authorization)

    row = pd.DataFrame([payload.model_dump()])
    # Bucket this customer's ad_budget with the same tertile edges the model
    # was trained on (see notebooks/04_super_customer_score.ipynb).
    row["budget_tier"] = pd.cut(
        row["ad_budget"], bins=_budget_tier_edges, labels=["Low", "Mid", "High"]
    ).astype(str)

    probability = float(_super_customer_model.predict_proba(row[SUPER_CUSTOMER_FEATURES])[0][1])
    return {"super_customer_score": round(probability * 100, 1)}


class BudgetAllocationRequest(BaseModel):
    campaign_budgets: list[float]


def _predict_campaign_profit(budget: float) -> float:
    # Clip to the bucket range actually seen in training data - a budget far
    # outside data/funnel_marketing_data.csv's 500-20,000 range has no
    # typical profile to borrow from.
    bucket = int(budget // 500 * 500)
    bucket = min(max(bucket, _budget_profile.index.min()), _budget_profile.index.max())

    row = _budget_profile.loc[bucket, LTV_FEATURES].copy()
    row["ad_budget"] = budget
    return float(_budget_profit_model.predict(row.to_frame().T)[0])


@app.post("/api/simulate/budget-allocation")
def simulate_budget_allocation(payload: BudgetAllocationRequest, authorization: str | None = Header(default=None)):
    _require_session(authorization)

    if not payload.campaign_budgets:
        raise HTTPException(status_code=422, detail="campaign_budgets must not be empty")

    total_spend = sum(payload.campaign_budgets)
    total_profit = sum(_predict_campaign_profit(b) for b in payload.campaign_budgets)

    # Notebook finding: the "typical profile" approximation breaks down at
    # the low end (bucket width becomes proportionally huge vs. the target
    # budget), verified there as a real 3x overprediction at 500 campaigns.
    low_budget_warning = any(b < 1000 for b in payload.campaign_budgets)

    return {
        "n_campaigns": len(payload.campaign_budgets),
        "total_spend": total_spend,
        "predicted_profit": round(total_profit, 0),
        "roi": round(total_profit / total_spend, 3),
        "low_budget_warning": low_budget_warning,
    }


app.mount("/", StaticFiles(directory=ROOT / "app" / "static", html=True), name="static")
