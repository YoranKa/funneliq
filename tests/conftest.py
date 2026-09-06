import os

# app/main.py reads these at import time. CI has no real Supabase project,
# so tests use fake values and only exercise endpoints that don't need a
# real connection (the auth-rejection paths, and any request that never
# calls Supabase before returning).
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "fake-service-role-key")
