import { state, getPersonaSelection, getFormatsByPersona, getHypothesisConfig, loadDefaults } from "./state.js";
import { setStatus, setSelectOptions } from "./ui.js";
import { renderPersonas, showPersonaSkeletons, renderGlobalFormats, renderLanguageModes } from "./personas.js";
import { renderHypothesisUI } from "./hypothesis.js";
import { loadRuns as loadAndRenderRuns, showRunsSkeletons } from "./runs.js";
import { stopProgressPolling } from "./chrome.js";
import { initTheme } from "./theme.js";
import { fetchJSON, invalidateRuns } from "./api.js";

const providerSelectEl = document.getElementById("opencodeProvider");
const modelSelectEl = document.getElementById("opencodeModel");
const defaultsInfoEl = document.getElementById("defaultsInfo");

function renderModelOptions(provider, preferredModel = "") {
  const models = state.modelsByProvider[provider] || [];
  const selected = preferredModel && models.includes(preferredModel) ? preferredModel : (models[0] || "");
  setSelectOptions(modelSelectEl, models.length ? models : [""], selected);
}

async function initDefaults() {
  showPersonaSkeletons();
  try {
    const data = await loadDefaults();
    renderPersonas();
    renderGlobalFormats();
    renderLanguageModes();
    renderHypothesisUI();

    const imageCount = (data.input_images || []).length;
    defaultsInfoEl.textContent = `Using defaults: product=${data.default_files.product_info}, mechanism=${data.default_files.playbook}, input/images=${imageCount} file(s)`;

    const opencode = data.opencode || {};
    state.modelsByProvider = opencode.models_by_provider || {};
    document.getElementById("opencodeApiUrl").value = opencode.api_url || "http://127.0.0.1:4090";

    const providers = opencode.providers || Object.keys(state.modelsByProvider);
    const defaultModel = opencode.default_model || "";
    const defaultProvider = defaultModel.includes("/") ? defaultModel.split("/", 1)[0] : (providers[0] || "");

    setSelectOptions(providerSelectEl, providers.length ? providers : [""], defaultProvider);
    renderModelOptions(defaultProvider, defaultModel);
  } catch (err) {
    setStatus(`Failed to load defaults: ${String(err)}`);
  }
}

const runBtn = document.getElementById("runBtn");

async function runPipeline() {
  const selectedPersonas = getPersonaSelection();
  if (!selectedPersonas.length) {
    setStatus("Select at least one persona.");
    return;
  }

  const cfg = {
    selected_personas: selectedPersonas,
    language_mode: state.selectedLanguageMode,
    global_formats: [...state.selectedGlobalFormats],
    formats_by_persona: getFormatsByPersona(),
    generate_images: false,
    server_type: state.currentServerType,
    opencode_api_url: document.getElementById("opencodeApiUrl").value.trim(),
    opencode_api_key: document.getElementById("opencodeApiKey").value.trim(),
    opencode_model: (modelSelectEl.value || "").trim(),
    hypothesis: getHypothesisConfig(),
  };

  const form = new FormData();
  form.append("config", JSON.stringify(cfg));

  const uploads = [
    ["product_info_file", document.getElementById("productFile")],
    ["mechanism_file", document.getElementById("mechanismFile")],
    ["faq_file", document.getElementById("faqFile")],
    ["image_source_file", document.getElementById("imageSourcesFile")],
  ];
  uploads.forEach(([name, input]) => {
    if (input.files && input.files[0]) form.append(name, input.files[0]);
  });

  const inputImageFilesEl = document.getElementById("inputImageFiles");
  const clearInputImagesEl = document.getElementById("clearInputImages");
  if (inputImageFilesEl?.files?.length) {
    [...inputImageFilesEl.files].forEach((file) => form.append("input_image_files", file));
  }
  form.append("clear_input_images", clearInputImagesEl?.checked ? "true" : "false");

  setStatus("Running pipeline... this can take time.");
  if (runBtn) {
    runBtn.disabled = true;
    runBtn.classList.add("is-loading");
  }
  try {
    const data = await fetchJSON("/api/runs/execute", { method: "POST", body: form });
    setStatus(`Done\nRun: ${data.run_id}\nBatch: ${data.batch}\nLLM mode: ${data.llm_mode}\nCopy source: ${data.copy_source || data.llm_mode}\nPrompts: ${data.prompt_files.length}\nImages: ${data.image_files.length}`);
    invalidateRuns();
    await loadAndRenderRuns();
  } catch (err) {
    setStatus(`Failed: ${String(err)}`);
  } finally {
    stopProgressPolling();
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.classList.remove("is-loading");
    }
  }
}

// Server type change handler
document.getElementById("serverType")?.addEventListener("change", async (e) => {
  state.currentServerType = e.target.value;
  const apiUrlInput = document.getElementById("opencodeApiUrl");
  if (state.currentServerType === "blackbox") {
    apiUrlInput.value = "http://127.0.0.1:4091";
    try {
      const data = await fetchJSON("http://127.0.0.1:4091/v1/models", {
        headers: { Authorization: "Basic " + btoa("user:blackbox-local-pass") },
      });
      const models = data.data || [];
      state.modelsByProvider = { blackbox: models.map((m) => m.id) };
      setSelectOptions(providerSelectEl, ["blackbox"], "blackbox");
      setSelectOptions(modelSelectEl, models.map((m) => m.id), models[0]?.id || "");
    } catch (err) {
      console.error("Failed to fetch Blackbox models:", err);
    }
  } else {
    apiUrlInput.value = "http://127.0.0.1:4090";
    initDefaults();
  }
});

document.getElementById("runBtn")?.addEventListener("click", () => {
  runPipeline().catch((err) => setStatus(String(err)));
});

if (providerSelectEl) {
  providerSelectEl.addEventListener("change", () => {
    renderModelOptions(providerSelectEl.value, "");
  });
}

// Init
initTheme();
showRunsSkeletons();
Promise.all([initDefaults(), loadAndRenderRuns()]).catch((err) => setStatus(String(err)));
