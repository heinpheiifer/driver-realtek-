/**
 * Move Bookmap Order Flow from floating overlay → full-width strip below chart.
 */
(function () {
  const MARKER = "data-ot-bookmap-below";
  const STACK_CLASS = "ot-chart-stack";

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
    "canvas#priceChart",
  ];

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
    "[class*='bookmap']",
    "[id*='bookmap']",
  ];

  function firstMatch(selectors, root) {
    for (const sel of selectors) {
      try {
        const el = (root || document).querySelector(sel);
        if (el) return el;
      } catch (_) {
        /* invalid selector */
      }
    }
    return null;
  }

  function findBookmapByText() {
    const nodes = document.querySelectorAll(
      "h1,h2,h3,h4,h5,h6,header,div,section,aside"
    );
    for (const node of nodes) {
      const text = (node.textContent || "").replace(/\s+/g, " ").trim();
      if (!text.includes("Bookmap Order Flow")) continue;
      if (text.length > 120) continue;
      return (
        node.closest(
          "[class*='bookmap'],[id*='bookmap'],[class*='order-flow'],[class*='orderflow'],[class*='panel'],[class*='overlay']"
        ) ||
        node.parentElement?.parentElement ||
        node.parentElement
      );
    }
    return null;
  }

  function findChartBlock() {
    const direct = firstMatch(CHART_SELECTORS);
    if (direct) return direct;

    const lwcCanvas = document.querySelector(
      "canvas, table canvas, .tv-lightweight-charts canvas"
    );
    if (lwcCanvas) {
      let node = lwcCanvas.parentElement;
      for (let i = 0; i < 12 && node; i += 1) {
        const rect = node.getBoundingClientRect();
        if (rect.height >= 240 && rect.width >= 320) return node;
        node = node.parentElement;
      }
    }

    const canvases = [...document.querySelectorAll("canvas")].filter((c) => {
      const r = c.getBoundingClientRect();
      return r.width > 200 && r.height > 150;
    });
    canvases.sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight);
    return canvases[0]?.closest("div, section, main") || null;
  }

  function unfloat(el) {
    el.style.setProperty("position", "static", "important");
    el.style.setProperty("top", "auto", "important");
    el.style.setProperty("right", "auto", "important");
    el.style.setProperty("left", "auto", "important");
    el.style.setProperty("bottom", "auto", "important");
    el.style.setProperty("float", "none", "important");
    el.style.setProperty("transform", "none", "important");
    el.style.setProperty("width", "100%", "important");
    el.style.setProperty("max-width", "none", "important");
    el.style.setProperty("min-width", "0", "important");
    el.style.setProperty("height", "auto", "important");
    el.style.setProperty("max-height", "none", "important");
    el.style.setProperty("margin", "0", "important");
    el.style.setProperty("inset", "auto", "important");
    el.style.setProperty("z-index", "1", "important");
    el.style.setProperty("flex", "0 0 auto", "important");
    el.style.setProperty("order", "2", "important");
    el.setAttribute(MARKER, "1");
  }

  function stackHost(host, chart, bookmap) {
    host.classList.add(STACK_CLASS);
    host.style.setProperty("display", "flex", "important");
    host.style.setProperty("flex-direction", "column", "important");
    host.style.setProperty("align-items", "stretch", "important");
    chart.style.setProperty("order", "1", "important");
    chart.style.setProperty("flex", "1 1 auto", "important");
    chart.style.setProperty("width", "100%", "important");
    chart.style.setProperty("min-height", "45vh", "important");
    if (bookmap.parentElement !== host) host.appendChild(bookmap);
    if (chart.nextElementSibling !== bookmap) {
      chart.insertAdjacentElement("afterend", bookmap);
    }
  }

  function moveBookmapBelowChart() {
    const bookmap =
      firstMatch(BOOKMAP_SELECTORS) || findBookmapByText();
    const chart = findChartBlock();
    if (!bookmap || !chart || bookmap === chart || bookmap.contains(chart)) {
      return false;
    }

    unfloat(bookmap);

    let host =
      chart.parentElement &&
      chart.parentElement !== document.body &&
      !chart.parentElement.matches("body,html,#root")
        ? chart.parentElement
        : null;

    if (host && bookmap.parentElement === host) {
      stackHost(host, chart, bookmap);
      return true;
    }

    const shared =
      chart.parentElement &&
      bookmap.parentElement &&
      chart.parentElement.contains(bookmap)
        ? chart.parentElement
        : bookmap.parentElement?.parentElement || chart.parentElement?.parentElement;

    if (shared) {
      stackHost(shared, chart, bookmap);
      return true;
    }

    const outer = chart.closest("main, section, .main, .workspace, #app, #root > div");
    if (outer) {
      stackHost(outer, chart, bookmap);
      return true;
    }

    return false;
  }

  function run() {
    moveBookmapBelowChart();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }

  window.addEventListener("load", run);
  [300, 800, 2000, 5000].forEach((ms) => setTimeout(run, ms));
  new MutationObserver(run).observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "style"],
  });
})();
