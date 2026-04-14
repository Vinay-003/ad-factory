# Obesity Killer Ad Creative System Playbook
# Version 2.0 — Revised with full prompt system, background variation engine, and live registry logic

---

## 0) Quick Start (Read First)

How to use this playbook in chat:
- If user gives no specific inputs (persona/headline/format), generate a default starter batch immediately.
- If user gives specific inputs (persona and/or headline and/or format), use those inputs first.
- If user gives partial inputs, use what they gave and fill missing fields with defaults from this playbook.
- Always keep claims restricted to `info/productinfo.txt` and preserve product fidelity rules.

Accepted user input styles (examples):
- "Create ads" -> generate default starter batch (all 5 formats, 1 variation each)
- "Persona 9, HERO + TEST" -> use persona 9 for those formats
- "Use this headline: ... for FEAT" -> keep that headline, generate rest as needed
- "UGC only" -> generate only UGC with default persona/headline mode unless user specifies

Default starter batch profile (use when no specific input is given):
- Persona selection: random from 1-22 per format (do not use a fixed mapping)
- Prefer unique personas across selected formats in the same batch when possible
- If user provides persona for only some formats, keep those fixed and randomize remaining formats
- Headline mode: AI-generated fresh headlines
- Formats: HERO, BA, TEST, FEAT, UGC

---

## 1) Objective

Generate high-converting static ads for Obesity Killer Kit across 5 formats:
- HERO
- BA (Before/After journey style)
- TEST (Testimonial)
- FEAT (Features/benefits)
- UGC (Creator-style)

Current testing mode:
- Generate 1 variation per format first.
- Expand to 8 variations per format only after quality is stable.

---

## 2) Source of Truth (Do not invent)

Use only approved claims and context from `info/productinfo.txt`.

Approved anchors:
- 3-5 kg average in 15 days (with asterisk/disclaimer)
- Ayurvedic kit, natural ingredients
- Cravings/hunger control support
- Digestion/metabolism support
- No crash diets, no heavy workouts
- Trusted by 70,000+ users
- Money-back terms apply

Never add unsupported medical claims, disease cures, or made-up mechanisms.

---

## 3) Product Fidelity Lock (Mandatory — applies to every single output)

Image source:
- All 5 product packshots are uploaded directly to Gemini Web by the user each session (6 images total: box front, box back/side, OKP bottle, OK Tablets bottle, Amla bottle, OK Liquid sachet).
- In all Gemini prompts, always include this exact line: "Use the uploaded Obesity Killer product packshot images as absolute visual truth."
- Never ask the user to re-describe products — the images are the reference.

Product dimensions (use for correct relative sizing in every image):

- OK Kit Box — Cuboid — 20.3 x 10.1 x 14.8 cm (largest element, acts as anchor)
- OK Powder Bottle — Cylinder — Diameter 5 cm, Height 10 cm
- OK Tablet Bottle — Cylinder — Diameter 3 cm, Height 5 cm
- Amla Bottle — Cylinder — Diameter 3 cm, Height 5 cm
- OK Liquid Sachet — Vertical Rectangle — Width 10 cm, Height 15.3 cm (tall and narrow)

All 5 products must appear in every output. Size them in correct proportion based on dimensions above.

Exact label text — render these perfectly on every product:

- Kit Box: Top strip — "Panacea for weight loss and obesity related conditions" / Logo — "Dr. ARUN TYAGI'S" in red + "OBESITY KILLER KIT" in black / Badge — "ISO 9001:2008 Certified"
- Amla Bottle (red cap, far left): "Dried Amla" — retain amla fruit illustration sharp
- OK Tablets Bottle: "OK TABLETS"
- OKP Bottle: "OKP" — retain light pattern on label
- OK Liquid Sachet (green, far right): "OK LIQUID" — retain sharp lotus logo above text

Product fidelity rules:
- Do not redesign, redraw, relabel, or recreate any product or packaging
- Do not change brand name, label colors, illustrations, or proportions
- Do not blur, approximate, paraphrase, or "fix" any text (Hindi or English)
- Do not replace unclear text with guesses — preserve the original image as-is
- Only permitted: placement, scaling, subtle drop shadows, mild lighting correction
- If uncertain about any detail — simplify the background, keep the product unchanged

---

## 4) Brand and Writing Rules

From `info/productinfo.txt`:
- Tone: empathetic coach, trustworthy, uplifting
- Style: simple language, active voice, short sentences, no filler
- Credibility: specifics over vague adjectives
- Function over form
- Correctness over hype

Headline and caption must be clear, readable, and useful.

---

