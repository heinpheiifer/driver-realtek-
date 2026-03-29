"use strict";

const CHECKLIST_SECTIONS = [
  {
    title: "Pre-start planning",
    items: [
      "SWMS/JSA reviewed with team before work starts",
      "Emergency contacts and first aid kit available onsite",
      "Weather checked and safe to proceed",
      "Site-specific hazards identified and communicated"
    ]
  },
  {
    title: "Electrical safety controls",
    items: [
      "Isolation/lock-out process in place before electrical work",
      "Test equipment in date and functioning correctly",
      "Circuits tested and verified de-energized where required",
      "Cables and tools inspected for damage before use"
    ]
  },
  {
    title: "Working at heights / roof safety",
    items: [
      "Roof access is safe and secured",
      "Fall prevention controls (harness/edge protection) in place",
      "Ladders positioned and tied/secured correctly",
      "Fragile roof sections identified and avoided/protected"
    ]
  },
  {
    title: "Solar installation controls",
    items: [
      "PV array isolation points labelled and accessible",
      "DC cable routing protected from abrasion and heat",
      "Inverter location has safe clearance and ventilation",
      "Signage and labelling meet installation requirements"
    ]
  },
  {
    title: "Post-install checks",
    items: [
      "Work area left safe and tidy",
      "Client advised on shutdown and emergency procedures",
      "Defects/incidents documented",
      "Final verification/testing records completed"
    ]
  }
];

const STORAGE_KEY = "solar-safety-app-draft-v1";

const state = {
  photos: [] // { id, name, caption, dataUrl }
};

const checklistContainer = document.getElementById("checklistContainer");
const photoInput = document.getElementById("photoInput");
const photoList = document.getElementById("photoList");
const saveDraftBtn = document.getElementById("saveDraftBtn");
const clearDraftBtn = document.getElementById("clearDraftBtn");
const generatePdfBtn = document.getElementById("generatePdfBtn");

function init() {
  renderChecklist();
  wireEvents();
  setDefaultDates();
  loadDraft();
}

function setDefaultDates() {
  const today = new Date().toISOString().slice(0, 10);
  const siteDate = document.getElementById("siteDate");
  const signOffDate = document.getElementById("signOffDate");
  if (!siteDate.value) siteDate.value = today;
  if (!signOffDate.value) signOffDate.value = today;
}

function wireEvents() {
  photoInput.addEventListener("change", handlePhotoPick);
  saveDraftBtn.addEventListener("click", saveDraft);
  clearDraftBtn.addEventListener("click", clearDraft);
  generatePdfBtn.addEventListener("click", generatePdf);
}

function renderChecklist() {
  checklistContainer.innerHTML = "";
  CHECKLIST_SECTIONS.forEach((section, sectionIdx) => {
    const sectionEl = document.createElement("div");
    sectionEl.className = "checklist-section";

    const heading = document.createElement("h3");
    heading.textContent = section.title;
    sectionEl.appendChild(heading);

    section.items.forEach((item, itemIdx) => {
      const itemEl = document.createElement("div");
      itemEl.className = "check-item";

      const key = `section_${sectionIdx}_item_${itemIdx}`;
      const text = document.createElement("div");
      text.className = "check-text";
      text.textContent = item;
      itemEl.appendChild(text);

      const radios = document.createElement("div");
      radios.className = "radio-row";

      ["Yes", "No", "N/A"].forEach((label) => {
        const radioLabel = document.createElement("label");
        const input = document.createElement("input");
        input.type = "radio";
        input.name = key;
        input.value = label;
        radioLabel.appendChild(input);
        radioLabel.append(label);
        radios.appendChild(radioLabel);
      });

      const comment = document.createElement("input");
      comment.type = "text";
      comment.placeholder = "Optional note";
      comment.dataset.commentKey = key;

      itemEl.appendChild(radios);
      itemEl.appendChild(comment);
      sectionEl.appendChild(itemEl);
    });

    checklistContainer.appendChild(sectionEl);
  });
}

