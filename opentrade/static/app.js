const CONFIG_FIELDS = [
  ["risk_per_trade", "Risk Per Trade", 0.0075],
  ["atr_stop_multiplier", "ATR Stop Multiplier", 1.4],
  ["reward_risk", "Reward/Risk", 1.9],
  ["min_confidence", "Min Confidence", 0.35],
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

function renderConfigFields(config = {}) {
  const container = $("configFields");
  container.innerHTML = CONFIG_FIELDS.map(([key, label, fallback]) => {
    const value = config[key] ?? fallback;
    const step = Number.isInteger(fallback) ? 1 : 0.01;
    return `
      <div>
        <label>${label}</label>
        <input data-config-key="${key}" type="number" step="${step}" value="${value}" />
      </div>`;
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
  list.innerHTML = strategies.map((strategy) => `
    <div class="strategy-item ${strategy.id === activeStrategyId ? "active" : ""}" data-id="${strategy.id}">
      <strong>${strategy.name}</strong><br />
      <small>${strategy.symbol} ${strategy.timeframe} · ${strategy.mode}</small>
    </div>
  `).join("");

  list.querySelectorAll(".strategy-item").forEach((item) => {
    item.addEventListener("click", () => {
      activeStrategyId = item.dataset.id;
      const strategy = strategies.find((row) => row.id === activeStrategyId);
      if (strategy) fillStrategyForm(strategy);
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
  const payload = {
    id: activeStrategyId,
    name: $("strategyName").value,
    mode: $("strategyMode").value,
    symbol: $("strategySymbol").value,
    timeframe: $("strategyTimeframe").value,
    config: readConfigFromForm(),
  };
  const saved = await api("/api/strategies", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  activeStrategyId = saved.id;
  await loadStrategies();
  alert("Strategy saved.");
}

function renderMetrics(result) {
  const metrics = [
    ["Return %", result.total_return_pct, true],
    ["Win Rate %", result.win_rate_pct, true],
    ["Max DD %", result.max_drawdown_pct, false],
    ["Trades/Day", result.trades_per_day, true],
    ["Trades", result.trades, true],
    ["Trading Days", result.trading_days, true],
  ];
  $("metrics").innerHTML = metrics.map(([label, value, higherBetter]) => {
    const cls = higherBetter ? (value >= 0 ? "positive" : "negative") : "";
    return `<div class="metric"><div class="label">${label}</div><div class="value ${cls}">${value}</div></div>`;
  }).join("");
}

function drawEquity(curve) {
  const canvas = $("equityChart");
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
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

function renderTrades(trades) {
  $("tradesBody").innerHTML = (trades || []).slice(-20).reverse().map((trade) => `
    <tr>
      <td>${trade.side}</td>
      <td>${trade.entry_time}</td>
      <td>${trade.exit_time}</td>
      <td class="${trade.pnl >= 0 ? "positive" : "negative"}">${trade.pnl}</td>
      <td>${trade.reason}</td>
    </tr>
  `).join("");
}

async function runBacktest() {
  $("backtestStatus").textContent = "Running backtest...";
  const payload = {
    strategy_id: activeStrategyId,
    mode: $("strategyMode").value,
    walk_forward: true,
  };
  const result = await api("/api/backtest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  const test = result.test || result.result;
  $("backtestStatus").textContent = result.walk_forward
    ? `Walk-forward complete. Train return ${result.train.total_return_pct}% · Test return ${test.total_return_pct}%`
    : `Backtest complete. Return ${test.total_return_pct}%`;
  renderMetrics(test);
  drawEquity(test.equity_curve);
  renderTrades(test.trade_rows);
  setActiveTab("backtest");
}

function renderOptimizerMetrics(best) {
  if (!best) {
    $("optimizerMetrics").innerHTML = "";
    return;
  }
  const rows = [
    ["Objective", best.objective],
    ["Test Win Rate %", best.win_rate_test_pct],
    ["Rolling Min Win Rate %", best.rolling_min_win_rate_pct],
    ["Trades/Day (test)", best.trades_per_day_test],
    ["Rolling Trades/Day", best.rolling_trades_per_day],
    ["Test Return %", best.total_return_test_pct],
  ];
  $("optimizerMetrics").innerHTML = rows.map(([label, value]) => `
    <div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>
  `).join("");
}

async function pollOptimizer() {
  if (!optimizerJobId) return;
  const job = await api(`/api/optimizer/jobs/${optimizerJobId}`);
  $("optimizerStatus").textContent =
    `Iteration ${job.iteration} · ${job.message} · status=${job.status}`;
  renderOptimizerMetrics(job.best);
  if (job.status === "running") {
    optimizerPollTimer = setTimeout(pollOptimizer, 3000);
  } else if (job.gate_met) {
    $("optimizerStatus").textContent = "Gate met: strategy reached target win rate and trade frequency.";
  }
}

async function startOptimizer() {
  const payload = {
    max_iterations: 0,
    gates: {
      min_win_rate: parseFloat($("gateWinRate").value),
      min_trades_per_day: parseFloat($("gateMinTpd").value),
      max_trades_per_day: parseFloat($("gateMaxTpd").value),
      max_test_drawdown: parseFloat($("gateMaxDd").value),
      target_test_return: 0.5,
      min_test_trades: 20,
    },
  };
  const job = await api("/api/optimizer/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  optimizerJobId = job.id;
  $("optimizerStatus").textContent = "Optimizer started...";
  setActiveTab("optimizer");
  pollOptimizer();
}

function setActiveTab(tabName) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabName);
  });
  $("settingsTab").classList.toggle("hidden", tabName !== "settings");
  $("backtestTab").classList.toggle("hidden", tabName !== "backtest");
  $("optimizerTab").classList.toggle("hidden", tabName !== "optimizer");
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => setActiveTab(tab.dataset.tab));
});

$("saveStrategyBtn").addEventListener("click", () => saveStrategy().catch((err) => alert(err.message)));
$("runBacktestBtn").addEventListener("click", () => runBacktest().catch((err) => alert(err.message)));
$("startOptimizerBtn").addEventListener("click", () => startOptimizer().catch((err) => alert(err.message)));
$("newStrategyBtn").addEventListener("click", () => {
  activeStrategyId = null;
  fillStrategyForm({
    name: "New Strategy",
    mode: "paper",
    symbol: "EURUSD",
    timeframe: "M1",
    config: {},
  });
  renderStrategyList();
});
$("strategyMode").addEventListener("change", (event) => {
  $("modeBadge").textContent = `${event.target.value} mode`;
});

loadStrategies().catch((err) => {
  $("backtestStatus").textContent = `Failed to load app data: ${err.message}`;
});
