const fallbackResults = [
  { id: "TTE-2026-017", name: "Narmada logistics expansion", location: "Hoshangabad · MP", score: 0.92, quality: 0.96, date: "2022-01-17", before_date: "2021-11-08", sensor: "Sentinel-2 L2A", cloud: 4, surface: "after" },
  { id: "TTE-2026-042", name: "Riverside industrial construction", location: "Bharuch · GJ", score: 0.88, quality: 0.93, date: "2023-03-09", before_date: "2022-12-14", sensor: "Sentinel-2 L2A", cloud: 7, surface: "after" },
  { id: "TTE-2026-105", name: "Warehouse complex near channel", location: "Nagpur · MH", score: 0.83, quality: 0.91, date: "2025-01-27", before_date: "2024-10-04", sensor: "Sentinel-2 L2A", cloud: 6, surface: "after" },
  { id: "TTE-2026-331", name: "Transport yard near tributary", location: "Vadodara · GJ", score: 0.78, quality: 0.89, date: "2022-12-14", before_date: "2022-08-20", sensor: "Sentinel-2 L2A", cloud: 10, surface: "before" },
  { id: "TTE-2026-208", name: "Agricultural clearing near water", location: "Khandwa · MP", score: 0.69, quality: 0.86, date: "2024-02-21", before_date: "2023-11-06", sensor: "Sentinel-2 L2A", cloud: 13, surface: "before" }
];

let results = fallbackResults.map((item) => ({ ...item }));

const similarSites = [
  { name: "Intermodal depot expansion", location: "Surat · GJ", score: 0.89, date: "11 May 2025", cluster: "CL-08", surface: "after" },
  { name: "River freight terminal", location: "Bharuch · GJ", score: 0.86, date: "03 Nov 2024", cluster: "CL-08", surface: "after" },
  { name: "Warehouse construction", location: "Nashik · MH", score: 0.81, date: "18 Jan 2026", cluster: "CL-14", surface: "after" },
  { name: "Industrial land clearing", location: "Sehore · MP", score: 0.77, date: "22 Feb 2025", cluster: "CL-14", surface: "before" },
  { name: "Highway logistics park", location: "Indore · MP", score: 0.74, date: "07 Jun 2026", cluster: "CL-21", surface: "after" },
  { name: "Agricultural river bend", location: "Raisen · MP", score: 0.68, date: "16 Mar 2025", cluster: "HARD NEG.", surface: "before" }
];

const initialQueue = [
  { id: "TTE-2026-017", name: "Narmada logistics expansion", location: "Hoshangabad · MP", type: "Construction", area: "18.4 ha", support: 0.87, quality: 0.94, surface: "after" },
  { id: "TTE-2026-061", name: "Linear corridor development", location: "Dhar · MP", type: "Road", area: "6.8 km", support: 0.79, quality: 0.91, surface: "after" },
  { id: "TTE-2026-113", name: "Seasonal water boundary shift", location: "Nandurbar · MH", type: "Water", area: "42.1 ha", support: 0.73, quality: 0.88, surface: "before" }
];

let selectedIndex = 0;
let descending = true;
let toastTimer;
let sceneTotal = 5;
let apiOnline = false;
let currentAnalysis = null;
let queue = JSON.parse(localStorage.getItem("terratraceQueue") || "null") || initialQueue.map((item) => ({ ...item }));
let counters = JSON.parse(localStorage.getItem("terratraceCounters") || "null") || { confirmed: 12, rejected: 7 };

const viewMeta = {
  search: ["DISCOVERY / SEMANTIC RETRIEVAL", "Search the local archive"],
  timeline: ["INVESTIGATION / TEMPORAL REASONING", "Determine when change became defensible"],
  evidence: ["VERIFICATION / SOURCE-TO-DECISION", "Inspect the supporting evidence"],
  similar: ["DISCOVERY / IMAGE RETRIEVAL", "Find visually similar sites"],
  review: ["HUMAN-IN-THE-LOOP / AUDIT", "Review candidate changes"]
};

