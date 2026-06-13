/**
 * Move Bookmap Order Flow DOM node directly under the chart (fallback if CSS alone is not enough).
 */
(function () {
  const CHART_SELECTORS = [
    ".chart-main",
    "#chart-container",
    "#chart",
    "#tv-chart-container",
    "#price-chart",
    "#priceChart",
    ".chart-container",
    ".lightweight-charts",
    "canvas#priceChart",
  ];

  const BOOKMAP_SELECTORS = [
    "#bookmapPanel",
    ".bookmap-panel",
    ".bookmap-container",
    ".bookmap-sidebar",
    ".order-flow-panel",
    "#order-flow",
    "#bookmap-order-flow",
    "[class*='bookmap']",
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

  function moveBookmapBelowChart() {
    const chart =
      firstMatch(CHART_SELECTORS) ||
      document.querySelector("canvas")?.closest("div, section, main");
    const bookmap = firstMatch(BOOKMAP_SELECTORS);

    if (!chart || !bookmap || chart === bookmap) return false;

    const parent = chart.parentElement;
    if (!parent || bookmap.parentElement !== parent) {
      const host = chart.parentElement?.parentElement || chart.parentElement;
      if (host && bookmap.parentElement !== host) {
        host.appendChild(bookmap);
      }
    }

    if (chart.nextElementSibling !== bookmap) {
      chart.insertAdjacentElement("afterend", bookmap);
    }
    return true;
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
  setTimeout(run, 500);
  setTimeout(run, 2000);
  new MutationObserver(run).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