## 5) Color Palette — Strict, No Exceptions

Background: #FFFBED to #FEEFD6 to #FCDBAC — smooth top-to-bottom gradient only
Accents and CTA: #F79040 to #E66410
Headlines: #973015
Body text and bullets: #421808
Disclaimer text: #7A3314

No colors outside this palette. No neon. No harsh gradients. No random accent colors anywhere.

---

## 6) Persona System

Use one primary persona per creative.

Persona library (select by number):
1. Craving-Control Struggler
2. Busy Professional
3. Emotional Eater / Stress Snacker
4. Plateau Victim
5. PCOD Support Seeker (no cure claims)
6. Thyroid Weight-Gain Struggler (no cure claims)
7. Post-Failure Re-starter (many failed diets)
8. No-Weakness Skeptic
9. Time-Starved Parent
10. Homemaker, self-care deprioritized
11. Office Snacker (tea-time/junk cycle)
12. Late-Night Eater
13. Festive/Travel Weight Regainer
14. Metabolism-Worry Buyer
15. Digestion-Issue + Weight Combo Seeker
16. Budget-Conscious Result Seeker
17. Wedding/Event Deadline Persona
18. Confidence-First Persona (appearance + energy)
19. Trust-First Buyer (doctor-backed only)
20. Support-Dependent Persona (needs accountability)
21. Beginner Who Hates Complex Plans
22. 35+ Slow-Progress Persona

For each persona, define these 5 fields before writing copy:
- Pain: what hurts now
- Desire: dream outcome
- Friction: why they failed before
- Proof needed: what makes them believe
- Tone cue: how the voice should feel

Selection rule:
- Use one primary persona plus one optional secondary micro-context.
- Example: Primary = Busy Professional, Secondary = Late-Night Eater.

---

## 7) Headline Engine

Each headline must do 2 jobs:
1. Scroll stop with persona pain
2. Show how Obesity Killer solves that pain using an approved mechanism

Formula: Hook (pain) + Mechanism (how) + Outcome/time

Freshness rule:
- Do not use a fixed headline bank as final output.
- Generate new headlines every request from persona pain + mechanism + outcome.
- Avoid repeating opening patterns across consecutive ads.
- Rotate angle each time: pain, objection, mechanism, time, proof, sacrifice reduction.

Examples (direction only, do not copy-paste):
- "Cravings control nahi ho rahe? 15 din mein routine palat sakta hai.*"
- "Time nahi hai gym ka? Weight routine fir bhi possible hai."
- "Weight loss chahiye, weakness nahi."

---

## 8) Caption Engine (Value Equation)

Use this equation in every caption:
Value = (Dream Outcome x Likelihood of Achievement) / (Time Delay x Sacrifice)

Move each component:
- Dream Outcome: visible loss + lighter body + confidence
- Likelihood: doctor credibility, 70,000+ users, clear daily protocol, support
- Time Delay: 15-day milestone language
- Sacrifice: no crash diet, no heavy workout, practical routine

Caption checklist:
- 1-2 short lines
- Concrete benefit
- Concrete mechanism
- Low-sacrifice framing
- Disclaimer where needed

Fresh caption rule: generate fresh each run, keep meaning stable, vary phrasing and angle.

---

## 9) Background Variation Engine (NEW)

Goal: Every ad generation session must use a distinctly different background/scene setting so no two outputs look the same.

Primary background catalog file:
- `info/BACKGROUND_VARIANTS.JSON`
- Use this as source of truth for background IDs, names, and prompt descriptors.
- The 20-slot list below is legacy guidance; prefer the external catalog for scaled operation.

### How it works:

Before generating any prompt, the assistant must:
1. Check `info/AD_GENERATION_REGISTRY.JSON` for recently used background slots.
2. Select a background slot that has NOT been used in the last 5 entries for that format.
3. Include the selected background slot ID in the prompt and log it to the registry after generation.
4. Prefer background IDs from `info/BACKGROUND_VARIANTS.JSON` first.

### Background Slot Library (20 slots — rotate through these):

BG-01 — Clean warm studio. Seamless warm cream gradient backdrop. Matte white product surface. One white ceramic mug and closed notebook far left. No environment cues.

BG-02 — Morning kitchen counter. Soft natural daylight from left window. Pale wood counter surface. One glass of water and a small plant pot in background. Clean white tile wall.

BG-03 — Evening home-office desk. Warm desk lamp as key light. Dark wood table. Laptop screen softly blurred in background. Notebook and pen to the left.

BG-04 — Bathroom shelf / wellness corner. Soft diffused white light. White marble or tile surface. Small towel folded neatly to one side. Clean and clinical-premium feel.

