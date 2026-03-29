"use strict";

const STORAGE_KEY = "solar-electrix-coc-draft-v2";
const VERIFICATION_ITEMS = [
  "Isolation completed and safe to proceed",
  "Polarity verified",
  "Earthing/bonding continuity verified",
  "Protection devices correct and operational",
  "RCD/RCBO testing completed (where applicable)",
  "PV labelling/signage completed (where applicable)",
  "Final verification records completed"
];

const verificationContainer = document.getElementById("verificationContainer");
const saveDraftBtn = document.getElementById("saveDraftBtn");
const clearDraftBtn = document.getElementById("clearDraftBtn");
const generatePdfBtn = document.getElementById("generatePdfBtn");
const logoImg = document.querySelector(".company-logo");

init();

function init() {
  renderVerificationChecklist();
  setDefaultValues();
  wireEvents();
  loadDraft();
}

function wireEvents() {
  saveDraftBtn.addEventListener("click", saveDraft);
  clearDraftBtn.addEventListener("click", clearDraft);
  generatePdfBtn.addEventListener("click", generatePdf);
}

function renderVerificationChecklist() {
  verificationContainer.innerHTML = "";
  VERIFICATION_ITEMS.forEach((item, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "verify-item";

    const text = document.createElement("div");
    text.className = "verify-text";
    text.textContent = item;
    wrapper.appendChild(text);

    const key = `verify_${index}`;
    const options = document.createElement("div");
    options.className = "radio-row";
    ["Pass", "Fail", "N/A"].forEach((label) => {
      const optionLabel = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = key;
      input.value = label;
      optionLabel.appendChild(input);
      optionLabel.append(label);
      options.appendChild(optionLabel);
    });
    wrapper.appendChild(options);

    const note = document.createElement("input");
    note.type = "text";
    note.placeholder = "Optional note";
    note.dataset.verifyNoteKey = key;
    wrapper.appendChild(note);

    verificationContainer.appendChild(wrapper);
  });
}

function setDefaultValues() {
  const today = new Date().toISOString().slice(0, 10);
  setIfEmpty("completionDate", today);
  setIfEmpty("declarationDate", today);
  setIfEmpty("businessName", "Solar Electrix");
  setIfEmpty("declaredBy", "Hein Pheiffer");
}

function setIfEmpty(id, value) {
  const el = document.getElementById(id);
  if (el && !el.value) el.value = value;
}

function getFormSnapshot() {
  const fields = [
    "businessName",
    "electricianName",
    "licenceNumber",
    "electricianPhone",
    "clientName",
    "jobNumber",
    "siteAddress",
    "completionDate",
    "workType",
    "supplyType",
    "workDescription",
    "standardsUsed",
    "declarationText",
    "declaredBy",
    "declarationDate"
  ];

  const values = {};
  fields.forEach((id) => {
    values[id] = document.getElementById(id)?.value || "";
  });

  const verification = {};
  VERIFICATION_ITEMS.forEach((_, index) => {
    const key = `verify_${index}`;
    const selected = document.querySelector(`input[name="${key}"]:checked`);
    const note = document.querySelector(`input[data-verify-note-key="${key}"]`)?.value || "";
    verification[key] = {
      result: selected ? selected.value : "",
      note: note.trim()
    };
  });

  return { values, verification };
}

function applySnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;

  Object.entries(snapshot.values || {}).forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (el) el.value = value;
  });

  Object.entries(snapshot.verification || {}).forEach(([key, data]) => {
    if (!data || typeof data !== "object") return;
    if (data.result) {
      const radio = document.querySelector(
        `input[name="${key}"][value="${CSS.escape(data.result)}"]`
      );
      if (radio) radio.checked = true;
    }
    const noteInput = document.querySelector(`input[data-verify-note-key="${key}"]`);
    if (noteInput) noteInput.value = data.note || "";
  });
}

function saveDraft() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(getFormSnapshot()));
    alert("COC draft saved on this device.");
  } catch (error) {
    console.error(error);
    alert("Could not save COC draft.");
  }
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    applySnapshot(JSON.parse(raw));
  } catch (error) {
    console.warn("Failed loading COC draft:", error);
  }
}

