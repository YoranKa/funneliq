const loginView = document.getElementById("login-view");
const dashboardView = document.getElementById("dashboard-view");
const loginForm = document.getElementById("login-form");
const loginSubmit = document.getElementById("login-submit");
const errorEl = document.getElementById("error");
const userEmailEl = document.getElementById("user-email");
const dashboardEl = document.getElementById("dashboard");
const tierPanelEl = document.getElementById("tier-panel");
const dropoutPanelEl = document.getElementById("dropout-panel");
const profileForm = document.getElementById("profile-form");
const ltvResultEl = document.getElementById("ltv-result");
const upsellResultEl = document.getElementById("upsell-result");
const superCustomerResultEl = document.getElementById("super-customer-result");
let currentAccessToken = null;

function readProfileForm() {
  const payload = {};
  for (const input of profileForm.querySelectorAll("[data-key]")) {
    payload[input.dataset.key] = input.type === "checkbox" ? input.checked : Number(input.value);
  }
  return payload;
}

let supabaseClient;

async function init() {
  const res = await fetch("/api/config");
  const { supabase_url, supabase_anon_key } = await res.json();
  supabaseClient = window.supabase.createClient(supabase_url, supabase_anon_key);

  const {
    data: { session },
  } = await supabaseClient.auth.getSession();
  render(session);

  supabaseClient.auth.onAuthStateChange((_event, session) => render(session));
}

function render(session) {
  if (session) {
    loginView.hidden = true;
    dashboardView.hidden = false;
    userEmailEl.textContent = session.user.email;
    currentAccessToken = session.access_token;
    loadDashboard(session.access_token);
    loadConversionByTier(session.access_token);
    loadFollowupDropout(session.access_token);
  } else {
    loginView.hidden = false;
    dashboardView.hidden = true;
  }
}

async function loadDashboard(accessToken) {
  dashboardEl.textContent = "Loading funnel data...";
  try {
    const res = await fetch("/api/funnel-summary", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const summary = await res.json();

    dashboardEl.innerHTML = `
      <dl>
        <dt>Visible records</dt><dd>${summary.visible_row_count}</dd>
        <dt>Avg. LTV (months)</dt><dd>${summary.avg_ltv_months}</dd>
        <dt>Upsell rate</dt><dd>${(summary.upsell_rate * 100).toFixed(1)}%</dd>
        <dt>Referral rate</dt><dd>${(summary.referred_rate * 100).toFixed(1)}%</dd>
      </dl>
      <p><small>Sampled ${summary.sampled_rows} of ${summary.visible_row_count} rows visible to your account.</small></p>
    `;
  } catch (err) {
    dashboardEl.textContent = `Could not load data: ${err.message}`;
  }
}

async function loadConversionByTier(accessToken) {
  tierPanelEl.textContent = "Loading budget-tier analysis...";
  try {
    const res = await fetch("/api/insights/conversion-by-budget-tier", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const { row_count, tiers } = await res.json();

    const rows = tiers
      .map((t) => `<tr><td>${t.label}</td><td>${(t.conversion_rate * 100).toFixed(1)}%</td></tr>`)
      .join("");

    tierPanelEl.innerHTML = `
      <table>
        <thead><tr><th>Budget tier</th><th>Conversion rate</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <p><small>Computed live from all ${row_count} rows in Supabase (Package 1 finding).</small></p>
    `;
  } catch (err) {
    tierPanelEl.textContent = `Could not load tier analysis: ${err.message}`;
  }
}

async function loadFollowupDropout(accessToken) {
  dropoutPanelEl.textContent = "Loading follow-up dropout analysis...";
  try {
    const res = await fetch("/api/insights/followup-dropout", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const { row_count, stage_dropout, profit_by_calls, recommendation } = await res.json();

    const maxDropout = Math.max(...stage_dropout.map((s) => s.dropout_rate));
    const dropoutBars = stage_dropout
      .map(
        (s) => `
        <div class="bar-row">
          <span>${s.stage}</span>
          <span class="bar-track"><span class="bar-fill" style="width:${(s.dropout_rate / maxDropout) * 100}%"></span></span>
          <span>${(s.dropout_rate * 100).toFixed(1)}%</span>
        </div>`
      )
      .join("");

    const profitRows = profit_by_calls
      .map((p) => `<tr><td>${p.calls_to_closed}</td><td>&#8362;${p.avg_profit_per_deal.toLocaleString()}</td><td>${p.count}</td></tr>`)
      .join("");

    dropoutPanelEl.innerHTML = `
      <p><small>Dropout rate per follow-up stage, computed live from all ${row_count} rows in Supabase:</small></p>
      ${dropoutBars}
      <table>
        <thead><tr><th>Calls to close</th><th>Avg. profit/deal</th><th>Deals</th></tr></thead>
        <tbody>${profitRows}</tbody>
      </table>
      <p id="dropout-recommendation"><small><b>Recommendation:</b> ${recommendation}</small></p>
    `;
  } catch (err) {
    dropoutPanelEl.textContent = `Could not load dropout analysis: ${err.message}`;
  }
}

document.getElementById("ltv-submit").addEventListener("click", async () => {
  ltvResultEl.textContent = "Predicting...";
  try {
    const res = await fetch("/api/predict/ltv", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${currentAccessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(readProfileForm()),
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const { predicted_ltv_months } = await res.json();
    ltvResultEl.textContent = `Predicted lifetime: ${predicted_ltv_months} months`;
  } catch (err) {
    ltvResultEl.textContent = `Could not get a prediction: ${err.message}`;
  }
});

document.getElementById("upsell-submit").addEventListener("click", async () => {
  upsellResultEl.textContent = "Predicting...";
  try {
    const { purchased, ...upsellPayload } = readProfileForm();
    const res = await fetch("/api/predict/upsell", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${currentAccessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(upsellPayload),
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const { upsell_probability, business_rule_flag } = await res.json();
    upsellResultEl.textContent =
      `Upsell probability: ${(upsell_probability * 100).toFixed(1)}% ` +
      `(business rule: ${business_rule_flag ? "flag for outreach" : "no flag"})`;
  } catch (err) {
    upsellResultEl.textContent = `Could not get a prediction: ${err.message}`;
  }
});

document.getElementById("super-customer-submit").addEventListener("click", async () => {
  superCustomerResultEl.textContent = "Scoring...";
  try {
    const res = await fetch("/api/predict/super-customer-score", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${currentAccessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(readProfileForm()),
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const { super_customer_score } = await res.json();
    superCustomerResultEl.textContent = `Super-customer score: ${super_customer_score} / 100`;
  } catch (err) {
    superCustomerResultEl.textContent = `Could not get a score: ${err.message}`;
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorEl.textContent = "";
  loginSubmit.disabled = true;

  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
  if (error) errorEl.textContent = error.message;

  loginSubmit.disabled = false;
});

document.getElementById("signout").addEventListener("click", async () => {
  await supabaseClient.auth.signOut();
});

init();
