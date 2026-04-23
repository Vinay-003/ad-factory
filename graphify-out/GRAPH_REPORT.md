# Graph Report - info  (2026-04-23)

## Corpus Check
- 17 files · ~231,738 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 227 nodes · 476 edges · 17 communities detected
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.8)
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

## God Nodes (most connected - your core abstractions)
1. `main()` - 23 edges
2. `write_text()` - 21 edges
3. `api_run_execute()` - 20 edges
4. `main()` - 20 edges
5. `api_run_generate_916_selected()` - 12 edges
6. `generate_916_for_run()` - 11 edges
7. `main()` - 10 edges
8. `run_cmd()` - 9 edges
9. `normalize_generated_copy()` - 9 edges
10. `call_opencode_compatible()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `call_opencode_compatible()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `refresh_manifest_file_state()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `api_run_execute()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `main()` --calls--> `write_text()`  [INFERRED]
  notusing/legacy_persona/generate_persona_txt.py → scripts/kie_nano_batch.py
- `call_opencode_repair_copy()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (34): add_used_text(), append_background_index(), aspect_ratio_folder(), base_layout_lines_for_format(), build_seeded_background_sentence(), build_ugc_subject_line(), CopyBlock, ensure_slot_tracker() (+26 more)

### Community 1 - "Community 1"
Cohesion: 0.15
Nodes (25): build_image_inputs(), build_image_inputs_from_file(), compose_prompt(), conversion_lock_instruction(), create_task(), download_file(), ensure_dir(), extension_from_url() (+17 more)

### Community 2 - "Community 2"
Cohesion: 0.24
Nodes (19): api_run_generate_916(), api_run_generate_916_selected(), api_run_generate_images_45(), api_run_generate_images_916_from_45(), api_run_update_prompt_copies(), apply_visual_locks(), call_opencode_repair_copy(), collect_run_result() (+11 more)

### Community 3 - "Community 3"
Cohesion: 0.19
Nodes (17): applyTheme(), fetchDefaults(), fileInput(), getFormatsByPersona(), getPersonaSelection(), initTheme(), loadRuns(), renderGlobalFormats() (+9 more)

### Community 4 - "Community 4"
Cohesion: 0.19
Nodes (16): api_file_content(), api_run(), api_runs(), build_multipart_form(), ensure_dirs(), load_env_file(), now_iso(), refresh_manifest_file_state() (+8 more)

### Community 5 - "Community 5"
Cohesion: 0.24
Nodes (13): build_generation_context(), build_prompt(), ensure_list_of_strings(), main(), normalize_canonical(), now_iso(), parse_args(), parse_json_object_from_text() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.3
Nodes (11): add_list(), extract_existing_snapshots(), fallback_snapshot(), load_rows(), main(), make_language_bank(), parse_args(), Extract Basic snapshot bullet lines from existing persona file.      Keeps exist (+3 more)

### Community 7 - "Community 7"
Cohesion: 0.38
Nodes (11): build_final_prompt(), choose_seed(), composition_variants(), crop_safety_variants(), cta_safe_space_variants(), detect_layout_mode(), layout_intent_variants(), main() (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.22
Nodes (10): api_run_execute(), assembler_language_mode(), build_persona_payload(), coalesce_path(), make_run_id(), parse_json_stdout(), parse_uniqueness_collisions(), resolve_format_plan() (+2 more)

### Community 9 - "Community 9"
Cohesion: 0.29
Nodes (10): build_template_copy(), choose_text(), _clean_bullets(), _clean_str(), ensure_testimonial_attribution(), ensure_testimonial_headline(), normalize_generated_copy(), _persona_name_from_candidate() (+2 more)

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (9): api_opencode_catalog(), build_opencode_catalog(), list_models_for_provider(), list_opencode_models(), list_opencode_provider_labels(), opencode_discovery_env(), provider_id_from_label(), run_opencode_discovery_cmd() (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.29
Nodes (8): api_run_prompt_copies(), collect_45_visual_locks(), extract_on_image_copy_lines(), extract_selected_ad_keys_from_45_prompts(), parse_background_lock_from_prompt(), parse_persona_number_from_prompt(), _parse_prompt_field(), parse_prompt_filename()

### Community 12 - "Community 12"
Cohesion: 0.5
Nodes (7): faq_categories(), keep_categories(), keep_sections(), main(), mechanism_sections(), product_sections(), slice_blocks()

### Community 13 - "Community 13"
Cohesion: 0.47
Nodes (6): call_opencode_compatible(), choose_extractor_model(), choose_openai_gpt52(), parse_json_object_from_text(), parse_opencode_json_output(), sanitize_dashboard_model()

### Community 14 - "Community 14"
Cohesion: 0.6
Nodes (5): build_payload(), get_persona_block(), main(), parse_args(), parse_bullets()

### Community 15 - "Community 15"
Cohesion: 0.83
Nodes (3): load_json(), main(), parse_args()

### Community 16 - "Community 16"
Cohesion: 0.67
Nodes (3): api_defaults(), parse_persona_library(), read_active_images()

## Knowledge Gaps
- **1 isolated node(s):** `Extract Basic snapshot bullet lines from existing persona file.      Keeps exist`
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `write_text()` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 13`, `Community 15`?**
  _High betweenness centrality (0.555) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 0` to `Community 2`?**
  _High betweenness centrality (0.182) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 5` to `Community 2`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `write_text()` (e.g. with `call_opencode_repair_copy()` and `call_opencode_compatible()`) actually correct?**
  _`write_text()` has 18 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Extract Basic snapshot bullet lines from existing persona file.      Keeps exist` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._