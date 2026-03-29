"use strict";

const STORAGE_KEY = "solar-coc-commissioning-data-v1";
const SCHEMA_VERSION = 2;

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
const pdfBtn = document.getElementById("pdfBtn");
const emailBtn = document.getElementById("emailBtn");
const resetBtn = document.getElementById("resetBtn");

const jobSelect = document.getElementById("jobSelect");
const newJobBtn = document.getElementById("newJobBtn");
const renameJobBtn = document.getElementById("renameJobBtn");
const duplicateJobBtn = document.getElementById("duplicateJobBtn");
const deleteJobBtn = document.getElementById("deleteJobBtn");
const jobMeta = document.getElementById("jobMeta");
const jobEmailTo = document.getElementById("jobEmailTo");
const jobEmailCc = document.getElementById("jobEmailCc");

const signatureCanvas = document.getElementById("signatureCanvas");
const clearSignatureBtn = document.getElementById("clearSignatureBtn");

const db = {
  version: SCHEMA_VERSION,
  activeJobId: null,
  jobs: []
};

let sigCtx = null;
let isDrawing = false;
let lastPoint = null;

function uid(prefix = "id") {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function createBlankStringTest() {
  return {
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
  };
}

function createEmptyJob(title = "") {
  const createdAt = nowIso();
  return {
    id: uid("job"),
    title: title.trim() || "New Job",
    createdAt,
    updatedAt: createdAt,
    fields: {},
    emailTo: "",
    emailCc: "",
    stringTests: [createBlankStringTest()],
    installationPhotos: [],
    electricalPhotos: [],
    signatureDataUrl: ""
  };
}

function normalizePhotoArray(photos) {
  if (!Array.isArray(photos)) return [];
  return photos
    .filter((photo) => photo && typeof photo.dataUrl === "string")
    .map((photo) => ({
      id: photo.id || uid("photo"),
      type: photo.type || "",
      name: photo.name || "",
      size: Number(photo.size || 0),
      mimeType: photo.mimeType || "",
      caption: photo.caption || "",
      dataUrl: photo.dataUrl
    }));
}

function normalizeStringTests(stringTests) {
  if (!Array.isArray(stringTests) || !stringTests.length) {
    return [createBlankStringTest()];
  }
  return stringTests.map((test) => ({
    id: test?.id || uid("string"),
    label: test?.label || "",
    maxVoltage: test?.maxVoltage || "",
    continuity: test?.continuity || "",
    earthContinuity: test?.earthContinuity || "",
    insPlus: test?.insPlus || "",
    insMinus: test?.insMinus || "",
    ocVoltage: test?.ocVoltage || "",
    scCurrent: test?.scCurrent || "",
    opVoltage: test?.opVoltage || "",
    opCurrent: test?.opCurrent || "",
    opPower: test?.opPower || ""
  }));
}

function normalizeJob(rawJob, index = 0) {
  const fallbackTitle = `Job ${index + 1}`;
  const titleFromFields = rawJob?.fields?.jobNumber ? String(rawJob.fields.jobNumber) : "";
  return {
    id: rawJob?.id || uid("job"),
    title: (rawJob?.title || titleFromFields || fallbackTitle).trim(),
    createdAt: rawJob?.createdAt || nowIso(),
    updatedAt: rawJob?.updatedAt || nowIso(),
    fields: rawJob?.fields && typeof rawJob.fields === "object" ? rawJob.fields : {},
    emailTo: typeof rawJob?.emailTo === "string" ? rawJob.emailTo : "",
    emailCc: typeof rawJob?.emailCc === "string" ? rawJob.emailCc : "",
    stringTests: normalizeStringTests(rawJob?.stringTests),
    installationPhotos: normalizePhotoArray(rawJob?.installationPhotos),
    electricalPhotos: normalizePhotoArray(rawJob?.electricalPhotos),
    signatureDataUrl: typeof rawJob?.signatureDataUrl === "string" ? rawJob.signatureDataUrl : ""
  };
}

function normalizeDatabase(rawDb) {
  const jobs = Array.isArray(rawDb?.jobs) ? rawDb.jobs.map((job, index) => normalizeJob(job, index)) : [];
  if (!jobs.length) {
    jobs.push(createEmptyJob("Job 1"));
  }
  let activeJobId = rawDb?.activeJobId;
  if (!jobs.some((job) => job.id === activeJobId)) {
    activeJobId = jobs[0].id;
  }
  return {
    version: SCHEMA_VERSION,
    activeJobId,
    jobs
  };
}

function migrateLegacySingleJob(rawData) {
  const migrated = normalizeJob(
    {
      title: rawData?.fields?.jobNumber || "Migrated Job",
      fields: rawData?.fields || {},
      stringTests: rawData?.stringTests || [],
      installationPhotos: rawData?.installationPhotos || [],
      electricalPhotos: rawData?.electricalPhotos || [],
      signatureDataUrl: rawData?.signatureDataUrl || ""
    },
    0
  );
  return normalizeDatabase({
    jobs: [migrated],
    activeJobId: migrated.id
  });
}

function applyDatabase(nextDb) {
  db.version = SCHEMA_VERSION;
  db.activeJobId = nextDb.activeJobId;
  db.jobs = nextDb.jobs;
}

function saveDatabase() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
}

