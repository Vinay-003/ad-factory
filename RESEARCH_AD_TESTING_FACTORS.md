# Ad Creative Testing Factors — Research & Recommendation

> Generated from web research on Meta/Facebook creative testing frameworks + analysis of current Obesity Killer ad generation system.

---

## 1. Current System Audit (What's Already Tracked)

### 1.1 Fields Already in Registry (117 entries)

| Field | Coverage | Used for Hypothesis? |
|-------|----------|---------------------|
| `format` (HERO/BA/TEST/FEAT/UGC) | 117/117 | No |
| `persona_number` / `persona_name` | 117/117 | No |
| `headline_angle` | 117/117 | Partially (only "mechanism" repeated) |
| `visual_archetype` | 117/117 | No |
| `background_slot` / `background_name` | 117/117 | No |
| `awareness_stage` | 30/117 | **87 entries are NULL** — major gap |
| `concept_angle` | 30/117 | **87 entries are NULL** |
| `concept_structure` | 30/117 | **87 entries are NULL** |
| `language` | 117/117 | No |
| `output_quality` | 117/117 | Always `"pending"` — never updated |

### 1.2 Fields Defined in Playbook but NEVER Logged (0/117)

These are the **most critical missing pieces** for hypothesis testing:

- `opening_pattern_4tok_en` / `opening_pattern_4tok_hi` — first 4-token pattern
- `copy_skeleton` — structural flow (e.g., `pain_mechanism_time`)
- `hook_structure_class` — `question_lead`, `contrast_loop`, `command_lead`, `confession_lead`, `proof_lead`
- `proof_style_class` — `social_proof`, `mechanism_explainer`, `authority_anchor`, `routine_clarity`, `objection_flip`
- `cta_voice_class` — `urgent_start`, `guided_next_step`, `reassurance_start`, `challenge_action`, `discovery_action`

**Verdict**: You have a sophisticated taxonomy defined, but the generation pipeline is not populating ~60% of the fields. Without these, you cannot run structured hypothesis tests.

---

## 2. What Industry Research Says About Creative Testing

### 2.1 The "If… Then…" Hypothesis Formula

Every testable hypothesis must follow: **"If we change X, then metric Y will improve because of Z."**

Examples from industry:
- *"If we use testimonial-led visuals, then engagement will increase vs. product-only imagery."*
- *"If the CTA says 'Book Your Free Consultation' instead of 'Learn More', then conversion rate will rise."*
- *"If the headline leads with a question vs. a statement, then CTR will improve for problem-aware personas."*

### 2.2 Key Creative Variables to Test (from Segwise, Pilothouse, Invoke Media)

**High-Impact Variables (test these first):**
1. **Visual Hook / First 3 Seconds** — static vs. video, product vs. lifestyle, UGC vs. studio
2. **Headline / Opening Hook** — question vs. statement, emotional vs. factual, pain-led vs. outcome-led
3. **Messaging Angle / Concept Angle** — benefit-focused vs. problem-focused vs. social-proof vs. authority
4. **CTA** — direct vs. soft, button text, placement
5. **Awareness Stage Alignment** — matching message to funnel position (unaware → product_aware)

**Medium-Impact Variables:**
6. **Copy Structure** — PAS vs. BAB vs. FAB vs. 4U's
7. **Proof Framing** — mechanism explainer vs. authority stamp vs. social proof
8. **Tone / Voice** — empathetic vs. direct vs. curiosity-driven
9. **Format** — HERO vs. UGC vs. TEST vs. FEAT vs. BA
10. **Background / Visual Context** — studio vs. lifestyle vs. kitchen vs. clinical

**Lower-Impact but Measurable:**
11. **Headline Length** — 5-8 words vs. 9-12 words
12. **Language** — English vs. Hindi vs. Hinglish
13. **Color/Layout Variations** (currently locked in your system — consider unlocking)
14. **Specific CTA Wording** — "See The Steps" vs. "View Details" vs. "Start Today"

### 2.3 The 3-3-3 Framework (Pilothouse)

Organizes testing into 3 dimensions with 3 options each = 27 combinations:
- **3 Funnel Levels**: TOFU (awareness), MOFU (evaluation), BOFU (conversion)
- **3 Distinct Angles**: Different pain points per persona segment
- **3 Creative Formats**: Static, Video, Product Catalog

This gives you "enough variety to satisfy the algorithm while keeping scope manageable."

---

## 3. Recommended Testing Framework for Obesity Killer

### 3.1 Tier 1: Strategic Hypotheses (Test These First)

These test your core creative strategy, not just wording:

