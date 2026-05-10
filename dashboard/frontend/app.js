const personaListEl = document.getElementById("personaList");
const globalFormatsEl = document.getElementById("globalFormats");
const inputImageFilesEl = document.getElementById("inputImageFiles");
const clearInputImagesEl = document.getElementById("clearInputImages");
const defaultsInfoEl = document.getElementById("defaultsInfo");
const statusEl = document.getElementById("status");
const runsEl = document.getElementById("runs");
const runPrevEl = document.getElementById("runPrev");
const runNextEl = document.getElementById("runNext");
const runIndexEl = document.getElementById("runIndex");
const themeToggleEl = document.getElementById("themeToggle");
const languageModesEl = document.getElementById("languageModes");
const providerSelectEl = document.getElementById("opencodeProvider");
const modelSelectEl = document.getElementById("opencodeModel");
const hypothesisTypeEl = document.getElementById("hypothesisType");
const hypothesisVariantEl = document.getElementById("hypothesisVariant");
const hypothesisVariantRowEl = document.getElementById("hypothesisVariantRow");
const hypothesisSummaryEl = document.getElementById("hypothesisSummary");

const formats = ["HERO", "BA", "TEST", "FEAT", "UGC"];
const languageModes = ["ALL", "EN", "HI", "HINGLISH"];
let defaultData = null;
let selectedGlobalFormats = new Set(["HERO"]);
let selectedLanguageMode = "ALL";
let modelsByProvider = {};
let runsData = [];
let currentRunIndex = 0;
let hypothesisConfig = { type: "none", variant: "" };
let currentServerType = "opencode";
let headlessModeEnabled = false;

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
  applyBtn.className = "ghost-btn";
  applyBtn.textContent = "Apply to selected personas";
  applyBtn.onclick = () => {
    const selectedPersonas = new Set(getPersonaSelection());
    if (!selectedPersonas.size) {
      setStatus("Select at least one persona to apply global formats.");
      return;
    }
    for (const persona of defaultData.personas) {
      if (!selectedPersonas.has(persona.number)) continue;
      for (const fmt of formats) {
        const el = document.getElementById(`p-${persona.number}-${fmt}`);
        if (el) {
          el.checked = selectedGlobalFormats.has(fmt);
          el.dispatchEvent(new Event("change"));
        }
      }
    }
  };
  globalFormatsEl.appendChild(applyBtn);
}

function renderLanguageModes() {
  if (!languageModesEl) return;
  languageModesEl.innerHTML = "";
  languageModes.forEach((mode) => {
    languageModesEl.appendChild(chip(mode, selectedLanguageMode === mode, () => {
      selectedLanguageMode = mode;
      renderLanguageModes();
    }));
  });
}

function renderHypothesisUI() {
  if (!hypothesisTypeEl || !defaultData) return;
  const vars = defaultData.hypothesis?.variables || {};

  hypothesisTypeEl.innerHTML = "";
  Object.entries(vars).forEach(([key, defn]) => {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = defn.label || key;
    if (hypothesisConfig.type === key) opt.selected = true;
    hypothesisTypeEl.appendChild(opt);
  });

  updateHypothesisVariantOptions();
  updateHypothesisSummary();
}

function updateHypothesisVariantOptions() {
  if (!hypothesisVariantEl || !defaultData) return;
  const type = hypothesisTypeEl.value;
  const vars = defaultData.hypothesis?.variables || {};
  const defn = vars[type];

  if (!defn || !defn.options || defn.options.length === 0) {
    hypothesisVariantRowEl?.classList.add("hidden");
    return;
  }

  hypothesisVariantRowEl?.classList.remove("hidden");

  hypothesisVariantEl.innerHTML = "";
  defn.options.forEach((opt) => {
    const option = document.createElement("option");
    option.value = opt.id;
    option.textContent = opt.label;
    if (hypothesisConfig.variant === opt.id) option.selected = true;
    hypothesisVariantEl.appendChild(option);
  });
}

