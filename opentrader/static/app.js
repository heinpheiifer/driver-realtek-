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

let marketState = {
  symbol: "BTCUSD",
  source: "blackbull",
  timeframe: "M5",
  csv_path: null,
  source_label: "",
};
let blackbullRefreshTimer = null;

function $(id) {
  return document.getElementById(id);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail = await response.text();
    try {
      const parsed = JSON.parse(detail);
      detail = parsed.detail?.message || parsed.detail || parsed.message || detail;
      if (typeof parsed.detail === "object") {
        detail = parsed.detail.message || JSON.stringify(parsed.detail);
      }
    } catch (_) { /* plain text */ }
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function fmtMoney(v) {
  const sign = v >= 0 ? "+" : "";
  return `${sign}$${Number(v).toFixed(2)}`;
}

function fmtPrice(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return v >= 100 ? v.toFixed(2) : v.toFixed(5);
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
  $("symbolInput").value = strategy.symbol;
  marketState.symbol = strategy.symbol;
  marketState.timeframe = strategy.timeframe;
  renderConfigFields(strategy.config);
  $("modeBadge").textContent = strategy.mode;
  syncTimeframeButtons(strategy.timeframe);
}

function syncTimeframeButtons(tf) {
  document.querySelectorAll(".tf").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tf === tf);
  });
}

function renderStrategyList() {
  const list = $("strategyList");
  list.innerHTML = strategies.map((s) => `
    <div class="strategy-item ${s.id === activeStrategyId ? "active" : ""}" data-id="${s.id}">
      <strong>${s.name}</strong><br /><small>${s.symbol} ${s.timeframe}</small>
    </div>`).join("");
  list.querySelectorAll(".strategy-item").forEach((item) => {
    item.addEventListener("click", async () => {
      activeStrategyId = item.dataset.id;
      fillStrategyForm(strategies.find((r) => r.id === activeStrategyId));
      renderStrategyList();
      await loadMarket().catch((e) => { $("liveStatus").textContent = e.message; });
    });
  });
}