function formatDate(value) {
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

async function checkBackend() {
  try {
    const health = await api("/api/health");
    apiOnline = true;
    sceneTotal = health.scenes;
    document.getElementById("sceneCount").textContent = `${sceneTotal} scenes`;
    document.getElementById("archiveMeta").textContent = `${health.engine} · SQLite`;
    document.getElementById("archivePercent").textContent = "Live";
    document.getElementById("systemStatus").innerHTML = "<i></i> Local engine connected";
  } catch {
    apiOnline = false;
    document.getElementById("systemStatus").innerHTML = "<i></i> Static demo mode";
    document.getElementById("archiveMeta").textContent = "Open with start-SIH26227.bat";
    document.getElementById("archivePercent").textContent = "Demo";
  }
}

function showToast(title, message) {
  const toast = document.getElementById("toast");
  document.getElementById("toastTitle").textContent = title;
  document.getElementById("toastMessage").textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function setView(name) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((button) => {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.getElementById(`view-${name}`).classList.add("active");
  document.getElementById("viewEyebrow").textContent = viewMeta[name][0];
  document.getElementById("viewTitle").textContent = viewMeta[name][1];
  window.scrollTo({ top: 0, behavior: "smooth" });
  if ((name === "timeline" || name === "evidence") && apiOnline) loadAnalysis(false);
}

function renderResults() {
  const ordered = results.map((item, index) => ({ ...item, originalIndex: index })).sort((a, b) => descending ? b.score - a.score : a.score - b.score);
  document.getElementById("resultList").innerHTML = ordered.map((item, rank) => `
    <button class="result-card ${item.originalIndex === selectedIndex ? "active" : ""}" type="button" data-select="${item.originalIndex}">
      <span class="result-thumb satellite-surface ${item.surface}-surface"></span>
      <span class="result-copy"><b>${item.name}</b><span>${item.location} · ${formatDate(item.date)}</span><span class="result-tags"><i>${item.sensor || "S2 L2A"}</i><i>Q ${Number(item.quality).toFixed(2)}</i><i>${Number(item.cloud).toFixed(0)}% cloud</i></span></span>
      <span class="result-score"><strong>${item.score.toFixed(2)}</strong><small>semantic</small></span>
    </button>`).join("");
  document.querySelectorAll("[data-select]").forEach((button) => button.addEventListener("click", () => selectResult(Number(button.dataset.select))));
  renderSelection();
}

function renderSelection() {
  const item = results[selectedIndex];
  document.getElementById("selectionStrip").innerHTML = `
    <div class="selected-title"><span>SELECTED · ${item.id}</span><b>${item.name}</b></div>
    <div class="selection-stat"><span>Semantic score</span><b>${item.score.toFixed(2)}</b></div>
    <div class="selection-stat"><span>Observation quality</span><b>${item.quality.toFixed(2)}</b></div>
    <div class="selection-stat"><span>Acquired</span><b>${formatDate(item.date)}</b></div>
    <button class="primary-button" type="button" data-go="timeline">Open change timeline <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"></path></svg></button>`;
  document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => setView(button.dataset.go)));
}

function selectResult(index) {
  selectedIndex = index;
  document.querySelectorAll(".map-pin").forEach((pin) => pin.classList.toggle("selected", Number(pin.dataset.result) === index));
  renderResults();
  showToast("Candidate selected", `${results[index].id} · ${results[index].name}`);
}

async function runSearch() {
  const button = document.getElementById("searchButton");
  const query = document.getElementById("semanticQuery").value.trim() || "all indexed scenes";
  button.disabled = true;
  button.querySelector("span").textContent = "Searching…";
  document.getElementById("scanLine").classList.remove("scanning");
  void document.getElementById("scanLine").offsetWidth;
  document.getElementById("scanLine").classList.add("scanning");
  const started = performance.now();
  try {
    if (apiOnline) {
      const sensor = document.getElementById("sensorFilter").value;
      const cloud = document.getElementById("cloudFilter").value;
      const payload = await api(`/api/search?q=${encodeURIComponent(query)}&sensor=${encodeURIComponent(sensor)}&max_cloud=${encodeURIComponent(cloud)}`);
      results = payload.results.length ? payload.results : fallbackResults.map((item) => ({ ...item }));
    } else {
      await new Promise((resolve) => setTimeout(resolve, 650));
    }
    const elapsed = Math.max(1, Math.round(performance.now() - started));
    button.disabled = false;
    button.querySelector("span").textContent = "Run search";
    document.getElementById("resultSummary").textContent = `${results.length} matches in ${elapsed} ms`;
    document.getElementById("mapMeta").textContent = `${results.length} indexed scenes · ${apiOnline ? "offline hybrid retrieval" : "static demo ranking"}`;
    selectedIndex = 0;
    descending = true;
    renderResults();
    showToast("Search complete", `${results.length} ranked matches for “${query}”`);
  } catch (error) {
    button.disabled = false;
    button.querySelector("span").textContent = "Run search";
    showToast("Search could not complete", error.message);
  }
}

function bindCompare(rangeId, afterId, dividerId) {
  const range = document.getElementById(rangeId);
  const after = document.getElementById(afterId);
  const divider = document.getElementById(dividerId);
  const update = () => {
    const value = Number(range.value);
    after.style.clipPath = `inset(0 ${100 - value}% 0 0)`;
    divider.style.left = `${value}%`;
  };
  range.addEventListener("input", update);
  update();
}

async function loadAnalysis(announce = true) {
  if (!apiOnline || !results[selectedIndex]) return;
  const button = document.getElementById("runAnalysis");
  button.disabled = true;
  button.textContent = "MEASURING…";
  try {
    const item = results[selectedIndex];
    const analysis = await api(`/api/cases/${encodeURIComponent(item.id)}/analysis`);
    currentAnalysis = analysis;
    document.getElementById("caseId").textContent = `CASE ${analysis.scene_id} · MEASURED LOCALLY`;
    document.getElementById("caseName").textContent = analysis.name;
    document.getElementById("caseLocation").textContent = `${analysis.location} · ${analysis.sensor} · ${analysis.crs}`;
    document.getElementById("caseSupport").textContent = Number(analysis.support_score).toFixed(2);
    document.getElementById("caseMethod").textContent = analysis.method;
    document.getElementById("detectedArea").textContent = Number(analysis.changed_area_ha).toFixed(2);
    document.getElementById("registrationResidual").textContent = Number(analysis.registration_residual_px).toFixed(2);
    document.getElementById("changedPixels").textContent = (Number(analysis.changed_fraction) * 100).toFixed(1);
    document.getElementById("usablePixels").textContent = (Number(analysis.usable_pixel_fraction) * 100).toFixed(0);
    document.getElementById("registrationCheck").textContent = `Measured shift ${analysis.alignment_shift.x}, ${analysis.alignment_shift.y} px`;
    document.getElementById("registrationGate").textContent = analysis.quality_gates.registration ? "PASS" : "ABSTAIN";
    document.getElementById("differenceCheck").textContent = `Mean |ΔRGB| ${Number(analysis.mean_absolute_difference).toFixed(4)} · threshold ${Number(analysis.threshold).toFixed(4)}`;
    document.getElementById("evidenceSource").textContent = `${analysis.sensor} · ${analysis.method} · ${analysis.crs}`;
    document.getElementById("beforeScene").textContent = `${analysis.scene_id} · ${analysis.before_date}`;
    document.getElementById("afterScene").textContent = `${analysis.scene_id} · ${analysis.after_date}`;
    document.getElementById("processingRun").textContent = analysis.processing_run;
    document.getElementById("pipelineName").textContent = analysis.method;
    document.getElementById("assetHashState").textContent = `Verified · ${analysis.asset_hashes.after_sha256.slice(0, 12)}…`;
    document.querySelector(".interval-chip").innerHTML = `${formatDate(analysis.before_date)} <b>→</b> ${formatDate(analysis.after_date)}`;
    const mask = document.getElementById("changeMaskImage");
    mask.src = `${analysis.mask_url}?run=${encodeURIComponent(analysis.processing_run)}`;
    mask.style.display = document.getElementById("changeLayer").checked ? "block" : "none";
    document.querySelector(".evidence-poly").style.display = "none";
    if (announce) showToast("Measured analysis complete", `${analysis.decision} · ${(analysis.changed_fraction * 100).toFixed(1)}% changed pixels · source hashes verified.`);
  } catch (error) {
    if (announce) showToast("Analysis unavailable", error.message);
  } finally {
    button.disabled = false;
    button.textContent = "RUN MEASURED ANALYSIS";
  }
}

function renderSimilar() {
  const threshold = Number(document.getElementById("similarRange").value) / 100;
  const filtered = similarSites.filter((site) => site.score >= threshold);
  document.getElementById("similarGrid").innerHTML = filtered.length ? filtered.map((site, index) => `
    <article class="site-card panel">
      <div class="site-image satellite-surface ${site.surface}-surface"><span class="site-rank">${index + 1}</span><span class="site-score">${site.score.toFixed(2)}</span></div>
      <div class="site-copy"><b>${site.name}</b><p>${site.location}</p><div><span>${site.date}</span><span>${site.cluster}</span></div></div>
    </article>`).join("") : `<div class="queue-empty"><b>No sites clear this threshold</b>Lower the minimum similarity score to widen the candidate set.</div>`;
}

function saveQueue() {
  localStorage.setItem("terratraceQueue", JSON.stringify(queue));
  localStorage.setItem("terratraceCounters", JSON.stringify(counters));
}

function renderQueue() {
  document.getElementById("queueCount").textContent = queue.length;
  document.getElementById("pendingMetric").textContent = queue.length;
  document.getElementById("confirmedMetric").textContent = counters.confirmed;
  document.getElementById("rejectedMetric").textContent = counters.rejected;
  const table = document.getElementById("queueTable");
  if (!queue.length) {
    table.innerHTML = `<div class="queue-empty"><b>Review queue cleared</b>All prepared candidates have an analyst decision.</div>`;
    return;
  }
  table.innerHTML = `
    <div class="queue-row header"><span>Candidate</span><span>Change class</span><span>Extent</span><span>Support</span><span>Decision</span></div>
    ${queue.map((item) => `<div class="queue-row">
      <div class="queue-case"><span class="queue-thumb satellite-surface ${item.surface}-surface"></span><div><b>${item.name}</b><small>${item.id} · ${item.location}</small></div></div>
      <div class="queue-cell"><b>${item.type}</b><small>likely</small></div>
      <div class="queue-cell"><b>${item.area}</b><small>mapped</small></div>
      <div class="queue-cell"><b class="high">${item.support.toFixed(2)}</b><small>Q ${item.quality.toFixed(2)}</small></div>
      <div class="row-decisions"><button type="button" data-id="${item.id}" data-mini="uncertain">Uncertain</button><button type="button" data-id="${item.id}" data-mini="rejected">Reject</button><button type="button" data-id="${item.id}" data-mini="confirmed">Confirm</button></div>
    </div>`).join("")}`;
  document.querySelectorAll("[data-mini]").forEach((button) => button.addEventListener("click", () => applyDecision(button.dataset.id, button.dataset.mini)));
}

async function applyDecision(id, decision) {
  const item = queue.find((candidate) => candidate.id === id) || results.find((candidate) => candidate.id === id);
  if (!item) return;
  if (apiOnline) {
    try {
      await api("/api/review", {
        method: "POST",
        body: JSON.stringify({ scene_id: id, decision, analyst: "Analyst K-07", note: "Recorded from SIH26227 prototype", evidence: currentAnalysis || {} })
      });
    } catch (error) {
      showToast("Saved to this browser only", `Local engine did not accept the review: ${error.message}`);
    }
  }
  queue = queue.filter((candidate) => candidate.id !== id);
  if (decision === "confirmed") counters.confirmed += 1;
  if (decision === "rejected") counters.rejected += 1;
  saveQueue();
  renderQueue();
  document.getElementById("decisionTitle").textContent = decision === "confirmed" ? "Change confirmed by Analyst K-07" : decision === "rejected" ? "Candidate rejected by Analyst K-07" : "Candidate marked uncertain";
  document.getElementById("decisionNote").textContent = `Decision recorded locally at ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} with evidence snapshot.`;
  document.querySelectorAll(".decision").forEach((button) => button.classList.toggle("active", button.dataset.decision === decision));
  showToast("Decision recorded", `${id} marked ${decision}. Audit record updated.`);
}

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
document.querySelectorAll(".map-pin").forEach((button) => button.addEventListener("click", () => selectResult(Number(button.dataset.result))));
document.getElementById("searchButton").addEventListener("click", runSearch);
document.getElementById("semanticQuery").addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });

