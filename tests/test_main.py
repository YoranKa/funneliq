from fastapi.testclient import TestClient

from app.main import app

# Deliberately NOT using "with TestClient(app) as client" - that would run
# the app's lifespan, which trains 4 models against a real Supabase project.
# Calling the client directly skips lifespan, so only endpoints that don't
# touch Supabase (or that reject the request before they would) are safe
# to test here.
client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_exposes_public_supabase_values():
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert body["supabase_url"] == "https://fake.supabase.co"
    assert body["supabase_anon_key"] == "fake-anon-key"


EARLY_FUNNEL_FIELDS = {
    "ad_budget": 1,
    "num_leads": 1,
    "leads_answered": 1,
    "leads_not_answered": 1,
    "followup_1": 1,
    "followup_2": 1,
    "followup_3": 1,
    "followup_4": 1,
    "followup_5": 1,
}
FULL_FUNNEL_FIELDS = {
    **EARLY_FUNNEL_FIELDS,
    "not_closed": 1,
    "closed": 1,
    "calls_to_closed": 1,
    "calls_to_not_closed": 1,
    "customer_acquisition_cost": 1,
}


def test_predict_ltv_requires_auth():
    # A well-formed body with no Authorization header - checks the auth
    # gate itself, not FastAPI's separate request-body validation (422).
    response = client.post("/api/predict/ltv", json={**FULL_FUNNEL_FIELDS, "purchased": True})
    assert response.status_code == 401


def test_predict_upsell_requires_auth():
    response = client.post("/api/predict/upsell", json=FULL_FUNNEL_FIELDS)
    assert response.status_code == 401


def test_predict_super_customer_score_requires_auth():
    response = client.post("/api/predict/super-customer-score", json=EARLY_FUNNEL_FIELDS)
    assert response.status_code == 401


def test_simulate_budget_allocation_requires_auth():
    response = client.post("/api/simulate/budget-allocation", json={"campaign_budgets": [2000]})
    assert response.status_code == 401


def test_insights_endpoints_require_auth():
    assert client.get("/api/funnel-summary").status_code == 401
    assert client.get("/api/insights/conversion-by-budget-tier").status_code == 401
    assert client.get("/api/insights/followup-dropout").status_code == 401
