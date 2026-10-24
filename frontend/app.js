"use strict";
let CSRF = "";
let MODULES = [];
let ACTIVE_ROUTE = "command";
const TODAY = new Date().toISOString().slice(0, 10);
const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function money(value, currency = "NGN") {
  if (value === null || value === undefined) return "Unavailable";
  const n = Number(value);
  if (!Number.isFinite(n)) return "Unavailable";
  return new Intl.NumberFormat("en-NG", {
    style: "currency", currency, maximumFractionDigits: 0,
  }).format(n);
}
function num(value, digits = 1) {
  return value === null || value === undefined || !Number.isFinite(Number(value))
    ? "—" : Number(value).toLocaleString("en-NG", { maximumFractionDigits: digits });
}
function pct(value, digits = 1) {
  return value == null || !Number.isFinite(Number(value)) ? "—" : num(value, digits) + "%";
}
function json(value) {
  return '<pre class="json-block">' + esc(JSON.stringify(value, null, 2)) + "</pre>";
}
function badge(value) {
  return '<span class="pill ' + (value === "baseline" ? "baseline" : "") + '">' +
    esc(value || "ready") + "</span>";
}
function metric(title, value, foot) {
  return '<div class="kpi"><span class="label">' + esc(title) +
    '</span><div class="value">' + esc(value) + '</div><div class="foot">' +
    esc(foot || "") + "</div></div>";
}
function section(title, subtitle) {
  return '<div class="section-title"><h2>' + esc(title) + '</h2><p>' + esc(subtitle || "") + "</p></div>";
}
function panel(inner, title) {
  return '<section class="card">' + (title ? "<h3>" + esc(title) + "</h3>" : "") + inner + "</section>";
}
function note(text) { return '<div class="note">' + esc(text) + "</div>"; }
function output(id) { return '<div class="results" id="' + esc(id) + '" hidden aria-live="polite"></div>'; }
function table(headers, rows) {
  if (!rows.length) return '<div class="empty">No records yet. Add a record to begin.</div>';
  return '<div class="table-wrap"><table><thead><tr>' +
    headers.map((h) => "<th>" + esc(h) + "</th>").join("") + "</tr></thead><tbody>" +
    rows.map((r) => "<tr>" + r.map((c) => "<td>" + esc(c) + "</td>").join("") + "</tr>").join("") +
    "</tbody></table></div>";
}
function barChart(items) {
  const pairs = Object.entries(items || {});
  const total = pairs.reduce((sum, p) => sum + Math.max(0, Number(p[1])), 0);
  if (total <= 0) return '<div class="empty">No priced assets yet.</div>';
  return pairs.sort((a, b) => b[1] - a[1]).map(([k, v]) => {
    const share = Math.max(0, v / total * 100);
    return '<div class="bar-item"><span>' + esc(k.replaceAll("_", " ")) +
      '</span><div class="bar-track"><div class="bar-fill" style="width:' + share.toFixed(2) +
      '%"></div></div><strong>' + share.toFixed(1) + '%</strong></div>';
  }).join("");
}
function field(name, label, type = "text", value = "", settings = {}) {
  const required = settings.optional ? "" : " required";
  const attr = (key) => settings[key] === undefined ? "" : " " + key + '="' + esc(settings[key]) + '"';
  const cls = settings.wide ? "wide" : "";
  let control;
  if (type === "select") {
    control = '<select name="' + esc(name) + '"' + required + '>' +
      (settings.options || []).map((option) => {
        const [v, l] = Array.isArray(option) ? option : [option, option];
        return '<option value="' + esc(v) + '"' + (String(v) === String(value) ? " selected" : "") +
          ">" + esc(l) + "</option>";
      }).join("") + "</select>";
  } else if (type === "textarea") {
    control = '<textarea name="' + esc(name) + '"' + required + '>' + esc(value) + "</textarea>";
  } else {
    control = '<input name="' + esc(name) + '" type="' + esc(type) +
      '" value="' + esc(value) + '"' + required + attr("placeholder") + attr("min") + attr("max") +
      attr("step") + ">";
  }
  return '<label class="' + cls + '">' + esc(label) + control + "</label>";
}
function form(id, title, fields, button = "Calculate") {
  return panel('<form class="form-grid" id="' + esc(id) + '">' + fields.join("") +
    '<div class="form-actions wide"><button class="primary" type="submit">' +
    esc(button) + '</button></div></form>' + output(id + "-out"), title);
}
function success(id, contents) {
  const node = $(id);
  if (!node) return;
  node.hidden = false;
  node.innerHTML = contents;
}
function error(id, err) {
  success(id, '<p class="error-text">' + esc(err.message || String(err)) + "</p>");
}
function fvalues(f) {
  const out = {};
  const fd = new FormData(f);
  fd.forEach((value, key) => { out[key] = value; });
  return out;
}
function numeric(v, key) {
  const n = Number(v);
  if (v === "" || !Number.isFinite(n)) throw new Error("Valid number required: " + key);
  return n;
}
async function api(path, options = {}) {
  const isFile = options.body instanceof FormData;
  const headers = Object.assign({}, isFile ? {} : { "Content-Type": "application/json" },
    options.headers || {});
  if (options.method && !["GET", "HEAD"].includes(options.method)) {
    headers["X-CSRF-Token"] = CSRF;
  }
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options, headers,
  });
  if (response.status === 401) {
    if (path !== "/auth/me") window.location.replace("/login.html");
    throw new Error("Session expired — please sign in");
  }
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = result.detail || "Request failed (" + response.status + ")";
    throw new Error(typeof detail === "string" ? detail :
      (Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : JSON.stringify(detail)));
  }
  return result;
}
function post(path, data) {
  return api(path, { method: "POST", body: JSON.stringify(data) });
}
function bindCalc(formId, endpoint, transform, decorate) {
  const el = $(formId);
  if (!el) return;
  el.addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = el.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const payload = transform(fvalues(el));
      const result = await post(endpoint, payload);
      success(formId + "-out", decorate ? decorate(result) : json(result));
    } catch (err) {
      error(formId + "-out", err);
    } finally { btn.disabled = false; }
  });
}
function bindCreate(formId, endpoint, transform, after) {
  const el = $(formId);
  if (!el) return;
  el.addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = el.querySelector('button[type="submit"]');
    btn.disabled = true;
    try {
      const result = await post(endpoint, transform(fvalues(el)));
      success(formId + "-out", '<p class="success-text">Saved successfully. Record ID: ' +
        esc(result.id || "created") + "</p>");
      if (after) await after();
    } catch (err) { error(formId + "-out", err); }
    finally { btn.disabled = false; }
  });
}
function slide(title, subtitle, inner) {
  return '<div class="breadcrumb">WEALTH INTELLIGENCE / ' + esc(title.toUpperCase()) +
    '</div><div class="section-title"><div><h2>' + esc(title) + '</h2><p>' +
    esc(subtitle || "") + "</p></div></div>" + inner;
}
function renderNav() {
  const nav = $("module-nav");
  let currentCategory = "";
  let html = '<button class="nav-item" data-route="command"><span class="nav-icon">◫</span><span class="text">Overview</span></button>' +
    '<button class="nav-item" data-route="data"><span class="nav-icon">▦</span><span class="text">Data workspace</span></button>';
  const symbols = ["◫","◎","◈","◇","▤","〽","◉","▥","⊞","◷","✎","⇄","⬡","✧","▣"];
  MODULES.forEach((module, idx) => {
    if (module.category !== currentCategory) {
      currentCategory = module.category;
      html += '<div class="nav-heading">' + esc(currentCategory) + "</div>";
    }
    html += '<button class="nav-item" data-route="' + esc(module.id) +
      '"><span class="nav-icon">' + esc(symbols[idx] || "•") +
      '</span><span class="text">' + esc(module.name) + "</span></button>";
  });
  nav.innerHTML = html;
}
async function navigate() {
  const slug = window.location.hash.replace("#", "") || "command";
  ACTIVE_ROUTE = slug;
  document.querySelectorAll("[data-route]").forEach((el) =>
    el.classList.toggle("active", el.dataset.route === slug));
  const module = MODULES.find((m) => m.id === slug);
  $("page-title").textContent = slug === "data" ? "Data workspace" :
    slug === "command" ? "Wealth overview" : (module ? module.name : "Overview");
  $("content").innerHTML = '<div class="loading">Running your wealth analytics…</div>';
  try {
    if (slug === "data") return await renderDataWorkspace();
    if (slug === "command") return await renderCommandCenter();
    if (module) return await renderModule(module);
    window.location.hash = "#command";
  } catch (err) {
    $("content").innerHTML = panel('<p class="error-text">' + esc(err.message) +
      '</p><button class="secondary" id="retry">Try again</button>', "Something went wrong");
    $("retry").addEventListener("click", navigate);
  }
}
async function init() {
  try {
    const auth = await api("/auth/me");
    CSRF = auth.csrf;
    $("owner").textContent = auth.username.slice(0, 2).toUpperCase();
    $("today").textContent = new Date().toLocaleDateString("en-GB",
      { weekday: "short", day: "numeric", month: "short", year: "numeric" });
    MODULES = (await api("/modules")).modules;
    renderNav();
    $("module-nav").addEventListener("click", (event) => {
      const item = event.target.closest("[data-route]");
      if (!item) return;
      window.location.hash = "#" + item.dataset.route;
      if (window.location.hash === "#" + item.dataset.route && ACTIVE_ROUTE === item.dataset.route)
        navigate();
    });
    $("refresh").addEventListener("click", navigate);
    $("logout").addEventListener("click", async () => {
      try { await post("/auth/logout", {}); }
      finally { window.location.replace("/login.html"); }
    });
    window.addEventListener("hashchange", navigate);
    await navigate();
  } catch (err) {
    window.location.replace("/login.html");
  }
}
document.addEventListener("DOMContentLoaded", init);