document.getElementById("cloudFilter").addEventListener("input", (event) => { document.getElementById("cloudValue").textContent = `${event.target.value}%`; });
document.getElementById("similarRange").addEventListener("input", (event) => { document.getElementById("similarValue").textContent = (event.target.value / 100).toFixed(2); renderSimilar(); });
document.getElementById("refreshSimilar").addEventListener("click", () => { renderSimilar(); showToast("Similarity set refreshed", "Exact search completed across the active index shards."); });

document.getElementById("resetFilters").addEventListener("click", () => {
  document.getElementById("aoiFilter").selectedIndex = 0;
  document.getElementById("dateFilter").selectedIndex = 0;
  document.getElementById("sensorFilter").selectedIndex = 0;
  document.getElementById("cloudFilter").value = 15;
  document.getElementById("cloudValue").textContent = "15%";
  showToast("Filters reset", "Archive defaults restored.");
});

document.getElementById("sortButton").addEventListener("click", (event) => {
  descending = !descending;
  event.currentTarget.textContent = descending ? "Score ↓" : "Score ↑";
  renderResults();
});

document.querySelectorAll("[data-map]").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll("[data-map]").forEach((item) => item.classList.toggle("active", item === button));
  const map = document.getElementById("searchMap");
  map.classList.remove("ndvi", "quality");
  if (button.dataset.map !== "rgb") map.classList.add(button.dataset.map);
}));