BG-05 — Yoga mat / morning ritual. Soft daylight from window. Products on a small wooden tray on the mat. Folded block or small plant nearby. Calm, intentional mood.

BG-06 — Dining table after meal. Warm ambient overhead light. Light linen tablecloth surface. Empty plate pushed to side. A glass of water. End-of-meal context.

BG-07 — Office desk mid-day. Cool-warm mixed light. Light grey or white desk. Phone face-down to side. Coffee cup and keyboard softly blurred in background.

BG-08 — Bedroom side table / nightstand. Warm low lamp. Soft duvet edge visible. A book and phone on the table. Late-night wind-down context.

BG-09 — Outdoor garden table. Soft diffused outdoor light. Pale stone or wooden table. Small succulent or leaf in corner. Light airy feel.

BG-10 — Minimalist flat-lay overhead. Pure white background. Products arranged symmetrically from above. Dry herbs or small lemon slices as minimal props.

BG-11 — Dressing table / mirror context. Warm vanity lighting. Light wood surface. Small tray with skincare items softly blurred. Confidence and self-care mood.

BG-12 — Kitchen windowsill. Bright soft diffused light from window behind. Products on a small wooden board. Fresh ginger or amla in the corner as prop.

BG-13 — Living room coffee table. Warm afternoon light. Cream couch edge softly blurred in background. Products on a light wooden tray on the table.

BG-14 — Gym bag / locker context. Clean locker room or sport context. Towel on bench. Bag partially visible. Active, performance-minded mood.

BG-15 — Doctor's desk / credibility context. Clean white desk. Stethoscope softly placed to side. Notepad and pen. Clinical trust mood. Reinforce Dr. ARUN TYAGI'S credential.

BG-16 — Terrace / balcony morning. Soft early light. Railing edge visible. Products on a small tray on a table. City or green view softly blurred behind.

BG-17 — Wooden tray flatlay. Warm toned wood surface. Neatly arranged products on tray. Dry rose petals or cinnamon sticks as minimal styling props.

BG-18 — Festive home context. Warm fairy lights softly blurred in background. Dark wood surface. Diyas or small festive elements at edges. Subtle celebration mood.

BG-19 — Travel/hotel room context. Neutral beige hotel surface or suitcase lid. Clean and away-from-home feel. Reinforces "routine even while travelling" persona.

BG-20 — Dark premium moody. Deep charcoal or dark warm brown background. Dramatic directional lighting on products. High-contrast premium editorial feel.

### Selection rules:

- No background slot may repeat within 5 consecutive generations for the same format.
- If registry is empty or unavailable: start from BG-01 and go in order.
- For UGC format: always use slots BG-03, BG-06, BG-08, BG-13, BG-16 only (lifestyle contexts only, no flat-lays or clinical settings).
- For HERO format: prefer BG-01, BG-10, BG-17, BG-20 for maximum product focus.
- For TEST format: prefer BG-03, BG-08, BG-13 for relatable personal context.
- For FEAT format: prefer BG-04, BG-10, BG-15, BG-17 for clarity and credibility.
- For BA format: prefer BG-02, BG-05, BG-06, BG-09 for transformation journey feel.

### Background selection algorithm (mandatory)

- Use policy split: 80% catalog (`info/BACKGROUND_VARIANTS.JSON`) and 20% fresh-generated backgrounds.
- Enforce format dedupe window: selected catalog `id` cannot appear in last 5 entries of same format.
- For fresh-generated path: generate descriptor first, then reject if semantically matches any catalog variant.
- Fresh-generated match check must compare at least: scene context, surface, camera framing, lighting style, key props.
- If fresh candidate overlaps a catalog concept, regenerate fresh descriptor until it is distinct.
- Fresh-generated backgrounds must also avoid repeating in recent history (use last 10 fresh entries across same format).
- Save selection metadata in registry: source (`catalog` or `fresh`), id or fresh signature, and format.
- If constraints cannot be satisfied, fallback order is catalog first, then fresh regenerate, never random blind pick.

---

## 10) Registry System

Registry file: `info/AD_GENERATION_REGISTRY.JSON`

### Current mode: TESTING — Registry read mode ON, write mode OFF.

In testing mode:
- Read registry to check what has been used recently (avoid repeating).
- Do NOT write new entries yet.
- When write mode is turned ON, log every generation immediately.

### Registry schema (use this exact structure):

