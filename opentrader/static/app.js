const CONFIG_FIELDS = [
  ["risk_per_trade", "Risk Per Trade", 0.0075],
  ["atr_stop_multiplier", "ATR Stop Multiplier", 1.4],
  ["reward_risk", "Reward/Risk", 1.9],
  ["min_confidence", "Min Confidence", 0.40],
  ["min_agreeing_agents", "Min Agreeing Agents", 2],
  ["vp_window", "Volume Profile Window", 120],
  ["sm_window", "Smart Money Window", 50],
  ["liq_window", "Liquidity Window", 35],
  ["trend_fast", "Trend Fast EMA", 12],
  ["trend_slow", "Trend Slow EMA", 48],
  ["spread_bps", "Spread (bps)", 1.0],
  ["slippage_bps", "Slippage (bps)", 0.5],
  ["weight_volume_profile", "Weight: Volume Profile", 1.2],
  ["weight_smart_money", "Weight: Smart Money", 1.4],
  ["weight_liquidity_sweep", "Weight: Liquidity Sweep", 1.1],
  ["weight_trend_bias", "Weight: Trend Bias", 0.8],
];

let strategies = [];
let activeStrategyId = null;
let optimizerJobId = null;
let optimizerPollTimer = null;
let eventSource = null;
let liveEquity = [];
let lastOrderflow = null;