function updateHypothesisSummary() {
  if (!hypothesisSummaryEl || !defaultData) return;
  const type = hypothesisTypeEl.value;
  const vars = defaultData.hypothesis?.variables || {};
  const defn = vars[type];

  if (!defn || type === "none") {
    hypothesisSummaryEl.textContent = "No hypothesis style selected. Ads will generate normally.";
    return;
  }

  const variant = hypothesisVariantEl.value;
  const variantLabel = defn.options?.find((o) => o.id === variant)?.label || variant;

  hypothesisSummaryEl.textContent = `Style: ${defn.label} - ${variantLabel}`;
}

function getHypothesisConfig() {
  const type = hypothesisTypeEl?.value || "none";
  if (type === "none") return { type: "none", variant: "" };
  return {
    type,
    variant: hypothesisVariantEl?.value || "",
  };
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
    chips.className = "chips format-chip-group";
    formats.forEach((fmt) => {
      const lbl = document.createElement("label");
      lbl.className = `chip chip-format fmt-${fmt.toLowerCase()}`;

      const input = document.createElement("input");
      input.id = `p-${p.number}-${fmt}`;
      input.type = "checkbox";
      input.className = "format-check";

      const text = document.createElement("span");
      text.textContent = fmt;

      const syncState = () => {
        lbl.classList.toggle("checked", input.checked);
      };
      input.addEventListener("change", syncState);
      syncState();

      lbl.append(input, text);
      chips.appendChild(lbl);
    });
    card.appendChild(chips);

    card.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest("input") || target.closest("button") || target.closest("label")) return;
      const checkbox = card.querySelector(".persona-check");
      if (!(checkbox instanceof HTMLInputElement)) return;
      checkbox.checked = !checkbox.checked;
    });

    personaListEl.appendChild(card);
  });
}

async function fetchDefaults() {
  const res = await fetch("/api/defaults");
  if (!res.ok) throw new Error("Failed to load defaults");
  defaultData = await res.json();
  renderPersonas();
  renderGlobalFormats();
  renderLanguageModes();
  renderHypothesisUI();
  const imageCount = (defaultData.input_images || []).length;
  defaultsInfoEl.textContent = `Using defaults: product=${defaultData.default_files.product_info}, mechanism=${defaultData.default_files.mechanism}, faq=${defaultData.default_files.faq}, input/images=${imageCount} file(s)`;

  const opencode = defaultData.opencode || {};
  modelsByProvider = opencode.models_by_provider || {};
  document.getElementById("opencodeApiUrl").value = opencode.api_url || "http://127.0.0.1:4090";

  const providers = opencode.providers || Object.keys(modelsByProvider);
  const defaultModel = opencode.default_model || "";
  const defaultProvider = defaultModel.includes("/") ? defaultModel.split("/", 1)[0] : (providers[0] || "");

  setSelectOptions(providerSelectEl, providers.length ? providers : [""], defaultProvider);
  renderModelOptions(defaultProvider, defaultModel);

  // Server type change handler
  document.getElementById("serverType").addEventListener("change", async (e) => {
    currentServerType = e.target.value;
    const apiUrlInput = document.getElementById("opencodeApiUrl");
    
    if (currentServerType === "blackbox") {
      apiUrlInput.value = "http://127.0.0.1:4091";
      try {
        const res = await fetch("http://127.0.0.1:4091/v1/models", {
          headers: { "Authorization": "Basic " + btoa("user:blackbox-local-pass") }
        });
        const data = await res.json();
        const models = data.data || [];
        modelsByProvider = { "blackbox": models.map(m => m.id) };
        setSelectOptions(providerSelectEl, ["blackbox"], "blackbox");
        setSelectOptions(modelSelectEl, models.map(m => m.id), models[0]?.id || "");
      } catch (err) {
        console.error("Failed to fetch Blackbox models:", err);
      }
    } else {
      apiUrlInput.value = "http://127.0.0.1:4090";
      fetchDefaults();
    }
  });
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

  const cfg = {
    selected_personas: selectedPersonas,
    language_mode: selectedLanguageMode,
    global_formats: [...selectedGlobalFormats],
    formats_by_persona: getFormatsByPersona(),
    generate_images: false,
    server_type: currentServerType,
    opencode_api_url: document.getElementById("opencodeApiUrl").value.trim(),
    opencode_api_key: document.getElementById("opencodeApiKey").value.trim(),
    opencode_model: (modelSelectEl.value || "").trim(),
    hypothesis: getHypothesisConfig(),
  };

  const form = new FormData();
  form.append("config", JSON.stringify(cfg));

  const uploads = [
    ["product_info_file", fileInput("productFile")],
    ["mechanism_file", fileInput("mechanismFile")],
    ["faq_file", fileInput("faqFile")],
    ["image_source_file", fileInput("imageSourcesFile")],
  ];

  uploads.forEach(([name, input]) => {
    if (input.files && input.files[0]) form.append(name, input.files[0]);
  });

  if (inputImageFilesEl?.files?.length) {
    [...inputImageFilesEl.files].forEach((file) => form.append("input_image_files", file));
  }
  form.append("clear_input_images", clearInputImagesEl?.checked ? "true" : "false");

  setStatus("Running pipeline... this can take time.");
  const res = await fetch("/api/runs/execute", { method: "POST", body: form });
  const raw = await res.text();
  let data = null;
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    setStatus(`Failed: ${raw || "unknown error"}`);
    return;
  }
  if (!res.ok) {
    setStatus(`Failed: ${data.detail || "unknown error"}`);
    return;
  }
  setStatus(`Done\nRun: ${data.run_id}\nBatch: ${data.batch}\nLLM mode: ${data.llm_mode}\nCopy source: ${data.copy_source || data.llm_mode}\nPrompts: ${data.prompt_files.length}\nImages: ${data.image_files.length}`);
  await loadRuns();
}