function createPhotoId() {
  return `p_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function handlePhotoPick(event) {
  const files = Array.from(event.target.files || []);
  files.forEach((file) => {
    const reader = new FileReader();
    reader.onload = () => {
      state.photos.push({
        id: createPhotoId(),
        name: file.name || "Site photo",
        caption: "",
        dataUrl: String(reader.result || "")
      });
      renderPhotos();
    };
    reader.readAsDataURL(file);
  });
  photoInput.value = "";
}

function renderPhotos() {
  photoList.innerHTML = "";
  state.photos.forEach((photo) => {
    const item = document.createElement("div");
    item.className = "photo-item";

    const image = document.createElement("img");
    image.src = photo.dataUrl;
    image.alt = photo.name;
    item.appendChild(image);

    const meta = document.createElement("div");
    meta.className = "photo-meta";

    const caption = document.createElement("input");
    caption.type = "text";
    caption.placeholder = "Photo caption (example: Roof anchor point)";
    caption.value = photo.caption || "";
    caption.addEventListener("input", (e) => {
      photo.caption = e.target.value;
    });
    meta.appendChild(caption);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-photo";
    remove.textContent = "Remove photo";
    remove.addEventListener("click", () => {
      state.photos = state.photos.filter((p) => p.id !== photo.id);
      renderPhotos();
    });
    meta.appendChild(remove);

    item.appendChild(meta);
    photoList.appendChild(item);
  });
}

function getFormSnapshot() {
  const fields = [
    "businessName",
    "teamLeader",
    "teamMembers",
    "jobNumber",
    "clientName",
    "siteAddress",
    "siteDate",
    "weather",
    "siteNotes",
    "signOffName",
    "signOffDate"
  ];

  const values = {};
  fields.forEach((id) => {
    values[id] = document.getElementById(id).value;
  });

  const checklist = {};
  const radioGroups = new Set();
  document.querySelectorAll('input[type="radio"]').forEach((radio) => {
    radioGroups.add(radio.name);
  });

  radioGroups.forEach((groupName) => {
    const selected = document.querySelector(`input[name="${groupName}"]:checked`);
    checklist[groupName] = {
      result: selected ? selected.value : "",
      note: (
        document.querySelector(`input[data-comment-key="${groupName}"]`)?.value || ""
      ).trim()
    };
  });

  return {
    values,
    checklist,
    photos: state.photos
  };
}

function applySnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;
  const values = snapshot.values || {};
  Object.entries(values).forEach(([id, value]) => {
    const el = document.getElementById(id);
    if (el) el.value = value;
  });

  const checklist = snapshot.checklist || {};
  Object.entries(checklist).forEach(([key, data]) => {
    if (!data || typeof data !== "object") return;
    if (data.result) {
      const radio = document.querySelector(
        `input[name="${key}"][value="${CSS.escape(data.result)}"]`
      );
      if (radio) radio.checked = true;
    }
    const comment = document.querySelector(`input[data-comment-key="${key}"]`);
    if (comment) comment.value = data.note || "";
  });

  state.photos = Array.isArray(snapshot.photos) ? snapshot.photos : [];
  renderPhotos();
}

function saveDraft() {
  try {
    const snapshot = getFormSnapshot();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
    alert("Draft saved on this device.");
  } catch (error) {
    alert("Could not save draft. Storage may be full.");
    console.error(error);
  }
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    applySnapshot(JSON.parse(raw));
  } catch (error) {
    console.warn("Could not load saved draft:", error);
  }
}

function clearDraft() {
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
}

function formatChecklistForPdf() {
  const lines = [];
  CHECKLIST_SECTIONS.forEach((section, sectionIdx) => {
    lines.push(`${section.title}:`);
    section.items.forEach((item, itemIdx) => {
      const key = `section_${sectionIdx}_item_${itemIdx}`;
      const selected = document.querySelector(`input[name="${key}"]:checked`);
      const result = selected ? selected.value : "Not marked";
      const note = document.querySelector(`input[data-comment-key="${key}"]`)?.value?.trim();
      lines.push(`- ${item} -> ${result}${note ? ` | Note: ${note}` : ""}`);
    });
    lines.push("");
  });
  return lines;
}

function addWrappedText(doc, text, x, y, maxWidth, lineHeight = 6) {
  const lines = doc.splitTextToSize(text, maxWidth);
  doc.text(lines, x, y);
  return y + lines.length * lineHeight;
}

async function generatePdf() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();

  const snapshot = getFormSnapshot();
  const { values } = snapshot;

  let y = 14;
  doc.setFontSize(16);
  doc.text("Solar Site Health & Safety Report", 14, y);
  y += 8;

  doc.setFontSize(10);
  const detailLines = [
    `Business: ${values.businessName || "-"}`,
    `Team leader: ${values.teamLeader || "-"}`,
    `Team members: ${values.teamMembers || "-"}`,
    `Job number: ${values.jobNumber || "-"}`,
    `Client: ${values.clientName || "-"}`,
    `Address: ${values.siteAddress || "-"}`,
    `Date: ${values.siteDate || "-"}`,
    `Weather: ${values.weather || "-"}`
  ];

  detailLines.forEach((line) => {
    y = addWrappedText(doc, line, 14, y, 182);
  });
  y += 3;

  doc.setFontSize(12);
  doc.text("Checklist", 14, y);
  y += 6;
  doc.setFontSize(10);

  const checklistLines = formatChecklistForPdf();
  for (const line of checklistLines) {
    if (y > 275) {
      doc.addPage();
      y = 14;
    }
    y = addWrappedText(doc, line, 14, y, 182);
  }

  if (y > 250) {
    doc.addPage();
    y = 14;
  }
  y += 2;
  doc.setFontSize(12);
  doc.text("Notes & Sign-off", 14, y);
  y += 6;
  doc.setFontSize(10);
  y = addWrappedText(doc, `Notes: ${values.siteNotes || "-"}`, 14, y, 182);
  y = addWrappedText(doc, `Supervisor: ${values.signOffName || "-"}`, 14, y, 182);
  y = addWrappedText(doc, `Sign-off date: ${values.signOffDate || "-"}`, 14, y, 182);

  for (let i = 0; i < state.photos.length; i += 1) {
    const photo = state.photos[i];
    doc.addPage();
    doc.setFontSize(12);
    doc.text(`Photo ${i + 1}`, 14, 14);
    doc.setFontSize(10);
    doc.text(photo.caption || photo.name || "Site photo", 14, 21);

    try {
      const imgProps = doc.getImageProperties(photo.dataUrl);
      const maxWidth = 180;
      const maxHeight = 250;
      const ratio = Math.min(maxWidth / imgProps.width, maxHeight / imgProps.height);
      const width = imgProps.width * ratio;
      const height = imgProps.height * ratio;
      const x = 14 + (maxWidth - width) / 2;
      const yPos = 26;
      doc.addImage(photo.dataUrl, "JPEG", x, yPos, width, height);
    } catch (error) {
      doc.setTextColor(200, 0, 0);
      doc.text("Could not embed this photo.", 14, 30);
      doc.setTextColor(0, 0, 0);
      console.warn("Image embed failed:", error);
    }
  }

  const fileDate = values.siteDate || new Date().toISOString().slice(0, 10);
  const safeBusiness = (values.businessName || "solar-team").replace(/[^a-z0-9]+/gi, "-");
  doc.save(`${safeBusiness}-site-safety-${fileDate}.pdf`);
}

init();