function getActiveJob() {
  return db.jobs.find((job) => job.id === db.activeJobId) || null;
}

function collectChecklistBooleanKeys() {
  const checkboxElements = form.querySelectorAll("input[type='checkbox'][name]");
  return Array.from(checkboxElements).map((checkbox) => checkbox.name);
}

function serializeForm() {
  const fields = Object.fromEntries(new FormData(form).entries());
  for (const checkboxName of collectChecklistBooleanKeys()) {
    fields[checkboxName] = Boolean(form.elements.namedItem(checkboxName)?.checked);
  }
  return fields;
}

function hydrateForm(fields) {
  form.reset();
  if (!fields || typeof fields !== "object") return;
  Object.entries(fields).forEach(([name, value]) => {
    const input = form.elements.namedItem(name);
    if (!input) return;
    if (input.type === "checkbox") {
      input.checked = value === true || value === "on";
    } else {
      input.value = value ?? "";
    }
  });
}

function persistCurrentJobFromUI(touchUpdated = true) {
  const job = getActiveJob();
  if (!job) return;
  job.fields = serializeForm();
  job.emailTo = (jobEmailTo?.value || "").trim();
  job.emailCc = (jobEmailCc?.value || "").trim();
  if (touchUpdated) {
    job.updatedAt = nowIso();
  }
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(`Unable to read file: ${file.name}`));
    reader.readAsDataURL(file);
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

function renderJobSelect() {
  const activeId = db.activeJobId;
  jobSelect.innerHTML = "";
  db.jobs.forEach((job, index) => {
    const option = document.createElement("option");
    option.value = job.id;
    option.textContent = `${index + 1}. ${job.title}`;
    jobSelect.appendChild(option);
  });
  jobSelect.value = activeId;
}

function updateJobMeta() {
  const job = getActiveJob();
  if (!job) {
    jobMeta.textContent = "";
    return;
  }
  const emailInfo = job.emailTo ? ` | Email To: ${job.emailTo}` : "";
  jobMeta.textContent = `Created: ${new Date(job.createdAt).toLocaleString()} | Updated: ${new Date(job.updatedAt).toLocaleString()} | Strings: ${job.stringTests.length} | Installation photos: ${job.installationPhotos.length} | Electrical photos: ${job.electricalPhotos.length}${emailInfo}`;
}

function renderStringTests() {
  const job = getActiveJob();
  if (!job) return;
  stringTestsContainer.innerHTML = "";
  job.stringTests.forEach((test, idx) => {
    const fragment = stringTemplate.content.cloneNode(true);
    const title = fragment.querySelector(".string-title");
    title.textContent = `String Test ${idx + 1}`;

    const inputs = fragment.querySelectorAll("[data-field]");
    inputs.forEach((input) => {
      const field = input.dataset.field;
      input.value = test[field] ?? "";
      input.addEventListener("input", (event) => {
        job.stringTests[idx][field] = event.target.value;
        job.updatedAt = nowIso();
        saveDatabase();
        updateJobMeta();
      });
    });

    const removeBtn = fragment.querySelector(".remove-string");
    removeBtn.addEventListener("click", () => {
      job.stringTests.splice(idx, 1);
      if (!job.stringTests.length) {
        job.stringTests.push(createBlankStringTest());
      }
      job.updatedAt = nowIso();
      renderStringTests();
      saveDatabase();
      updateJobMeta();
    });

    stringTestsContainer.appendChild(fragment);
  });
}