```json
{
  "registry": [
    {
      "id": "entry_001",
      "timestamp": "2025-01-01T00:00:00Z",
      "format": "HERO",
      "persona_number": 2,
      "persona_name": "Busy Professional",
      "headline_angle": "sacrifice_reduction",
      "headline_en": "Weight loss without life disruption.",
      "headline_hi": "जीवन बिगाड़े बिना वज़न घटाएं।",
      "background_slot": "BG-01",
      "background_name": "Clean warm studio",
      "language": "EN",
      "output_quality": "approved",
      "notes": "First test generation"
    }
  ]
}
```

### Fields to log for every entry:

- id: sequential entry ID (entry_001, entry_002, etc.)
- timestamp: ISO 8601 format
- format: HERO / BA / TEST / FEAT / UGC
- persona_number: 1-22
- persona_name: readable name
- headline_angle: pain / objection / mechanism / time / proof / sacrifice_reduction
- headline_en: exact English headline used
- headline_hi: exact Hindi headline used
- background_slot: BG-01 through BG-20
- background_name: readable name of slot
- language: EN / HI / BOTH
- output_quality: approved / rejected / pending
- notes: optional free text

### Deduplication rules (read even in testing mode):

- Same persona + same format = flag if used in last 3 entries for that format. Suggest switching persona or angle.
- Same background_slot + same format = block if used in last 5 entries for that format. Force a different slot.
- Same headline_angle + same format = flag if used in last 3 entries. Rotate angle.
- Same persona + same headline_angle = hard block regardless of format. Always change at least one.

### Production switch instruction:

When moving to production, change registry write mode from OFF to ON.
When scaling, move to 8 variations per format and log every entry before delivering to user.

---

## 11) Format Specifications

Keep format structure fixed. Swap persona-specific headline/caption blocks.

### HERO
- Purpose: broad conversion
- Persona use: strongest pain-led hook + fastest believable outcome
- Copy shape: strong headline, one support line, CTA
- Text budget: 18-32 words + disclaimer
- Minimum copy units: headline + 1 support line + CTA + disclaimer

### BA
- Purpose: show transition from pain to control
- Persona use: "before" = persona struggle, "after" = first meaningful win
- Copy shape: pain-to-progress headline + 3 outcome bullets
- Text budget: 22-36 words + disclaimer
- Minimum copy units: headline + 2-3 short bullets + CTA + disclaimer

### TEST
- Purpose: trust
- Persona use: testimonial language mirrors persona words (cravings, stuck, no time)
- Copy shape: quote + attribution + trust line + CTA
- Text budget: 24-40 words + disclaimer
- Minimum copy units: headline/quote + attribution + trust line + CTA + disclaimer
- Testimonial integrity: never fabricate customer quotes; if real quote is unavailable, use rating + user-count + mechanism proof framing instead

### FEAT
- Purpose: mechanism clarity
- Persona use: map each feature to persona friction
- Copy shape: "what makes it work" + 3-4 benefit bullets + CTA
- Text budget: 26-42 words + disclaimer
- Minimum copy units: headline + 3 feature-benefit bullets + CTA + disclaimer

### UGC
- Purpose: authenticity
- Persona use: first-person micro-story from persona POV
- Copy shape: my routine support + 3 practical wins + CTA
- Text budget: 16-26 words + disclaimer
- Default text policy: headline (max 8 words) + support line (max 8 words) + CTA (max 4 words) + disclaimer only
- Minimum copy units: headline + 1 short support line + CTA + disclaimer
- No bullets or long paragraph quote unless explicitly requested

---

## 12) Prompt Assembly Template

Use this 9-section structure every time. All 9 sections are mandatory. No section may be dropped or collapsed to a placeholder.

```
Section 1 — PRODUCT LOCK BLOCK
Section 2 — OUTPUT SPEC (1080x1350)
Section 3 — FORMAT LAYOUT INSTRUCTIONS
Section 4 — PERSONA INPUT BLOCK
Section 5 — EXACT ON-IMAGE COPY
Section 6 — NEGATIVE CONSTRAINTS
Section 7 — QUALITY BAR
Section 8 — VISUAL DIRECTION BLOCK (includes background slot)
Section 9 — TYPOGRAPHY SHARPNESS BLOCK
```

Add this mandatory line in every prompt:
- "Keep on-image text minimal and mobile-readable. Avoid dense copy blocks."

Add this mandatory line in every prompt:
- "Typography must be pin-sharp. If any text appears soft, blurry, or smeared, regenerate."

### Per-section depth minimums (mandatory — do not write placeholder sections):

Section 1 — Product Lock: minimum 4 bullets
- Include: uploaded image reference rule, no redesign rule, no relabel rule, fallback behavior