function renderRun(run) {
  const div = document.createElement("div");
  div.className = "run run-active";

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

  const promptActions = document.createElement("div");
  promptActions.className = "prompt-actions";
  const loadBtn = document.createElement("button");
  loadBtn.type = "button";
  loadBtn.className = "ghost-btn";
  loadBtn.textContent = "Load editable copy";
  const loadHint = document.createElement("div");
  loadHint.className = "hint";
  loadHint.textContent = "Lazy loaded to keep dashboard fast.";
  promptActions.append(loadBtn, loadHint);
  div.appendChild(promptActions);

  loadBtn.onclick = () => {
    loadBtn.disabled = true;
    loadHint.textContent = "Loading editable on-image copy...";
    fetch(`/api/runs/${run.run_id}/prompt-copies`)
    .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
    .then(({ ok, data }) => {
      if (!ok) {
        loadHint.textContent = `Could not load editable copy: ${data.detail || "unknown error"}`;
        return;
      }

      const prompts = (data.prompts || []).filter((item) => (item.copy_lines || []).length > 0);
      if (!prompts.length) {
        loadHint.textContent = "No editable copy block found for this run.";
        return;
      }
      loadBtn.remove();
      loadHint.remove();

      const controls = document.createElement("div");
      controls.className = "prompt-controls";

      const selectAllBtn = document.createElement("button");
      selectAllBtn.type = "button";
      selectAllBtn.textContent = "Select all";

      const clearBtn = document.createElement("button");
      clearBtn.type = "button";
      clearBtn.textContent = "Clear selection";

      const saveBtn = document.createElement("button");
      saveBtn.type = "button";
      saveBtn.textContent = "Save edited copy";

      const exportCopyBtn = document.createElement("button");
      exportCopyBtn.type = "button";
      exportCopyBtn.textContent = "EXPORT ON-IMAGE COPY";

      const importCopyBtn = document.createElement("button");
      importCopyBtn.type = "button";
      importCopyBtn.textContent = "IMPORT EXCEL & UPDATE PROMPTS";

      const importFileEl = document.createElement("input");
      importFileEl.type = "file";
      importFileEl.accept = ".xlsx";
      importFileEl.style.display = "none";

      exportCopyBtn.onclick = async () => {
        exportCopyBtn.disabled = true;
        try {
          setStatus(`Exporting EXACT ON-IMAGE COPY to XLSX for ${run.run_id}...`);
          const res = await fetch(`/api/runs/${run.run_id}/export-on-image-copy`);
          if (!res.ok) {
            const txt = await res.text();
            setStatus(`Export failed: ${txt || res.statusText}`);
            return;
          }
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          const contentDisposition = res.headers.get("Content-Disposition");
          const fnMatch = contentDisposition && contentDisposition.match(/filename="([^"]+)"/);
          const suggestedName = fnMatch ? fnMatch[1] : `on-image-copy-${run.run_id}.xlsx`;
          a.download = suggestedName;
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
          setStatus(`Export ready: ${run.run_id}`);
        } catch (err) {
          setStatus(String(err));
        } finally {
          exportCopyBtn.disabled = false;
        }
      };

      importCopyBtn.onclick = () => {
        importFileEl.click();
      };

      importFileEl.onchange = async () => {
        const file = importFileEl.files && importFileEl.files[0];
        if (!file) return;

        const previewEl = document.createElement("pre");
        previewEl.className = "status";
        previewEl.style.marginTop = "10px";

        importCopyBtn.disabled = true;
        try {
          setStatus("Importing XLSX and generating preview...");
          const fd = new FormData();
          fd.append("file", file);
          fd.append("confirm", "false");

          const res = await fetch(`/api/runs/${run.run_id}/import-on-image-copy`, {
            method: "POST",
            body: fd,
          });

          const raw = await res.text();
          let data = null;
          try {
            data = raw ? JSON.parse(raw) : {};
          } catch {
            data = { detail: raw };
          }

          if (!res.ok) {
            setStatus(`Import validation failed`);
            previewEl.textContent = JSON.stringify(data.detail || data, null, 2);
            promptActions.appendChild(previewEl);
            return;
          }

          previewEl.textContent =
            `Preview ready for ${data.changed_rows_count} rows (skipped ${data.skipped_rows}):\n` +
            (data.items || [])
              .slice(0, 30)
              .map((x) => `- ${x.prompt_id}: ${x.old_copy} => ${x.new_copy}`)
              .join("\n") +
            ((data.items || []).length > 30 ? `\n... (${(data.items || []).length - 30} more)` : "");

          promptActions.appendChild(previewEl);

          const ok = window.confirm(
            `Preview generated.\nApply changes for ${data.changed_rows_count} rows?\n(Any row skipped/missing exact block will not be modified.)`
          );

          if (!ok) {
            setStatus("Import canceled (no overwrite applied).");
            return;
          }

          setStatus("Applying XLSX changes (exact-block overwrite only)...");
          const fd2 = new FormData();
          fd2.append("file", file);
          fd2.append("confirm", "true");

          const res2 = await fetch(`/api/runs/${run.run_id}/import-on-image-copy`, {
            method: "POST",
            body: fd2,
          });

          const raw2 = await res2.text();
          let data2 = null;
          try {
            data2 = raw2 ? JSON.parse(raw2) : {};
          } catch {
            data2 = { detail: raw2 };
          }

          if (!res2.ok) {
            setStatus("Import apply failed.");
            previewEl.textContent = JSON.stringify(data2.detail || data2, null, 2);
            return;
          }

          setStatus(`Import applied. Updated ${data2.changed_rows_count} rows. Skipped ${data2.skipped_rows}.`);
          await loadRuns();
        } catch (err) {
          setStatus(String(err));
        } finally {
          importCopyBtn.disabled = false;
          importFileEl.value = "";
        }
      };

      const generate916PromptBtn = document.createElement("button");
      generate916PromptBtn.type = "button";
      generate916PromptBtn.textContent = "Generate 9:16 prompts for selected";

      const generate45Btn = document.createElement("button");
      generate45Btn.type = "button";
      generate45Btn.textContent = "Generate 4:5 in Gemini";

      const generate916Btn = document.createElement("button");
      generate916Btn.type = "button";
      generate916Btn.textContent = "Generate 9:16 in Gemini from 4:5 images";

      controls.append(
        selectAllBtn,
        clearBtn,
        saveBtn,
        exportCopyBtn,
        importCopyBtn,
        generate916PromptBtn,
        generate45Btn,
        generate916Btn
      );

      promptActions.appendChild(controls);

      const editorList = document.createElement("div");
      editorList.className = "prompt-editor-list";
      promptActions.appendChild(editorList);

      const items = [];
      prompts.forEach((prompt) => {
        const card = document.createElement("div");
        card.className = "prompt-editor";

        const top = document.createElement("div");
        top.className = "prompt-editor-top";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = true;
        const link = document.createElement("a");
        link.href = prompt.review_url;
        link.target = "_blank";
        link.textContent = prompt.prompt_file;
        top.append(checkbox, link);
        card.appendChild(top);

        const lineInputs = [];
        (prompt.copy_lines || []).forEach((line) => {
          const row = document.createElement("div");
          row.className = "prompt-line";
          const label = document.createElement("label");
          label.textContent = line.label;
          const input = document.createElement("input");
          input.type = "text";
          input.value = line.value || "";
          row.append(label, input);
          card.appendChild(row);
          lineInputs.push({ label: line.label, input });
        });

        items.push({ promptFile: prompt.prompt_file, personaNumber: prompt.persona_number, checkbox, lineInputs });
        editorList.appendChild(card);
      });

      selectAllBtn.onclick = () => {
        items.forEach((item) => {
          item.checkbox.checked = true;
        });
      };
      clearBtn.onclick = () => {
        items.forEach((item) => {
          item.checkbox.checked = false;
        });
      };

      saveBtn.onclick = async () => {
        saveBtn.disabled = true;
        try {
          const edits = items.map((item) => ({
            prompt_file: item.promptFile,
            persona_number: item.personaNumber,
            copy_lines: item.lineInputs.map((line) => ({ label: line.label, value: line.input.value.trim() })),
          }));
          const res = await fetch(`/api/runs/${run.run_id}/prompt-copies`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ edits }),
          });
          const raw = await res.text();
          let data = null;
          try {
            data = raw ? JSON.parse(raw) : {};
          } catch {
            setStatus(`Failed: ${raw || "save error"}`);
            return;
          }
          if (!res.ok) {
            setStatus(`Failed: ${data.detail || "save error"}`);
            return;
          }
          setStatus(`Saved edited copy for ${run.run_id}. Prompt files regenerated.`);
          await loadRuns();
        } catch (err) {
          setStatus(String(err));
        } finally {
          saveBtn.disabled = false;
        }
      };

      generate916PromptBtn.onclick = async () => {
        const selected = items.filter((item) => item.checkbox.checked).map((item) => item.promptFile);
        if (!selected.length) {
          setStatus("Select at least one 4:5 prompt.");
          return;
        }

        generate916PromptBtn.disabled = true;
        setStatus(`Generating 9:16 prompts for ${selected.length} selected 4:5 prompt(s) from ${run.run_id}...`);
        try {
          const res = await fetch(`/api/runs/${run.run_id}/generate-916-selected`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt_files: selected }),
          });
          const raw = await res.text();
          let data = null;
          try {
            data = raw ? JSON.parse(raw) : {};
          } catch {
            setStatus(`Failed: ${raw || "9:16 prompt generation error"}`);
            return;
          }
          if (!res.ok) {
            setStatus(`Failed: ${data.detail || "9:16 prompt generation error"}`);
            return;
          }
          setStatus(`Done\nRun: ${data.run_id}\nBatch: ${data.batch}\nGenerated 9:16 prompts for selected items`);
          await loadRuns();
        } catch (err) {
          setStatus(String(err));
        } finally {
          generate916PromptBtn.disabled = false;
        }
      };

      generate45Btn.onclick = async () => {
        const selected = items.filter((item) => item.checkbox.checked).map((item) => item.promptFile);
        if (!selected.length) {
          setStatus("Select at least one prompt.");
          return;
        }
        generate45Btn.disabled = true;
        setStatus(`Generating 4:5 images in Gemini for ${selected.length} selected prompt(s) from ${run.run_id}...`);
        try {
          const res = await fetch(`/api/runs/${run.run_id}/generate-images-45`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt_files: selected, headless: headlessModeEnabled }),
          });
          const raw = await res.text();
          let data = null;
          try {
            data = raw ? JSON.parse(raw) : {};
          } catch {
            stopProgressPolling();
            setStatus(`Failed: ${raw || "image generation error"}`);
            return;
          }
          if (!res.ok) {
            stopProgressPolling();
            setStatus(`Failed: ${data.detail || "image generation error"}`);
            return;
          }
          const batchKey = data.batch_key || data.run_id || "";
          if (batchKey && headlessModeEnabled) {
            startProgressPolling(batchKey);
          }
          setStatus(`Done\nRun: ${data.run_id}\nBatch: ${data.batch}\nGenerated 4:5 in Gemini for selected prompts: ${selected.length}`);
          stopProgressPolling();
          await loadRuns();
        } catch (err) {
          stopProgressPolling();
          setStatus(String(err));
        } finally {
          generate45Btn.disabled = false;
        }
      };

      generate916Btn.onclick = async () => {
        const selected = items.filter((item) => item.checkbox.checked).map((item) => item.promptFile);
        if (!selected.length) {
          setStatus("Select at least one prompt.");
          return;
        }
        generate916Btn.disabled = true;
        setStatus(`Generating 9:16 in Gemini from selected 4:5 image references for ${selected.length} prompt(s)...`);
        try {
          const res = await fetch(`/api/runs/${run.run_id}/generate-images-916-from-45`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt_files: selected, headless: headlessModeEnabled }),
          });
          const raw = await res.text();
          let data = null;
          try {
            data = raw ? JSON.parse(raw) : {};
          } catch {
            stopProgressPolling();
            setStatus(`Failed: ${raw || "9:16 generation error"}`);
            return;
          }
          if (!res.ok) {
            stopProgressPolling();
            setStatus(`Failed: ${data.detail || "9:16 generation error"}`);
            return;
          }
          const batchKey = data.batch || "";
          if (batchKey && headlessModeEnabled) {
            startProgressPolling(batchKey);
          }
          setStatus(`Done\nRun: ${data.run_id}\nBatch: ${data.batch}\nGenerated 9:16 in Gemini from selected 4:5 refs`);
          stopProgressPolling();
          await loadRuns();
        } catch (err) {
          stopProgressPolling();
          setStatus(String(err));
        } finally {
          generate916Btn.disabled = false;
        }
      };
    })
    .catch((err) => {
      loadHint.textContent = `Could not load editable copy: ${String(err)}`;
      loadBtn.disabled = false;
    });
  };

  if (run.image_files && run.image_files.length) {
    const p = document.createElement("div");
    p.style.marginTop = "6px";
    p.innerHTML = `<strong>Image files</strong>`;
    div.appendChild(p);
    run.image_files.forEach((path) => {
      const a = document.createElement("a");
      a.href = path.startsWith("generated_images/")
        ? `/generated_images/${path.replace(/^generated_images\//, "")}`
        : `/generated_image/${path.replace(/^generated_image\//, "")}`;
      a.target = "_blank";
      a.textContent = path;
      div.appendChild(a);
      div.appendChild(document.createElement("br"));
    });
  }

  return div;
}

