const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");
const statsEl = document.getElementById("stats");

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    statsEl.textContent = `${data.pages.toLocaleString()} pages indexed · ${data.domains.toLocaleString()} domains · ${data.queued.toLocaleString()} in crawl queue`;
  } catch {
    statsEl.textContent = "";
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

async function runSearch(q) {
  statusEl.textContent = "Searching…";
  resultsEl.innerHTML = "";

  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=25`);
    if (!res.ok) throw new Error("Search failed");
    const data = await res.json();

    if (data.results.length === 0) {
      statusEl.textContent = `No results for “${q}”. Try crawling more pages or different keywords.`;
      return;
    }

    statusEl.textContent = `${data.total} result${data.total === 1 ? "" : "s"}`;
    resultsEl.innerHTML = data.results
      .map(
        (hit) => `
      <li class="result-item">
        <p class="result-title"><a href="${escapeHtml(hit.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(hit.title)}</a></p>
        <p class="result-url">${escapeHtml(hit.url)}</p>
        <p class="result-snippet">${hit.snippet || ""}</p>
      </li>`
      )
      .join("");
  } catch (err) {
    statusEl.textContent = "Could not reach the search server. Is api.py running?";
    console.error(err);
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = queryInput.value.trim();
  if (q) {
    runSearch(q);
    history.replaceState(null, "", `?q=${encodeURIComponent(q)}`);
  }
});

const params = new URLSearchParams(window.location.search);
const initialQ = params.get("q");
if (initialQ) {
  queryInput.value = initialQ;
  runSearch(initialQ);
}

loadStats();