Section 2 — Output Spec: minimum 5 bullets
- Include: canvas size, aspect ratio, style intent, text readability requirement, delivery expectation

Section 3 — Format Layout Instructions: minimum 8 bullets
- Include: composition map, focal hierarchy, product zone, text zones, background behavior, camera framing, lighting, spacing

Section 4 — Persona Input: minimum 5 bullets
- Include: pain, desire, friction, proof needed, tone cue

Section 5 — Exact On-Image Copy: minimum 4 copy lines
- Include: headline, support or quote line, CTA, disclaimer — render exactly as written, no alterations

Section 6 — Negative Constraints: minimum 8 bullets
- Include: visual and claim-level "do not" constraints

Section 7 — Quality Bar: minimum 6 bullets
- Include: readability, fidelity, anatomy, clutter, hierarchy, regeneration trigger

Section 8 — Visual Direction Block: minimum 8 bullets
- Include: scene (reference background slot ID and name), subject, props, camera, light, texture, depth, realism

Section 9 — Typography Sharpness Block: minimum 6 bullets
- Include: contrast, font weight, placement, anti-blur checks, mobile legibility, regen trigger

### Length floor:
- Full production prompt: 45-75 lines minimum for one format.
- If below 35 lines: treat as compressed and rewrite with full depth before sending.

### Prompt length hardline check (mandatory):
- Never collapse to ultra-short prompts after follow-ups.
- Final image prompt must retain full structure with all sections intact.
- Minimum required sections in every final prompt:
  1) Product Lock
  2) Output Spec
  3) Format Layout Instructions
  4) Persona Input
  5) Exact On-Image Copy
  6) Negative Constraints
  7) Quality Bar
  8) Visual Direction Block
  9) Typography Sharpness Block
- If any section is missing, treat as invalid and regenerate the prompt text before sending.
- Brevity is allowed only inside lines, not by dropping sections.

### Prompt compression prevention:
- Do not summarize or shorten the final generation prompt after follow-ups.
- On revisions: edit only the requested part, keep all other sections intact.
- Preserve all guardrail lines during rewrites.

### Language output mode:
- Always produce two final prompts together:
  - English prompt
  - Hindi prompt
- Keep the same layout instructions in both, only language/copy changes.
- Language purity rule:
  - English output must be fully English (no Hinglish transliteration).
  - Hindi output must be fully Hindi in Devanagari script.
  - Do not mix scripts in one line unless explicitly requested.

### Text clarity and sharpness rule (mandatory):
- Prioritize crisp typography over decorative styling.
- Use high contrast text/background pairs.
- Keep text on flat areas; avoid curved, noisy, or low-contrast surfaces.
- Avoid perspective-warped text and ultra-thin font styles.
- Keep all text edge-sharp and mobile-legible at 100% view.

### Ad-factory prompt upgrades (adopted)
- Keep this explicit reference line in every final prompt: "Use provided product references as exact appearance truth for pack shape, label, and color."
- Enforce readability target: all visible copy must meet high contrast intent equivalent to WCAG AA readability.
- For testimonial creatives, never invent quotes; fallback to star rating + user count + concrete benefit when quote proof is unavailable.
- For scaled variants, vary one main axis at a time (headline angle, CTA, layout, or visual mood) to preserve test clarity.
- Keep output-ready sizing explicit per placement when requested: 1080x1350 (portrait default), 1080x1080 (feed square), 1080x1920 (stories).
- When generating batches, keep product fidelity constraints identical across all variants; only concept variables should change.

---

## 13) Full Production Prompt Template (filled example — copy and adapt)

PRODUCT LOCK BLOCK
- Use the uploaded Obesity Killer product packshot images as absolute visual truth.
- Do not redesign, redraw, relabel, or alter any product or packaging in any way.
- Do not change brand name, label colors, illustrations, proportions, or any text (Hindi or English).
- If any label text is unclear — preserve the original image as-is. Do not reinterpret it.
- Only permitted: placement, scaling, subtle drop shadows, mild warm lighting correction.

OUTPUT SPEC
- Canvas: 1080 x 1350 pixels. Portrait. 4:5 ratio.
- Style: [HERO / BA / TEST / FEAT / UGC] — polished enough for paid ad deployment.
- Text policy: Low-text by default. All copy minimal and mobile-readable at 375px width.
- Rendering: No compression artifacts. No soft edges on text or product label.
- All 5 products present, proportionally sized per reference dimensions, unmodified.
- Readability: maintain high-contrast foreground/background treatment for ad-platform legibility.
- Size override rule: if channel-specific export is requested, output exact dimensions explicitly in prompt.