function updateRunNav() {
  const total = runsData.length;
  const latestBatch = total ? (runsData[0].batch || "-") : "-";
  if (runIndexEl) {
    const position = total ? `${currentRunIndex + 1}/${total}` : "0/0";
    runIndexEl.textContent = `${position} | latest batch ${latestBatch}`;
  }
  if (runPrevEl) runPrevEl.disabled = total <= 1;
  if (runNextEl) runNextEl.disabled = total <= 1;
}

function renderRunCarousel() {
  runsEl.innerHTML = "";
  if (!runsData.length) {
    const empty = document.createElement("div");
    empty.className = "hint";
    empty.textContent = "No runs yet.";
    runsEl.appendChild(empty);
    updateRunNav();
    return;
  }

  if (currentRunIndex < 0) currentRunIndex = 0;
  if (currentRunIndex >= runsData.length) currentRunIndex = runsData.length - 1;

  // Lazy render: only current run card is mounted.
  runsEl.appendChild(renderRun(runsData[currentRunIndex]));
  updateRunNav();
}

function getSelectedBatchValues() {
  return Array.from(document.querySelectorAll(".batch-check:checked")).map((c) => c.value);
}

function updateBatchDropdownButtonLabel() {
  const btn = document.getElementById("batchDropdownBtn");
  if (!btn) return;

  const selectedCount = getSelectedBatchValues().length;
  btn.textContent = selectedCount ? `${selectedCount} batch(es) selected` : "Select batch(es)";
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

let batchDropdownInitialized = false;

async function loadRuns() {
  const res = await fetch("/api/runs");
  if (!res.ok) return;
  const data = await res.json();
  runsData = data.runs || [];
  currentRunIndex = 0;

  const batchMenu = document.getElementById("batchDropdownMenu");
  batchMenu.innerHTML = "";

  const batches = new Set();
  runsData.forEach((r) => {
    if (r.batch) batches.add(r.batch);
  });

  const grid = document.createElement("div");
  grid.className = "batch-grid";

  const batchList = Array.from(batches).sort().reverse();
  // UX requirement: split the grid into halves (top/bottom).
  // If odd count, add one more column (i.e., ceil(N/2) columns over 2 rows).
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

    cb.addEventListener("change", () => updateBatchDropdownButtonLabel());

    // UX: clicking the tile toggles checkbox (check/uncheck).
    item.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;

      // If user directly clicks the checkbox, let default behavior + change event run.
      if (target.closest("input[type='checkbox']")) return;

      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event("change", { bubbles: true }));
    });

    item.append(cb, labelSpan);
    grid.appendChild(item);
  });

  batchMenu.appendChild(grid);

  // Initialize dropdown behaviors once
  if (!batchDropdownInitialized) {
    batchDropdownInitialized = true;

    const dropdownRoot = document.querySelector(".batch-dropdown");
    const btn = document.getElementById("batchDropdownBtn");

    btn?.addEventListener("click", (e) => {
      e.stopPropagation();
      const menu = document.getElementById("batchDropdownMenu");
      if (!menu) return;
      if (menu.classList.contains("hidden")) openBatchDropdown();
      else closeBatchDropdown();
    });

    document.addEventListener("click", (e) => {
      const menu = document.getElementById("batchDropdownMenu");
      if (!menu || menu.classList.contains("hidden")) return;

      const target = e.target;
      if (!(target instanceof Node)) return;

      // Close if click is outside the batch dropdown widget
      if (dropdownRoot && !dropdownRoot.contains(target)) closeBatchDropdown();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeBatchDropdown();
    });
  }

  // Default label state: based on whatever is checked (probably none after refresh)
  updateBatchDropdownButtonLabel();

  renderRunCarousel();
}

