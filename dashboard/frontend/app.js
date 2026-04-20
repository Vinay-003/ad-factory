const personaListEl = document.getElementById("personaList");
const globalFormatsEl = document.getElementById("globalFormats");
const activeImagesEl = document.getElementById("activeImages");
const defaultsInfoEl = document.getElementById("defaultsInfo");
const statusEl = document.getElementById("status");
const runsEl = document.getElementById("runs");
const themeToggleEl = document.getElementById("themeToggle");
const providerSelectEl = document.getElementById("opencodeProvider");
const modelSelectEl = document.getElementById("opencodeModel");

const formats = ["HERO", "BA", "TEST", "FEAT", "UGC"];
let defaultData = null;
let selectedGlobalFormats = new Set(["HERO"]);
let modelsByProvider = {};

function setSelectOptions(selectEl, values, selectedValue) {
  selectEl.innerHTML = "";
  values.forEach((value) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    if (selectedValue && selectedValue === value) opt.selected = true;
    selectEl.appendChild(opt);
  });
}

function renderModelOptions(provider, preferredModel = "") {
  const models = modelsByProvider[provider] || [];
  const selected = preferredModel && models.includes(preferredModel) ? preferredModel : (models[0] || "");
  setSelectOptions(modelSelectEl, models.length ? models : [""], selected);
}

function applyTheme(theme) {
  document.body.setAttribute("data-theme", theme);
  localStorage.setItem("dashboard_theme", theme);
  if (themeToggleEl) {
    themeToggleEl.textContent = theme === "dark" ? "Light mode" : "Dark mode";
  }
}

function initTheme() {
  const saved = localStorage.getItem("dashboard_theme");
  if (saved === "dark" || saved === "light") {
    applyTheme(saved);
    return;
  }
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(prefersDark ? "dark" : "light");
}

function chip(label, active, onClick) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = `chip ${active ? "active" : ""}`;
  el.textContent = label;
  el.onclick = onClick;
  return el;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function getPersonaSelection() {
  const boxes = [...document.querySelectorAll(".persona-check")];
  return boxes.filter((x) => x.checked).map((x) => Number(x.value));
}

function getFormatsByPersona() {
  const map = {};
  for (const persona of defaultData.personas) {
    const selected = [];
    for (const fmt of formats) {
      const id = `p-${persona.number}-${fmt}`;
      const el = document.getElementById(id);
      if (el && el.checked) selected.push(fmt);
    }
    map[String(persona.number)] = selected;
  }
  return map;
}

function renderGlobalFormats() {
  globalFormatsEl.innerHTML = "";
  formats.forEach((fmt) => {
    globalFormatsEl.appendChild(chip(fmt, selectedGlobalFormats.has(fmt), () => {
      if (selectedGlobalFormats.has(fmt)) selectedGlobalFormats.delete(fmt);
      else selectedGlobalFormats.add(fmt);
      renderGlobalFormats();
    }));
  });

  const applyBtn = document.createElement("button");
  applyBtn.type = "button";
  applyBtn.textContent = "Apply to all personas";
  applyBtn.onclick = () => {
    for (const persona of defaultData.personas) {
      for (const fmt of formats) {
        const el = document.getElementById(`p-${persona.number}-${fmt}`);
        if (el) el.checked = selectedGlobalFormats.has(fmt);
      }
    }
  };
  globalFormatsEl.appendChild(applyBtn);
}

function renderPersonas() {
  personaListEl.innerHTML = "";
  defaultData.personas.forEach((p) => {
    const card = document.createElement("div");
    card.className = "persona";

    const main = document.createElement("label");
    main.innerHTML = `<input class="persona-check" type="checkbox" value="${p.number}" /> ${p.number}. ${p.name}`;
    card.appendChild(main);

    const chips = document.createElement("div");
    chips.className = "chips";
    formats.forEach((fmt) => {
      const lbl = document.createElement("label");
      lbl.className = "chip";
      lbl.innerHTML = `<input id="p-${p.number}-${fmt}" type="checkbox" style="margin-right:6px;"/> ${fmt}`;
      chips.appendChild(lbl);
    });
    card.appendChild(chips);

    personaListEl.appendChild(card);
  });
}

async function fetchDefaults() {
  const res = await fetch("/api/defaults");
  if (!res.ok) throw new Error("Failed to load defaults");
  defaultData = await res.json();
  renderPersonas();
  renderGlobalFormats();
  activeImagesEl.value = (defaultData.active_images || []).join("\n");
  defaultsInfoEl.textContent = `Using defaults: product=${defaultData.default_files.product_info}, mechanism=${defaultData.default_files.mechanism}, faq=${defaultData.default_files.faq}, persona_txt=${defaultData.default_files.persona_txt}`;

  const opencode = defaultData.opencode || {};
  modelsByProvider = opencode.models_by_provider || {};
  document.getElementById("opencodeApiUrl").value = opencode.api_url || "http://127.0.0.1:4090";

  const providers = opencode.providers || Object.keys(modelsByProvider);
  const defaultModel = opencode.default_model || "";
  const defaultProvider = defaultModel.includes("/") ? defaultModel.split("/", 1)[0] : (providers[0] || "");

  setSelectOptions(providerSelectEl, providers.length ? providers : [""], defaultProvider);
  renderModelOptions(defaultProvider, defaultModel);
}