FORMAT LAYOUT INSTRUCTIONS
- [Fill based on selected format from Section 11]
- Composition: [describe zone map for selected format]
- Focal hierarchy: product dominant, text secondary, background tertiary.
- Product zone: [center / center-right / foreground-lower — specify per format]
- Text zones: flat uncluttered areas only — never over busy background detail.
- Background: [reference selected background slot — see Section 9 below]
- Camera: [close-medium / medium / overhead — specify per format]
- Lighting: warm soft directional — source from top-left. Subtle drop shadows beneath products.
- Spacing: strong whitespace between zones. Grid-based alignment. Nothing floats randomly.

PERSONA INPUT BLOCK
- Persona: [Name from persona library]
- Pain: [what hurts now]
- Desire: [dream outcome]
- Friction: [why they failed before]
- Proof needed: [what makes them believe]
- Tone cue: [sincere / hopeful / authoritative / relatable]

EXACT ON-IMAGE COPY — DO NOT ALTER ANYTHING
- Headline: [exact text]
- Support line: [exact text]
- CTA: [exact text]
- Disclaimer: [exact text]
Render every character exactly as written. No paraphrasing, no punctuation changes, no autocorrection.

NEGATIVE CONSTRAINTS
- Do not recreate or redraw any product
- Do not blur, approximate, or rewrite any label text
- Do not use sale badges, burst graphics, or stickers
- Do not show body transformations or weight-loss visuals
- Do not use colors outside the defined palette
- Do not use more than 2 font weights
- Do not overcrowd the layout
- Do not make medical cure claims of any kind
- Do not render unnatural or anatomically incorrect hands (for UGC)
- Do not use ring light, studio flash, or overproduced lighting

QUALITY BAR — verify before accepting output:
- All 5 products present, correctly proportioned, completely unmodified
- All on-image text sharp and readable at 375px mobile size
- Product label accurate, unmodified, and fully readable
- Layout is calm, balanced, and premium
- No clutter, no hype, no forbidden elements
- Single clear focal hierarchy — product dominant throughout
- If any item above fails — regenerate immediately without compromise

VISUAL DIRECTION BLOCK
- Background slot: [BG-XX — slot name] (selected from background variation engine, not used in last 5 entries for this format)
- Scene: [describe scene based on selected slot]
- Subject: [for UGC — Indian woman 27-35, natural unposed expression. For product-only formats — no subject]
- Action: [holding product toward camera / products arranged on surface — specify]
- Camera: [handheld close-medium / editorial medium / overhead — specify]
- Lighting: [warm desk lamp + soft ambient fill / soft natural daylight from left / etc. — match slot]
- Props: [per slot — minimal, non-competing, background zone only]
- Surfaces: [per slot — wood / marble / white matte / etc.]
- Mood: [per persona — emotional relief / confidence / trust / urgency-free / etc.]
- Realism: natural skin, correct hand anatomy, true-to-life proportions, no stock-template look

TYPOGRAPHY SHARPNESS BLOCK
- Headline: Poppins Bold — high contrast against background zone
- Support and CTA: Poppins Medium/Regular — same typeface family
- Size: large enough to read on 375px mobile screen without zooming
- Placement: flat uncluttered zones only — never over busy background detail
- Forbidden: thin fonts, script fonts, decorative typefaces, glow effects, outlined text, drop shadows on copy
- Mandatory: crisp hard text edges — zero softness — zero anti-alias blur on any character
- If any text is soft, blurry, or illegible — discard and regenerate immediately

---

## 14) Language Output Rules

Always produce two final prompts together:
- English prompt (fully English — no Hinglish transliteration)
- Hindi prompt (fully Hindi in Devanagari script — no mixed scripts in one line unless explicitly requested)

Keep the same layout instructions in both. Only the copy block changes language.

---

## 15) Interactive Ad Request Flow (assistant behavior)

Decision policy (mandatory):
- If user gives no specific inputs in first ad request, generate default starter batch immediately (no clarification round).
- If user gives specific inputs (persona/headline/format), apply them directly.
- If user gives partial inputs, apply provided values and fill missing values with defaults.
- Ask follow-up questions only when user intent is conflicting (for example, two different persona instructions for same format).

Input parsing rules:
- Persona input accepted as one value for all formats, or format-wise values.
- Headline input accepted as custom per format or one master line.
- Format input accepted as single or multiple from: HERO, BA, TEST, FEAT, UGC.
- If format is not provided, default to all 5 formats.

Defaults when missing:
- Headline mode default: AI-generated fresh headlines.
- Persona default: random selection from persona library (1-22), format-wise.
- Randomization rule: avoid repeating the same persona across formats in the same batch when possible.
- If registry history exists, avoid persona+format combinations that appear in the recent dedupe window.