document.getElementById("runBtn").addEventListener("click", () => {
  runPipeline().catch((err) => setStatus(String(err)));
});

document.getElementById("refreshRuns").addEventListener("click", () => {
  loadRuns().catch(() => {});
});


document.getElementById("batchGen45").addEventListener("click", async () => {
  const checks = document.querySelectorAll(".batch-check:checked");
  const selectedBatches = Array.from(checks).map((c) => c.value);
  if (!selectedBatches.length) {
    setStatus("Select at least one batch.");
    return;
  }
  const runsForBatches = runsData.filter((r) => selectedBatches.includes(r.batch));
  if (!runsForBatches.length) {
    setStatus("No runs found for selected batch(es).");
    return;
  }
  const runIds = runsForBatches.map((r) => r.run_id);
  setStatus(`Batch generating 4:5 for ${runIds.length} run(s)...`);
  try {
    const res = await fetch("/api/batch/generate-images-45", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_ids: runIds, headless: headlessModeEnabled }),
    });
    const data = await res.json();
    if (!res.ok) {
      stopProgressPolling();
      setStatus(`Failed: ${data.detail || "batch 4:5 error"}`);
      return;
    }
    const batchKey = data.batch_key || "";
    if (batchKey && headlessModeEnabled) {
      startProgressPolling(batchKey);
    }
    setStatus(`Done. Batch: ${data.batch_key}, Prompts: ${data.total_prompts}`);
    stopProgressPolling();
    await loadRuns();
  } catch (err) {
    stopProgressPolling();
    setStatus(String(err));
  }
});