function addBlankStringTest() {
  const job = getActiveJob();
  if (!job) return;
  job.stringTests.push(createBlankStringTest());
  job.updatedAt = nowIso();
  renderStringTests();
  saveDatabase();
  updateJobMeta();
}

function renderPhotoList(targetEl, photos, type) {
  targetEl.innerHTML = "";
  if (!photos.length) {
    const placeholder = document.createElement("p");
    placeholder.className = "placeholder";
    placeholder.textContent = "No photos added yet.";
    targetEl.appendChild(placeholder);
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
    caption.addEventListener("input", (event) => {
      photos[idx].caption = event.target.value;
      const job = getActiveJob();
      if (!job) return;
      job.updatedAt = nowIso();
      saveDatabase();
      updateJobMeta();
    });
    meta.appendChild(caption);

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "danger";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", () => {
      photos.splice(idx, 1);
      const job = getActiveJob();
      if (!job) return;
      job.updatedAt = nowIso();
      renderPhotoList(targetEl, photos, type);
      saveDatabase();
      updateJobMeta();
    });
    meta.appendChild(removeBtn);

    card.appendChild(meta);
    targetEl.appendChild(card);
  });
}

async function handlePhotoUpload(files, targetArray, targetElement, type) {
  if (!files?.length) return;
  const list = Array.from(files);
  for (const file of list) {
    const dataUrl = await fileToDataUrl(file);
    targetArray.push({
      id: uid("photo"),
      type,
      name: file.name,
      size: file.size,
      mimeType: file.type,
      caption: "",
      dataUrl
    });
  }
  const job = getActiveJob();
  if (!job) return;
  job.updatedAt = nowIso();
  renderPhotoList(targetElement, targetArray, type);
  saveDatabase();
  updateJobMeta();
}

function clearCanvas() {
  if (!sigCtx) return;
  sigCtx.clearRect(0, 0, signatureCanvas.width, signatureCanvas.height);
}

function getCanvasPoint(event) {
  const rect = signatureCanvas.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  };
}

function saveSignatureFromCanvas() {
  const job = getActiveJob();
  if (!job) return;
  job.signatureDataUrl = signatureCanvas.toDataURL("image/png");
  job.updatedAt = nowIso();
  saveDatabase();
  updateJobMeta();
}

function drawSignatureImage(dataUrl) {
  clearCanvas();
  if (!dataUrl) return;
  const image = new Image();
  image.onload = () => {
    const drawWidth = signatureCanvas.clientWidth;
    const drawHeight = signatureCanvas.clientHeight;
    const ratio = Math.min(drawWidth / image.width, drawHeight / image.height);
    const width = image.width * ratio;
    const height = image.height * ratio;
    const x = (drawWidth - width) / 2;
    const y = (drawHeight - height) / 2;
    sigCtx.drawImage(image, x, y, width, height);
  };
  image.src = dataUrl;
}

function resizeSignatureCanvas(redraw = true) {
  if (!signatureCanvas) return;
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = signatureCanvas.clientWidth || 760;
  const cssHeight = 220;
  signatureCanvas.width = Math.floor(cssWidth * dpr);
  signatureCanvas.height = Math.floor(cssHeight * dpr);
  sigCtx = signatureCanvas.getContext("2d");
  sigCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  sigCtx.lineCap = "round";
  sigCtx.lineJoin = "round";
  sigCtx.lineWidth = 2;
  sigCtx.strokeStyle = "#0f172a";
  clearCanvas();
  if (!redraw) return;
  const job = getActiveJob();
  if (job?.signatureDataUrl) {
    drawSignatureImage(job.signatureDataUrl);
  }
}

