# Graph Report - info  (2026-05-05)

## Corpus Check
- 18 files · ~21,546,175 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 339 nodes · 658 edges · 43 communities detected
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 27 edges (avg confidence: 0.8)
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
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
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

## God Nodes (most connected - your core abstractions)
1. `run()` - 32 edges
2. `api_run_execute()` - 25 edges
3. `main()` - 23 edges
4. `write_text()` - 22 edges
5. `main()` - 21 edges
6. `api_run_generate_916_selected()` - 12 edges
7. `call_opencode_compatible()` - 11 edges
8. `generate_916_for_run()` - 11 edges
9. `main()` - 11 edges
10. `collect_run_result()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `run_cmd()` --calls--> `run()`  [INFERRED]
  dashboard/backend/app.py → scripts/gemini_web_automation.py
- `run_opencode_discovery_cmd()` --calls--> `run()`  [INFERRED]
  dashboard/backend/app.py → scripts/gemini_web_automation.py
- `call_opencode_repair_copy()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `call_opencode_compatible()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py
- `refresh_manifest_file_state()` --calls--> `write_text()`  [INFERRED]
  dashboard/backend/app.py → scripts/kie_nano_batch.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (68): api_defaults(), api_file_content(), api_opencode_catalog(), api_run(), api_run_execute(), api_runs(), assembler_language_mode(), build_copy_requirements() (+60 more)

### Community 1 - "Community 1"
Cohesion: 0.1
Nodes (41): auto_launch_debug_browser(), build_driver(), build_local_image_paths(), click_first_visible_css(), click_send(), click_text_options(), close_active_tab(), collect_upload_images_from_dir() (+33 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (34): build_image_inputs(), choose_logo_variant_with_minimax(), compose_prompt(), conversion_lock_instruction(), create_task(), discover_minimax_model(), download_file(), ensure_dir() (+26 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (34): add_used_text(), append_background_index(), aspect_ratio_folder(), base_layout_lines_for_format(), build_seeded_background_sentence(), build_ugc_subject_line(), CopyBlock, ensure_slot_tracker() (+26 more)

### Community 4 - "Community 4"
Cohesion: 0.16
Nodes (26): api_run_generate_916(), api_run_generate_916_selected(), api_run_generate_images_45(), api_run_generate_images_916_from_45(), api_run_prompt_copies(), api_run_update_prompt_copies(), apply_visual_locks(), collect_45_visual_locks() (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.23
Nodes (18): _append_unique(), _clean_lines(), compact_lines(), default_product_path(), extract_faq_sections(), extract_headline_strategy(), extract_keyword_lines(), extract_line_groups() (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.19
Nodes (17): applyTheme(), fetchDefaults(), fileInput(), getFormatsByPersona(), getPersonaSelection(), initTheme(), loadRuns(), renderGlobalFormats() (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.21
Nodes (15): build_generation_context(), build_prompt(), default_product_path(), ensure_list_of_strings(), main(), merge_product_directives(), normalize_canonical(), now_iso() (+7 more)

### Community 8 - "Community 8"
Cohesion: 0.3
Nodes (11): add_list(), extract_existing_snapshots(), fallback_snapshot(), load_rows(), main(), make_language_bank(), parse_args(), Extract Basic snapshot bullet lines from existing persona file.      Keeps exist (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.38
Nodes (11): build_final_prompt(), choose_seed(), composition_variants(), crop_safety_variants(), cta_safe_space_variants(), detect_layout_mode(), layout_intent_variants(), main() (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.6
Nodes (5): build_payload(), get_persona_block(), main(), parse_args(), parse_bullets()

### Community 11 - "Community 11"
Cohesion: 0.83
Nodes (3): load_json(), main(), parse_args()

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Open a brand-new tab, navigate to Gemini, return the new handle.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Navigate to a clean new-chat state.     Strategy: just GET the base Gemini URL —

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Click the 'New chat' sidebar button once. No retry loops.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Click the model picker and select Pro. Returns True if Pro is confirmed visible.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Open the Tools menu and select 'Create image'. Returns True on success.

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Return src of images that are large enough to be a generated output.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Wait until a new large image appears that wasn't in before_sources,     and gene

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Hover over the generated image and click any Download button that appears.

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Process a single prompt job. Opens a fresh tab, runs the full flow,     download

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Find any enabled file input, including inside shadow DOM.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Click the attach/plus button once to reveal the file input.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Return src of images that are large enough to be a generated output.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Wait until a new large image appears that wasn't in before_sources,     and gene

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Hover over the generated image and click any Download button that appears.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Process a single prompt job. Opens a fresh tab, runs the full flow,     download

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Click the attach/plus button once to reveal the file input.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Return src of images that are large enough to be a generated output.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Wait until a new large image appears that wasn't in before_sources,     and gene

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Hover over the generated image and click any Download button that appears.

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Process a single prompt job. Opens a fresh tab, runs the full flow,     download

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Open Gemini in a brand-new tab and keep Selenium focused on that tab.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Make the active Gemini tab a fresh chat without clicking unrelated UI.      The

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Click a visible control by text without clicking arbitrary page text.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Click Gemini's upload/add-file button near the composer, not the sidebar.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Open Gemini's attachment UI using only composer-area controls.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Open Gemini's model picker without clicking upgrade/promotional UI.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Return True only when a visible model control/chip itself says Pro.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Select a Pro model from Gemini's model picker and verify the chip.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Optionally select Gemini's Create image tool without broad page clicking.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Absorb images that appear immediately when Gemini moves uploads into the sent us

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): # IMPORTANT: capture baseline after uploads and prompt insertion.

## Knowledge Gaps
- **32 isolated node(s):** `Extract Basic snapshot bullet lines from existing persona file.      Keeps exist`, `Open a brand-new tab, navigate to Gemini, return the new handle.`, `Navigate to a clean new-chat state.     Strategy: just GET the base Gemini URL —`, `Click the 'New chat' sidebar button once. No retry loops.`, `Click the model picker and select Pro. Returns True if Pro is confirmed visible.` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 18`** (1 nodes): `Open a brand-new tab, navigate to Gemini, return the new handle.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Navigate to a clean new-chat state.     Strategy: just GET the base Gemini URL —`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Click the 'New chat' sidebar button once. No retry loops.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Click the model picker and select Pro. Returns True if Pro is confirmed visible.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Open the Tools menu and select 'Create image'. Returns True on success.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Return src of images that are large enough to be a generated output.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Wait until a new large image appears that wasn't in before_sources,     and gene`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Hover over the generated image and click any Download button that appears.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Process a single prompt job. Opens a fresh tab, runs the full flow,     download`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Find any enabled file input, including inside shadow DOM.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Click the attach/plus button once to reveal the file input.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Return src of images that are large enough to be a generated output.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Wait until a new large image appears that wasn't in before_sources,     and gene`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Hover over the generated image and click any Download button that appears.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Process a single prompt job. Opens a fresh tab, runs the full flow,     download`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Click the attach/plus button once to reveal the file input.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Return src of images that are large enough to be a generated output.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Wait until a new large image appears that wasn't in before_sources,     and gene`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Hover over the generated image and click any Download button that appears.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Process a single prompt job. Opens a fresh tab, runs the full flow,     download`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Open Gemini in a brand-new tab and keep Selenium focused on that tab.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Make the active Gemini tab a fresh chat without clicking unrelated UI.      The`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Click a visible control by text without clicking arbitrary page text.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Click Gemini's upload/add-file button near the composer, not the sidebar.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Open Gemini's attachment UI using only composer-area controls.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Open Gemini's model picker without clicking upgrade/promotional UI.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Return True only when a visible model control/chip itself says Pro.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Select a Pro model from Gemini's model picker and verify the chip.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Optionally select Gemini's Create image tool without broad page clicking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Absorb images that appear immediately when Gemini moves uploads into the sent us`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `# IMPORTANT: capture baseline after uploads and prompt insertion.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `write_text()` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 7`, `Community 8`, `Community 9`, `Community 11`?**
  _High betweenness centrality (0.427) - this node is a cross-community bridge._
- **Why does `run()` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`, `Community 7`?**
  _High betweenness centrality (0.190) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 7` to `Community 4`?**
  _High betweenness centrality (0.138) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `run()` (e.g. with `run_cmd()` and `run_opencode_discovery_cmd()`) actually correct?**
  _`run()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `write_text()` (e.g. with `run_gemini_generation()` and `call_opencode_repair_copy()`) actually correct?**
  _`write_text()` has 20 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Extract Basic snapshot bullet lines from existing persona file.      Keeps exist`, `Open a brand-new tab, navigate to Gemini, return the new handle.`, `Navigate to a clean new-chat state.     Strategy: just GET the base Gemini URL —` to the rest of the system?**
  _32 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._