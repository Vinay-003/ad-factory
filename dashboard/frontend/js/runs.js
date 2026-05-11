import { state } from "./state.js";
import { setStatus, setChromeStatus, skeletonRunCard } from "./ui.js";
import { fetchJSON, invalidateRuns } from "./api.js";
import { buildImageGallery } from "./images.js";
import { buildPromptEditor } from "./prompts.js";

const runsEl = document.getElementById("runs");
const runPrevEl = document.getElementById("runPrev");
const runNextEl = document.getElementById("runNext");
const runIndexEl = document.getElementById("runIndex");

let batchDropdownInitialized = false;

export function renderRun(run) {
  const div = document.createElement("div");
  div.className = "run run-active";

  const header = document.createElement("div");
  header.className = "run-header";
  header.innerHTML = `<strong>${run.run_id}</strong><span class="run-meta">batch ${run.batch} &middot; prompts ${run.prompt_files.length} &middot; images ${run.image_files.length}</span>`;
  div.appendChild(header);

  const llm = document.createElement("div");
  llm.className = "run-updated";
  llm.textContent = `Updated: ${run.updated_at || "-"}`;
  div.appendChild(llm);

  if (run.prompt_files && run.prompt_files.length) {
    const pf = document.createElement("div");
    pf.className = "run-prompt-files";
    pf.innerHTML = `<strong>Prompt files</strong>`;
    const ul = document.createElement("ul");
    run.prompt_files.forEach((path) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `/output/${path.replace(/^output\//, "")}`;
      a.target = "_blank";
      a.textContent = path;
      li.appendChild(a);
      ul.appendChild(li);
    });
    pf.appendChild(ul);
    div.appendChild(pf);
  }

  const promptActions = document.createElement("div");
  promptActions.className = "prompt-actions";
  buildPromptEditor(run, promptActions);
  div.appendChild(promptActions);

  const gallery = buildImageGallery(run);
  if (gallery) div.appendChild(gallery);

  return div;
}

function updateRunNav() {
  const total = state.runsData.length;
  const latestBatch = total ? (state.runsData[0].batch || "-") : "-";
  if (runIndexEl) {
    const position = total ? `${state.currentRunIndex + 1}/${total}` : "0/0";
    runIndexEl.textContent = `${position} | latest batch ${latestBatch}`;
  }
  if (runPrevEl) runPrevEl.disabled = total <= 1;
  if (runNextEl) runNextEl.disabled = total <= 1;
}

export function renderRunCarousel() {
  if (!runsEl) return;
  runsEl.innerHTML = "";
  if (!state.runsData.length) {
    const empty = document.createElement("div");
    empty.className = "hint empty-runs";
    empty.textContent = "No runs yet.";
    runsEl.appendChild(empty);
    updateRunNav();
    return;
  }
  if (state.currentRunIndex < 0) state.currentRunIndex = 0;
  if (state.currentRunIndex >= state.runsData.length) state.currentRunIndex = state.runsData.length - 1;
  runsEl.appendChild(renderRun(state.runsData[state.currentRunIndex]));
  updateRunNav();
}

export function showRunsSkeletons(count = 2) {
  if (!runsEl) return;
  runsEl.innerHTML = "";
  const frag = document.createDocumentFragment();
  for (let i = 0; i < count; i++) frag.appendChild(skeletonRunCard());
  runsEl.appendChild(frag);
}

function getSelectedBatchValues() {
  return Array.from(document.querySelectorAll(".batch-check:checked")).map((c) => c.value);
}

function updateBatchDropdownButtonLabel() {
  const btn = document.getElementById("batchDropdownBtn");
  if (!btn) return;
  const count = getSelectedBatchValues().length;
  btn.textContent = count ? `${count} batch(es) selected` : "Select batch(es)";
}

function closeBatchDropdown() {
  const menu = document.getElementById("batchDropdownMenu");
  const btn = document.getElementById("batchDropdownBtn");
  if (menu && !menu.classList.contains("hidden")) menu.classList.add("hidden");
  if (btn) btn.setAttribute("aria-expanded", "false");
}

function openBatchDropdown() {
  const menu = document.getElementById("batchDropdownMenu");
  const btn = document.getElementById("batchDropdownBtn");
  if (menu) menu.classList.remove("hidden");
  if (btn) btn.setAttribute("aria-expanded", "true");
}