function setupSignaturePad() {
  if (!signatureCanvas) return;
  resizeSignatureCanvas(false);

  signatureCanvas.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    isDrawing = true;
    signatureCanvas.setPointerCapture(event.pointerId);
    lastPoint = getCanvasPoint(event);
  });

  signatureCanvas.addEventListener("pointermove", (event) => {
    if (!isDrawing) return;
    event.preventDefault();
    const point = getCanvasPoint(event);
    sigCtx.beginPath();
    sigCtx.moveTo(lastPoint.x, lastPoint.y);
    sigCtx.lineTo(point.x, point.y);
    sigCtx.stroke();
    lastPoint = point;
  });

  const finishStroke = (event) => {
    if (!isDrawing) return;
    event.preventDefault();
    isDrawing = false;
    saveSignatureFromCanvas();
  };

  signatureCanvas.addEventListener("pointerup", finishStroke);
  signatureCanvas.addEventListener("pointerleave", finishStroke);
  signatureCanvas.addEventListener("pointercancel", finishStroke);

  window.addEventListener("resize", () => resizeSignatureCanvas(true));
}

function clearSignature() {
  const job = getActiveJob();
  if (!job) return;
  clearCanvas();
  job.signatureDataUrl = "";
  job.updatedAt = nowIso();
  saveDatabase();
  updateJobMeta();
}

function loadActiveJobIntoUI() {
  const job = getActiveJob();
  if (!job) return;
  hydrateForm(job.fields);
  if (jobEmailTo) jobEmailTo.value = job.emailTo || "";
  if (jobEmailCc) jobEmailCc.value = job.emailCc || "";
  renderStringTests();
  renderPhotoList(installationPhotoList, job.installationPhotos, "installation");
  renderPhotoList(electricalPhotoList, job.electricalPhotos, "electrical");
  resizeSignatureCanvas(false);
  if (job.signatureDataUrl) {
    drawSignatureImage(job.signatureDataUrl);
  } else {
    clearCanvas();
  }
  renderJobSelect();
  updateJobMeta();
}

function setActiveJob(jobId) {
  if (jobId === db.activeJobId) return;
  persistCurrentJobFromUI();
  db.activeJobId = jobId;
  saveDatabase();
  loadActiveJobIntoUI();
}

function createNewJob() {
  persistCurrentJobFromUI();
  const name = prompt("Enter a name for the new job:", `Job ${db.jobs.length + 1}`);
  if (name === null) return;
  const job = createEmptyJob(name);
  db.jobs.push(job);
  db.activeJobId = job.id;
  saveDatabase();
  loadActiveJobIntoUI();
}

function renameCurrentJob() {
  const job = getActiveJob();
  if (!job) return;
  const name = prompt("Rename current job:", job.title);
  if (name === null) return;
  job.title = name.trim() || job.title;
  job.updatedAt = nowIso();
  saveDatabase();
  renderJobSelect();
  updateJobMeta();
}

function duplicateCurrentJob() {
  const job = getActiveJob();
  if (!job) return;
  persistCurrentJobFromUI();
  const copy = normalizeJob(deepClone(job), db.jobs.length);
  copy.id = uid("job");
  copy.title = `${job.title} (Copy)`;
  copy.createdAt = nowIso();
  copy.updatedAt = nowIso();
  db.jobs.push(copy);
  db.activeJobId = copy.id;
  saveDatabase();
  loadActiveJobIntoUI();
}

function deleteCurrentJob() {
  if (db.jobs.length <= 1) {
    alert("At least one job must exist.");
    return;
  }
  const job = getActiveJob();
  if (!job) return;
  const confirmed = confirm(`Delete job "${job.title}"? This cannot be undone.`);
  if (!confirmed) return;
  const index = db.jobs.findIndex((item) => item.id === job.id);
  db.jobs.splice(index, 1);
  db.activeJobId = db.jobs[Math.max(0, index - 1)].id;
  saveDatabase();
  loadActiveJobIntoUI();
}

