/**
 * Move Bookmap Order Flow below chart — runs a few times then stops (no observer loop).
 */
(function () {
  const MARKER = "data-ot-bookmap-below";
  const STACK_CLASS = "ot-chart-stack";
  const MAX_ATTEMPTS = 25;
  let attempts = 0;
  let done = false;

  const BOOKMAP_SELECTORS = [
    "#bookmapPanel",
    ".bookmap-panel",
    ".bookmap-container",
    ".bookmap-sidebar",
    ".bookmap-overlay",
    ".bookmap-float",
    ".order-flow-panel",
    ".orderflow-panel",
    "#order-flow",
    "#bookmap-order-flow",
  ];

  const CHART_SELECTORS = [
    ".tv-lightweight-charts",
    ".lightweight-charts",
    "#chart-container",
    "#chart",
    "#tv-chart-container",
    "#price-chart",
    "#priceChart",
    ".chart-main",
    ".chart-container",
    ".chart-wrapper",
    ".chart-pane",
  ];

  function firstMatch(selectors) {
    for (const sel of selectors) {
      try {
        const el = document.querySelector(sel);
        if (el) return el;
      } catch (_) {
        /* invalid selector */
      }
    }
    return null;
  }

  function findBookmapByText() {
    const nodes = document.querySelectorAll("h1,h2,h3,h4,h5,h6,header,div,section,aside");
    for (const node of nodes) {
      const text = (node.textContent || "").replace(/\s+/g, " ").trim();
      if (!text.includes("Bookmap Order Flow") || text.length > 120) continue;
      const panel = node.closest(
        ".bookmap-panel,.bookmap-container,.bookmap-overlay,.bookmap-sidebar,.order-flow-panel,#bookmapPanel"
      );
      return panel || node.parentElement?.parentElement || node.parentElement;
    }
    return null;
  }

  function findChartBlock() {
    const direct = firstMatch(CHART_SELECTORS);
    if (direct) return direct;

    const canvas = document.querySelector(
      ".tv-lightweight-charts canvas, table canvas, .lightweight-charts canvas"
    );
    if (canvas) {
      let node = canvas.parentElement;
      for (let i = 0; i < 10 && node; i += 1) {
        const r = node.getBoundingClientRect();
        if (r.height >= 200 && r.width >= 300) return node;
        node = node.parentElement;
      }
    }
    return null;
  }

  function applyLayout(bookmap, chart) {
    bookmap.setAttribute(MARKER, "1");
    bookmap.classList.add("ot-bookmap-below");

    const host =
      chart.parentElement?.contains(bookmap)
        ? chart.parentElement
        : chart.closest("main, section, .chart-area, .workspace, #app") ||
          chart.parentElement;

    if (!host) return false;

    host.classList.add(STACK_CLASS);
    if (bookmap.parentElement !== host) host.appendChild(bookmap);
    if (chart.nextElementSibling !== bookmap) {
      chart.insertAdjacentElement("afterend", bookmap);
    }
    return bookmap.nextElementSibling === null || chart.nextElementSibling === bookmap;
  }

  function tryMove() {
    if (done || attempts >= MAX_ATTEMPTS) return;
    attempts += 1;

    const existing = document.querySelector(`[${MARKER}="1"]`);
    if (existing) {
      done = true;
      return;
    }

    const bookmap = firstMatch(BOOKMAP_SELECTORS) || findBookmapByText();
    const chart = findChartBlock();
    if (!bookmap || !chart || bookmap === chart || bookmap.contains(chart)) return;

    if (applyLayout(bookmap, chart)) done = true;
  }

  function schedule() {
    tryMove();
    if (!done && attempts < MAX_ATTEMPTS) {
      setTimeout(tryMove, 400);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule, { once: true });
  } else {
    schedule();
  }
  window.addEventListener("load", tryMove, { once: true });
})();