function clearDraft() {
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
}

function formatVerificationForPdf() {
  const lines = [];
  VERIFICATION_ITEMS.forEach((item, index) => {
    const key = `verify_${index}`;
    const selected = document.querySelector(`input[name="${key}"]:checked`);
    const result = selected ? selected.value : "Not marked";
    const note = document.querySelector(`input[data-verify-note-key="${key}"]`)?.value?.trim();
    lines.push(`- ${item}: ${result}${note ? ` | Note: ${note}` : ""}`);
  });
  return lines;
}

function addWrappedText(doc, text, x, y, maxWidth, lineHeight = 6) {
  const lines = doc.splitTextToSize(text, maxWidth);
  doc.text(lines, x, y);
  return y + lines.length * lineHeight;
}

async function imageUrlToDataUrl(url) {
  const response = await fetch(url);
  const blob = await response.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Failed reading image."));
    reader.readAsDataURL(blob);
  });
}

async function generatePdf() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  const snapshot = getFormSnapshot();
  const values = snapshot.values;

  let y = 14;

  if (logoImg && logoImg.src) {
    try {
      const logoDataUrl = await imageUrlToDataUrl(logoImg.src);
      const logoProps = doc.getImageProperties(logoDataUrl);
      const logoWidth = 46;
      const logoHeight = logoWidth * (logoProps.height / logoProps.width);
      doc.addImage(logoDataUrl, "PNG", 14, y - 2, logoWidth, logoHeight);
      y += logoHeight + 2;
    } catch (error) {
      console.warn("Logo embed failed:", error);
    }
  }

  doc.setFontSize(16);
  doc.text("Certificate of Compliance (COC)", 14, y);
  y += 8;

  doc.setFontSize(10);
  const details = [
    `Business: ${values.businessName || "-"}`,
    `Electrician: ${values.electricianName || "-"}`,
    `Licence / Registration No: ${values.licenceNumber || "-"}`,
    `Phone: ${values.electricianPhone || "-"}`,
    `Client: ${values.clientName || "-"}`,
    `Job number: ${values.jobNumber || "-"}`,
    `Site address: ${values.siteAddress || "-"}`,
    `Date of completion: ${values.completionDate || "-"}`,
    `Type of work: ${values.workType || "-"}`,
    `Supply type: ${values.supplyType || "-"}`,
    `Standards / references: ${values.standardsUsed || "-"}`
  ];
  details.forEach((line) => {
    y = addWrappedText(doc, line, 14, y, 182);
  });

  y += 3;
  doc.setFontSize(12);
  doc.text("Work Description", 14, y);
  y += 6;
  doc.setFontSize(10);
  y = addWrappedText(doc, values.workDescription || "-", 14, y, 182);

  if (y > 250) {
    doc.addPage();
    y = 14;
  }

  y += 3;
  doc.setFontSize(12);
  doc.text("Verification Checklist", 14, y);
  y += 6;
  doc.setFontSize(10);
  formatVerificationForPdf().forEach((line) => {
    if (y > 275) {
      doc.addPage();
      y = 14;
    }
    y = addWrappedText(doc, line, 14, y, 182);
  });

  if (y > 245) {
    doc.addPage();
    y = 14;
  }

  y += 3;
  doc.setFontSize(12);
  doc.text("Declaration", 14, y);
  y += 6;
  doc.setFontSize(10);
  y = addWrappedText(doc, values.declarationText || "-", 14, y, 182);
  y += 2;
  y = addWrappedText(doc, `Declared by: ${values.declaredBy || "-"}`, 14, y, 182);
  y = addWrappedText(doc, `Date: ${values.declarationDate || "-"}`, 14, y, 182);

  const safeBusiness = (values.businessName || "solar-electrix").replace(/[^a-z0-9]+/gi, "-");
  const safeDate = values.completionDate || new Date().toISOString().slice(0, 10);
  doc.save(`${safeBusiness}-COC-${safeDate}.pdf`);
}