function resetCurrentJob() {
  const job = getActiveJob();
  if (!job) return;
  const confirmed = confirm("Reset all fields, tests, photos, and signature for the current job?");
  if (!confirmed) return;
  job.fields = {};
  job.stringTests = [createBlankStringTest()];
  job.installationPhotos = [];
  job.electricalPhotos = [];
  job.signatureDataUrl = "";
  job.updatedAt = nowIso();
  saveDatabase();
  loadActiveJobIntoUI();
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

function renderStringTestsForPrint(stringTests) {
  if (!stringTests.length) return "<p>No PV string tests recorded.</p>";
  return stringTests
    .map((test, index) => {
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
        .map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`)
        .join("");
      return `<section class="print-subsection"><h4>String ${index + 1}</h4><table class="print-table">${rows}</table></section>`;
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

function buildReportData() {
  persistCurrentJobFromUI();
  const job = getActiveJob();
  if (!job) return null;
  return {
    title: job.title,
    emailTo: job.emailTo || "",
    emailCc: job.emailCc || "",
    fields: job.fields,
    stringTests: job.stringTests,
    installationPhotos: job.installationPhotos,
    electricalPhotos: job.electricalPhotos,
    signatureDataUrl: job.signatureDataUrl
  };
}

function buildEmailBody(report) {
  const lines = [
    "Hello,",
    "",
    "Please find the Solar COC & Commissioning report summary below.",
    "",
    `Job: ${report.title || ""}`,
    `Job Number: ${report.fields.jobNumber || ""}`,
    `Installation Address: ${report.fields.installationAddress || ""}`,
    `Installation Date: ${report.fields.installDate || ""}`,
    `Customer: ${report.fields.customerName || ""}`,
    `Worker: ${report.fields.workerName || ""}`,
    "",
    `PV Strings Recorded: ${report.stringTests.length}`,
    `Installation Photos: ${report.installationPhotos.length}`,
    `Electrical Test Photos: ${report.electricalPhotos.length}`,
    "",
    "Please attach the generated PDF report from the app to this email before sending.",
    "",
    "Regards"
  ];
  return lines.join("\n");
}

function openEmailReportDraft() {
  const report = buildReportData();
  if (!report) return;
  saveDatabase();
  updateJobMeta();

  const to = encodeURIComponent(report.emailTo || "");
  const cc = encodeURIComponent(report.emailCc || "");
  const subject = encodeURIComponent(
    `Solar COC Report - ${report.fields.jobNumber || report.title || "Solar Job"}`
  );
  const body = encodeURIComponent(buildEmailBody(report));
  const mailto = `mailto:${to}?cc=${cc}&subject=${subject}&body=${body}`;
  window.location.href = mailto;
}

function printReport() {
  const report = buildReportData();
  if (!report) return;
  saveDatabase();
  updateJobMeta();

  const acRows = [
    ["Grid Code", report.fields.gridCode],
    ["10 min OVP Setting (V)", report.fields.ovpSettingV],
    ["AC Open Circuit Voltage (V)", report.fields.acOpenVoltage],
    ["Earth Continuity (Ohm)", report.fields.acEarthContinuity],
    ["Loop Impedance Zs (Ohm)", report.fields.acLoopImpedance],
    ["PFC (kA)", report.fields.acPfc],
    ["Bonding (Ohm)", report.fields.acBonding],
    ["AC Insulation (MOhm)", report.fields.acInsulationMOhm]
  ]
    .map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");

  const signatureHtml = report.signatureDataUrl
    ? `<p><strong>Drawn Signature:</strong></p><p><img src="${report.signatureDataUrl}" alt="Drawn signature" style="max-width: 320px; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px;" /></p>`
    : "<p><strong>Drawn Signature:</strong> Not provided</p>";

  const html = `
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
        <p><strong>Dashboard Job:</strong> ${escapeHtml(report.title)}</p>
        <p>Generated: ${new Date().toLocaleString()}</p>
        <section><h2>Project Summary</h2>${buildSummaryTable(report.fields)}</section>
        <section>
          <h2>Certification Checklist</h2>
          ${renderChecklistForPrint(report.fields)}
          <p><strong>Certification Notes:</strong> ${escapeHtml(report.fields.certificationNotes)}</p>
          <p><strong>System Description:</strong> ${escapeHtml(report.fields.systemDescription)}</p>
        </section>
        <section><h2>PV String Tests</h2>${renderStringTestsForPrint(report.stringTests)}</section>
        <section>
          <h2>Inverter Settings & AC Tests</h2>
          <table class="print-table">${acRows}</table>
          <p><strong>Settings Notes:</strong> ${escapeHtml(report.fields.inverterSettingsNotes)}</p>
        </section>
        ${renderPhotosForPrint(report.installationPhotos, "Installation Photos")}
        ${renderPhotosForPrint(report.electricalPhotos, "Electrical Test Photos")}
        <section>
          <h2>Final Declaration</h2>
          <table class="print-table">
            <tr><th>Responsible Person</th><td>${escapeHtml(report.fields.declarationName)}</td></tr>
            <tr><th>Licence Number</th><td>${escapeHtml(report.fields.declarationLicense)}</td></tr>
            <tr><th>Signature (typed)</th><td>${escapeHtml(report.fields.declarationSignature)}</td></tr>
            <tr><th>Date</th><td>${escapeHtml(report.fields.declarationDate)}</td></tr>
          </table>
          ${signatureHtml}
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
  printWindow.document.write(html);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

function detectImageFormat(dataUrl) {
  if (dataUrl.startsWith("data:image/png")) return "PNG";
  if (dataUrl.startsWith("data:image/webp")) return "WEBP";
  return "JPEG";
}

function getImageDimensions(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ width: img.width, height: img.height });
    img.onerror = () => reject(new Error("Image load failed"));
    img.src = dataUrl;
  });
}