function fileInput(id) {
  return document.getElementById(id);
}

async function runPipeline() {
  const selectedPersonas = getPersonaSelection();
  if (!selectedPersonas.length) {
    setStatus("Select at least one persona.");
    return;
  }

  const generateImages = document.getElementById("generateImages").checked;
  const cfg = {
    selected_personas: selectedPersonas,
    global_formats: [...selectedGlobalFormats],
    formats_by_persona: getFormatsByPersona(),
    active_image_urls: activeImagesEl.value.split("\n").map((x) => x.trim()).filter(Boolean),
    generate_images: generateImages,
    kie_api_key: document.getElementById("kieApiKey").value.trim(),
    opencode_api_url: document.getElementById("opencodeApiUrl").value.trim(),
    opencode_api_key: document.getElementById("opencodeApiKey").value.trim(),
    opencode_model: (modelSelectEl.value || "").trim(),
  };

  const form = new FormData();
  form.append("config", JSON.stringify(cfg));

  const uploads = [
    ["product_info_file", fileInput("productFile")],
    ["mechanism_file", fileInput("mechanismFile")],
    ["faq_file", fileInput("faqFile")],
    ["persona_txt_file", fileInput("personaTxtFile")],
    ["persona_csv_file", fileInput("personaCsvFile")],
    ["active_images_file", fileInput("activeImagesFile")],
  ];

  uploads.forEach(([name, input]) => {
    if (input.files && input.files[0]) form.append(name, input.files[0]);
  });

  setStatus("Running pipeline... this can take time.");
  const res = await fetch("/api/runs/execute", { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) {
    setStatus(`Failed: ${data.detail || "unknown error"}`);
    return;
  }
  setStatus(`Done\nRun: ${data.run_id}\nBatch: ${data.batch}\nLLM mode: ${data.llm_mode}\nPrompts: ${data.prompt_files.length}\nImages: ${data.image_files.length}`);
  await loadRuns();
}

function renderRun(run) {
  const div = document.createElement("div");
  div.className = "run";

  const title = document.createElement("div");
  title.innerHTML = `<strong>${run.run_id}</strong> | batch ${run.batch} | prompts ${run.prompt_files.length} | images ${run.image_files.length}`;
  div.appendChild(title);

  const llm = document.createElement("div");
  llm.textContent = `Updated: ${run.updated_at || "-"}`;
  div.appendChild(llm);

  if (run.prompt_files && run.prompt_files.length) {
    const p = document.createElement("div");
    p.innerHTML = `<strong>Prompt files</strong>`;
    div.appendChild(p);
    run.prompt_files.forEach((path) => {
      const a = document.createElement("a");
      a.href = `/output/${path.replace(/^output\//, "")}`;
      a.target = "_blank";
      a.textContent = path;
      div.appendChild(a);
      div.appendChild(document.createElement("br"));
    });
  }

  if (run.image_files && run.image_files.length) {
    const p = document.createElement("div");
    p.style.marginTop = "6px";
    p.innerHTML = `<strong>Image files</strong>`;
    div.appendChild(p);
    run.image_files.slice(0, 20).forEach((path) => {
      const a = document.createElement("a");
      a.href = `/generated_image/${path.replace(/^generated_image\//, "")}`;
      a.target = "_blank";
      a.textContent = path;
      div.appendChild(a);
      div.appendChild(document.createElement("br"));
    });
  }

  return div;
}

async function loadRuns() {
  const res = await fetch("/api/runs");
  if (!res.ok) return;
  const data = await res.json();
  runsEl.innerHTML = "";
  (data.runs || []).forEach((run) => runsEl.appendChild(renderRun(run)));
}

document.getElementById("runBtn").addEventListener("click", () => {
  runPipeline().catch((err) => setStatus(String(err)));
});

document.getElementById("refreshRuns").addEventListener("click", () => {
  loadRuns().catch(() => {});
});

if (providerSelectEl) {
  providerSelectEl.addEventListener("change", () => {
    renderModelOptions(providerSelectEl.value, "");
  });
}

if (themeToggleEl) {
  themeToggleEl.addEventListener("click", () => {
    const current = document.body.getAttribute("data-theme") === "dark" ? "dark" : "light";
    applyTheme(current === "dark" ? "light" : "dark");
  });
}

initTheme();
fetchDefaults().then(loadRuns).catch((err) => setStatus(String(err)));