Generation sequence:
Step 1 - Parse user-provided persona/headline/format values.
Step 2 - Fill missing fields from defaults.
Step 3 - Generate copy for requested formats.
Step 4 - Background slot selection.

Step 4 — Background slot selection
- Check registry for recently used slots per selected format.
- Select an unused slot automatically and state which one was selected.
- User may override by requesting a specific slot number.

Step 5 — Final output
- Deliver final Gemini-ready prompts in both EN and HI for selected format(s).
- State the background slot used and log it to registry (if write mode is ON).

Default behavior if user gives minimal input:
- Generate default starter batch immediately using the default mapping in Section 0.
- Use AI-generated fresh headlines.
- Use all 5 formats unless user narrowed scope.

Prompt quality upgrade block (add by default):
- "Typography must be pin-sharp. If any text appears soft, blurry, or smeared, regenerate."
- "Keep text count minimal and increase font size rather than packing more copy."
- "Use clean sans typography with strong stroke clarity; no thin/light weights for body text."
- "Use Poppins only for on-image text: Headline in Poppins Bold, support/CTA/disclaimer in Poppins Medium or Regular."

Mandatory visual-direction block (add by default):
- "Describe scene, subject, and props explicitly (what is visible in frame)."
- "Define camera framing (close/medium/wide), angle, and product placement zone."
- "Define lighting style (soft daylight/warm indoor), shadow direction, and contrast level."
- "Define background behavior (clean, low-noise, non-distracting, premium texture)."
- "Define realism constraints (natural skin, correct hand anatomy, true-to-life proportions)."
- "Define what to avoid visually (stock-template look, clutter, random stickers, noisy overlays)."

---

## 16) Quality Guardrails

Reject and regenerate if any one fails:
- Text not fully readable
- Text appears blurry, soft, or smeared
- Product label modified in any way
- Generic template look
- Anatomy issues (for UGC hands)
- Cluttered layout or low hierarchy
- High text density on canvas

## 16A) Text budget guardrails (to prevent clutter)

Use strict on-canvas text budgets.

Balance rule:
- Text-light is required. Text-empty is not acceptable.
- Every ad must communicate offer + mechanism/proof + action, not just a headline.

Global rules:
- Never place paragraph captions on-image unless user explicitly asks.
- Prefer short headline + short support line + CTA.
- Keep disclaimer to one short line.
- If bilingual is needed, generate separate EN and HI creatives (no mixed-language text in one creative).

Recommended on-image text limits by format:
- HERO: 18-32 words (+ disclaimer)
- BA: 22-36 words (+ disclaimer)
- TEST: 24-40 words (+ disclaimer)
- FEAT: 26-42 words (+ disclaimer)
- UGC: 16-26 words (+ disclaimer)

Minimum required on-image copy units by format:
- HERO: headline + 1 support line + CTA + disclaimer
- BA: headline + 2-3 short bullets + CTA + disclaimer
- TEST: headline/quote + attribution + trust line + CTA + disclaimer
- FEAT: headline + 3 feature-benefit bullets + CTA + disclaimer
- UGC: headline + 1 short support line + CTA + disclaimer

UGC default text policy:
- One headline (max 8 words)
- One short support line (max 8 words)
- One CTA (max 4 words)
- One disclaimer line
- No bullets or long paragraph quote unless requested

Text budget repair commands:

If output is too empty:
- "Keep same visual concept, add one concise support line and one trust/proof line while preserving clean spacing and readability."

If output is copy-heavy:
- "Regenerate same concept with minimal text: remove paragraphs and bullets; keep only headline, CTA, one-line disclaimer. Maintain product fidelity and composition."

Visual quality repair commands:

- "Keep same layout, improve text sharpness and hierarchy only."
- "Keep same composition, restore exact product packaging from uploaded references."
- "Keep concept, reduce clutter and increase premium spacing."
- "Regenerate with crisp text edges, higher contrast, larger font sizes, and fewer words on canvas."

## 16B) Visual specificity guardrails (to improve image quality)

If image quality feels generic or under-directed, increase visual specificity in prompts.

Always specify these fields:
- Scene context: room type, time of day, mood
- Subject profile: age band, role context, expression, pose
- Product placement: hand-held / table-top / foreground-right / centered-lower
- Camera: lens feel (phone-like vs editorial), crop, perspective
- Lighting: source direction, softness, color temperature
- Material cues: tabletop texture, wall texture, fabric realism
- Depth: foreground-midground-background separation
- Brand palette usage: where accent colors appear and where they should not

