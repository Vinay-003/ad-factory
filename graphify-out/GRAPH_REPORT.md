# Graph Report - info  (2026-05-11)

## Corpus Check
- 18 files · ~3,800,078 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 530 nodes · 1051 edges · 57 communities detected
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 39 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]

## God Nodes (most connected - your core abstractions)
1. `main()` - 34 edges
2. `write_text()` - 33 edges
3. `api_run_execute()` - 31 edges
4. `run()` - 29 edges
5. `main()` - 21 edges
6. `collect_run_result()` - 12 edges
7. `api_run_generate_916_selected()` - 12 edges
8. `click_send_and_confirm()` - 12 edges
9. `generate_916_for_run()` - 11 edges
10. `main()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `run_cmd()` --calls--> `run()`  [INFERRED]
  dashboard/backend/app.py → scripts/gemini_web_automation.py
- `run_opencode_discovery_cmd()` --calls--> `run()`  [INFERRED]
  dashboard/backend/app.py → scripts/gemini_web_automation.py
- `write_product_context_cache()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `call_opencode_repair_copy()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `call_blackbox_http()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (53): add_used_text(), append_background_index(), append_concept_combo_index(), aspect_ratio_folder(), base_layout_lines_for_format(), build_seeded_background_sentence(), build_ugc_subject_line(), classify_cta_voice() (+45 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (34): api_defaults(), api_file_content(), api_kill_chrome(), api_launch_visible_browser(), build_multipart_form(), classify_cta_voice_text(), classify_hook_structure(), classify_proof_style_text() (+26 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (35): build_image_inputs(), choose_logo_variant_with_minimax(), compose_prompt(), conversion_lock_instruction(), create_task(), discover_minimax_model(), download_file(), ensure_dir() (+27 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (33): assert_not_temporary_chat(), _attachment_spinner_count(), build_browser_context(), build_local_image_paths(), collect_upload_images_from_dir(), discover_prompt_jobs(), download_to_temp(), _format_sort_key() (+25 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (34): api_batch_generate_images_45(), api_batch_generate_images_916(), api_delete_image(), api_delete_prompt(), api_edit_prompt(), api_progress(), api_run_generate_916(), api_run_generate_916_selected() (+26 more)

### Community 5 - "Community 5"
Cohesion: 0.1
Nodes (26): applyTheme(), fetchDefaults(), fileInput(), getFormatsByPersona(), getHypothesisConfig(), getPersonaSelection(), getSelectedBatchValues(), hideChromeKillButton() (+18 more)

### Community 6 - "Community 6"
Cohesion: 0.15
Nodes (26): clear_composer_keyboard(), click_send_and_confirm(), _compact_prompt_compare(), find_composer(), focus_composer(), format_prompt_integrity(), generation_in_progress(), get_composer_text() (+18 more)

### Community 7 - "Community 7"
Cohesion: 0.17
Nodes (22): _append_unique(), _clean_lines(), compact_lines(), default_product_path(), extract_headline_strategy(), extract_keyword_lines(), extract_line_groups(), extract_priority_block() (+14 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (23): _capture_download_from_click(), _click_download_control_js(), click_exact_image_and_download(), _configure_download_dir(), _default_chrome_download_dirs(), _download_control_available(), download_generated_image(), infer_ext_from_src() (+15 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (20): api_run_execute(), assembler_language_mode(), build_copy_requirements(), build_persona_payload(), coalesce_path(), expand_plan_with_hypothesis(), file_sha256(), _framework_item() (+12 more)

### Community 10 - "Community 10"
Cohesion: 0.17
Nodes (18): api_opencode_catalog(), build_generation_payload_for_llm(), build_opencode_catalog(), call_blackbox_http(), call_opencode_compatible(), call_opencode_repair_copy(), choose_extractor_model(), choose_openai_gpt52() (+10 more)

### Community 11 - "Community 11"
Cohesion: 0.2
Nodes (3): BaseHTTPRequestHandler, BlackboxHandler, BlackboxHandler

### Community 12 - "Community 12"
Cohesion: 0.21
Nodes (15): build_generation_context(), build_prompt(), default_product_path(), ensure_list_of_strings(), main(), merge_product_directives(), normalize_canonical(), now_iso() (+7 more)

### Community 13 - "Community 13"
Cohesion: 0.14
Nodes (16): _active_window_title(), click_attach_button_near_composer(), _click_attach_menu_button_only(), _click_upload_files_menu_item(), _native_dialog_choose_file(), _native_file_dialog_active(), _open_upload_file_chooser(), Click the visible attachment/add-files control closest to the composer. (+8 more)

### Community 14 - "Community 14"
Cohesion: 0.19
Nodes (15): build_template_copy(), choose_text(), _clean_bullets(), _clean_str(), concept_ids_from_requirements(), ensure_testimonial_attribution(), ensure_testimonial_headline(), feature_template() (+7 more)

### Community 15 - "Community 15"
Cohesion: 0.21
Nodes (12): api_export_on_image_copy(), api_import_on_image_copy(), _append_audit_log(), _extract_created_at_iso_from_file(), extract_exact_on_image_copy_block(), _extract_prompt_row_metadata(), _extract_vn_from_prompt_rel_path(), _load_run_prompt_files() (+4 more)

### Community 16 - "Community 16"
Cohesion: 0.38
Nodes (11): build_final_prompt(), choose_seed(), composition_variants(), crop_safety_variants(), cta_safe_space_variants(), detect_layout_mode(), layout_intent_variants(), main() (+3 more)

### Community 17 - "Community 17"
Cohesion: 0.22
Nodes (9): api_run(), api_runs(), ensure_dirs(), load_env_file(), refresh_manifest_file_state(), scan_image_files_for_batch(), scan_prompt_files_for_batch(), startup() (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.25
Nodes (9): api_run_prompt_copies(), collect_45_visual_locks(), extract_on_image_copy_lines(), extract_selected_ad_keys_from_45_prompts(), parse_background_lock_from_prompt(), parse_persona_number_from_prompt(), _parse_prompt_field(), parse_prompt_filename() (+1 more)

### Community 19 - "Community 19"
Cohesion: 0.22
Nodes (9): _describe_input_attrs(), _dispatch_file_input_events_via_cdp(), _find_file_input_across_frames(), _find_file_input_anywhere(), open_attachment_ui(), Find an existing file input. Hidden inputs are OK for set_input_files()., Open the + / attachment menu only.      Important: do NOT click the "Upload file, Assign files to an existing Gemini file input through CDP.      Gemini usually c (+1 more)

### Community 20 - "Community 20"
Cohesion: 0.32
Nodes (8): create_image_tool_selected(), dismiss_open_overlays(), pro_model_selected(), _safe_click_js(), safe_click_labels(), select_create_image_tool(), select_model_and_tool_if_requested(), select_pro_model()

### Community 21 - "Community 21"
Cohesion: 0.33
Nodes (7): gemini_app_ready(), goto_gemini_app(), navigate_to_fresh_chat(), Navigate to Gemini without failing only because the SPA never fires full load., Navigate to a fresh Gemini chat using URL Stability Locks to defeat SPA race con, _url_is_base_app(), wait_for_manual_login()

### Community 22 - "Community 22"
Cohesion: 0.47
Nodes (6): click_send_button(), find_enabled_send_button(), _locator_rect(), _send_button_action(), _send_button_diagnostics(), wait_until_send_enabled()

### Community 23 - "Community 23"
Cohesion: 0.5
Nodes (4): _image_candidates(), Return visible generated-image candidates.      Use an arrow function for Playwr, response_completed_with_media(), wait_for_generated_image()

### Community 24 - "Community 24"
Cohesion: 0.83
Nodes (3): load_json(), main(), parse_args()

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Classify a headline opening pattern for hypothesis sanity checks.      The class

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Call Blackbox server via HTTP API

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Legacy-ish extractor used by the dashboard editor.      It DOES NOT preserve exa

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Task 5: Extract ONLY the content inside:       EXACT ON-IMAGE COPY - DO NOT ALTE

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Expand ad plan to include hypothesis style.      When a hypothesis is active, ge

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Preserve EXACT headline value text as written in the exact block.      We intent

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Trigger Gemini's Ctrl+Shift+O new-chat shortcut in the active tab.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): True when the page already contains visible prior-turn content.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Small diagnostic report used before upload/send.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Hard guard: no upload is allowed unless the current tab is a clean /app chat.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Open a new tab directly at /app and switch to it. Previous tabs stay open.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Force the active tab to /app using browser navigation, not keyboard shortcuts.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Final guard before Send: never submit unless the active tab URL is exactly /app.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Click only a real New chat button/link. Never click history rows or 3-dot menus.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Open/switch to the tab that will own this prompt.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Guarantee a clean fresh Gemini chat before upload.      This intentionally does

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Read text from Gemini's real composer, not old messages or upload chips.

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Use Chrome DevTools Input.insertText so newlines are inserted as text, not Enter

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Paste through the browser clipboard; this updates Gemini like a real user paste.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Last-resort DOM insertion. It is verified strictly before Send is allowed.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Return a short list of visible composer-area buttons for debugging.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Find Gemini's actual composer Send/Submit control.      The earlier versions loo

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Count text-node matches for the prompt outside the editable composer.

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Confirm Gemini accepted the prompt.      Important: an empty composer alone is N

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Focus Gemini composer and perform a real Selenium Enter keypress.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Return True if the URL is a blank new-chat (no conversation ID).      Fresh chat

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Open Gemini in a new browser tab/window for each prompt, then ensure composer is

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Send Ctrl+Shift+O to the page, with a JS fallback.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Collect all candidate generated-image URLs from the current tab.

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Best-effort check that uploads have been attached in Gemini UI.      We look for

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Wait until a new image appears in the page that wasn't there before sending.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Save the generated image to out_path_no_ext + inferred extension.      Strategy

## Knowledge Gaps
- **82 isolated node(s):** `Classify a headline opening pattern for hypothesis sanity checks.      The class`, `Call Blackbox server via HTTP API`, `Collect generated image paths for a specific aspect ratio.      Searches both le`, `Write generation_metadata.json alongside generated images with persona,     form`, `Legacy-ish extractor used by the dashboard editor.      It DOES NOT preserve exa` (+77 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 31`** (1 nodes): `Classify a headline opening pattern for hypothesis sanity checks.      The class`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Call Blackbox server via HTTP API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Legacy-ish extractor used by the dashboard editor.      It DOES NOT preserve exa`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Task 5: Extract ONLY the content inside:       EXACT ON-IMAGE COPY - DO NOT ALTE`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Expand ad plan to include hypothesis style.      When a hypothesis is active, ge`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Preserve EXACT headline value text as written in the exact block.      We intent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Trigger Gemini's Ctrl+Shift+O new-chat shortcut in the active tab.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `True when the page already contains visible prior-turn content.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Small diagnostic report used before upload/send.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Hard guard: no upload is allowed unless the current tab is a clean /app chat.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Open a new tab directly at /app and switch to it. Previous tabs stay open.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Force the active tab to /app using browser navigation, not keyboard shortcuts.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Final guard before Send: never submit unless the active tab URL is exactly /app.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Click only a real New chat button/link. Never click history rows or 3-dot menus.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Open/switch to the tab that will own this prompt.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Guarantee a clean fresh Gemini chat before upload.      This intentionally does`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Read text from Gemini's real composer, not old messages or upload chips.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Use Chrome DevTools Input.insertText so newlines are inserted as text, not Enter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Paste through the browser clipboard; this updates Gemini like a real user paste.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Last-resort DOM insertion. It is verified strictly before Send is allowed.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Return a short list of visible composer-area buttons for debugging.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Find Gemini's actual composer Send/Submit control.      The earlier versions loo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Count text-node matches for the prompt outside the editable composer.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Confirm Gemini accepted the prompt.      Important: an empty composer alone is N`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Focus Gemini composer and perform a real Selenium Enter keypress.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Return True if the URL is a blank new-chat (no conversation ID).      Fresh chat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Open Gemini in a new browser tab/window for each prompt, then ensure composer is`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Send Ctrl+Shift+O to the page, with a JS fallback.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Collect all candidate generated-image URLs from the current tab.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Best-effort check that uploads have been attached in Gemini UI.      We look for`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Wait until a new image appears in the page that wasn't there before sending.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Save the generated image to out_path_no_ext + inferred extension.      Strategy`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `write_text()` connect `Community 4` to `Community 0`, `Community 2`, `Community 3`, `Community 6`, `Community 9`, `Community 10`, `Community 12`, `Community 15`, `Community 16`, `Community 17`, `Community 24`?**
  _High betweenness centrality (0.391) - this node is a cross-community bridge._
- **Why does `run()` connect `Community 3` to `Community 2`, `Community 4`, `Community 6`, `Community 8`, `Community 10`, `Community 11`, `Community 12`, `Community 13`, `Community 20`, `Community 21`, `Community 23`?**
  _High betweenness centrality (0.271) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 0` to `Community 4`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `write_text()` (e.g. with `run_gemini_generation()` and `write_product_context_cache()`) actually correct?**
  _`write_text()` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `run()` (e.g. with `.do_POST()` and `run_cmd()`) actually correct?**
  _`run()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Classify a headline opening pattern for hypothesis sanity checks.      The class`, `Call Blackbox server via HTTP API`, `Collect generated image paths for a specific aspect ratio.      Searches both le` to the rest of the system?**
  _82 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._