async function loadStrategies() {
  strategies = await api("/api/strategies");
  if (!activeStrategyId && strategies.length) {
    activeStrategyId = strategies[0].id;
    fillStrategyForm(strategies[0]);
  } else if (!strategies.length) {
    fillStrategyForm({ name: "Swarm Scalper", mode: "paper", symbol: "BTCUSD", timeframe: "M5", config: {} });
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
    ctx.fillText(fmtPrice(price), width - pad.r + 4, y + 4);
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
    $("lastPriceLabel").textContent = fmtPrice(last.close);
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
    $(pocElId).textContent = fmtPrice(orderflow.poc_price);
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
      <span>${fmtPrice(s.price)}</span>
      <span>${s.side ?? ""}</span>
      <span>${s.timestamp ?? ""}</span>
    </li>`).join("");
}

function setBookmapLive(live, source) {
  const dot = $("bookmapLiveDot");
  const src = $("bookmapSource");
  if (dot) dot.classList.toggle("live", live);
  if (src) {
    src.textContent = live
      ? `Live · ${source || "stream"}`
      : "Waiting for signals… Enable Bookmap export addon or use replay";
  }
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
  if (!marketState.csv_path) return;
  try {
    await api("/api/bookmap/stop", { method: "POST" }).catch(() => {});
    await api("/api/bookmap/start-replay", {
      method: "POST",
      body: JSON.stringify({ csv_path: marketState.csv_path, tick_ms: 150, window: 100 }),
    });
    setBookmapLive(true, "replay");
    connectBookmapStream();
  } catch (e) {
    $("liveStatus").textContent = `Bookmap: ${e.message}`;
  }
}

async function updateMt5Status() {
  try {
    const data = await api("/api/market/mt5/status");
    const mt5 = data.mt5 || {};
    const el = $("mt5Status");
    if (!el) return;
    if (mt5.connected) {
      el.textContent = `MT5 ✓ ${mt5.server || mt5.broker || "connected"}`;
      el.className = "mt5-status connected";
    } else if (mt5.available) {
      el.textContent = "MT5 offline";
      el.className = "mt5-status offline";
    } else {
      el.textContent = "MT5 bridge needed";
      el.className = "mt5-status offline";
    }
    el.title = mt5.last_error || "BlackBull MT5 connection status";
  } catch (_) {
    const el = $("mt5Status");
    if (el) { el.textContent = "MT5 ?"; el.className = "mt5-status offline"; }
  }
}

function scheduleBlackbullRefresh() {
  if (blackbullRefreshTimer) clearInterval(blackbullRefreshTimer);
  if (marketState.source !== "blackbull") return;
  blackbullRefreshTimer = setInterval(() => {
    loadMarket(true).catch(() => {});
  }, 15000);
}

async function syncMt5() {
  $("liveStatus").textContent = "Syncing from BlackBull MT5…";
  const data = await api(
    `/api/market/blackbull/sync?symbol=${encodeURIComponent(marketState.symbol)}&timeframe=${marketState.timeframe}&bars=800`,
    { method: "POST" }
  );
  marketState.csv_path = data.csv_path;
  marketState.source_label = data.source;
  renderCharts(data.orderflow);
  $("dataSourceTag").textContent = `${data.source} · ${data.count} bars`;
  $("dataSourceTag").classList.remove("synthetic-warning");
  $("liveStatus").textContent = `MT5 synced · ${fmtPrice(data.last_price)} · ${data.source}`;
  await updateMt5Status();
  await startBookmapReplay();
}

function defaultCsvPath() {
  const sym = marketState.symbol.toLowerCase();
  const tf = marketState.timeframe.toLowerCase();
  return `trading_data/blackbull_import/${sym}_${tf}.csv`;
}

function resolveCsvPath(quiet = false) {
  const autoPath = defaultCsvPath();
  if (!quiet) {
    const entered = prompt("CSV file path:", marketState.csv_path || autoPath);
    if (entered !== null) {
      marketState.csv_path = entered.trim() || autoPath;
    } else if (!marketState.csv_path) {
      marketState.csv_path = autoPath;
    }
  } else if (!marketState.csv_path) {
    marketState.csv_path = autoPath;
  }
  return marketState.csv_path;
}

async function loadSymbols() {
  try {
    const data = await api("/api/symbols");
    const list = $("symbolList");
    if (!list) return;
    const symbols = data.symbols || [];
    list.innerHTML = symbols.map((s) => {
      const name = typeof s === "string" ? s : s.name || s.symbol || "";
      return name ? `<option value="${name}"></option>` : "";
    }).join("");
  } catch (_) { /* symbols optional until MT5 manifest exists */ }
}

async function loadMarket(quiet = false, allowYahooFallback = true) {
  marketState.symbol = ($("symbolInput")?.value || "BTCUSD").toUpperCase().replace("/", "");
  marketState.timeframe = $("strategyTimeframe")?.value || "M5";
  $("chartSymbol").textContent = marketState.symbol;
  $("strategySymbol").value = marketState.symbol;
  syncTimeframeButtons(marketState.timeframe);
  if (!quiet) $("liveStatus").textContent = `Loading ${marketState.symbol} from ${marketState.source}…`;

  let csvParam = "";
  if (marketState.source === "csv") {
    const csvPath = resolveCsvPath(quiet);
    csvParam = `&csv_path=${encodeURIComponent(csvPath)}`;
  }

  try {
    const data = await api(
      `/api/market/candles?symbol=${encodeURIComponent(marketState.symbol)}&source=${marketState.source}&timeframe=${marketState.timeframe}&bars=800&window=120${csvParam}`
    );

    marketState.csv_path = data.csv_path;
    marketState.source_label = data.source;
    const tag = $("dataSourceTag");
    if (tag) {
      tag.textContent = `${data.source} · ${data.count} bars${data.used_cache ? " (cached)" : ""}`;
      tag.classList.toggle("synthetic-warning", !!data.is_synthetic);
    }
    renderCharts(data.orderflow);
    let status = `${marketState.symbol} ${marketState.timeframe} · ${data.source} · ${fmtPrice(data.last_price)}`;
    if (data.is_synthetic) status += " · ⚠ synthetic fallback";
    if (data.used_cache) status += " · cached MT5 data";
    $("liveStatus").textContent = status;
    if (data.mt5) updateMt5StatusFromPayload(data.mt5);
    if (!quiet) await startBookmapReplay();
  } catch (e) {
    if (marketState.source === "blackbull" && allowYahooFallback) {
      $("liveStatus").textContent = "BlackBull unavailable — loading Yahoo…";
      marketState.source = "yahoo";
      document.querySelectorAll(".source-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.source === "yahoo");
      });
      $("syncMt5Btn")?.classList.add("hidden");
      return loadMarket(quiet, false);
    }
    $("liveStatus").textContent = `Load failed: ${e.message}`;
    await updateMt5Status();
    throw e;
  }
}

function updateMt5StatusFromPayload(mt5) {
  const el = $("mt5Status");
  if (!el) return;
  if (mt5.connected) {
    el.textContent = `MT5 ✓ ${mt5.server || mt5.broker || "connected"}`;
    el.className = "mt5-status connected";
  } else {
    el.textContent = "MT5 bridge needed";
    el.className = "mt5-status offline";
  }
  el.title = mt5.last_error || mt5.hint || "";
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
  if (state.last_price) $("lastPriceLabel").textContent = fmtPrice(state.last_price);

  const pos = state.open_position;
  if (pos) {
    $("openPositionPanel").innerHTML = `
      <strong>${pos.side.toUpperCase()}</strong> @ ${fmtPrice(pos.entry_price)}<br />
      SL ${fmtPrice(pos.stop_loss)} · TP ${fmtPrice(pos.take_profit)}<br />
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
  if (!marketState.csv_path) await loadMarket();
  await saveStrategy();
  const state = await api("/api/session/start", {
    method: "POST",
    body: JSON.stringify({
      strategy_id: activeStrategyId,
      csv_path: marketState.csv_path,
      tick_ms: 100,
    }),
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
    ["Avg", fmtMoney(stats.avg_pnl), ""],
  ]);

  const tbody = $("journalTable")?.querySelector("tbody");
  if (tbody) {
    tbody.innerHTML = (data.trades || []).slice(0, 100).map((t) => `
      <tr>
        <td>${(t.exit_time || t.entry_time || "").slice(0, 16)}</td>
        <td class="${t.side === "long" ? "positive" : "negative"}">${t.side}</td>
        <td>${fmtPrice(t.entry_price)}</td>
        <td>${fmtPrice(t.exit_price)}</td>
        <td class="${t.pnl >= 0 ? "positive" : "negative"}">${fmtMoney(t.pnl)}</td>
        <td>${t.entry_confidence != null ? Number(t.entry_confidence).toFixed(2) : "—"}</td>
      </tr>`).join("");
  }
}

function renderBacktestResults(result) {
  const el = $("backtestResults");
  if (!el) return;
  const train = result.train || {};
  const test = result.test || result.result || {};
  el.innerHTML = `
    <h3>Backtest Results</h3>
    <div class="results-grid">
      <div><span class="muted">Test Return</span><strong class="${test.total_return_pct >= 0 ? "positive" : "negative"}">${test.total_return_pct}%</strong></div>
      <div><span class="muted">Win Rate</span><strong class="${test.win_rate_pct >= 65 ? "positive" : "negative"}">${test.win_rate_pct}%</strong></div>
      <div><span class="muted">Trades</span><strong>${test.trades ?? test.trades_count ?? "—"}</strong></div>
      <div><span class="muted">Max DD</span><strong class="negative">${test.max_drawdown_pct ?? "—"}%</strong></div>
      <div><span class="muted">Profit Factor</span><strong>${test.profit_factor ?? "—"}</strong></div>
      <div><span class="muted">Sharpe</span><strong>${test.sharpe ?? "—"}</strong></div>
    </div>
    ${train.total_return_pct != null ? `<p class="muted">Train: ${train.total_return_pct}% return · ${train.win_rate_pct}% WR</p>` : ""}
    <p class="muted">Data: ${marketState.source_label || marketState.csv_path || "—"}</p>`;
  switchRightTab("backtest");
}

async function runBacktest() {
  if (!marketState.csv_path) await loadMarket();
  $("liveStatus").textContent = "Running backtest…";
  const result = await api("/api/backtest", {
    method: "POST",
    body: JSON.stringify({
      strategy_id: activeStrategyId,
      csv_path: marketState.csv_path,
      walk_forward: true,
    }),
  });
  renderBacktestResults(result);
  $("liveStatus").textContent = `Backtest: ${(result.test || result).total_return_pct}% return · ${(result.test || result).win_rate_pct}% WR`;
  if (result.orderflow) renderCharts(result.orderflow);
  else {
    const flow = await api(`/api/orderflow?csv_path=${encodeURIComponent(marketState.csv_path)}&window=120`);
    renderCharts(flow);
  }
}

function renderOptimizerStatus(job) {
  const el = $("optimizerStatus");
  if (!el) return;
  const best = job.best || {};
  const gates = job.gates || {};
  el.innerHTML = `
    <h3>AI Optimizer</h3>
    <p>Status: <strong class="${job.status === "running" ? "positive" : ""}">${job.status}</strong> · Iteration ${job.iteration ?? 0}</p>
    <div class="results-grid">
      <div><span class="muted">Rolling Min WR</span><strong class="${(best.rolling_min_win_rate_pct || 0) >= 65 ? "positive" : "negative"}">${best.rolling_min_win_rate_pct ?? "—"}%</strong></div>
      <div><span class="muted">Test WR</span><strong>${best.win_rate_test_pct ?? "—"}%</strong></div>
      <div><span class="muted">Test Return</span><strong>${best.total_return_test_pct ?? "—"}%</strong></div>
      <div><span class="muted">Target WR</span><strong>${gates.min_win_rate ?? 65}%</strong></div>
      <div><span class="muted">Gate Met</span><strong class="${job.gate_met ? "positive" : "negative"}">${job.gate_met ? "Yes" : "No"}</strong></div>
    </div>
    ${job.message ? `<p class="muted">${job.message}</p>` : ""}`;
  switchRightTab("optimizer");
}

async function startOptimizer() {
  if (!marketState.csv_path) await loadMarket();
  const job = await api("/api/optimizer/start", {
    method: "POST",
    body: JSON.stringify({
      csv_path: marketState.csv_path,
      max_iterations: 0,
      gates: { min_win_rate: 65, max_test_drawdown: 10, target_test_return: 0.5, min_test_trades: 20 },
    }),
  });
  optimizerJobId = job.id;
  renderOptimizerStatus(job);
  pollOptimizer();
}

async function pollOptimizer() {
  if (!optimizerJobId) return;
  const job = await api(`/api/optimizer/jobs/${optimizerJobId}`);
  renderOptimizerStatus(job);
  if (job.status === "running") {
    optimizerPollTimer = setTimeout(pollOptimizer, 5000);
  }
}

function switchRightTab(tab) {
  document.querySelectorAll(".right-tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.rtab === tab);
  });
  ["Settings", "Journal", "Backtest", "Optimizer"].forEach((name) => {
    const panel = $(`panel${name}`);
    if (panel) panel.classList.toggle("hidden", tab !== name.toLowerCase());
  });
  if (tab === "journal") loadJournal();
}

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