function $(id) {
  return document.getElementById(id);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function fmtMoney(v) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}$${Number(v).toFixed(2)}`;
}

function renderConfigFields(config = {}) {
  $("configFields").innerHTML = CONFIG_FIELDS.map(([key, label, fallback]) => {
    const value = config[key] ?? fallback;
    const step = Number.isInteger(fallback) ? 1 : 0.01;
    return `<div><label>${label}</label><input data-config-key="${key}" type="number" step="${step}" value="${value}" /></div>`;
  }).join("");
}

function readConfigFromForm() {
  const config = {};
  document.querySelectorAll("[data-config-key]").forEach((input) => {
    const key = input.dataset.configKey;
    const raw = input.value;
    config[key] = raw.includes(".") ? parseFloat(raw) : parseInt(raw, 10);
  });
  return config;
}

function fillStrategyForm(strategy) {
  $("strategyName").value = strategy.name;
  $("strategyMode").value = strategy.mode;
  $("strategySymbol").value = strategy.symbol;
  $("strategyTimeframe").value = strategy.timeframe;
  renderConfigFields(strategy.config);
  $("modeBadge").textContent = `${strategy.mode} mode`;
}

function renderStrategyList() {
  const list = $("strategyList");
  list.innerHTML = strategies.map((s) => `
    <div class="strategy-item ${s.id === activeStrategyId ? "active" : ""}" data-id="${s.id}">
      <strong>${s.name}</strong><br /><small>${s.symbol} ${s.timeframe} · ${s.mode}</small>
    </div>`).join("");
  list.querySelectorAll(".strategy-item").forEach((item) => {
    item.addEventListener("click", () => {
      activeStrategyId = item.dataset.id;
      fillStrategyForm(strategies.find((r) => r.id === activeStrategyId));
      renderStrategyList();
    });
  });
}

async function loadStrategies() {
  strategies = await api("/api/strategies");
  if (!activeStrategyId && strategies.length) {
    activeStrategyId = strategies[0].id;
    fillStrategyForm(strategies[0]);
  }
  renderStrategyList();
}

async function saveStrategy() {
  const saved = await api("/api/strategies", {
    method: "POST",
    body: JSON.stringify({
      id: activeStrategyId,
      name: $("strategyName").value,
      mode: $("strategyMode").value,
      symbol: $("strategySymbol").value,
      timeframe: $("strategyTimeframe").value,
      config: readConfigFromForm(),
    }),
  });
  activeStrategyId = saved.id;
  await loadStrategies();
}

function renderMetricCards(containerId, rows) {
  $(containerId).innerHTML = rows.map(([label, value, cls]) =>
    `<div class="metric"><div class="label">${label}</div><div class="value ${cls || ""}">${value}</div></div>`
  ).join("");
}

function drawEquity(canvasId, curve) {
  const canvas = $(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 600;
  const height = canvas.clientHeight || 220;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);
  if (!curve || curve.length < 2) return;
  const min = Math.min(...curve);
  const max = Math.max(...curve);
  const range = Math.max(1, max - min);
  ctx.strokeStyle = "#4f8cff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  curve.forEach((value, index) => {
    const x = (index / (curve.length - 1)) * (width - 20) + 10;
    const y = height - 10 - ((value - min) / range) * (height - 20);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawPriceChart(canvasId, orderflow) {
  const canvas = $(canvasId);
  if (!canvas || !orderflow?.columns?.length) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 600;
  const height = canvas.clientHeight || 260;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);

  const cols = orderflow.columns;
  const pad = { l: 52, r: 12, t: 12, b: 22 };
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const priceMin = orderflow.price_min;
  const priceMax = orderflow.price_max;
  const priceRange = Math.max(1e-9, priceMax - priceMin);

  const xAt = (i) => pad.l + (i / Math.max(1, cols.length - 1)) * plotW;
  const yAt = (p) => pad.t + plotH - ((p - priceMin) / priceRange) * plotH;

  ctx.strokeStyle = "#24314f";
  ctx.lineWidth = 1;
  for (let g = 0; g <= 4; g++) {
    const y = pad.t + (plotH * g) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(width - pad.r, y);
    ctx.stroke();
    const price = priceMax - (priceRange * g) / 4;
    ctx.fillStyle = "#93a4c7";
    ctx.font = "10px sans-serif";
    ctx.fillText(price.toFixed(5), 4, y + 3);
  }

  const barW = Math.max(2, plotW / cols.length * 0.6);
  cols.forEach((col, i) => {
    const x = xAt(i) - barW / 2;
    const bullish = col.close >= col.open;
    const bodyTop = yAt(Math.max(col.open, col.close));
    const bodyBot = yAt(Math.min(col.open, col.close));
    const wickTop = yAt(col.high);
    const wickBot = yAt(col.low);
    ctx.strokeStyle = bullish ? "#22c997" : "#ff6b6b";
    ctx.fillStyle = bullish ? "rgba(34,201,151,0.85)" : "rgba(255,107,107,0.85)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(xAt(i), wickTop);
    ctx.lineTo(xAt(i), wickBot);
    ctx.stroke();
    ctx.fillRect(x, bodyTop, barW, Math.max(1, bodyBot - bodyTop));
  });

  if (orderflow.poc_price) {
    const pocY = yAt(orderflow.poc_price);
    ctx.strokeStyle = "rgba(255, 200, 80, 0.8)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.l, pocY);
    ctx.lineTo(width - pad.r, pocY);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function drawOrderflow(canvasId, orderflow, deltaElId, pocElId) {
  const canvas = $(canvasId);
  if (!canvas || !orderflow?.columns?.length) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 600;
  const height = canvas.clientHeight || 200;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);

  const cols = orderflow.columns;
  const bins = orderflow.bins;
  const pad = { l: 52, r: 12, t: 8, b: 8 };
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const priceMin = orderflow.price_min;
  const priceMax = orderflow.price_max;
  const priceRange = Math.max(1e-9, priceMax - priceMin);

  let maxVol = 0;
  cols.forEach((col) => {
    for (let b = 0; b < bins; b++) {
      maxVol = Math.max(maxVol, (col.buy[b] || 0) + (col.sell[b] || 0));
    }
  });
  maxVol = Math.max(maxVol, 1e-9);

  const colW = plotW / cols.length;
  const binH = plotH / bins;

  cols.forEach((col, ci) => {
    const x = pad.l + ci * colW;
    for (let b = 0; b < bins; b++) {
      const buy = col.buy[b] || 0;
      const sell = col.sell[b] || 0;
      const total = buy + sell;
      if (total <= 0) continue;
      const price = priceMin + (b + 0.5) * (priceRange / bins);
      const y = pad.t + plotH - ((price - priceMin) / priceRange) * plotH - binH;
      const intensity = Math.min(1, total / maxVol);
      if (buy >= sell) {
        ctx.fillStyle = `rgba(34, 201, 151, ${0.15 + intensity * 0.75})`;
      } else {
        ctx.fillStyle = `rgba(255, 107, 107, ${0.15 + intensity * 0.75})`;
      }
      ctx.fillRect(x, y, Math.max(1, colW - 0.5), Math.max(1, binH - 0.5));
    }
  });

  ctx.fillStyle = "#93a4c7";
  ctx.font = "10px sans-serif";
  for (let g = 0; g <= 4; g++) {
    const price = priceMax - (priceRange * g) / 4;
    const y = pad.t + (plotH * g) / 4;
    ctx.fillText(price.toFixed(5), 4, y + 3);
  }

  if (deltaElId && $(deltaElId)) {
    const d = orderflow.delta || 0;
    $(deltaElId).textContent = `Delta: ${d >= 0 ? "+" : ""}${d}`;
    $(deltaElId).className = d >= 0 ? "legend-buy" : "legend-sell";
  }
  if (pocElId && $(pocElId)) {
    $(pocElId).textContent = `POC: ${orderflow.poc_price ?? "—"}`;
  }
}

function renderCharts(orderflow, prefix = "") {
  if (!orderflow) return;
  lastOrderflow = orderflow;
  const priceId = prefix ? `${prefix}PriceChart` : "priceChart";
  const flowId = prefix ? `${prefix}OrderflowChart` : "orderflowChart";
  const deltaId = prefix ? `${prefix}OrderflowDelta` : "orderflowDelta";
  const pocId = prefix ? null : "orderflowPoc";
  drawPriceChart(priceId, orderflow);
  drawOrderflow(flowId, orderflow, deltaId, pocId);
}

async function loadOrderflowPreview() {
  try {
    const flow = await api("/api/orderflow?window=120");
    renderCharts(flow);
  } catch (_) { /* ignore */ }
}

function updateLiveDashboard(state) {
  if (!state || state.status === "idle") return;

  const pnl = state.realized_pnl + (state.unrealized_pnl || 0);
  $("headerPnl").textContent = fmtMoney(pnl);
  $("headerPnl").className = `live-pnl ${pnl >= 0 ? "positive" : "negative"}`;
  $("sessionBadge").textContent = state.status;
  $("sessionBadge").className = `badge ${state.status === "running" ? "running" : "idle"}`;

  renderMetricCards("liveMetrics", [
    ["Equity", `$${Number(state.equity).toFixed(2)}`, state.equity >= state.initial_balance ? "positive" : "negative"],
    ["Realized PnL", fmtMoney(state.realized_pnl), state.realized_pnl >= 0 ? "positive" : "negative"],
    ["Unrealized PnL", fmtMoney(state.unrealized_pnl || 0), (state.unrealized_pnl || 0) >= 0 ? "positive" : "negative"],
    ["Win Rate %", `${state.win_rate_pct}%`, state.win_rate_pct >= 65 ? "positive" : ""],
    ["Trades", state.trades_count, ""],
    ["Return %", `${state.total_return_pct}%`, state.total_return_pct >= 0 ? "positive" : "negative"],
    ["Last Price", state.last_price, ""],
    ["Candle", `${state.candle_index}/${state.candles_total}`, ""],
  ]);

  $("liveStatus").textContent =
    `${state.strategy_name} · ${state.symbol} · ${state.last_timestamp || "—"} · ${state.mode} mode`;

  if (state.equity_curve) {
    liveEquity = state.equity_curve;
    drawEquity("liveEquityChart", liveEquity);
  }

  if (state.orderflow) {
    renderCharts(state.orderflow);
  }

  const pos = state.open_position;
  if (pos) {
    $("openPositionPanel").innerHTML = `
      <div><strong>${pos.side.toUpperCase()}</strong> @ ${pos.entry_price.toFixed(5)}</div>
      <div>Qty: ${pos.quantity.toFixed(4)}</div>
      <div>SL: ${pos.stop_loss.toFixed(5)} · TP: ${pos.take_profit.toFixed(5)}</div>
      <div class="${pos.unrealized_pnl >= 0 ? "positive" : "negative"}">Unrealized: ${fmtMoney(pos.unrealized_pnl)}</div>`;
  } else {
    $("openPositionPanel").textContent = "No open position";
  }

  $("progressFill").style.width = `${state.progress_pct || 0}%`;
  $("progressLabel").textContent = `${state.progress_pct || 0}%`;
}

function connectStream() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/session/stream");
  eventSource.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.equity !== undefined || payload.event) {
      updateLiveDashboard(payload);
    }
    if (payload.event === "trade_closed") {
      loadJournal();
    }
  };
  eventSource.onerror = () => {
    setTimeout(connectStream, 3000);
  };
}

async function startSession() {
  if (!activeStrategyId) throw new Error("Select a strategy first.");
  await saveStrategy();
  const state = await api("/api/session/start", {
    method: "POST",
    body: JSON.stringify({ strategy_id: activeStrategyId, tick_ms: 100 }),
  });
  liveEquity = state.equity_curve || [];
  updateLiveDashboard(state);
  connectStream();
  setActiveTab("dashboard");
}

async function stopSession() {
  try {
    const state = await api("/api/session/stop", { method: "POST" });
    updateLiveDashboard(state);
  } catch (_) {
    /* no active session */
  }
  if (eventSource) eventSource.close();
  await loadJournal();
}

async function loadJournal() {
  const data = await api("/api/journal?limit=500");
  const stats = data.stats;
  renderMetricCards("journalStats", [
    ["Total Trades", stats.total_trades, ""],
    ["Win Rate %", `${stats.win_rate_pct}%`, stats.win_rate_pct >= 65 ? "positive" : "negative"],
    ["Total PnL", fmtMoney(stats.total_pnl), stats.total_pnl >= 0 ? "positive" : "negative"],
    ["Profit Factor", stats.profit_factor, stats.profit_factor >= 1 ? "positive" : "negative"],
    ["Avg Win", fmtMoney(stats.avg_win), "positive"],
    ["Avg Loss", fmtMoney(stats.avg_loss), "negative"],
    ["Best Trade", fmtMoney(stats.best_trade), "positive"],
    ["Worst Trade", fmtMoney(stats.worst_trade), "negative"],
  ]);
  $("journalBody").innerHTML = (data.trades || []).map((t) => `
    <tr>
      <td>${t.side}</td>
      <td>${t.entry_time}</td>
      <td>${t.exit_time}</td>
      <td>${Number(t.entry_price).toFixed(5)}</td>
      <td>${Number(t.exit_price).toFixed(5)}</td>
      <td>${Number(t.quantity).toFixed(4)}</td>
      <td class="${t.pnl >= 0 ? "positive" : "negative"}">${fmtMoney(t.pnl)}</td>
      <td>$${Number(t.balance_after).toFixed(2)}</td>
      <td>${Number(t.entry_confidence).toFixed(2)}</td>
      <td>${t.reason}</td>
    </tr>`).join("");
}

async function runBacktest() {
  $("backtestStatus").textContent = "Running backtest...";
  const result = await api("/api/backtest", {
    method: "POST",
    body: JSON.stringify({ strategy_id: activeStrategyId, walk_forward: true }),
  });
  const test = result.test || result.result;
  $("backtestStatus").textContent = result.walk_forward
    ? `Train ${result.train.total_return_pct}% · Test ${test.total_return_pct}% · WR ${test.win_rate_pct}%`
    : `Return ${test.total_return_pct}% · WR ${test.win_rate_pct}%`;
  renderMetricCards("metrics", [
    ["Return %", `${test.total_return_pct}%`, test.total_return_pct >= 0 ? "positive" : "negative"],
    ["Win Rate %", `${test.win_rate_pct}%`, test.win_rate_pct >= 65 ? "positive" : "negative"],
    ["Max DD %", `${test.max_drawdown_pct}%`, "negative"],
    ["Trades", test.trades, ""],
    ["Trades/Day", test.trades_per_day, ""],
  ]);
  drawEquity("equityChart", test.equity_curve);
  try {
    const flow = await api("/api/orderflow?window=120");
    renderCharts(flow, "backtest");
  } catch (_) { /* ignore */ }
  $("tradesBody").innerHTML = (test.trade_rows || []).slice(-50).reverse().map((t) => `
    <tr>
      <td>${t.side}</td><td>${t.entry_time}</td><td>${t.exit_time}</td>
      <td>${t.entry_price}</td><td>${t.exit_price}</td>
      <td class="${t.pnl >= 0 ? "positive" : "negative"}">${t.pnl}</td><td>${t.reason}</td>
    </tr>`).join("");
  setActiveTab("backtest");
}

function renderOptimizerMetrics(best) {
  if (!best) { $("optimizerMetrics").innerHTML = ""; return; }
  renderMetricCards("optimizerMetrics", [
    ["Objective", best.objective, ""],
    ["Rolling Min WR %", `${best.rolling_min_win_rate_pct}%`, best.rolling_min_win_rate_pct >= 65 ? "positive" : ""],
    ["Test WR %", `${best.win_rate_test_pct}%`, ""],
    ["Test Return %", `${best.total_return_test_pct}%`, ""],
    ["Rolling Min Return %", `${best.rolling_min_return_pct}%`, ""],
    ["Test Trades", best.trades_test, ""],
  ]);
}

async function pollOptimizer() {
  if (!optimizerJobId) return;
  const job = await api(`/api/optimizer/jobs/${optimizerJobId}`);
  $("optimizerStatus").textContent = `Iter ${job.iteration} · ${job.message} · ${job.status}`;
  renderOptimizerMetrics(job.best);
  if (job.status === "running") optimizerPollTimer = setTimeout(pollOptimizer, 3000);
  else if (job.gate_met) $("optimizerStatus").textContent = "Gate met: 65%+ win rate achieved.";
}

async function startOptimizer() {
  const job = await api("/api/optimizer/start", {
    method: "POST",
    body: JSON.stringify({
      max_iterations: 0,
      gates: {
        min_win_rate: parseFloat($("gateWinRate").value),
        max_test_drawdown: parseFloat($("gateMaxDd").value),
        target_test_return: 0.5,
        min_test_trades: 20,
      },
    }),
  });
  optimizerJobId = job.id;
  setActiveTab("optimizer");
  pollOptimizer();
}

function setActiveTab(tabName) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tabName));
  ["dashboard", "journal", "settings", "backtest", "optimizer"].forEach((name) => {
    $(`${name}Tab`).classList.toggle("hidden", tabName !== name);
  });
  if (tabName === "journal") loadJournal().catch(console.error);
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => setActiveTab(tab.dataset.tab));
});

$("saveStrategyBtn").addEventListener("click", () => saveStrategy().then(() => alert("Saved")).catch((e) => alert(e.message)));
$("runBacktestBtn").addEventListener("click", () => runBacktest().catch((e) => alert(e.message)));
$("startOptimizerBtn").addEventListener("click", () => startOptimizer().catch((e) => alert(e.message)));
$("startSessionBtn").addEventListener("click", () => startSession().catch((e) => alert(e.message)));
$("stopSessionBtn").addEventListener("click", () => stopSession().catch((e) => alert(e.message)));
$("newStrategyBtn").addEventListener("click", () => {
  activeStrategyId = null;
  fillStrategyForm({ name: "New Strategy", mode: "paper", symbol: "EURUSD", timeframe: "M1", config: {} });
  renderStrategyList();
});
$("strategyMode").addEventListener("change", (e) => { $("modeBadge").textContent = `${e.target.value} mode`; });

async function init() {
  await loadStrategies();
  await loadJournal();
  await loadOrderflowPreview();
  const status = await api("/api/session/status");
  if (status.status && status.status !== "idle") {
    updateLiveDashboard(status);
    connectStream();
  }
  // Auto-start optimizer in background
  try {
    const jobs = await api("/api/optimizer/jobs");
    const running = jobs.find((j) => j.status === "running");
    if (!running) await startOptimizer();
    else { optimizerJobId = running.id; pollOptimizer(); }
  } catch (_) { /* ignore */ }
}

init().catch((err) => { $("liveStatus").textContent = `Init error: ${err.message}`; });
