/**
 * app.js — Trading Dashboard JavaScript
 * Handles WebSocket connection, real-time updates, and UI interactions.
 */

"use strict";

// ── State ────────────────────────────────────────────────────────────────────
let state = {};
let tradeFilter = "all";
let socket = null;

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initSocket();
  startClock();
  fetchInitialState();
});

// ── WebSocket ─────────────────────────────────────────────────────────────────
function initSocket() {
  socket = io({ transports: ["websocket", "polling"] });

  socket.on("connect", () => {
    console.log("✓ WebSocket connected");
    setClockDot(true);
  });

  socket.on("disconnect", () => {
    console.log("✗ WebSocket disconnected");
    setClockDot(false);
    toast("Connection lost. Reconnecting...", "warning");
  });

  socket.on("update", (data) => {
    state = data;
    renderAll(data);
  });

  // Keep-alive ping every 30s
  setInterval(() => { if (socket?.connected) socket.emit("ping"); }, 30000);
}

function setClockDot(connected) {
  const dot = document.getElementById("clockDot");
  if (!dot) return;
  dot.style.background    = connected ? "var(--green)" : "var(--red)";
  dot.style.boxShadow     = connected ? "0 0 8px var(--green)" : "0 0 8px var(--red)";
  dot.style.animationName = connected ? "pulse" : "none";
}