document.querySelectorAll(".time-node").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".time-node").forEach((node) => node.removeAttribute("aria-current"));
  button.setAttribute("aria-current", "true");
  document.querySelector("#timelineReadout b").textContent = button.dataset.time;
}));

document.getElementById("qualityLayer").addEventListener("change", (event) => { document.getElementById("qualityHatch").style.display = event.target.checked ? "block" : "none"; });
document.getElementById("gridLayer").addEventListener("change", (event) => { document.getElementById("registrationGrid").style.display = event.target.checked ? "block" : "none"; });
document.getElementById("changeLayer").addEventListener("change", (event) => {
  const mask = document.getElementById("changeMaskImage");
  if (currentAnalysis) mask.style.display = event.target.checked ? "block" : "none";
  else document.querySelector(".evidence-poly").style.display = event.target.checked ? "block" : "none";
});
document.getElementById("runAnalysis").addEventListener("click", () => loadAnalysis(true));

document.querySelectorAll(".decision").forEach((button) => button.addEventListener("click", () => applyDecision(results[selectedIndex]?.id || "TTE-2026-017", button.dataset.decision)));

document.getElementById("copyProvenance").addEventListener("click", async () => {
  const record = "TTE-2026-017 | S2B_MSIL2A_20211108_T43QGE → S2A_MSIL2A_20220117_T43QGE | run-20260914-0942-k07 | classical-v0.7.4 | SHA-256 verified";
  try { await navigator.clipboard.writeText(record); showToast("Provenance copied", "Evidence chain copied to the clipboard."); }
  catch { showToast("Provenance ready", record); }
});

