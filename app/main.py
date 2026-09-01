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
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from postgrest.exceptions import APIError
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]

app = FastAPI(title="FunnelIQ")


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


app.mount("/", StaticFiles(directory=ROOT / "app" / "static", html=True), name="static")
