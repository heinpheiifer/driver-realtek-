"use strict";

const STORAGE_KEY = "solar-coc-commissioning-data-v1";
const form = document.getElementById("cocForm");
const stringTestsContainer = document.getElementById("stringTestsContainer");
const stringTemplate = document.getElementById("stringTestTemplate");
const addStringBtn = document.getElementById("addStringBtn");
const installationPhotoInput = document.getElementById("installationPhotoInput");
const electricalPhotoInput = document.getElementById("electricalPhotoInput");
const installationPhotoList = document.getElementById("installationPhotoList");
const electricalPhotoList = document.getElementById("electricalPhotoList");

const saveBtn = document.getElementById("saveBtn");
const exportBtn = document.getElementById("exportBtn");
const importInput = document.getElementById("importInput");
const printBtn = document.getElementById("printBtn");
const resetBtn = document.getElementById("resetBtn");

const appState = {
  stringTests: [],
  installationPhotos: [],
  electricalPhotos: []
};

function uid(prefix = "id") {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(`Unable to read file: ${file.name}`));
    reader.readAsDataURL(file);
  });
}

function serializeForm() {
  const raw = Object.fromEntries(new FormData(form).entries());
  return raw;
}

function hydrateForm(data) {
  if (!data || typeof data !== "object") return;
  Object.entries(data).forEach(([name, value]) => {
    const input = form.elements.namedItem(name);
    if (!input) return;
    if (input.type === "checkbox") {
      input.checked = value === true || value === "on";
    } else {
      input.value = value ?? "";
    }
  });
}

function collectChecklistBooleanKeys() {
  const checkboxElements = form.querySelectorAll("input[type='checkbox'][name]");
  return Array.from(checkboxElements).map((checkbox) => checkbox.name);
}

function serializeState() {
  const fields = serializeForm();
  for (const checkboxName of collectChecklistBooleanKeys()) {
    fields[checkboxName] = Boolean(form.elements.namedItem(checkboxName)?.checked);
  }

  return {
    version: 1,
    savedAt: new Date().toISOString(),
    fields,
    stringTests: appState.stringTests,
    installationPhotos: appState.installationPhotos,
    electricalPhotos: appState.electricalPhotos
  };
}

function saveToLocalStorage() {
  const payload = serializeState();
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function renderStringTests() {
  stringTestsContainer.innerHTML = "";
  appState.stringTests.forEach((test, idx) => {
    const fragment = stringTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".string-card");
    const title = fragment.querySelector(".string-title");
    title.textContent = `String Test ${idx + 1}`;

    const inputs = fragment.querySelectorAll("[data-field]");
    inputs.forEach((input) => {
      const field = input.dataset.field;
      input.value = test[field] ?? "";
      input.addEventListener("input", (e) => {
        appState.stringTests[idx][field] = e.target.value;
      });
    });

    const removeBtn = fragment.querySelector(".remove-string");
    removeBtn.addEventListener("click", () => {
      appState.stringTests.splice(idx, 1);
      renderStringTests();
      saveToLocalStorage();
    });

    card.dataset.id = test.id;
    stringTestsContainer.appendChild(fragment);
  });
}

function addBlankStringTest() {
  appState.stringTests.push({
    id: uid("string"),
    label: "",
    maxVoltage: "",
    continuity: "",
    earthContinuity: "",
    insPlus: "",
    insMinus: "",
    ocVoltage: "",
    scCurrent: "",
    opVoltage: "",
    opCurrent: "",
    opPower: ""
  });
  renderStringTests();
}