const ingestDialog = document.getElementById("ingestDialog");
document.getElementById("ingestButton").addEventListener("click", () => {
  if (!apiOnline) {
    showToast("Start the local engine first", "Open start-SIH26227.bat, then use ingestion from the connected workspace.");
    return;
  }
  ingestDialog.showModal();
});
document.getElementById("closeIngest").addEventListener("click", () => ingestDialog.close());
document.getElementById("cancelIngest").addEventListener("click", () => ingestDialog.close());

function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

document.getElementById("ingestForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = document.getElementById("submitIngest");
  const beforeFile = document.getElementById("beforeFile").files[0];
  const afterFile = document.getElementById("afterFile").files[0];
  if (!beforeFile || !afterFile) return;
  submit.disabled = true;
  submit.textContent = "Ingesting and measuring…";
  try {
    const fields = Object.fromEntries(new FormData(event.currentTarget).entries());
    fields.aoi_area_ha = Number(fields.aoi_area_ha);
    fields.before_data = await readFile(beforeFile);
    fields.after_data = await readFile(afterFile);
    fields.description = `${fields.name} near ${fields.location}`;
    fields.tags = "local,change,construction";
    const payload = await api("/api/ingest-pair", { method: "POST", body: JSON.stringify(fields) });
    const scene = payload.scene;
    results.unshift({ id: scene.id, name: scene.name, location: scene.location, date: scene.acquired_at, before_date: scene.before_at, sensor: scene.sensor, cloud: scene.cloud, quality: scene.quality, score: 0.91, surface: "after", source: "local-upload" });
    selectedIndex = 0;
    currentAnalysis = payload.analysis;
    sceneTotal += 1;
    document.getElementById("sceneCount").textContent = `${sceneTotal} scenes`;
    renderResults();
    ingestDialog.close();
    setView("search");
    showToast("Pair indexed and analysed", `${scene.id} · ${(payload.analysis.changed_fraction * 100).toFixed(1)}% changed pixels.`);
    event.currentTarget.reset();
  } catch (error) {
    showToast("Ingestion failed", error.message);
  } finally {
    submit.disabled = false;
    submit.textContent = "Ingest and analyse";
  }
});

