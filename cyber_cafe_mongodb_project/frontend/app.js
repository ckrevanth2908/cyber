const $ = id => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function money(value) {
  return `₹${Number(value || 0).toFixed(2)}`;
}

function message(text, error = false) {
  $("message").textContent = text;
  $("message").className = "message " + (error ? "error" : "success");
}

async function loadDashboard() {
  const d = await apiRequest("/api/dashboard");
  $("totalCustomers").textContent = d.total_customers;
  $("totalTerminals").textContent = d.total_terminals;
  $("availableTerminals").textContent = d.available_terminals;
  $("totalRevenue").textContent = money(d.total_revenue);
}

async function loadCustomers() {
  const data = await apiRequest("/api/customers");
  $("customerSelect").innerHTML = data.length
    ? data.map(c => `<option value="${c._id}">${escapeHtml(c.name)}</option>`).join("")
    : `<option value="">Add a customer first</option>`;

  $("customersTable").innerHTML = `<div class="table-wrap"><table>
    <tr><th>Name</th><th>Phone</th><th>Email</th></tr>
    ${data.map(c => `<tr><td>${escapeHtml(c.name)}</td><td>${escapeHtml(c.phone || "-")}</td><td>${escapeHtml(c.email || "-")}</td></tr>`).join("")}
  </table></div>`;
}

async function loadTerminals() {
  const data = await apiRequest("/api/terminals");
  const available = data.filter(t => t.status === "available");
  $("terminalSelect").innerHTML = available.length
    ? available.map(t => `<option value="${t._id}">Terminal ${t.terminal_no}</option>`).join("")
    : `<option value="">No available terminals</option>`;

  $("terminalsTable").innerHTML = `<div class="table-wrap"><table>
    <tr><th>Terminal</th><th>Status</th></tr>
    ${data.map(t => `<tr><td>#${t.terminal_no}</td><td><span class="badge ${t.status}">${escapeHtml(t.status)}</span></td></tr>`).join("")}
  </table></div>`;
}

async function loadRates() {
  const data = await apiRequest("/api/rates");
  $("rateSelect").innerHTML = data.map(r => `<option value="${r._id}">${escapeHtml(r.name)} · ${money(r.hourly_rate)}/hr</option>`).join("");
}

async function loadSessions() {
  const data = await apiRequest("/api/active-sessions");
  $("activeCount").textContent = `${data.length} ACTIVE`;
  $("activeSessions").innerHTML = data.length ? data.map(s => `
    <div class="session-card">
      <div><strong>${escapeHtml(s.customer.name || "Unknown customer")}</strong><p>Terminal ${s.terminal.terminal_no} · ${escapeHtml(s.start_time)}</p></div>
      <button onclick="completeSession('${s._id}')">Complete</button>
    </div>`).join("") : "<p class='muted'>No active sessions right now.</p>";
}

async function completeSession(id) {
  const payment = prompt("Payment method: cash, card, or upi", "cash") || "cash";
  try {
    const result = await apiRequest(`/api/sessions/${id}/complete`, {
      method: "POST", body: JSON.stringify({payment_method: payment})
    });
    message(`Session completed. Amount: ${money(result.amount)}`);
    await refreshAll();
  } catch (e) { message(e.message, true); }
}

$("customerForm").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await apiRequest("/api/customers", {
      method: "POST",
      body: JSON.stringify({
        name: $("customerName").value,
        phone: $("customerPhone").value,
        email: $("customerEmail").value
      })
    });
    e.target.reset();
    message("Customer added successfully.");
    await refreshAll();
  } catch (err) { message(err.message, true); }
});

$("sessionForm").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await apiRequest("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        customer_id: $("customerSelect").value,
        terminal_id: $("terminalSelect").value,
        rate_id: $("rateSelect").value
      })
    });
    message("Session started successfully.");
    await refreshAll();
  } catch (err) { message(err.message, true); }
});

async function refreshAll() {
  try {
    await Promise.all([loadDashboard(), loadCustomers(), loadTerminals(), loadRates(), loadSessions()]);
  } catch (e) { message(e.message, true); }
}

refreshAll();