document.getElementById("batchGen916").addEventListener("click", async () => {
  const checks = document.querySelectorAll(".batch-check:checked");
  const selectedBatches = Array.from(checks).map((c) => c.value);
  if (!selectedBatches.length) {
    setStatus("Select at least one batch.");
    return;
  }
  const runsForBatches = runsData.filter((r) => selectedBatches.includes(r.batch));
  if (!runsForBatches.length) {
    setStatus("No runs found for selected batch(es).");
    return;
  }
  const runIds = runsForBatches.map((r) => r.run_id);
  setStatus(`Batch generating 9:16 for ${runIds.length} run(s) (no input images)...`);
  try {
    const res = await fetch("/api/batch/generate-images-916", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_ids: runIds, headless: headlessModeEnabled }),
    });
    const data = await res.json();
    if (!res.ok) {
      stopProgressPolling();
      setStatus(`Failed: ${data.detail || "batch 9:16 error"}`);
      return;
    }
    const batchKey = data.batch_key || "";
    if (batchKey && headlessModeEnabled) {
      startProgressPolling(batchKey);
    }
    setStatus(`Done. Batch: ${data.batch_key}, Prompts: ${data.total_prompts}`);
    stopProgressPolling();
    await loadRuns();
  } catch (err) {
    stopProgressPolling();
    setStatus(String(err));
  }
});