**H1 — Awareness Stage Matching**
- *Hypothesis*: Ads where `awareness_stage` matches the persona's actual funnel position will outperform mismatched ones.
- *How to test*: For the same persona, generate 2 ads — one with `problem_aware` and one with `product_aware`. Keep everything else identical.
- *Metric to track*: CTR, conversion rate
- *Current gap*: 87 entries have NULL awareness_stage. You need to backfill or start fresh with 100% coverage.

**H2 — Concept Angle by Format**
- *Hypothesis*: Certain `concept_angle` + `format` combinations are systematically stronger (e.g., `social_proof` in TEST format, `pain_point` in BA format).
- *How to test*: Run controlled matrix: 4 concept angles × 5 formats, same persona, same background. Measure which angle-format pairs win.
- *Metric to track*: ROAS, CPA
- *Current gap*: concept_angle is NULL in 87 entries.

**H3 — Hook Structure Performance**
- *Hypothesis*: `question_lead` headlines outperform `proof_lead` headlines for unaware/problem_aware audiences; `proof_lead` wins for product_aware.
- *How to test*: Same headline rewritten with 3 different hook structures. Same visual, same support line.
- *Metric to track*: CTR, scroll-stop rate
- *Current gap*: hook_structure_class is not logged at all (0/117).

**H4 — Proof Style by Persona**
- *Hypothesis*: `authority_anchor` works best for doctor-trust personas (e.g., #19 Trust-First Buyer); `social_proof` works best for skeptical personas (e.g., #8 No-Weakness Skeptic).
- *How to test*: Same persona, same headline angle, vary only `proof_style_class` in the support line.
- *Metric to track*: Conversion rate
- *Current gap*: proof_style_class is not logged.

### 3.2 Tier 2: Tactical Hypotheses (Test After Tier 1)

**H5 — Background Context Effect**
- *Hypothesis*: Kitchen/lifestyle backgrounds outperform studio backgrounds for homemaker personas; clinical-minimal backgrounds outperform lifestyle for trust-first personas.
- *How to test*: Same ad copy, 3 different background slots from different scene categories.
- *Metric to track*: Engagement rate, CTR

**H6 — CTA Voice by Funnel Stage**
- *Hypothesis*: `discovery_action` ("Check If It Fits") outperforms `urgent_start` ("Start Today") for problem_aware; reverse for product_aware.
- *How to test*: Same ad, only CTA text changes.
- *Metric to track*: Click-through rate, conversion rate
- *Current gap*: cta_voice_class is not logged.

**H7 — Format Effectiveness by Persona Type**
- *Hypothesis*: UGC format outperforms HERO for younger personas; HERO outperforms UGC for older/trust-first personas.
- *How to test*: Same persona, same concept angle, generate across all 5 formats. Compare.
- *Metric to track*: Overall ROAS per format

**H8 — Headline Length vs. Performance**
- *Hypothesis*: 5-8 word headlines outperform 9-12 word headlines on mobile feeds.
- *How to test*: Same concept, rewrite headline in short and long versions.
- *Metric to track*: CTR

### 3.3 Tier 3: Micro-Optimization (Test Last)

**H9 — Specific CTA Phrase Testing**
- "See The Steps" vs. "View Details" vs. "Check The Routine"

**H10 — Opening Pattern Repetition**
- *Hypothesis*: Repeating the same 4-token opening pattern across ads causes ad fatigue even when full text differs.
- *How to test*: Track performance decay when `opening_pattern_4tok` repeats vs. rotates.
- *Current gap*: opening_pattern is not logged.

**H11 — Language Preference by Demographic**
- *Hypothesis*: Hindi-first ads outperform English-first for Tier 2/3 audiences; English-first wins for Tier 1 urban professionals.
- *How to test*: Same ad, EN vs. HI versions, targeted to different geo tiers.
- *Metric to track*: Conversion rate by region

---

## 4. What Additional Factors Should Be Added

### 4.1 Missing Fields to Add to Registry

| New Field | Type | Purpose |
|-----------|------|---------|
| `hypothesis_id` | string | Tag every ad with the hypothesis it's testing (e.g., "H3-hook-structure") |
| `test_group` | string | "control" or "variant_A" / "variant_B" for A/B tests |
| `predicted_ctr` | float | Pre-launch prediction to compare against actual |
| `predicted_conversion` | float | Pre-launch prediction |
| `headline_word_count` | int | For H8 testing |
| `support_line_word_count` | int | For readability testing |
| `has_protocol_mechanics` | bool | Whether support line mentions AM/PM/4-hour window |
| `has_social_proof_number` | bool | Whether copy mentions "70,000+" or other numbers |
| `emotional_score` | int (1-5) | Human-rated emotional intensity of headline |
| `rational_score` | int (1-5) | Human-rated rational/logical intensity |
| `background_scene_category` | string | Kitchen, studio, bedroom, clinical, outdoor, etc. |
| `persona_age_group` | string | Inferred from persona (25-34, 35-44, 45-54, 55+) |
| `persona_gender_skew` | string | Male-leaning, female-leaning, neutral |
| `creative_fatigue_risk` | string | Low/medium/high based on similarity to recent entries |

### 4.2 New Testing Infrastructure Needed

1. **Creative Learning Log** — A simple spreadsheet/JSON with: date, hypothesis, test structure, winner, CPA delta, next hypothesis. After 20 tests, this becomes your most valuable strategic asset.

2. **A/B Test Pair Generator** — A script that takes a base ad and generates exactly ONE controlled variation (changing only the hypothesis variable).

3. **Performance Backfill Pipeline** — Once ads run, you need to feed CTR/CPA/ROAS back into the registry and update `output_quality` from "pending" to actual results.

4. **Concept-Combo Exhaustion Tracker** — Your playbook says `awareness_stage + concept_angle + concept_structure` = creative idea ID. You should track which combos have been tested and which need more data.

5. **Hypothesis Outcome Predictor** — After 50+ tests, you can start predicting which combos will win for which personas before generating.

---

## 5. Immediate Action Plan (No Code Changes Yet)

### Phase 1: Fix Data Gaps (Week 1)
- [ ] Decide if you will backfill the 87 NULL entries or start fresh
- [ ] Update generation pipeline to populate ALL defined fields:
  - `awareness_stage`, `concept_angle`, `concept_structure`
  - `opening_pattern_4tok`, `copy_skeleton`
  - `hook_structure_class`, `proof_style_class`, `cta_voice_class`
- [ ] Add new fields: `hypothesis_id`, `test_group`, `headline_word_count`

### Phase 2: Run First Controlled Test (Week 2)
- [ ] Pick ONE hypothesis from Tier 1 (e.g., H3 — Hook Structure)
- [ ] Generate 3 ads: same persona, same format, same background, same concept — only `hook_structure_class` varies
- [ ] Tag each with `hypothesis_id: "H3-hook-structure-v1"`
- [ ] Launch and measure CTR

### Phase 3: Build Learning Log (Week 3-4)
- [ ] Create a simple JSON/CSV log of every test
- [ ] After each test, record: hypothesis, variables changed, winner, metric delta
- [ ] Use this to inform the next hypothesis — don't test randomly

### Phase 4: Scale to Matrix Testing (Month 2)
- [ ] Run a 3×3 matrix: 3 concept angles × 3 formats for one persona
- [ ] Measure which angle-format pairs are strongest
- [ ] Apply learnings across all personas

---

## 6. Key Research Sources

1. **Segwise** — "A Complete Guide to Modern Ad Creative Testing" — Emphasizes multivariate testing and the 4-step framework (hypothesis → variations → launch → scale).
2. **Pilothouse** — "Meta Creative Testing Framework: The 3-3-3 Approach" — Funnel levels (TOFU/MOFU/BOF), distinct angles per pain point, format diversity.
3. **Invoke Media** — "Creative Testing Frameworks for Facebook & Instagram" — "If… Then…" hypothesis formula, key metrics (CTR, CPA, ROAS).
4. **AdRow/Wevion** — "Creative Testing Framework for Meta Ads (2026)" — Creative Learning Log concept: "After 20 tests, this log becomes your most valuable strategic asset."

---

## 7. Bottom Line

**Your system is 80% ready for structured hypothesis testing.**

You already have:
- ✅ A rich taxonomy (persona, format, awareness stage, concept angle, concept structure, headline angle, visual archetype)
- ✅ A deduplication system to prevent repetitive ads
- ✅ Background rotation to ensure visual diversity
- ✅ A registry to log everything

**What you're missing:**
- ❌ The newer copy-diversity fields are defined in the playbook but never populated
- ❌ No `hypothesis_id` field — you don't know WHY each ad was created
- ❌ No test_group/control field — you can't run A/B tests
- ❌ `output_quality` is always "pending" — no performance feedback loop
- ❌ No Creative Learning Log to accumulate insights across tests

**My recommendation**: Start with Phase 1 (fix data gaps) and Phase 2 (run one controlled H3 test). Don't try to test everything at once. Pick one variable, control everything else, measure, log, iterate.

---

*Research completed. Ready to implement when you confirm direction.*