export async function loadRuns() {
  if (state.isRunsLoading) return;
  state.isRunsLoading = true;
  try {
    const data = await fetchJSON("/api/runs");
    state.runsData = data.runs || [];
    state.currentRunIndex = 0;

    const batchMenu = document.getElementById("batchDropdownMenu");
    batchMenu.innerHTML = "";

    const batches = new Set();
    state.runsData.forEach((r) => { if (r.batch) batches.add(r.batch); });

    const grid = document.createElement("div");
    grid.className = "batch-grid";
    const batchList = Array.from(batches).sort().reverse();
    const num = batchList.length;
    const rows = num <= 1 ? 1 : 2;
    const cols = rows === 1 ? 1 : Math.ceil(num / 2);
    grid.style.gridTemplateColumns = `repeat(${cols}, minmax(170px, 1fr))`;
    grid.style.gridAutoRows = "auto";
    grid.style.gridTemplateRows = `repeat(${rows}, auto)`;

    batchList.forEach((batch) => {
    const item = document.createElement("div");
    item.className = "batch-grid-item";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = batch;
    cb.className = "batch-check";
    const labelSpan = document.createElement("span");
    labelSpan.className = "batch-label";
    labelSpan.textContent = batch;
    cb.addEventListener("change", updateBatchDropdownButtonLabel);
    item.addEventListener("click", (event) => {
      if (event.target.closest("input[type='checkbox']")) return;
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event("change", { bubbles: true }));
    });
    item.append(cb, labelSpan);
    grid.appendChild(item);
    });

    batchMenu.appendChild(grid);

    if (!batchDropdownInitialized) {
      batchDropdownInitialized = true;
      const dropdownRoot = document.querySelector(".batch-dropdown");
      const btn = document.getElementById("batchDropdownBtn");
      btn?.addEventListener("click", (e) => {
        e.stopPropagation();
        const menu = document.getElementById("batchDropdownMenu");
        if (!menu) return;
        menu.classList.contains("hidden") ? openBatchDropdown() : closeBatchDropdown();
      });
      document.addEventListener("click", (e) => {
        const menu = document.getElementById("batchDropdownMenu");
        if (!menu || menu.classList.contains("hidden")) return;
        if (dropdownRoot && !dropdownRoot.contains(e.target)) closeBatchDropdown();
      });
      document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeBatchDropdown(); });
    }

    updateBatchDropdownButtonLabel();
    renderRunCarousel();
  } finally {
    state.isRunsLoading = false;
  }
}

if (runPrevEl) {
  runPrevEl.addEventListener("click", () => {
    if (!state.runsData.length) return;
    state.currentRunIndex = (state.currentRunIndex - 1 + state.runsData.length) % state.runsData.length;
    renderRunCarousel();
  });
}
if (runNextEl) {
  runNextEl.addEventListener("click", () => {
    if (!state.runsData.length) return;
    state.currentRunIndex = (state.currentRunIndex + 1) % state.runsData.length;
    renderRunCarousel();
  });
}

document.getElementById("refreshRuns")?.addEventListener("click", () => {
  invalidateRuns();
  loadRuns().catch(() => {});
});

document.getElementById("batchGen45")?.addEventListener("click", async () => {
  const selectedBatches = getSelectedBatchValues();
  if (!selectedBatches.length) { setStatus("Select at least one batch."); return; }
  const runsForBatches = state.runsData.filter((r) => selectedBatches.includes(r.batch));
  if (!runsForBatches.length) { setStatus("No runs found for selected batch(es)."); return; }
  const runIds = runsForBatches.map((r) => r.run_id);
  setStatus(`Batch generating 4:5 for ${runIds.length} run(s)...`);
  try {
    const data = await fetchJSON("/api/batch/generate-images-45", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_ids: runIds, headless: state.headlessModeEnabled }),
    });
    const batchKey = data.batch_key || "";
    if (batchKey && state.headlessModeEnabled) {
      import("./chrome.js").then((m) => m.startProgressPolling(batchKey));
    }
    setStatus(`Done. Batch: ${data.batch_key}, Prompts: ${data.total_prompts}`);
    loadRuns();
  } catch (err) {
    setStatus(String(err));
  }
});

document.getElementById("batchGen916")?.addEventListener("click", async () => {
  const selectedBatches = getSelectedBatchValues();
  if (!selectedBatches.length) { setStatus("Select at least one batch."); return; }
  const runsForBatches = state.runsData.filter((r) => selectedBatches.includes(r.batch));
  if (!runsForBatches.length) { setStatus("No runs found for selected batch(es)."); return; }
  const runIds = runsForBatches.map((r) => r.run_id);
  setStatus(`Batch generating 9:16 for ${runIds.length} run(s)...`);
  try {
    const data = await fetchJSON("/api/batch/generate-images-916", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_ids: runIds, headless: state.headlessModeEnabled }),
    });
    const batchKey = data.batch_key || "";
    if (batchKey && state.headlessModeEnabled) {
      import("./chrome.js").then((m) => m.startProgressPolling(batchKey));
    }
    setStatus(`Done. Batch: ${data.batch_key}, Prompts: ${data.total_prompts}`);
    loadRuns();
  } catch (err) {
    setStatus(String(err));
  }
});

document.getElementById("batchDownload")?.addEventListener("click", () => {
  const idx = state.currentRunIndex;
  const run = state.runsData[idx];
  if (!run) { setStatus("No run selected."); return; }
  const a = document.createElement("a");
  a.href = `/api/runs/${run.run_id}/download-batch`;
  a.download = "";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setStatus("Batch download started.");
});