async function exportPdf() {
  const report = buildReportData();
  if (!report) return;
  saveDatabase();
  updateJobMeta();

  const jsPdfNs = window.jspdf;
  if (!jsPdfNs?.jsPDF) {
    alert("PDF library failed to load. Check internet connectivity and retry.");
    return;
  }

  const doc = new jsPdfNs.jsPDF({ unit: "pt", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 40;
  const contentWidth = pageWidth - margin * 2;
  const lineHeight = 14;
  let y = margin;

  const ensureSpace = (height) => {
    if (y + height <= pageHeight - margin) return;
    doc.addPage();
    y = margin;
  };

  const addHeading = (text, size = 15) => {
    ensureSpace(size + 8);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(size);
    doc.text(String(text), margin, y);
    y += size + 6;
  };

  const addLine = (text, size = 10, style = "normal") => {
    doc.setFont("helvetica", style);
    doc.setFontSize(size);
    const lines = doc.splitTextToSize(String(text || ""), contentWidth);
    const blockHeight = lines.length * lineHeight + 2;
    ensureSpace(blockHeight);
    doc.text(lines, margin, y);
    y += blockHeight;
  };

  const addKeyValue = (label, value) => addLine(`${label}: ${value || ""}`, 10, "normal");

  const addSpacer = (space = 6) => {
    y += space;
  };

  addHeading("Electrical COC & Commissioning Report", 18);
  addLine(`Dashboard Job: ${report.title}`, 10, "normal");
  addLine(`Generated: ${new Date().toLocaleString()}`, 10, "normal");
  addSpacer(6);

  addHeading("Project Summary");
  [
    ["Job Number", report.fields.jobNumber],
    ["Installation Date", report.fields.installDate],
    ["Installation Address", report.fields.installationAddress],
    ["Customer Name", report.fields.customerName],
    ["Customer Phone", report.fields.customerPhone],
    ["Customer Email", report.fields.customerEmail],
    ["Worker Name", report.fields.workerName],
    ["Licence", report.fields.workerLicense],
    ["Organisation", report.fields.workerOrg],
    ["Work Type", report.fields.workType],
    ["Risk Type", report.fields.riskType],
    ["Date of Connection", report.fields.connectionDate],
    ["Panel Manufacturer", report.fields.panelManufacturer],
    ["Panel Model", report.fields.panelModel],
    ["Number of Panels", report.fields.panelCount],
    ["Number of Strings", report.fields.stringCount],
    ["Inverter Manufacturer", report.fields.inverterManufacturer],
    ["Inverter Model", report.fields.inverterModel],
    ["Battery Model", report.fields.batteryModel],
    ["Export Limitation (W)", report.fields.exportLimitW]
  ].forEach(([label, value]) => addKeyValue(label, value));
  addSpacer();

  addHeading("Certification Checklist");
  const checklistItems = [
    ["checkCertifiedDesign", "Installed in accordance with certified design"],
    ["checkStandards", "Installed in accordance with applicable standards"],
    ["checkEarthing", "Earthing system correctly rated"],
    ["checkSafeFittings", "Fittings safe to connect to supply"],
    ["checkSupplierDoc", "Relies on supplier declaration of conformity"],
    ["checkManufacturerDoc", "Relies on manufacturer instructions"],
    ["checkTested", "Satisfactorily tested in accordance with regulations"],
    ["checkSafeConnect", "Safe to connect and safe to use"]
  ];
  checklistItems.forEach(([key, label]) => addLine(`${report.fields[key] ? "YES" : "NO"} - ${label}`, 10, "normal"));
  addLine(`Certification Notes: ${report.fields.certificationNotes || ""}`, 10, "normal");
  addLine(`System Description: ${report.fields.systemDescription || ""}`, 10, "normal");
  addSpacer();

  addHeading("PV String Tests");
  report.stringTests.forEach((test, index) => {
    addLine(`String ${index + 1}`, 11, "bold");
    [
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
    ].forEach(([label, value]) => addKeyValue(label, value));
    addSpacer();
  });

  addHeading("Inverter Settings & AC Tests");
  [
    ["Grid Code", report.fields.gridCode],
    ["10 min OVP Setting (V)", report.fields.ovpSettingV],
    ["AC Open Circuit Voltage (V)", report.fields.acOpenVoltage],
    ["Earth Continuity (Ohm)", report.fields.acEarthContinuity],
    ["Loop Impedance Zs (Ohm)", report.fields.acLoopImpedance],
    ["PFC (kA)", report.fields.acPfc],
    ["Bonding (Ohm)", report.fields.acBonding],
    ["AC Insulation (MOhm)", report.fields.acInsulationMOhm]
  ].forEach(([label, value]) => addKeyValue(label, value));
  addLine(`Settings Notes: ${report.fields.inverterSettingsNotes || ""}`, 10, "normal");
  addSpacer();

  const addPhotoSection = async (heading, photos) => {
    addHeading(heading);
    if (!photos.length) {
      addLine("No photos attached.", 10, "normal");
      addSpacer();
      return;
    }
    for (let index = 0; index < photos.length; index += 1) {
      const photo = photos[index];
      const caption = photo.caption || photo.name || `Photo ${index + 1}`;
      addLine(caption, 10, "bold");

      try {
        const dimensions = await getImageDimensions(photo.dataUrl);
        const maxWidth = contentWidth;
        const maxHeight = 210;
        const ratio = Math.min(maxWidth / dimensions.width, maxHeight / dimensions.height, 1);
        const width = dimensions.width * ratio;
        const height = dimensions.height * ratio;
        ensureSpace(height + 8);
        doc.addImage(photo.dataUrl, detectImageFormat(photo.dataUrl), margin, y, width, height);
        y += height + 8;
      } catch {
        addLine("[Could not render image]", 10, "normal");
      }
    }
    addSpacer();
  };

  await addPhotoSection("Installation Photos", report.installationPhotos);
  await addPhotoSection("Electrical Test Photos", report.electricalPhotos);

  addHeading("Final Declaration");
  addKeyValue("Responsible Person", report.fields.declarationName);
  addKeyValue("Licence Number", report.fields.declarationLicense);
  addKeyValue("Signature (typed)", report.fields.declarationSignature);
  addKeyValue("Date", report.fields.declarationDate);

  if (report.signatureDataUrl) {
    addLine("Drawn Signature:", 10, "bold");
    try {
      const dimensions = await getImageDimensions(report.signatureDataUrl);
      const maxWidth = Math.min(320, contentWidth);
      const maxHeight = 120;
      const ratio = Math.min(maxWidth / dimensions.width, maxHeight / dimensions.height, 1);
      const width = dimensions.width * ratio;
      const height = dimensions.height * ratio;
      ensureSpace(height + 6);
      doc.addImage(report.signatureDataUrl, detectImageFormat(report.signatureDataUrl), margin, y, width, height);
      y += height + 8;
    } catch {
      addLine("[Could not render signature image]", 10, "normal");
    }
  } else {
    addLine("Drawn Signature: Not provided", 10, "normal");
  }

  const jobRef = (report.fields.jobNumber || report.title || "job").toString().trim().replace(/[^a-zA-Z0-9-_]+/g, "-");
  const dateRef = new Date().toISOString().slice(0, 10);
  doc.save(`solar-coc-${jobRef}-${dateRef}.pdf`);
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

function appendImportedJobs(importedJobs) {
  const existingIds = new Set(db.jobs.map((job) => job.id));
  const appended = importedJobs.map((job, index) => {
    const copy = normalizeJob(job, index);
    while (existingIds.has(copy.id)) {
      copy.id = uid("job");
    }
    existingIds.add(copy.id);
    return copy;
  });
  db.jobs.push(...appended);
  return appended;
}

async function importJson(file) {
  const text = await file.text();
  const parsed = JSON.parse(text);
  if (!parsed || typeof parsed !== "object") {
    throw new Error("Invalid JSON file.");
  }

  if (Array.isArray(parsed.jobs)) {
    const normalized = normalizeDatabase(parsed);
    const replaceAll = confirm("Replace all existing jobs with imported jobs? Click Cancel to append imported jobs.");
    if (replaceAll) {
      applyDatabase(normalized);
    } else {
      const appended = appendImportedJobs(normalized.jobs);
      if (appended.length) {
        db.activeJobId = appended[0].id;
      }
    }
  } else if (parsed.fields || parsed.stringTests || parsed.installationPhotos || parsed.electricalPhotos) {
    const importedLegacy = migrateLegacySingleJob(parsed);
    const importedJob = normalizeJob(importedLegacy.jobs[0], db.jobs.length);
    importedJob.title = `Imported - ${importedJob.title}`;
    db.jobs.push(importedJob);
    db.activeJobId = importedJob.id;
  } else {
    throw new Error("Unsupported JSON format.");
  }

  saveDatabase();
  loadActiveJobIntoUI();
}

function loadDatabase() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return false;
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed?.jobs)) {
      applyDatabase(normalizeDatabase(parsed));
    } else if (parsed?.fields || parsed?.stringTests || parsed?.installationPhotos || parsed?.electricalPhotos) {
      applyDatabase(migrateLegacySingleJob(parsed));
    } else {
      return false;
    }
    return true;
  } catch (error) {
    console.error(error);
    return false;
  }
}