async function fetchInitialState() {
  try {
    const res = await fetch("/api/state");
    const data = await res.json();
    state = data;
    renderAll(data);
  } catch (e) {
    console.error("Failed to fetch initial state:", e);
  }
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderAll(data) {
  renderKPIs(data);
  renderBotStatus(data);
  renderPositions(data.positions || []);
  renderSignals(data.signals || []);
  renderTrades(data.trades || [], tradeFilter);
  renderStrategies(data.strategies || {});
  renderWatchlist(data.watchlist || []);
}

function renderKPIs(data) {
  const stats = data.stats || {};
  const pnl   = stats.gross_pnl || 0;

  // P&L
  const pnlEl = document.getElementById("netPnl");
  if (pnlEl) {
    pnlEl.textContent  = formatCurrency(pnl);
    pnlEl.className    = "kpi-value " + pnlClass(pnl);
  }
  setText("winRate",    `Win rate: ${stats.win_rate ?? 0}%`);
  setText("totalTrades", stats.total_trades ?? 0);
  setText("winsLosses",  `W: ${stats.winning_trades ?? 0} / L: ${stats.losing_trades ?? 0}`);

  // Open positions
  const openPos   = data.positions || [];
  const unrealPnl = openPos.reduce((s, p) => s + (p.unrealised_pnl || 0), 0);
  setText("openCount", openPos.length);
  setText("openPnl",   `Unrealised: ${formatCurrency(unrealPnl)}`);
  document.getElementById("openPnl").className = "kpi-sub " + pnlClass(unrealPnl);

  // Capital
  if (data.capital) {
    setText("capitalDisplay", "₹" + Number(data.capital).toLocaleString("en-IN"));
  }
  if (data.total_pnl !== undefined) {
    const totalPnlEl = document.getElementById("totalPnlDisplay");
    totalPnlEl.innerText = "Total P&L: ₹" + Number(data.total_pnl).toLocaleString("en-IN");
    if (data.total_pnl > 0) totalPnlEl.style.color = "#10b981";
    else if (data.total_pnl < 0) totalPnlEl.style.color = "#ef4444";
    else totalPnlEl.style.color = "#9ca3af";
  }

  // Date
  if (data.date) setText("liveDate", data.date);
}

function renderBotStatus(data) {
  const modeBadge   = document.getElementById("modeBadge");
  const statusBadge = document.getElementById("botStatusBadge");

  if (modeBadge) {
    modeBadge.textContent = (data.mode || "paper").toUpperCase();
    modeBadge.className   = "mode-badge" + (data.mode === "live" ? " live" : "");
  }

  if (statusBadge) {
    const s = data.bot_status || "STOPPED";
    statusBadge.textContent = s;
    statusBadge.className   = "bot-status-badge" + (s === "RUNNING" ? " running" : "");
  }
}

function renderPositions(positions) {
  const tbody = document.getElementById("posTableBody");
  const badge = document.getElementById("posBadge");
  if (!tbody) return;

  if (badge) badge.textContent = positions.length;

  if (!positions.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="9">No open positions</td></tr>`;
    return;
  }

  tbody.innerHTML = positions.map(p => {
    const pnl     = p.unrealised_pnl || 0;
    const sideCls = p.direction === "BUY" ? "side-buy" : "side-sell";
    return `
      <tr class="animate-in">
        <td><strong>${p.symbol}</strong></td>
        <td><span class="${sideCls}">${p.direction}</span></td>
        <td>${p.quantity}</td>
        <td>${formatNum(p.entry_price)}</td>
        <td class="${pnlClass(pnl)}">${formatNum(p.current_price)}</td>
        <td class="pnl-negative">${formatNum(p.stop_loss)}</td>
        <td class="pnl-positive">${formatNum(p.target)}</td>
        <td class="${pnlClass(pnl)}">${formatCurrency(pnl)}</td>
        <td style="color:var(--text-muted);font-size:0.75rem">${p.strategy || "—"}</td>
      </tr>`;
  }).join("");
}

function renderSignals(signals) {
  const list  = document.getElementById("signalsList");
  const badge = document.getElementById("sigBadge");
  if (!list) return;

  if (badge) badge.textContent = signals.length;

  if (!signals.length) {
    list.innerHTML = `<div class="empty-state">No signals yet. Bot is scanning...</div>`;
    return;
  }

  list.innerHTML = signals.map(s => {
    const cls = s.direction === "BUY" ? "buy" : "sell";
    const sideCls = s.direction === "BUY" ? "side-buy" : "side-sell";
    return `
      <div class="signal-item ${cls} animate-in">
        <div class="sig-top">
          <span class="sig-symbol">${s.symbol} <span class="${sideCls}">${s.direction}</span></span>
          <span class="sig-time">${s.time || "—"}</span>
        </div>
        <div class="sig-details">
          <span>Entry: <strong>${formatNum(s.entry)}</strong></span>
          <span>SL: <strong style="color:var(--red)">${formatNum(s.sl)}</strong></span>
          <span>TGT: <strong style="color:var(--green)">${formatNum(s.target)}</strong></span>
        </div>
        <div class="sig-details" style="margin-top:0.2rem">
          <span>R:R: <strong>${s.rr || "—"}</strong></span>
          <span style="grid-column:span 2;color:var(--purple)">${s.strategy || ""}</span>
        </div>
        <div class="sig-notes" title="${s.notes || ""}">${s.notes || ""}</div>
      </div>`;
  }).join("");
}

function renderTrades(trades, filter) {
  const tbody = document.getElementById("tradeTableBody");
  if (!tbody) return;

  const filtered = filter === "all"
    ? trades
    : trades.filter(t => t.status === filter);

  if (!filtered.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="9">No trades for this filter</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(t => {
    const pnl     = t.pnl || 0;
    const sideCls = t.direction === "BUY" ? "side-buy" : "side-sell";
    const stCls   = `status-pill status-${(t.status || "").toLowerCase()}`;
    const time    = t.entry_time ? t.entry_time.split("T").pop().substring(0,8) : "—";
    return `
      <tr class="animate-in">
        <td style="color:var(--text-muted)">${time}</td>
        <td><strong>${t.symbol}</strong></td>
        <td><span class="${sideCls}">${t.direction}</span></td>
        <td>${t.quantity}</td>
        <td>${formatNum(t.entry_price)}</td>
        <td>${t.exit_price ? formatNum(t.exit_price) : "—"}</td>
        <td class="${pnlClass(pnl)}">${t.exit_price ? formatCurrency(pnl) : "—"}</td>
        <td><span class="${stCls}">${t.status || "OPEN"}</span></td>
        <td style="color:var(--text-muted);font-size:0.75rem">${t.strategy || "—"}</td>
      </tr>`;
  }).join("");
}

function renderStrategies(strategies) {
  const el = document.getElementById("strategiesList");
  if (!el) return;

  const names = {
    ema_crossover: "EMA 9/21 Crossover",
    rsi:           "RSI Mean Reversion",
    vwap:          "VWAP Momentum",
    supertrend:    "Supertrend",
    candlestick:   "Candlestick Patterns",
  };

  el.innerHTML = Object.entries(strategies).map(([key, enabled]) => `
    <div class="strategy-item">
      <span class="strategy-name">${names[key] || key}</span>
      <button
        class="strategy-toggle ${enabled ? "on" : "off"}"
        title="${enabled ? "Enabled" : "Disabled"}"
      >${enabled ? "●" : "○"}</button>
    </div>
  `).join("");
}

function renderWatchlist(watchlist) {
  const el    = document.getElementById("watchlistTags");
  const badge = document.getElementById("watchBadge");
  if (!el) return;
  if (badge) badge.textContent = watchlist.length;

  const openSymbols = new Set((state.positions || []).map(p => p.symbol));
  el.innerHTML = watchlist.map(sym => {
    const cls = openSymbols.has(sym) ? "stock-tag active" : "stock-tag";
    return `<span class="${cls}">${sym}</span>`;
  }).join("");
}

// ── Bot Controls ──────────────────────────────────────────────────────────────
async function botStart() {
  try {
    const r = await fetch("/api/bot/start", { method: "POST" });
    const d = await r.json();
    toast("Bot started! Scanning watchlist...", "success");
  } catch (e) {
    toast("Failed to start bot", "error");
  }
}

async function botStop() {
  showModal("Stop Bot", "Are you sure you want to stop the bot? Open positions will NOT be closed.", async () => {
    try {
      await fetch("/api/bot/stop", { method: "POST" });
      toast("Bot stopped.", "info");
    } catch (e) {
      toast("Failed to stop bot", "error");
    }
  });
}

async function squareOff() {
  showModal(
    "Square Off All Positions",
    "This will immediately close ALL open positions at market price. Are you sure?",
    async () => {
      try {
        await fetch("/api/square_off", { method: "POST" });
        toast("Square-off executed. All positions closing...", "warning");
      } catch (e) {
        toast("Square-off failed", "error");
      }
    }
  );
}

function filterTrades(filter, btn) {
  tradeFilter = filter;
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  if (btn) btn.classList.add("active");
  renderTrades(state.trades || [], filter);
}

// ── Clock ─────────────────────────────────────────────────────────────────────
function startClock() {
  function tick() {
    const now  = new Date();
    const time = now.toLocaleTimeString("en-IN", { hour12: false });
    const el   = document.getElementById("liveClock");
    if (el) el.textContent = time;
  }
  tick();
  setInterval(tick, 1000);
}

// ── Modal ─────────────────────────────────────────────────────────────────────
let _modalCallback = null;

function showModal(title, msg, onConfirm) {
  document.getElementById("modalTitle").textContent = title;
  document.getElementById("modalMsg").textContent   = msg;
  _modalCallback = onConfirm;
  document.getElementById("confirmModal").style.display = "flex";
  document.getElementById("modalConfirm").onclick = async () => {
    closeModal();
    if (_modalCallback) await _modalCallback();
  };
}

function closeModal() {
  document.getElementById("confirmModal").style.display = "none";
}

// ── Toast ─────────────────────────────────────────────────────────────────────
const TOAST_ICONS = { success: "✓", error: "✕", info: "ℹ", warning: "⚠" };

function toast(msg, type = "info", duration = 4000) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${TOAST_ICONS[type] || "•"}</span> <span>${msg}</span>`;
  container.appendChild(el);

  setTimeout(() => {
    el.style.opacity   = "0";
    el.style.transform = "translateX(30px)";
    el.style.transition = "all 0.3s";
    setTimeout(() => el.remove(), 300);
  }, duration);
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatNum(n) {
  if (n === null || n === undefined || n === "") return "—";
  return Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCurrency(n) {
  const abs  = Math.abs(n);
  const sign = n < 0 ? "-" : n > 0 ? "+" : "";
  return sign + "₹" + abs.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pnlClass(n) {
  if (n > 0)  return "pnl-positive";
  if (n < 0)  return "pnl-negative";
  return "pnl-neutral";
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}
