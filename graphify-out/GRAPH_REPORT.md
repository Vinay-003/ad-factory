# Graph Report - info  (2026-05-09)

## Corpus Check
- 18 files · ~3,474,023 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 462 nodes · 982 edges · 24 communities detected
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.8)
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
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]

## God Nodes (most connected - your core abstractions)
1. `main()` - 34 edges
2. `api_run_execute()` - 31 edges
3. `run()` - 31 edges
4. `write_text()` - 28 edges
5. `main()` - 21 edges
6. `click_send_and_confirm()` - 14 edges
7. `find_composer()` - 13 edges
8. `api_run_generate_916_selected()` - 12 edges
9. `collect_run_result()` - 11 edges
10. `generate_916_for_run()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `run_cmd()` --calls--> `run()`  [INFERRED]
  dashboard/backend/app.py → scripts/gemini_web_automation.py
- `run_opencode_discovery_cmd()` --calls--> `run()`  [INFERRED]
  dashboard/backend/app.py → scripts/gemini_web_automation.py
- `call_opencode_repair_copy()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `call_blackbox_http()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `call_opencode_compatible()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (114): assert_clean_fresh_chat_before_upload(), assert_fresh_url_immediately_before_send(), assert_not_temporary_chat(), auto_launch_debug_browser(), build_driver(), build_local_image_paths(), _chat_state_is_clean(), clear_composer_keyboard() (+106 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (53): add_used_text(), append_background_index(), append_concept_combo_index(), aspect_ratio_folder(), base_layout_lines_for_format(), build_seeded_background_sentence(), build_ugc_subject_line(), classify_cta_voice() (+45 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (35): build_image_inputs(), choose_logo_variant_with_minimax(), compose_prompt(), conversion_lock_instruction(), create_task(), discover_minimax_model(), download_file(), ensure_dir() (+27 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (27): api_defaults(), api_file_content(), build_multipart_form(), classify_cta_voice_text(), classify_hook_structure(), classify_proof_style_text(), copy_text_for_candidate(), cta_for_candidate() (+19 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (23): applyTheme(), fetchDefaults(), fileInput(), getFormatsByPersona(), getHypothesisConfig(), getPersonaSelection(), getSelectedBatchValues(), initTheme() (+15 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (26): api_batch_generate_images_45(), api_import_on_image_copy(), api_run_generate_916(), api_run_generate_916_selected(), api_run_generate_images_45(), api_run_generate_images_916_from_45(), api_run_update_prompt_copies(), _append_audit_log() (+18 more)

### Community 6 - "Community 6"
Cohesion: 0.17
Nodes (22): _append_unique(), _clean_lines(), compact_lines(), default_product_path(), extract_headline_strategy(), extract_keyword_lines(), extract_line_groups(), extract_priority_block() (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (20): api_run_execute(), assembler_language_mode(), build_copy_requirements(), build_persona_payload(), call_blackbox_http(), coalesce_path(), enforce_unique_ctas(), expand_plan_with_hypothesis() (+12 more)

### Community 8 - "Community 8"
Cohesion: 0.2
Nodes (3): BaseHTTPRequestHandler, BlackboxHandler, BlackboxHandler

### Community 9 - "Community 9"
Cohesion: 0.21
Nodes (15): build_generation_context(), build_prompt(), default_product_path(), ensure_list_of_strings(), main(), merge_product_directives(), normalize_canonical(), now_iso() (+7 more)

### Community 10 - "Community 10"
Cohesion: 0.15
Nodes (16): api_export_on_image_copy(), api_run_prompt_copies(), collect_45_visual_locks(), _extract_created_at_iso_from_file(), extract_on_image_copy_lines(), _extract_prompt_row_metadata(), extract_selected_ad_keys_from_45_prompts(), _extract_vn_from_prompt_rel_path() (+8 more)

### Community 11 - "Community 11"
Cohesion: 0.2
Nodes (16): api_opencode_catalog(), build_generation_payload_for_llm(), build_opencode_catalog(), call_opencode_compatible(), call_opencode_repair_copy(), choose_extractor_model(), choose_openai_gpt52(), hydrate_generated_ad_candidate() (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.19
Nodes (15): build_template_copy(), choose_text(), _clean_bullets(), _clean_str(), concept_ids_from_requirements(), ensure_testimonial_attribution(), ensure_testimonial_headline(), feature_template() (+7 more)

### Community 13 - "Community 13"
Cohesion: 0.38
Nodes (11): build_final_prompt(), choose_seed(), composition_variants(), crop_safety_variants(), cta_safe_space_variants(), detect_layout_mode(), layout_intent_variants(), main() (+3 more)

### Community 14 - "Community 14"
Cohesion: 0.18
Nodes (11): api_run(), api_runs(), ensure_dirs(), generated_image_roots(), load_batch_image_summary(), load_env_file(), refresh_manifest_file_state(), scan_image_files_for_batch() (+3 more)

### Community 15 - "Community 15"
Cohesion: 0.4
Nodes (5): api_batch_generate_images_916(), debugger_endpoint_reachable(), extract_persona_input_block(), gemini_debugger_args(), resolve_gemini_debugger_address()

### Community 16 - "Community 16"
Cohesion: 0.83
Nodes (3): load_json(), main(), parse_args()

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Return True if the URL is a blank new-chat (no conversation ID).      Fresh chat

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Open Gemini in a new browser tab/window for each prompt, then ensure composer is

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Send Ctrl+Shift+O to the page, with a JS fallback.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Collect all candidate generated-image URLs from the current tab.

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Best-effort check that uploads have been attached in Gemini UI.      We look for

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Wait until a new image appears in the page that wasn't there before sending.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Save the generated image to out_path_no_ext + inferred extension.      Strategy

## Knowledge Gaps
- **45 isolated node(s):** `Classify a headline opening pattern for hypothesis sanity checks.      The class`, `Call Blackbox server via HTTP API`, `Legacy-ish extractor used by the dashboard editor.      It DOES NOT preserve exa`, `Task 5: Extract ONLY the content inside:       EXACT ON-IMAGE COPY - DO NOT ALTE`, `Expand ad plan to include hypothesis style.      When a hypothesis is active, ge` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 23`** (1 nodes): `Return True if the URL is a blank new-chat (no conversation ID).      Fresh chat`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Open Gemini in a new browser tab/window for each prompt, then ensure composer is`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Send Ctrl+Shift+O to the page, with a JS fallback.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Collect all candidate generated-image URLs from the current tab.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Best-effort check that uploads have been attached in Gemini UI.      We look for`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Wait until a new image appears in the page that wasn't there before sending.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Save the generated image to out_path_no_ext + inferred extension.      Strategy`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `write_text()` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 7`, `Community 9`, `Community 11`, `Community 13`, `Community 14`, `Community 15`, `Community 16`?**
  _High betweenness centrality (0.447) - this node is a cross-community bridge._
- **Why does `run()` connect `Community 0` to `Community 2`, `Community 5`, `Community 8`, `Community 9`, `Community 11`?**
  _High betweenness centrality (0.303) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 1` to `Community 5`?**
  _High betweenness centrality (0.164) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `run()` (e.g. with `.do_POST()` and `run_cmd()`) actually correct?**
  _`run()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `write_text()` (e.g. with `run_gemini_generation()` and `write_product_context_cache()`) actually correct?**
  _`write_text()` has 26 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Classify a headline opening pattern for hypothesis sanity checks.      The class`, `Call Blackbox server via HTTP API`, `Legacy-ish extractor used by the dashboard editor.      It DOES NOT preserve exa` to the rest of the system?**
  _45 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.04 - nodes in this community are weakly interconnected._