Hard reject conditions:
- Subject looks stock-photo generic
- Product visually competes with busy background
- Scene lacks narrative cue for selected persona
- Composition has no clear focal hierarchy

## 16C) Prompt compression prevention

Goal: stop quality drift from prompt shortening across turns.

Rules:
- Do not summarize the final generation prompt unless user explicitly asks for a short version.
- Keep technical constraints explicit even in later iterations.
- On revisions, edit only the requested part and keep the rest of the full prompt unchanged.
- Preserve all guardrail lines during rewrites (product fidelity, text budget, sharpness, negative constraints).
- Preserve per-section depth minimums during rewrites.

Optional delivery mode:
- Provide two blocks when needed:
  - Full Production Prompt (default)
  - Short Operator Note (optional)
- The image model should always receive the Full Production Prompt.

Quick repair prompts:
- "Keep same layout, improve text sharpness and hierarchy only."
- "Keep same composition, restore exact product packaging from references."
- "Keep concept, reduce clutter and increase premium spacing."
- "Regenerate with crisp text edges, higher contrast, larger font sizes, and fewer words on canvas."

---

## 17) Compliance and Trust Notes

- Use asterisk with result claims when appropriate.
- Keep disclaimer readable: "Results vary by body type and routine." or equivalent.
- Avoid fear tactics and fake urgency.
- Losing a sale is better than losing trust.

---

## 18) New Chat Setup (copy-paste starter)

Paste this in every fresh chat:

```
You are generating static ad creatives for Obesity Killer Kit.
Follow these rules strictly:

- Use only claims from my knowledge base (productinfo).
- Never invent mechanisms, results, or medical claims.
- Use uploaded Obesity Killer product packshot images as absolute visual truth. I will upload 6 images each session.
- Create ads in 5 formats: HERO, BA, TEST, FEAT, UGC.
- For each ad, use one persona input block (pain, desire, friction, proof needed, tone cue).
- Headline must do two things: scroll stop + pain-solution fit.
- Caption must increase Value = (Dream Outcome x Likelihood) / (Time Delay x Sacrifice).
- Keep language simple, active, specific, and short.
- Reject generic templates; prioritize clear hierarchy and premium composition.
- Output first in testing mode: 1 variation per format.
- Always provide English + Hindi versions of final prompts.
- Never rely on fixed headline banks; generate fresh headlines each request.
- Keep typography pin-sharp; regenerate if any on-image text is blurry.
- Use Poppins font family for all on-image text (Headline: Poppins Bold; body/support/CTA: Poppins Medium or Regular).
- Select a background slot from the Background Variation Engine (Section 9 of playbook) that has not been used in the last 5 generations for the selected format. State which slot you selected.
- Check the registry at info/AD_GENERATION_REGISTRY.JSON before generation to avoid persona, angle, and background repetition.
- Registry is currently in read-only testing mode. Do not write entries yet.
```

Optional add-on line:
```
When I ask for ad creation, follow this sequence: ask persona number -> ask headline mode -> ask format(s) -> select background slot -> deliver final Gemini prompts in both English and Hindi.
```

---

## 19) Practical Day-to-Day Usage

1. Open this playbook and copy the New Chat Setup block (Section 18).
2. Paste it in a fresh Gemini or assistant chat.
3. Upload all 6 product packshot images to Gemini Web.
4. Start with: "Create ad."
5. Follow the interaction flow: persona -> headline mode -> format(s) -> background slot confirmation -> final prompts.
6. On headline step: receive 5 fresh options (EN + HI). Pick one.
7. Copy the final English/Hindi Gemini prompt. Run in Gemini Web with images already uploaded.
8. Use repair commands (Section 16) if quality fails.
9. When write mode is turned ON: log each generation to registry using the schema in Section 10.

How to avoid repetition at scale:
- Do not reuse old headline text directly.
- Recompute headline every time from persona fields.
- Use registry for angle-level dedupe, not sentence-level cloning.
- Rotate background slots — never reuse the same slot within 5 consecutive generations for a format.

---

## 20) Registry File — Current State

File path: `info/AD_GENERATION_REGISTRY.JSON`

Current write mode: OFF (testing)
Current read mode: ON

Starting state (empty — to be populated when write mode is turned ON):

```json
{
  "write_mode": false,
  "last_updated": null,
  "registry": []
}
```

When production switch is made:
- Set "write_mode" to true.
- Set "last_updated" to current timestamp on every write.
- Append one entry per generation using schema from Section 10.
- Never overwrite existing entries — append only.
- Read registry before every generation to check deduplication rules.