function wireEvents() {
  addStringBtn.addEventListener("click", addBlankStringTest);

  installationPhotoInput.addEventListener("change", async (event) => {
    const job = getActiveJob();
    if (!job) return;
    await handlePhotoUpload(event.target.files, job.installationPhotos, installationPhotoList, "installation");
    installationPhotoInput.value = "";
  });

  electricalPhotoInput.addEventListener("change", async (event) => {
    const job = getActiveJob();
    if (!job) return;
    await handlePhotoUpload(event.target.files, job.electricalPhotos, electricalPhotoList, "electrical");
    electricalPhotoInput.value = "";
  });

  form.addEventListener("input", () => {
    persistCurrentJobFromUI();
    saveDatabase();
    updateJobMeta();
  });

  saveBtn.addEventListener("click", () => {
    persistCurrentJobFromUI();
    saveDatabase();
    updateJobMeta();
    alert("Draft saved for the current job.");
  });

  jobEmailTo.addEventListener("input", () => {
    persistCurrentJobFromUI();
    saveDatabase();
    updateJobMeta();
  });

  jobEmailCc.addEventListener("input", () => {
    persistCurrentJobFromUI();
    saveDatabase();
    updateJobMeta();
  });

  exportBtn.addEventListener("click", () => {
    persistCurrentJobFromUI();
    saveDatabase();
    const fileName = `solar-coc-jobs-${new Date().toISOString().slice(0, 10)}.json`;
    downloadJson(fileName, db);
  });

  importInput.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      await importJson(file);
      alert("JSON imported.");
    } catch (error) {
      alert(`Import failed: ${error.message}`);
    } finally {
      importInput.value = "";
    }
  });

  printBtn.addEventListener("click", printReport);
  pdfBtn.addEventListener("click", async () => {
    try {
      await exportPdf();
    } catch (error) {
      console.error(error);
      alert(`PDF export failed: ${error.message}`);
    }
  });
  emailBtn.addEventListener("click", openEmailReportDraft);

  resetBtn.addEventListener("click", resetCurrentJob);

  jobSelect.addEventListener("change", (event) => setActiveJob(event.target.value));
  newJobBtn.addEventListener("click", createNewJob);
  renameJobBtn.addEventListener("click", renameCurrentJob);
  duplicateJobBtn.addEventListener("click", duplicateCurrentJob);
  deleteJobBtn.addEventListener("click", deleteCurrentJob);
  clearSignatureBtn.addEventListener("click", clearSignature);
}

function init() {
  setupSignaturePad();
  const loaded = loadDatabase();
  if (!loaded) {
    const firstJob = createEmptyJob("Job 1");
    db.jobs = [firstJob];
    db.activeJobId = firstJob.id;
    saveDatabase();
  }
  loadActiveJobIntoUI();
  wireEvents();
}

init();