document.getElementById("exportAudit").addEventListener("click", () => {
  const audit = { project: "SIH26227", system: "TerraTrace EO", exported_at: new Date().toISOString(), remaining_queue: queue, counters, offline: true, synthetic_demo_data: true };
  const url = URL.createObjectURL(new Blob([JSON.stringify(audit, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "SIH26227-audit-record.json";
  link.click();
  URL.revokeObjectURL(url);
  showToast("Audit exported", "SIH26227-audit-record.json saved locally.");
});

document.getElementById("resetDemo").addEventListener("click", () => {
  localStorage.removeItem("terratraceQueue");
  localStorage.removeItem("terratraceCounters");
  queue = initialQueue.map((item) => ({ ...item }));
  counters = { confirmed: 12, rejected: 7 };
  saveQueue();
  renderQueue();
  document.getElementById("decisionTitle").textContent = "This candidate has not been reviewed";
  document.getElementById("decisionNote").textContent = "Your decision is stored locally with the evidence and model version.";
  document.querySelectorAll(".decision").forEach((button) => button.classList.remove("active"));
  showToast("Demo reset", "Prepared review candidates restored.");
});

const dialog = document.getElementById("shortcutDialog");
document.getElementById("helpButton").addEventListener("click", () => dialog.showModal());
document.getElementById("closeDialog").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement.tagName !== "INPUT") { event.preventDefault(); setView("search"); document.getElementById("semanticQuery").focus(); }
  if (/^[1-5]$/.test(event.key) && document.activeElement.tagName !== "INPUT") setView(["search", "timeline", "evidence", "similar", "review"][Number(event.key) - 1]);
});

bindCompare("timelineRange", "timelineAfter", "timelineDivider");
bindCompare("evidenceRange", "evidenceAfter", "evidenceDivider");
renderResults();
renderSimilar();
renderQueue();
checkBackend();
