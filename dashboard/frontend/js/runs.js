import { state } from "./state.js";
import { appendLog, skeletonRunCard } from "./ui.js";
import { fetchJSON, invalidateRuns } from "./api.js";
import { buildImageGallery } from "./images.js";
import { buildPromptEditor } from "./prompts.js";
import { refreshSelect } from "./custom-select.js";

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

function updateBackgroundReuseRunOptions() {
  const select = document.getElementById("backgroundReuseRun");
  if (!select) return;
  const previous = select.value;
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "Select previous batch/run";
  select.appendChild(empty);
  state.runsData.forEach((run) => {
    const label = run.batch || run.run_id;
    const opt = document.createElement("option");
    opt.value = run.run_id;
    opt.textContent = label;
    select.appendChild(opt);
  });
  if (previous && Array.from(select.options).some((opt) => opt.value === previous)) {
    select.value = previous;
  }
  refreshSelect(select);
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
    updateBackgroundReuseRunOptions();

    const batchMenu = document.getElementById("batchDropdownMenu");
    batchMenu.innerHTML = "";

    const batches = new Set();
    state.runsData.forEach((r) => { if (r.batch) batches.add(r.batch); });

    const grid = document.createElement("div");
    grid.className = "batch-grid";
    const batchList = Array.from(batches).sort().reverse();
    const num = batchList.length;
    const cols = Math.max(1, Math.ceil(Math.sqrt(num)));
    const rows = Math.max(1, Math.ceil(num / cols));
    grid.style.gridTemplateColumns = `repeat(${cols}, minmax(140px, 1fr))`;
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
  if (!selectedBatches.length) { appendLog("Select at least one batch."); return; }

  const engine = await showEngineSelector();
  if (!engine) return;

  const runsForBatches = state.runsData.filter((r) => selectedBatches.includes(r.batch));
  if (!runsForBatches.length) { appendLog("No runs found for selected batch(es)."); return; }
  const runIds = runsForBatches.map((r) => r.run_id);
  const engineLabel = engine === "chatgpt" ? "ChatGPT" : "Gemini";
  appendLog(`Batch generating 4:5 in ${engineLabel} for ${runIds.length} run(s)...`);
  try {
    const data = await fetchJSON("/api/batch/generate-images-45", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_ids: runIds, headless: state.headlessModeEnabled, engine }),
    });
    const batchKey = data.batch_key || "";
    if (batchKey && state.headlessModeEnabled) {
      import("./chrome.js").then((m) => m.startProgressPolling(batchKey));
    }
    appendLog(`Done. Batch: ${data.batch_key}, Prompts: ${data.total_prompts}`);
    loadRuns();
  } catch (err) {
    appendLog(String(err));
  }
});

document.getElementById("batchGen916")?.addEventListener("click", async () => {
  const selectedBatches = getSelectedBatchValues();
  if (!selectedBatches.length) { appendLog("Select at least one batch."); return; }
  const runsForBatches = state.runsData.filter((r) => selectedBatches.includes(r.batch));
  if (!runsForBatches.length) { appendLog("No runs found for selected batch(es)."); return; }
  const runIds = runsForBatches.map((r) => r.run_id);
  appendLog(`Batch generating 9:16 for ${runIds.length} run(s)...`);
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
    appendLog(`Done. Batch: ${data.batch_key}, Prompts: ${data.total_prompts}`);
    loadRuns();
  } catch (err) {
    appendLog(String(err));
  }
});

document.getElementById("batchDownload")?.addEventListener("click", async () => {
  const selectedBatches = getSelectedBatchValues();
  if (!selectedBatches.length) { appendLog("Select at least one batch from the dropdown."); return; }
  appendLog(`Preparing download for ${selectedBatches.length} batch(es)...`);
  try {
    const res = await fetch("/api/runs/download-batches", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch_ids: selectedBatches }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      appendLog(`Download failed: ${err.detail || res.statusText}`);
      return;
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?(.+?)"?$/);
    a.download = match ? match[1] : `${selectedBatches.join("_")}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
    appendLog("Batch download complete.");
  } catch (err) {
    appendLog(`Download error: ${String(err)}`);
  }
});

function showEngineSelector() {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "engine-selector-overlay";
    overlay.innerHTML = `
      <div class="engine-selector-modal">
        <h3>Select Image Generation Engine</h3>
        <p>Choose which engine to use for generating 4:5 images:</p>
        <div class="engine-options">
          <button class="engine-option-btn" data-engine="gemini">
            <span class="engine-name">Gemini</span>
            <span class="engine-desc">Google Gemini image generation</span>
          </button>
          <button class="engine-option-btn" data-engine="chatgpt">
            <span class="engine-name">ChatGPT</span>
            <span class="engine-desc">OpenAI ChatGPT image generation</span>
          </button>
        </div>
        <button class="engine-cancel-btn">Cancel</button>
      </div>
    `;

    document.body.appendChild(overlay);

    const cleanup = () => overlay.remove();

    overlay.querySelector(".engine-cancel-btn").onclick = () => {
      cleanup();
      resolve(null);
    };

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        cleanup();
        resolve(null);
      }
    });

    overlay.querySelectorAll(".engine-option-btn").forEach((btn) => {
      btn.onclick = () => {
        cleanup();
        resolve(btn.dataset.engine);
      };
    });

    document.addEventListener("keydown", function handler(e) {
      if (e.key === "Escape") {
        document.removeEventListener("keydown", handler);
        cleanup();
        resolve(null);
      }
    });
  });
}