if (runPrevEl) {
  runPrevEl.addEventListener("click", () => {
    if (!runsData.length) return;
    currentRunIndex = (currentRunIndex - 1 + runsData.length) % runsData.length;
    renderRunCarousel();
  });
}

if (runNextEl) {
  runNextEl.addEventListener("click", () => {
    if (!runsData.length) return;
    currentRunIndex = (currentRunIndex + 1) % runsData.length;
    renderRunCarousel();
  });
}

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

if (hypothesisTypeEl) {
  hypothesisTypeEl.addEventListener("change", () => {
    updateHypothesisVariantOptions();
    updateHypothesisSummary();
  });
}

if (hypothesisVariantEl) {
  hypothesisVariantEl.addEventListener("change", updateHypothesisSummary);
}

let currentPollingInterval = null;

function startProgressPolling(batchKey) {
  if (currentPollingInterval) clearInterval(currentPollingInterval);
  currentPollingInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/progress/${encodeURIComponent(batchKey)}`);
      if (!res.ok) {
        if (res.status === 404) {
          clearInterval(currentPollingInterval);
          return;
        }
        return;
      }
      const data = await res.json();
      const step = data.step || "";
      const msg = data.message || "";
      const time = data.time ? new Date(data.time * 1000).toLocaleTimeString() : "";
      setStatus(`[${time}] [${step}] ${msg}\n`);
    } catch (_) {}
  }, 3000);
}

function stopProgressPolling() {
  if (currentPollingInterval) {
    clearInterval(currentPollingInterval);
    currentPollingInterval = null;
  }
}

initTheme();
fetchDefaults().then(loadRuns).catch((err) => setStatus(String(err)));

const headlessToggle = document.getElementById("headlessMode");
if (headlessToggle) {
  headlessToggle.addEventListener("change", () => {
    headlessModeEnabled = headlessToggle.checked;
    setStatus(`Headless mode ${headlessModeEnabled ? "ON" : "OFF"}`);
  });
}