document.querySelectorAll(".right-tab").forEach((tab) => {
  tab.addEventListener("click", () => switchRightTab(tab.dataset.rtab));
});

document.querySelectorAll(".source-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".source-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    marketState.source = btn.dataset.source;
    $("syncMt5Btn")?.classList.toggle("hidden", marketState.source !== "blackbull");
    scheduleBlackbullRefresh();
    loadMarket().catch((e) => { $("liveStatus").textContent = e.message; });
  });
});

$("btnBookmapToggle")?.addEventListener("click", () => {
  $("bookmapPanel")?.classList.toggle("collapsed");
  $("btnBookmapToggle")?.classList.toggle("active");
});

document.querySelectorAll(".tf").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tf").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    $("strategyTimeframe").value = btn.dataset.tf;
    marketState.timeframe = btn.dataset.tf;
    loadMarket().catch((e) => { $("liveStatus").textContent = e.message; });
  });
});

$("loadMarketBtn")?.addEventListener("click", () => loadMarket().catch((e) => alert(e.message)));
$("syncMt5Btn")?.addEventListener("click", () => syncMt5().catch((e) => alert(e.message)));
$("symbolInput")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadMarket().catch((err) => alert(err.message));
});

$("saveStrategyBtn")?.addEventListener("click", () => saveStrategy().catch((e) => alert(e.message)));
$("runBacktestBtn")?.addEventListener("click", () => runBacktest().catch((e) => alert(e.message)));
$("startOptimizerBtn")?.addEventListener("click", () => startOptimizer().catch((e) => alert(e.message)));
$("startSessionBtn")?.addEventListener("click", () => startSession().catch((e) => alert(e.message)));
$("stopSessionBtn")?.addEventListener("click", () => stopSession().catch((e) => alert(e.message)));
$("newStrategyBtn")?.addEventListener("click", () => {
  activeStrategyId = null;
  fillStrategyForm({ name: "New Strategy", mode: "paper", symbol: marketState.symbol, timeframe: marketState.timeframe, config: {} });
  renderStrategyList();
});