function renderPhotoList(targetEl, photos, type) {
  targetEl.innerHTML = "";
  if (!photos.length) {
    const p = document.createElement("p");
    p.className = "placeholder";
    p.textContent = "No photos added yet.";
    targetEl.appendChild(p);
    return;
  }

  photos.forEach((photo, idx) => {
    const card = document.createElement("article");
    card.className = "photo-item";

    const img = document.createElement("img");
    img.src = photo.dataUrl;
    img.alt = photo.caption || photo.name || `${type} photo`;
    card.appendChild(img);

    const meta = document.createElement("div");
    meta.className = "photo-meta";

    const name = document.createElement("p");
    name.className = "photo-name";
    name.textContent = photo.name || `Photo ${idx + 1}`;
    meta.appendChild(name);

    const caption = document.createElement("textarea");
    caption.rows = 2;
    caption.placeholder = "Add caption / test detail";
    caption.value = photo.caption || "";
    caption.addEventListener("input", (e) => {
      photos[idx].caption = e.target.value;
    });
    meta.appendChild(caption);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "danger";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", () => {
      photos.splice(idx, 1);
      renderPhotoList(targetEl, photos, type);
      saveToLocalStorage();
    });
    meta.appendChild(removeBtn);
    card.appendChild(meta);
    targetEl.appendChild(card);
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function handlePhotoUpload(files, photoArray, targetEl, type) {
  if (!files?.length) return;
  const list = Array.from(files);
  for (const file of list) {
    const dataUrl = await fileToDataUrl(file);
    photoArray.push({
      id: uid("photo"),
      type,
      name: file.name,
      size: file.size,
      mimeType: file.type,
      caption: "",
      dataUrl
    });
  }
  renderPhotoList(targetEl, photoArray, type);
  saveToLocalStorage();
}

function buildSummaryTable(fields) {
  const rows = [
    ["Job Number", fields.jobNumber],
    ["Installation Date", fields.installDate],
    ["Installation Address", fields.installationAddress],
    ["Customer Name", fields.customerName],
    ["Customer Phone", fields.customerPhone],
    ["Customer Email", fields.customerEmail],
    ["Worker Name", fields.workerName],
    ["Licence", fields.workerLicense],
    ["Organisation", fields.workerOrg],
    ["Work Type", fields.workType],
    ["Risk Type", fields.riskType],
    ["Date of Connection", fields.connectionDate],
    ["Panel Manufacturer", fields.panelManufacturer],
    ["Panel Model", fields.panelModel],
    ["Number of Panels", fields.panelCount],
    ["Number of Strings", fields.stringCount],
    ["Inverter Manufacturer", fields.inverterManufacturer],
    ["Inverter Model", fields.inverterModel],
    ["Battery Model", fields.batteryModel],
    ["Export Limitation (W)", fields.exportLimitW]
  ];

  const body = rows
    .map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");
  return `<table class="print-table">${body}</table>`;
}

function renderChecklistForPrint(fields) {
  const checklistLabels = {
    checkCertifiedDesign: "Installed in accordance with certified design",
    checkStandards: "Installed in accordance with applicable standards",
    checkEarthing: "Earthing system correctly rated",
    checkSafeFittings: "Fittings safe to connect to supply",
    checkSupplierDoc: "Relies on supplier declaration of conformity",
    checkManufacturerDoc: "Relies on manufacturer instructions",
    checkTested: "Satisfactorily tested in accordance with regulations",
    checkSafeConnect: "Safe to connect and safe to use"
  };

  const items = Object.entries(checklistLabels)
    .map(([key, label]) => `<li>${fields[key] ? "YES" : "NO"} - ${escapeHtml(label)}</li>`)
    .join("");

  return `<ul class="print-list">${items}</ul>`;
}

function renderStringTestsForPrint() {
  if (!appState.stringTests.length) return "<p>No PV string tests recorded.</p>";
  return appState.stringTests
    .map((test, idx) => {
      const rows = [
        ["Label", test.label],
        ["Max Voltage (V)", test.maxVoltage],
        ["Continuity / Polarity", test.continuity],
        ["Earth Continuity (Ohm)", test.earthContinuity],
        ["Insulation + (MOhm)", test.insPlus],
        ["Insulation - (MOhm)", test.insMinus],
        ["Open Circuit Voltage (V)", test.ocVoltage],
        ["Short Circuit Current (A)", test.scCurrent],
        ["Operational Voltage (V)", test.opVoltage],
        ["Operational Current (A)", test.opCurrent],
        ["Operational Power (W)", test.opPower]
      ]
        .map(([label, value]) => `<tr><th>${label}</th><td>${value || ""}</td></tr>`)
        .map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`)
        .join("");
      return `
        <section class="print-subsection">
          <h4>String ${idx + 1}</h4>
          <table class="print-table">${rows}</table>
        </section>
      `;
    })
    .join("");
}

function renderPhotosForPrint(photos, title) {
  if (!photos.length) return `<section><h4>${escapeHtml(title)}</h4><p>No photos attached.</p></section>`;
  const content = photos
    .map(
      (photo) => `
      <figure class="print-photo">
        <img src="${photo.dataUrl}" alt="${escapeHtml(photo.caption || photo.name || "photo")}" />
        <figcaption>${escapeHtml(photo.caption || photo.name || "")}</figcaption>
      </figure>
    `
    )
    .join("");
  return `<section><h4>${escapeHtml(title)}</h4><div class="print-photo-grid">${content}</div></section>`;
}

function printReport() {
  const fields = serializeState().fields;
  const summaryTable = buildSummaryTable(fields);
  const checklist = renderChecklistForPrint(fields);
  const stringTests = renderStringTestsForPrint();

  const acRows = [
    ["Grid Code", fields.gridCode],
    ["10 min OVP Setting (V)", fields.ovpSettingV],
    ["AC Open Circuit Voltage (V)", fields.acOpenVoltage],
    ["Earth Continuity (Ohm)", fields.acEarthContinuity],
    ["Loop Impedance Zs (Ohm)", fields.acLoopImpedance],
    ["PFC (kA)", fields.acPfc],
    ["Bonding (Ohm)", fields.acBonding],
    ["AC Insulation (MOhm)", fields.acInsulationMOhm]
  ]
    .map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");

  const printHtml = `
    <html>
      <head>
        <title>Solar COC & Commissioning Report</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 24px; color: #1e293b; }
          h1, h2, h3, h4 { margin: 0 0 8px; }
          section { margin-bottom: 20px; page-break-inside: avoid; }
          .print-table { width: 100%; border-collapse: collapse; margin-top: 8px; }
          .print-table th, .print-table td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; vertical-align: top; }
          .print-table th { width: 35%; background: #f8fafc; }
          .print-list { margin: 8px 0 0 20px; }
          .print-photo-grid { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
          .print-photo { border: 1px solid #cbd5e1; padding: 8px; margin: 0; }
          .print-photo img { max-width: 100%; max-height: 200px; object-fit: contain; display: block; margin: 0 auto 6px; }
          .print-photo figcaption { font-size: 12px; color: #334155; word-break: break-word; }
        </style>
      </head>
      <body>
        <h1>Electrical COC & Commissioning Report</h1>
        <p>Generated: ${new Date().toLocaleString()}</p>

        <section>
          <h2>Project Summary</h2>
          ${summaryTable}
        </section>

        <section>
          <h2>Certification Checklist</h2>
          ${checklist}
          <p><strong>Certification Notes:</strong> ${escapeHtml(fields.certificationNotes)}</p>
          <p><strong>System Description:</strong> ${escapeHtml(fields.systemDescription)}</p>
        </section>

        <section>
          <h2>PV String Tests</h2>
          ${stringTests}
        </section>

        <section>
          <h2>Inverter Settings & AC Tests</h2>
          <table class="print-table">${acRows}</table>
          <p><strong>Settings Notes:</strong> ${escapeHtml(fields.inverterSettingsNotes)}</p>
        </section>

        ${renderPhotosForPrint(appState.installationPhotos, "Installation Photos")}
        ${renderPhotosForPrint(appState.electricalPhotos, "Electrical Test Photos")}

        <section>
          <h2>Final Declaration</h2>
          <table class="print-table">
            <tr><th>Responsible Person</th><td>${escapeHtml(fields.declarationName)}</td></tr>
            <tr><th>Licence Number</th><td>${escapeHtml(fields.declarationLicense)}</td></tr>
            <tr><th>Signature</th><td>${escapeHtml(fields.declarationSignature)}</td></tr>
            <tr><th>Date</th><td>${escapeHtml(fields.declarationDate)}</td></tr>
          </table>
        </section>
      </body>
    </html>
  `;

  const printWindow = window.open("", "_blank", "noopener,noreferrer");
  if (!printWindow) {
    alert("Pop-up blocked. Please allow pop-ups to print.");
    return;
  }

  printWindow.document.open();
  printWindow.document.write(printHtml);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function importJson(file) {
  const text = await file.text();
  const parsed = JSON.parse(text);
  if (!parsed || typeof parsed !== "object") throw new Error("Invalid JSON file.");

  hydrateForm(parsed.fields || {});
  appState.stringTests = Array.isArray(parsed.stringTests) ? parsed.stringTests : [];
  appState.installationPhotos = Array.isArray(parsed.installationPhotos) ? parsed.installationPhotos : [];
  appState.electricalPhotos = Array.isArray(parsed.electricalPhotos) ? parsed.electricalPhotos : [];

  renderStringTests();
  renderPhotoList(installationPhotoList, appState.installationPhotos, "installation");
  renderPhotoList(electricalPhotoList, appState.electricalPhotos, "electrical");
  saveToLocalStorage();
}

function loadFromLocalStorage() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return false;
  try {
    const parsed = JSON.parse(raw);
    hydrateForm(parsed.fields || {});
    appState.stringTests = Array.isArray(parsed.stringTests) ? parsed.stringTests : [];
    appState.installationPhotos = Array.isArray(parsed.installationPhotos) ? parsed.installationPhotos : [];
    appState.electricalPhotos = Array.isArray(parsed.electricalPhotos) ? parsed.electricalPhotos : [];
    renderStringTests();
    renderPhotoList(installationPhotoList, appState.installationPhotos, "installation");
    renderPhotoList(electricalPhotoList, appState.electricalPhotos, "electrical");
    return true;
  } catch (err) {
    console.error(err);
    return false;
  }
}

function resetAll() {
  const confirmed = confirm("This will clear all entered data and photos. Continue?");
  if (!confirmed) return;
  form.reset();
  appState.stringTests = [];
  appState.installationPhotos = [];
  appState.electricalPhotos = [];
  renderStringTests();
  renderPhotoList(installationPhotoList, appState.installationPhotos, "installation");
  renderPhotoList(electricalPhotoList, appState.electricalPhotos, "electrical");
  localStorage.removeItem(STORAGE_KEY);
}

function wireEvents() {
  addStringBtn.addEventListener("click", () => {
    addBlankStringTest();
    saveToLocalStorage();
  });

  installationPhotoInput.addEventListener("change", async (e) => {
    await handlePhotoUpload(e.target.files, appState.installationPhotos, installationPhotoList, "installation");
    installationPhotoInput.value = "";
  });

  electricalPhotoInput.addEventListener("change", async (e) => {
    await handlePhotoUpload(e.target.files, appState.electricalPhotos, electricalPhotoList, "electrical");
    electricalPhotoInput.value = "";
  });

  form.addEventListener("input", () => saveToLocalStorage());
  saveBtn.addEventListener("click", () => {
    saveToLocalStorage();
    alert("Draft saved locally.");
  });

  exportBtn.addEventListener("click", () => {
    const fileName = `solar-coc-${new Date().toISOString().slice(0, 10)}.json`;
    downloadJson(fileName, serializeState());
  });

  importInput.addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await importJson(file);
      alert("JSON imported.");
    } catch (err) {
      alert(`Import failed: ${err.message}`);
    } finally {
      importInput.value = "";
    }
  });

  printBtn.addEventListener("click", printReport);
  resetBtn.addEventListener("click", resetAll);
}

function init() {
  const loaded = loadFromLocalStorage();
  if (!loaded) {
    addBlankStringTest();
    renderPhotoList(installationPhotoList, appState.installationPhotos, "installation");
    renderPhotoList(electricalPhotoList, appState.electricalPhotos, "electrical");
  }
  wireEvents();
}

init();
