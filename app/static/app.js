const loginView = document.getElementById("login-view");
const dashboardView = document.getElementById("dashboard-view");
const loginForm = document.getElementById("login-form");
const loginSubmit = document.getElementById("login-submit");
const errorEl = document.getElementById("error");
const userEmailEl = document.getElementById("user-email");
const dashboardEl = document.getElementById("dashboard");

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
    loadDashboard(session.access_token);
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