async function init() {
  await loadStrategies();
  await loadSymbols();
  marketState.symbol = ($("symbolInput")?.value || "BTCUSD").toUpperCase();
  marketState.timeframe = document.querySelector(".tf.active")?.dataset.tf || "M5";
  marketState.source = document.querySelector(".source-btn.active")?.dataset.source || "blackbull";
  $("strategySymbol").value = marketState.symbol;
  $("strategyTimeframe").value = marketState.timeframe;
  $("syncMt5Btn")?.classList.toggle("hidden", marketState.source !== "blackbull");
  await updateMt5Status();
  await loadJournal();
  try {
    await loadMarket();
  } catch (_) { /* status line shows setup hint */ }
  scheduleBlackbullRefresh();
  connectBookmapStream();
  const status = await api("/api/session/status");
  if (status.status && status.status !== "idle") {
    updateLiveDashboard(status);
    connectStream();
  }
  try {
    const jobs = await api("/api/optimizer/jobs");
    const running = jobs.find((j) => j.status === "running");
    if (running) {
      optimizerJobId = running.id;
      renderOptimizerStatus(running);
      pollOptimizer();
    }
  } catch (_) { /* ignore */ }
  window.addEventListener("resize", () => { if (lastOrderflow) renderCharts(lastOrderflow); });
}

init().catch((err) => { $("liveStatus").textContent = `Init error: ${err.message}`; });
