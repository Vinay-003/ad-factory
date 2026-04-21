# Ad Dashboard (Local-Only Storage)

This dashboard runs fully on the same machine as your OpenCode workflow.

- No database is used.
- Uploaded files are stored under `dashboard_storage/runs/<run_id>/inputs/`.
- Generated context and copy JSON are stored under `dashboard_storage/runs/<run_id>/context/`.
- Prompt files are written to existing `output/vN/`.
- Generated images are written to existing `generated_image/vN/`.

## Start

```bash
bash scripts/run_dashboard.sh
```

Open:

- `http://localhost:8787`

## Start Full Stack (recommended)

This starts OpenCode server in background, starts dashboard server, auto-connects dashboard to local OpenCode URL, and opens browser.

```bash
bash scripts/start_dashboard_stack.sh
```

Stop both services:

```bash
bash scripts/stop_dashboard_stack.sh
```

## One-command bootstrap (new machine)

Linux/macOS:

```bash
bash scripts/bootstrap_stack.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_stack.ps1
```

Windows stop:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_dashboard_stack.ps1
```

Bootstrap does all of this:

- creates `.venv` if missing
- installs Python deps from `requirements-dashboard.txt`
- installs OpenCode CLI if missing (`npm install -g opencode-cli`)
- starts OpenCode + dashboard stack
- opens browser automatically

## How it works

1. Dashboard loads defaults from:
   - `productinfomain.txt`
   - `PRODUCT_MECHANISM_V1.txt`
   - `faq.txt`
   - `input/activeimages.txt`

2. Retrieval scripts extract only required slices:
   - `scripts/build_canonical_context.py` (LLM reconciliation, primary)
   - `scripts/extract_format_rules.py`
   - `scripts/extract_product_context.py` (fallback only if canonical build fails)

3. Backend builds compact context JSON and tries OpenCode-compatible chat API (optional).

4. If no OpenCode API URL is provided, backend uses local template fallback to produce schema-compatible copy JSON.

5. Assembler creates prompts via:
   - `scripts/generate_ads.py`

6. Optional image generation via:
   - `scripts/kie_nano_batch.py`

## Provider + model dropdown

- Dashboard reads provider/model list directly from local OpenCode CLI:
  - `opencode providers list`
  - `opencode models`
- It groups models by provider and shows both in dropdowns.
- API URL is auto-populated from launcher (`http://127.0.0.1:4090` by default).

## How parsing works (and why token use is lower)

The dashboard does deterministic retrieval first, then generation.

1. User selects persona + format in UI.
2. Backend runs context-building scripts:
   - `scripts/build_canonical_context.py` (product + mechanism + FAQ reconciliation)
    - `scripts/extract_format_rules.py` from `AD_CREATIVE_SYSTEM_PLAYBOOK.md`
    - `scripts/extract_product_context.py` as fallback
3. Backend builds compact `run_context.json` in run storage.
4. OpenCode generates copy JSON only.
5. Backend normalizes schema and trims long copy lines.
6. Assembler script creates final prompt files.

This removes token-heavy "read whole docs" behavior and sends only relevant slices to model.

## API key behavior

- KIE API key is used only for request execution and is not persisted.
- OpenCode API key field is used as OpenCode server basic-auth password for attached calls.
- If empty, backend auto-uses `OPENCODE_SERVER_PASSWORD` from launcher env.

## Notes

- Persona selection now uses the persona library embedded in `AD_CREATIVE_SYSTEM_PLAYBOOK.md`.
