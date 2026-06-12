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
let bookmapSource = null;
let liveEquity = [];
let lastOrderflow = null;
let signalLog = [];

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
  const el = $("configFields");
  if (!el) return;
  el.innerHTML = CONFIG_FIELDS.map(([key, label, fallback]) => {
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
  $("chartSymbol").textContent = strategy.symbol;
  renderConfigFields(strategy.config);
  $("modeBadge").textContent = strategy.mode;
}

function renderStrategyList() {
  const list = $("strategyList");
  list.innerHTML = strategies.map((s) => `
    <div class="strategy-item ${s.id === activeStrategyId ? "active" : ""}" data-id="${s.id}">
      <strong>${s.name}</strong><br /><small>${s.symbol} ${s.timeframe}</small>
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
  $("chartSymbol").textContent = saved.symbol;
  await loadStrategies();
}

function renderMetricCards(containerId, rows) {
  const el = $(containerId);
  if (!el) return;
  el.innerHTML = rows.map(([label, value, cls]) =>
    `<div><span class="muted">${label}</span> <strong class="${cls || ""}">${value}</strong></div>`
  ).join("");
}

function drawEquity(canvasId, curve) {
  const canvas = $(canvasId);
  if (!canvas || !curve?.length) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 300;
  const height = canvas.clientHeight || 70;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);
  if (curve.length < 2) return;
  const min = Math.min(...curve);
  const max = Math.max(...curve);
  const range = Math.max(1, max - min);
  ctx.strokeStyle = "#3b82f6";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  curve.forEach((value, index) => {
    const x = (index / (curve.length - 1)) * (width - 8) + 4;
    const y = height - 4 - ((value - min) / range) * (height - 8);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function drawPriceChart(canvasId, orderflow) {
  const canvas = $(canvasId);
  if (!canvas || !orderflow?.columns?.length) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 800;
  const height = canvas.clientHeight || 320;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);

  const cols = orderflow.columns;
  const pad = { l: 56, r: 70, t: 16, b: 28 };
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const priceMin = orderflow.price_min;
  const priceMax = orderflow.price_max;
  const priceRange = Math.max(1e-9, priceMax - priceMin);

  const xAt = (i) => pad.l + (i / Math.max(1, cols.length - 1)) * plotW;
  const yAt = (p) => pad.t + plotH - ((p - priceMin) / priceRange) * plotH;

  ctx.fillStyle = "#0a0e14";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "#1e293b";
  for (let g = 0; g <= 5; g++) {
    const y = pad.t + (plotH * g) / 5;
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(width - pad.r, y);
    ctx.stroke();
    const price = priceMax - (priceRange * g) / 5;
    ctx.fillStyle = "#64748b";
    ctx.font = "11px sans-serif";
    ctx.fillText(price.toFixed(5), width - pad.r + 4, y + 4);
  }

  const barW = Math.max(2, (plotW / cols.length) * 0.65);
  cols.forEach((col, i) => {
    const bullish = col.close >= col.open;
    ctx.strokeStyle = bullish ? "#22c997" : "#ef4444";
    ctx.fillStyle = bullish ? "rgba(34,201,151,0.9)" : "rgba(239,68,68,0.9)";
    ctx.beginPath();
    ctx.moveTo(xAt(i), yAt(col.high));
    ctx.lineTo(xAt(i), yAt(col.low));
    ctx.stroke();
    const top = yAt(Math.max(col.open, col.close));
    const bot = yAt(Math.min(col.open, col.close));
    ctx.fillRect(xAt(i) - barW / 2, top, barW, Math.max(1, bot - top));
  });

  if (orderflow.poc_price) {
    const pocY = yAt(orderflow.poc_price);
    ctx.strokeStyle = "rgba(251,191,36,0.7)";
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.l, pocY);
    ctx.lineTo(width - pad.r, pocY);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  const last = cols[cols.length - 1];
  if (last) {
    $("lastPriceLabel").textContent = last.close.toFixed(5);
  }
}

function drawOrderflow(canvasId, orderflow, deltaElId, pocElId) {
  const canvas = $(canvasId);
  if (!canvas || !orderflow?.columns?.length) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 800;
  const height = canvas.clientHeight || 160;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);

  const cols = orderflow.columns;
  const bins = orderflow.bins;
  const pad = { l: 56, r: 12, t: 6, b: 6 };
  const plotW = width - pad.l - pad.r;
  const plotH = height - pad.t - pad.b;
  const priceMin = orderflow.price_min;
  const priceMax = orderflow.price_max;
  const priceRange = Math.max(1e-9, priceMax - priceMin);

  let maxVol = 1e-9;
  cols.forEach((col) => {
    for (let b = 0; b < bins; b++) {
      maxVol = Math.max(maxVol, (col.buy[b] || 0) + (col.sell[b] || 0));
    }
  });

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
      ctx.fillStyle = buy >= sell
        ? `rgba(34, 201, 151, ${0.12 + intensity * 0.82})`
        : `rgba(239, 68, 68, ${0.12 + intensity * 0.82})`;
      ctx.fillRect(x, y, Math.max(1, colW - 0.5), Math.max(1, binH - 0.5));
    }
  });

  if (deltaElId && $(deltaElId)) {
    const d = orderflow.delta || 0;
    $(deltaElId).textContent = d >= 0 ? `+${d}` : `${d}`;
    $(deltaElId).className = d >= 0 ? "positive" : "negative";
  }
  if (pocElId && $(pocElId)) {
    $(pocElId).textContent = orderflow.poc_price ?? "—";
  }
}

function drawVolumeChart(orderflow) {
  const canvas = $("volumeChart");
  if (!canvas || !orderflow?.columns?.length) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth || 800;
  const height = canvas.clientHeight || 160;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);

  const cols = orderflow.columns;
  const volumes = cols.map((c) => (c.buy || []).reduce((a, b) => a + b, 0) + (c.sell || []).reduce((a, b) => a + b, 0));
  const maxV = Math.max(...volumes, 1);
  const barW = (width - 20) / cols.length;

  cols.forEach((col, i) => {
    const v = volumes[i];
    const h = (v / maxV) * (height - 20);
    const bullish = col.close >= col.open;
    ctx.fillStyle = bullish ? "rgba(34,201,151,0.7)" : "rgba(239,68,68,0.7)";
    ctx.fillRect(10 + i * barW, height - 10 - h, Math.max(1, barW - 1), h);
  });
}

function renderCharts(orderflow) {
  if (!orderflow) return;
  lastOrderflow = orderflow;
  drawPriceChart("priceChart", orderflow);
  drawOrderflow("orderflowChart", orderflow, "orderflowDelta", "orderflowPoc");
  drawVolumeChart(orderflow);
}

function appendSignal(signal) {
  signalLog.unshift(signal);
  signalLog = signalLog.slice(0, 100);
  const feed = $("signalFeed");
  if (!feed) return;
  const typeClass = {
    sweep: "legend-sweep",
    absorption: "legend-absorption",
    large_print: "legend-large",
    imbalance: "legend-imbalance",
  }[signal.type] || "";
  feed.innerHTML = signalLog.map((s) => `
    <li class="${typeClass}">
      <span>${s.type}</span>
      <span>${s.price?.toFixed?.(5) ?? "—"}</span>
      <span>${s.side ?? ""}</span>
      <span>${s.timestamp ?? ""}</span>
    </li>`).join("");
}

function setBookmapLive(live, source) {
  const dot = $("bookmapLiveDot");
  const src = $("bookmapSource");
  if (dot) dot.classList.toggle("live", live);
  if (src) src.textContent = live ? `Live · ${source || "stream"}` : "waiting for signals…";
}

function connectBookmapStream() {
  if (bookmapSource) bookmapSource.close();
  bookmapSource = new EventSource("/api/bookmap/stream");
  bookmapSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.cvd !== undefined) $("bookmapCvd").textContent = Number(data.cvd).toFixed(3);
    if (data.orderflow) renderCharts(data.orderflow);
    if (data.signals?.length) data.signals.forEach(appendSignal);
    if (data.source || data.status) setBookmapLive(data.status === "live" || data.connected, data.source);
  };
  bookmapSource.onerror = () => setTimeout(connectBookmapStream, 3000);
}

async function startBookmapReplay() {
  try {
    await api("/api/bookmap/start-replay", {
      method: "POST",
      body: JSON.stringify({ tick_ms: 150, window: 100 }),
    });
    setBookmapLive(true, "replay");
    connectBookmapStream();
  } catch (e) {
    $("liveStatus").textContent = `Bookmap: ${e.message}`;
  }
}

async function loadOrderflowPreview() {
  try {
    const flow = await api("/api/orderflow?window=120");
    renderCharts(flow);
    $("liveStatus").textContent = "Chart loaded · starting Bookmap order flow…";
    await startBookmapReplay();
  } catch (e) {
    $("liveStatus").textContent = `Load error: ${e.message}`;
  }
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
    ["Win%", `${state.win_rate_pct}%`, state.win_rate_pct >= 65 ? "positive" : ""],
    ["Trades", state.trades_count, ""],
    ["Return", `${state.total_return_pct}%`, state.total_return_pct >= 0 ? "positive" : "negative"],
  ]);

  $("liveStatus").textContent = `${state.strategy_name} · ${state.symbol} · ${state.last_timestamp || "—"}`;

  if (state.equity_curve) {
    liveEquity = state.equity_curve;
    drawEquity("liveEquityChart", liveEquity);
  }
  if (state.orderflow) renderCharts(state.orderflow);
  if (state.last_price) $("lastPriceLabel").textContent = Number(state.last_price).toFixed(5);

  const pos = state.open_position;
  if (pos) {
    $("openPositionPanel").innerHTML = `
      <strong>${pos.side.toUpperCase()}</strong> @ ${pos.entry_price.toFixed(5)}<br />
      SL ${pos.stop_loss.toFixed(5)} · TP ${pos.take_profit.toFixed(5)}<br />
      <span class="${pos.unrealized_pnl >= 0 ? "positive" : "negative"}">${fmtMoney(pos.unrealized_pnl)}</span>`;
  } else {
    $("openPositionPanel").textContent = "No open position";
  }
}

function connectStream() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/session/stream");
  eventSource.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.equity !== undefined || payload.event) updateLiveDashboard(payload);
    if (payload.orderflow) renderCharts(payload.orderflow);
    if (payload.event === "trade_closed") loadJournal();
  };
  eventSource.onerror = () => setTimeout(connectStream, 3000);
}

async function startSession() {
  if (!activeStrategyId) throw new Error("Select a strategy first.");
  await saveStrategy();
  const state = await api("/api/session/start", {
    method: "POST",
    body: JSON.stringify({ strategy_id: activeStrategyId, tick_ms: 100 }),
  });
  updateLiveDashboard(state);
  connectStream();
  connectBookmapStream();
}

async function stopSession() {
  try {
    const state = await api("/api/session/stop", { method: "POST" });
    updateLiveDashboard(state);
  } catch (_) { /* ok */ }
  await api("/api/bookmap/stop", { method: "POST" }).catch(() => {});
  if (eventSource) eventSource.close();
  if (bookmapSource) bookmapSource.close();
  setBookmapLive(false);
  await loadJournal();
}

async function loadJournal() {
  const data = await api("/api/journal?limit=500");
  const stats = data.stats;
  renderMetricCards("journalStatsMini", [
    ["Trades", stats.total_trades, ""],
    ["WR%", `${stats.win_rate_pct}%`, stats.win_rate_pct >= 65 ? "positive" : "negative"],
    ["PnL", fmtMoney(stats.total_pnl), stats.total_pnl >= 0 ? "positive" : "negative"],
  ]);
}

async function runBacktest() {
  $("liveStatus").textContent = "Running backtest…";
  const result = await api("/api/backtest", {
    method: "POST",
    body: JSON.stringify({ strategy_id: activeStrategyId, walk_forward: true }),
  });
  const test = result.test || result.result;
  $("liveStatus").textContent = `Backtest: ${test.total_return_pct}% return · ${test.win_rate_pct}% WR`;
  const flow = await api("/api/orderflow?window=120");
  renderCharts(flow);
}

async function startOptimizer() {
  const job = await api("/api/optimizer/start", {
    method: "POST",
    body: JSON.stringify({
      max_iterations: 0,
      gates: { min_win_rate: 65, max_test_drawdown: 10, target_test_return: 0.5, min_test_trades: 20 },
    }),
  });
  optimizerJobId = job.id;
  pollOptimizer();
}

async function pollOptimizer() {
  if (!optimizerJobId) return;
  const job = await api(`/api/optimizer/jobs/${optimizerJobId}`);
  if (job.status === "running") {
    optimizerPollTimer = setTimeout(pollOptimizer, 5000);
  }
}

// Sub-tabs below chart: Heatmap | Signals | Volume
document.querySelectorAll(".sub-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".sub-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    ["Heatmap", "Signals", "Volume"].forEach((name) => {
      const panel = $(`sub${name}`);
      if (panel) panel.classList.toggle("hidden", tab.dataset.sub !== name.toLowerCase());
    });
  });
});

$("btnBookmapToggle")?.addEventListener("click", () => {
  $("bookmapPanel")?.classList.toggle("collapsed");
  $("btnBookmapToggle")?.classList.toggle("active");
});

document.querySelectorAll(".sidebar-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".sidebar-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    $("sidebarResearch")?.classList.toggle("hidden", tab.dataset.stab !== "research");
    $("sidebarJournal")?.classList.toggle("hidden", tab.dataset.stab !== "journal");
    if (tab.dataset.stab === "journal") loadJournal();
  });
});

document.querySelectorAll(".tf").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tf").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    $("strategyTimeframe").value = btn.dataset.tf;
  });
});

$("saveStrategyBtn")?.addEventListener("click", () => saveStrategy().catch((e) => alert(e.message)));
$("runBacktestBtn")?.addEventListener("click", () => runBacktest().catch((e) => alert(e.message)));
$("startOptimizerBtn")?.addEventListener("click", () => startOptimizer().catch((e) => alert(e.message)));
$("startSessionBtn")?.addEventListener("click", () => startSession().catch((e) => alert(e.message)));
$("stopSessionBtn")?.addEventListener("click", () => stopSession().catch((e) => alert(e.message)));
$("newStrategyBtn")?.addEventListener("click", () => {
  activeStrategyId = null;
  fillStrategyForm({ name: "New Strategy", mode: "paper", symbol: "EURUSD", timeframe: "M1", config: {} });
  renderStrategyList();
});

async function init() {
  await loadStrategies();
  await loadJournal();
  await loadOrderflowPreview();
  connectBookmapStream();
  const status = await api("/api/session/status");
  if (status.status && status.status !== "idle") {
    updateLiveDashboard(status);
    connectStream();
  }
  try {
    const jobs = await api("/api/optimizer/jobs");
    const running = jobs.find((j) => j.status === "running");
    if (!running) await startOptimizer();
    else { optimizerJobId = running.id; pollOptimizer(); }
  } catch (_) { /* ignore */ }
  window.addEventListener("resize", () => { if (lastOrderflow) renderCharts(lastOrderflow); });
}

init().catch((err) => { $("liveStatus").textContent = `Init error: ${err.message}`; });
