#!/usr/bin/env python3
"""
Assembler-only ad prompt generator.

What this script does:
  - Reads externally-generated ad copy from a JSON file (no copy generation here).
  - Selects catalog background slots with exhaustive per-format rotation.
  - Builds seeded background sentence from `background_variant.json`.
  - Assembles full 9-section prompts per playbook and writes `output/vN/OUTPUT_<FORMAT>_(EN|HI).txt`.
  - Enforces safe-zone rules by embedding an explicit SAFE-ZONE ENFORCEMENT block.
  - Appends entries to `AD_GENERATION_REGISTRY.JSON` and updates indexes (background rotation + used_text).

What this script explicitly does NOT do:
  - It does not call any LLM.
  - It does not invent persona fields or ad copy.
  - It does not “freshen” text; freshness is enforced by strict uniqueness checks against registry.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "AD_GENERATION_REGISTRY.JSON"
BACKGROUNDS_PATH = ROOT / "background_variant.json"
OUTPUT_DIR = ROOT / "output"

SUPPORTED_FORMATS = {"HERO", "BA", "TEST", "FEAT", "UGC"}
SUPPORTED_LANGS = {"EN", "HI"}


@dataclass(frozen=True)
class CopyBlock:
    headline: str
    cta: str
    support_line: str = ""
    trust_line: str = ""
    attribution: str = ""
    bullets: list[str] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble ad prompts from external copy JSON + catalog backgrounds")
    parser.add_argument("--copy-file", required=True, help="Path to copy batch JSON (produced by your LLM/operator step)")
    parser.add_argument("--batch", help="Output batch folder name like v8 (default: next available)")
    parser.add_argument("--seed", type=int, help="Deterministic seed for background rotation order + background sentence sampling")
    parser.add_argument("--language-mode", choices=["BOTH", "EN", "HI"], default="BOTH", help="Which prompt languages to assemble")
    parser.add_argument("--no-registry-write", action="store_true", help="Skip writing AD_GENERATION_REGISTRY.JSON updates")
    parser.add_argument("--skip-uniqueness-check", action="store_true", help="Allow duplicate copy values against registry")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print plan without writing files")
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_batches(output_dir: Path) -> list[int]:
    if not output_dir.exists():
        return []
    out: list[int] = []
    for child in output_dir.iterdir():
        if child.is_dir():
            m = re.match(r"^v(\d+)$", child.name)
            if m:
                out.append(int(m.group(1)))
    return sorted(out)


def next_batch_name(output_dir: Path) -> str:
    batches = list_batches(output_dir)
    return "v1" if not batches else f"v{batches[-1] + 1}"


def stable_fmt_seed(seed: int, fmt: str) -> int:
    return (seed * 31 + sum(ord(c) for c in fmt)) & 0x7FFFFFFF


def ensure_slot_tracker(registry: dict[str, Any], fmt: str, pool_ids: list[str], seed: int) -> dict[str, Any]:
    idx = registry.setdefault("indexes", {})
    tracker = idx.setdefault("slot_exhaustion_tracker", {}).setdefault(fmt, {})
    used = tracker.get("used") or []
    remaining = tracker.get("remaining") or []
    cycle = int(tracker.get("cycle_number") or 1)

    if remaining:
        tracker["used"] = used
        tracker["remaining"] = remaining
        tracker["cycle_number"] = cycle
        return tracker

    # Start (or restart) a cycle: refill remaining with a deterministic shuffle.
    if used:
        cycle += 1
    order = list(pool_ids)
    rng = random.Random(stable_fmt_seed(seed, fmt))
    rng.shuffle(order)

    tracker["cycle_number"] = cycle
    tracker["used"] = []
    tracker["remaining"] = order
    return tracker


def pick_background_slot(
    registry: dict[str, Any],
    backgrounds: dict[str, Any],
    fmt: str,
    seed: int,
) -> dict[str, Any]:
    variants: list[dict[str, Any]] = backgrounds.get("variants", [])
    pool = [v for v in variants if fmt in (v.get("formats") or [])]
    if not pool:
        raise RuntimeError(f"No background variants found for format {fmt}")
    pool_ids = [v["id"] for v in pool]
    tracker = ensure_slot_tracker(registry, fmt, pool_ids, seed)

    remaining: list[str] = tracker["remaining"]
    chosen_id = remaining.pop(0)
    tracker["used"].append(chosen_id)

    chosen = next((v for v in pool if v.get("id") == chosen_id), None)
    if not chosen:
        chosen = pool[0]
    default_overlay = backgrounds.get("default_text_overlay_treatment")
    if isinstance(default_overlay, list) and default_overlay and "text_overlay_treatment" not in chosen:
        chosen = dict(chosen)
        chosen["text_overlay_treatment"] = default_overlay
    return chosen


def get_background_by_id(backgrounds: dict[str, Any], fmt: str, bg_id: str) -> dict[str, Any]:
    variants: list[dict[str, Any]] = backgrounds.get("variants", [])
    wanted = bg_id.strip().upper()
    for item in variants:
        if str(item.get("id") or "").strip().upper() != wanted:
            continue
        formats = item.get("formats") or []
        if fmt not in formats:
            raise RuntimeError(f"Background {wanted} is not allowed for format {fmt}")
        default_overlay = backgrounds.get("default_text_overlay_treatment")
        if isinstance(default_overlay, list) and default_overlay and "text_overlay_treatment" not in item:
            item = dict(item)
            item["text_overlay_treatment"] = default_overlay
        return item
    raise RuntimeError(f"Background id not found: {wanted}")


def build_seeded_background_sentence(bg: dict[str, Any], seed: int, aspect_ratio: str) -> str:
    rng = random.Random(seed)
    base = bg["base"]
    lighting = rng.choice(bg["lighting"])
    surface = rng.choice(bg["surface"])
    environment = rng.choice(bg["environment"])
    mood = rng.choice(bg["mood"])
    camera = rng.choice(bg["camera"])
    color_tone = rng.choice(bg["color_tone"])
    composition = rng.choice(bg.get("composition") or ["balanced feed composition inside the central safe field"])
    layout_intent = rng.choice(bg.get("layout_intent") or ["preserve a stable center-of-interest corridor with consistent margin protection on every side"])
    cta_safe_space = rng.choice(bg.get("cta_safe_space") or ["maintain subtle low-contrast space near the lower edge to protect feed overlay readability"])
    crop_safety = rng.choice(bg.get("crop_safety") or ["maintain protected margin buffers so alternate crops do not clip meaningful scene structure"])
    text_overlay_treatment = rng.choice(
        bg.get("text_overlay_treatment")
        or [
            "if a text readability panel is used, keep it in the upper text zone only as a soft vertical fade (high opacity near top, fading to transparent before the product cluster), never behind or below products"
        ]
    )
    edge_tone_control = rng.choice(
        bg.get("edge_tone_control")
        or [
            "keep all frame edges tonally neutral with no orange, amber, or sepia cast; no border glow and no vignette halo"
        ]
    )

    if aspect_ratio == "9:16":
        format_clause = (
            "designed for 9:16 vertical placement with key subject content constrained to the 14-65 percent safe band, positioned slightly above center, and with the lower 35 percent kept visually quiet for overlays; avoid edge glow frames and tinted border gradients"
        )
    else:
        format_clause = (
            "designed for 4:5 feed framing with key content held inside the central safe field, centered to slightly above center, while top 10 percent, bottom 15 percent, and side edge zones remain low-priority; avoid edge glow frames and tinted border gradients"
        )

    return (
        f"{base} on a {surface}, with {environment}, lit by {lighting}, conveying {mood}; "
        f"{camera}, {composition}, {layout_intent}, {cta_safe_space}, {crop_safety}, {text_overlay_treatment}, {edge_tone_control}, {color_tone}, "
        f"{format_clause}, clean premium studio ad photography, ultra-detailed, flawless commercial finish."
    )


def build_ugc_subject_line(seed: int) -> str:
    rng = random.Random(seed)
    age_band = rng.choice(["24-29", "27-33", "30-36", "32-38"])
    tone = rng.choice(["calm confident", "warm assured", "focused optimistic", "grounded and practical"])
    attire = rng.choice([
        "solid kurta",
        "casual cotton shirt",
        "minimal blouse",
        "everyday premium casual wear",
    ])
    hair = rng.choice([
        "neat tied-back hair",
        "simple ponytail",
        "natural shoulder-length hair",
        "clean center-part tied style",
    ])
    return f"Indian woman {age_band}, {tone} expression, {attire}, {hair}; natural and unposed."


def safezone_enforcement_block(aspect_ratio: str) -> str:
    # Keep wording stable so downstream validators can key off consistent tokens.
    if aspect_ratio == "9:16":
        return (
            "SAFE-ZONE ENFORCEMENT (NON-NEGOTIABLE)\n"
            "- Keep all critical content inside the 14%-65% vertical safe band.\n"
            "- Reserve the lower 35% as quiet space; no product labels or headline copy in this band.\n"
            "- Keep side margins clean; no key content touching left or right frame edges.\n"
            "- Reject and regenerate if any headline, CTA, or product detail crosses restricted zones."
        )
    return (
        "SAFE-ZONE ENFORCEMENT (NON-NEGOTIABLE)\n"
        "- Frame: 1080x1350 (4:5).\n"
        "- Restricted bands: top 10% (0-135px), bottom 15% (1148-1350px), side edges outer 8% (0-86px and 994-1080px).\n"
        "- Keep all products and all on-image text fully inside the central safe field: x=86-994 and y=135-1148.\n"
        "- Keep the entire product cluster in a centered core with mild upward bias; do not touch any restricted band.\n"
        "- Reject and regenerate if any headline, CTA, or product detail crosses restricted zones."
    )


def require_str(obj: dict[str, Any], key: str, ctx: str) -> str:
    val = obj.get(key)
    if not isinstance(val, str) or not val.strip():
        raise RuntimeError(f"Missing or empty string '{key}' in {ctx}")
    return val.strip()


def require_int(obj: dict[str, Any], key: str, ctx: str) -> int:
    val = obj.get(key)
    if not isinstance(val, int):
        raise RuntimeError(f"Missing or non-int '{key}' in {ctx}")
    return val


def parse_copy_block(fmt: str, lang: str, raw: dict[str, Any]) -> CopyBlock:
    ctx = f"ads[].copy.{lang} for format={fmt}"
    headline = require_str(raw, "headline", ctx)
    cta = require_str(raw, "cta", ctx)
    support_line = (raw.get("support_line") or "").strip() if isinstance(raw.get("support_line"), str) else ""
    trust_line = (raw.get("trust_line") or "").strip() if isinstance(raw.get("trust_line"), str) else ""
    attribution = (raw.get("attribution") or "").strip() if isinstance(raw.get("attribution"), str) else ""
    bullets_val = raw.get("bullets")
    bullets: list[str] | None = None
    if bullets_val is not None:
        if not isinstance(bullets_val, list) or not all(isinstance(x, str) and x.strip() for x in bullets_val):
            raise RuntimeError(f"'bullets' must be a non-empty string list when present in {ctx}")
        bullets = [x.strip() for x in bullets_val]
        if fmt == "BA":
            bullets = [strip_ba_panel_label(x) for x in bullets]
    return CopyBlock(
        headline=headline,
        cta=cta,
        support_line=support_line,
        trust_line=trust_line,
        attribution=attribution,
        bullets=bullets,
    )


def strip_ba_panel_label(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^\s*(?:before|after)\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(?:पहले|बाद|पहले\s*में|बाद\s*में)\s*[:\-]\s*", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def registry_used_text(registry: dict[str, Any]) -> dict[str, set[str]]:
    buckets = (registry.get("indexes", {}) or {}).get("used_text", {}) or {}
    out: dict[str, set[str]] = {}
    for bucket, arr in buckets.items():
        if not isinstance(arr, list):
            continue
        out[bucket] = {s.strip() for s in arr if isinstance(s, str) and s.strip()}
    return out


def uniqueness_check(
    used: dict[str, set[str]],
    bucket: str,
    value: str,
    collisions: list[str],
    ctx: str,
) -> None:
    if value.strip() and value.strip() in used.get(bucket, set()):
        collisions.append(f"{ctx} collides with registry used_text.{bucket}: {value!r}")


def add_used_text(registry: dict[str, Any], bucket: str, values: list[str]) -> None:
    idx = registry.setdefault("indexes", {}).setdefault("used_text", {}).setdefault(bucket, [])
    for v in values:
        s = (v or "").strip()
        if s:
            idx.append(s)


def next_entry_id(registry: dict[str, Any]) -> str:
    entries = registry.get("entries") or []
    if not entries:
        return "entry_001"
    last = entries[-1].get("id", "")
    m = re.match(r"^entry_(\d+)$", str(last))
    if not m:
        return f"entry_{len(entries) + 1:03d}"
    return f"entry_{int(m.group(1)) + 1:03d}"


def append_background_index(registry: dict[str, Any], fmt: str, entry_id: str, timestamp: str, bg_id: str) -> None:
    idx = registry.setdefault("indexes", {}).setdefault("backgrounds_by_format", {}).setdefault(fmt, [])
    idx.append({"entry_id": entry_id, "timestamp": timestamp, "background_slot": bg_id, "background_source": "catalog"})


def render_prompt(
    fmt: str,
    lang: str,
    aspect_ratio: str,
    persona: dict[str, Any],
    copy: CopyBlock,
    bg: dict[str, Any],
    bg_seed: int,
    seeded_sentence: str,
    visual_lock: dict[str, Any] | None = None,
) -> str:
    if fmt == "HERO":
        style = "HERO, polished enough for paid ad deployment."
    elif fmt == "BA":
        style = "BA (before/after journey without body-shaming visuals)."
    elif fmt == "TEST":
        style = "TEST (trust-first testimonial/review framing)."
    elif fmt == "FEAT":
        style = "FEAT (features and mechanism clarity)."
    elif fmt == "UGC":
        style = "UGC (creator-style authenticity, premium and clean)."
    else:
        raise RuntimeError(f"Unsupported format: {fmt}")

    if lang == "EN":
        persona_name = require_str(persona, "name", "ads[].persona")
        pain = require_str(persona, "pain_en", "ads[].persona")
        desire = require_str(persona, "desire_en", "ads[].persona")
        friction = require_str(persona, "friction_en", "ads[].persona")
        proof = require_str(persona, "proof_needed_en", "ads[].persona")
        tone = require_str(persona, "tone_cue_en", "ads[].persona")
    else:
        persona_name = require_str(persona, "name", "ads[].persona")
        pain = require_str(persona, "pain_hi", "ads[].persona")
        desire = require_str(persona, "desire_hi", "ads[].persona")
        friction = require_str(persona, "friction_hi", "ads[].persona")
        proof = require_str(persona, "proof_needed_hi", "ads[].persona")
        tone = require_str(persona, "tone_cue_hi", "ads[].persona")

    persona_number = require_int(persona, "number", "ads[].persona")

    layout_lines: list[str]
    if fmt == "HERO":
        layout_lines = [
            "- HERO format: strong headline, one support line, and one CTA.",
            "- Composition: keep the product cluster inside the central safe field, slightly above center, with clean margin protection.",
            "- Focal hierarchy: product dominant, text secondary, background tertiary.",
            "- Product zone: central containment only, with all key pack details away from edge-risk zones.",
            "- Text zones: flat uncluttered areas only; never over busy background detail.",
            "- CTA must be rendered as a filled rounded button chip (high-contrast), never as plain text.",
            "- CTA button sits in lower safe band below support line with clear breathing room.",
            "- Camera framing: eye-level medium shot with natural perspective and stable horizon.",
            "- Lighting: soft, directional, premium, and clean enough to preserve label readability.",
            "- Spacing: strong whitespace between product and copy blocks; clear grid alignment; no floating elements.",
        ]
    elif fmt == "BA":
        layout_lines = [
            "- Format: BA.",
            "- Build a strict split contrast story: left panel = BEFORE struggle, right panel = AFTER first meaningful win.",
            "- Do NOT print literal BEFORE/AFTER words as on-image labels; show contrast through scene, behavior, and styling.",
            "- Keep a visible vertical divider between panels; contrast must be obvious even on quick scroll.",
            "- Left side expression/context should feel frustrated or stuck; right side should feel relieved/confident.",
            "- BEFORE panel must include concrete struggle cues (for example: cluttered routine surface, impulse-snack context, rushed/late-day lighting).",
            "- AFTER panel must include concrete control cues (for example: clean setup, simple fixed-step context, calmer morning-style lighting).",
            "- Do not rely on text-only contrast; make panel contrast visible in scene composition, props, and lighting.",
            "- Keep one unified base palette across both panels; create contrast using light, props, posture, and clarity (not random background color shifts).",
            "- Keep products grouped near lower center bridging both halves (inside safe field).",
            "- Place headline at top across both panels; make pain-to-progress transition unmistakable.",
            "- Place 2 to 3 short bullets favoring right panel outcomes; avoid generic motivational bullets.",
            "- Keep headline and all bullets in upper safe region only (top half); do not place bullets near product strip or lower half.",
            "- CTA must be rendered as a filled rounded button chip centered in lower safe band, never plain text.",
            "- Camera framing: medium lifestyle-product hybrid; premium and realistic.",
            "- Lighting: left side slightly flatter/dimmer, right side cleaner/brighter (subtle, not dramatic).",
        ]
    elif fmt == "TEST":
        layout_lines = [
            "- Format: TEST.",
            "- This must look evidently testimonial-first, not HERO with a person.",
            "- Use a clear quote/review card as primary element with opening quote mark and first-person statement.",
            "- Attribution must sit directly under quote (for example: Verified user / persona-matched user type).",
            "- Trust line sits as a separate proof strip below quote card; keep hierarchy quote -> attribution -> trust proof.",
            "- If no real testimonial text is available, generate one representative positive review line grounded in persona pain/desire (no absurd claims).",
            "- Human subject supports credibility but remains secondary to quote card; do not let product or headline dominate like HERO.",
            "- Product cluster anchored bottom-center with kit box as primary; keep all labels readable.",
            "- CTA must be rendered as a filled rounded button chip in lower safe band, never plain text.",
            "- Text zones must be flat and low-noise; prioritize legibility over decoration.",
            "- Camera framing: editorial testimonial scene with believable home/work context.",
            "- Lighting: clean, warm, premium; no harsh shadows; preserve label sharpness.",
        ]
    elif fmt == "FEAT":
        layout_lines = [
            "- Format: FEAT.",
            "- Build a clean information hierarchy: headline top-left, 3-4 feature bullets mid-left, CTA lower-left.",
            "- Product cluster stays center-right with kit box as anchor; all 5 products visible.",
            "- Keep spacing generous and grid aligned; avoid dense paragraphs.",
            "- Bullets must be functional benefits only; short, concrete, and readable.",
            "- CTA must be rendered as a filled rounded button chip, never plain text.",
            "- Camera framing: medium editorial product shot with crisp detail.",
            "- Lighting: neutral-warm, confidence-led, label-safe highlights.",
            "- Background stays premium and low-noise; never compete with text.",
        ]
    else:  # UGC
        layout_lines = [
            "- Format: UGC.",
            "- Creator-style authenticity with premium cleanliness; avoid stock-template look.",
            "- Subject holds the kit toward camera while remaining natural and unposed; all 5 products still visible.",
            "- Headline top, support line mid, context/proof line below support, CTA bottom; keep text compact but informative.",
            "- UGC copy density: headline should feel complete (about 6-12 words), support line should carry mechanism + outcome (about 8-16 words), and context/proof line should anchor real-life fit (about 6-12 words).",
            "- CTA must be rendered as a filled rounded button chip, never plain text.",
            "- Hands must look anatomically correct; no extra fingers or warped nails.",
            "- Camera framing: handheld close-to-medium, phone-like realism with stable focus on product labels.",
            "- Lighting: soft indoor daylight or warm ambient; avoid ring-light glow.",
            "- Background props minimal and non-competing; keep text zones flat and clean.",
        ]

    # Copy block: render EXACTLY what was provided.
    copy_lines: list[str] = []
    if fmt == "HERO":
        copy_lines = [
            f"- Headline: {copy.headline}",
            f"- Support line: {copy.support_line}",
            f"- CTA: {copy.cta}",
        ]
    elif fmt == "UGC":
        copy_lines = [
            f"- Headline: {copy.headline}",
            f"- Support line: {copy.support_line}",
            f"- Context line: {proof}",
            f"- CTA: {copy.cta}",
        ]
    elif fmt in {"BA", "FEAT"}:
        bullets = copy.bullets or []
        copy_lines = [f"- Headline: {copy.headline}"]
        for i, b in enumerate(bullets, start=1):
            copy_lines.append(f"- Bullet {i}: {b}")
        copy_lines.append(f"- CTA: {copy.cta}")
    else:  # TEST
        copy_lines = [
            f"- Headline: {copy.headline}",
            f"- Attribution: {copy.attribution}",
            f"- Trust line: {copy.trust_line}",
            f"- CTA: {copy.cta}",
        ]

    lock = visual_lock if isinstance(visual_lock, dict) else {}
    subject_line = (lock.get("subject") or "").strip() if isinstance(lock.get("subject"), str) else ""
    if not subject_line:
        if fmt == "UGC":
            subject_line = build_ugc_subject_line(bg_seed)
        elif fmt == "BA":
            subject_line = "Same adult subject identity appears in both panels: left shows routine struggle, right shows practical control; no body-shaming or body-morph visuals."
        else:
            subject_line = "No human subject, products only."
    action_line = (
        "Hold the kit box toward camera with one hand; the other products arranged on a clean surface in-frame."
        if fmt == "UGC"
        else "Arrange all 5 products as a cohesive premium cluster; kit box acts as anchor."
    )
    if fmt == "BA":
        action_line = "Split action: BEFORE panel shows rushed/impulsive routine cue; AFTER panel shows one clear repeatable step with cleaner setup and calmer behavior."
    if isinstance(lock.get("action"), str) and lock.get("action").strip():
        action_line = lock.get("action").strip()
    camera_line = "Handheld close-to-medium framing, phone-like realism, stable focus on labels." if fmt == "UGC" else "Eye-level medium framing with clean edge discipline."
    if isinstance(lock.get("camera"), str) and lock.get("camera").strip():
        camera_line = lock.get("camera").strip()
    realism_line = (
        "True-to-life proportions; no stock-template look; natural skin and correct hand anatomy."
        if fmt == "UGC"
        else "True-to-life proportions; no stock-template look."
    )
    if isinstance(lock.get("realism"), str) and lock.get("realism").strip():
        realism_line = lock.get("realism").strip()

    lines: list[str] = []
    canvas_spec = "1080 x 1920" if aspect_ratio == "9:16" else "1080 x 1350"
    lines.append("PRODUCT LOCK BLOCK")
    lines.extend(
        [
            "- Use the uploaded Obesity Killer product packshot images as absolute visual truth.",
            "- Use provided product references as exact appearance truth for pack shape, label, and color.",
            "- Do not redesign, redraw, relabel, or alter any product or packaging in any way.",
            "- Do not change brand name, label colors, illustrations, proportions, or any text (Hindi or English).",
            "- If any label text is unclear, preserve the original image as-is. Do not reinterpret it.",
            "- Only permitted: placement, scaling, subtle drop shadows, mild warm lighting correction.",
        ]
    )
    lines.append("")
    lines.append("OUTPUT SPEC")
    lines.extend(
        [
            f"- Canvas: {canvas_spec} pixels. Portrait. {aspect_ratio} ratio.",
            f"- Style: {style}",
            "- Full-bleed requirement: scene must reach all canvas edges; no inset poster card, no inner frame, no side matte bands, no faux border margins.",
            "- Text policy: low text by default; all copy minimal and mobile-readable at 375px width.",
            "- Rendering: no compression artifacts; no soft edges on text or product labels.",
            "- All 5 products present, proportionally sized per reference dimensions, unmodified.",
            "- Readability: maintain high-contrast foreground/background treatment for ad-platform legibility.",
        ]
    )
    lines.append("")
    lines.append("FORMAT LAYOUT INSTRUCTIONS")
    lines.extend(layout_lines)
    lines.append("")
    lines.append("PERSONA INPUT BLOCK")
    lines.extend(
        [
            f"- Persona: {persona_name} (Persona {persona_number})",
            f"- Pain: {pain}",
            f"- Desire: {desire}",
            f"- Friction: {friction}",
            f"- Proof needed: {proof}",
            f"- Tone cue: {tone}",
        ]
    )
    lines.append("")
    lines.append("EXACT ON-IMAGE COPY - DO NOT ALTER ANYTHING")
    lines.extend(copy_lines)
    lines.append("Render every character exactly as written. No paraphrasing, no punctuation changes, no autocorrection.")
    lines.append("")
    lines.append("NEGATIVE CONSTRAINTS")
    negative = [
        "- Do not recreate or redraw any product.",
        "- Do not blur, approximate, or rewrite any label text.",
        "- Do not use sale badges, burst graphics, or stickers.",
        "- Do not show body transformations or weight-loss visuals.",
        "- Do not use colors outside the defined palette.",
        "- Do not use more than 2 font weights.",
        "- Do not overcrowd the layout.",
        "- Do not add edge glows, tinted borders, amber/orange side casts, or decorative vignette frames.",
        "- Do not create inset-canvas look: no white frame border, no inner-card composition, no side fade bands, no outer padding effect.",
        "- Do not shrink main scene inside margins; composition must remain full-bleed to all four edges.",
        "- Do not place any translucent white panel behind or below the product cluster.",
        "- Do not make medical cure claims of any kind.",
        "- Do not use ring light, studio flash, or overproduced lighting.",
    ]
    if fmt == "UGC":
        negative.insert(8, "- Do not render unnatural or anatomically incorrect hands.")
    if fmt == "BA":
        negative.append("- Do not render literal BEFORE:/AFTER: words anywhere on-image.")
    lines.extend(negative)
    lines.append("")
    lines.append("QUALITY BAR - verify before accepting output")
    lines.extend(
        [
            "- All 5 products present, correctly proportioned, and completely unmodified.",
            "- All on-image text sharp and readable at 375px mobile size.",
            "- Product labels accurate, unmodified, and fully readable.",
            "- Layout calm, balanced, and premium.",
            "- No clutter, no hype, and no forbidden elements.",
            "- Single clear focal hierarchy with product dominance throughout.",
            "- If any item above fails, regenerate immediately without compromise.",
        ]
    )
    lines.append("")
    lines.append("VISUAL DIRECTION BLOCK")
    lines.extend(
        [
            f"- Background slot: {bg['id']} - {bg.get('title', '').strip() or 'Catalog background'}",
            f"- Background seed: {bg_seed}",
            f"- Seeded background direction (single sentence, exact): {seeded_sentence}",
            f"- Subject: {subject_line}",
            f"- Action: {action_line}",
            f"- Camera: {camera_line}",
            f"- Lighting: {(lock.get('lighting') or 'Warm, soft, directional (top-left) and label-safe.')}",
            f"- Props: {(lock.get('props') or 'Minimal, non-competing; keep edge zones quiet.')}",
            f"- Surfaces: {(lock.get('surfaces') or 'Premium, clean texture; avoid busy patterns under text.')}",
            "- Text panel treatment: if used, keep panel in upper text zone only with vertical fade to transparent before products; never place white panel behind or below product cluster.",
            "- Edge color control: keep border tones neutral and natural; no orange/amber edge tint and no ornamental frame glow.",
            "- Edge structure control: enforce full-bleed composition to edges; reject outputs with visible inset border, side matte strip, or inner-frame card look.",
            f"- Mood: {(lock.get('mood') or 'Calm confidence and practical consistency; no hype.')}",
            f"- Realism: {realism_line}",
        ]
    )
    if fmt == "BA":
        lines.extend(
            [
                "- BEFORE panel visual anchors: include at least 2 struggle cues (messy surface, unplanned snack context, low-clarity routine signals).",
                "- AFTER panel visual anchors: include at least 2 control cues (clean setup, fixed-step context, calmer brighter environment).",
                "- Identity continuity: if a person is shown, keep same person across both panels; change only mood/context, never fake body transformation.",
            ]
        )
    if lock:
        lines.append("- VISUAL MATCH LOCK (from base 4:5): keep same subject identity, camera feel, lighting direction, prop family, and product arrangement; only adjust spacing/scale for aspect-ratio fit.")
        if aspect_ratio == "9:16":
            lines.append("- For 9:16 conversion: preserve the same product left-right order and relative layering as base 4:5; allow only vertical re-spacing and minor scale adaptation.")
    lines.append("")
    lines.append("TYPOGRAPHY SHARPNESS BLOCK")
    lines.extend(
        [
            "- Headline: Poppins Bold with high contrast against clean background area.",
            "- Support and CTA: Poppins Medium/Regular, same family.",
            "- Size: readable on a 375px mobile screen without zooming.",
            "- Placement: flat uncluttered zones only; avoid noisy textures.",
            "- Forbidden: thin fonts, script fonts, decorative typefaces, glow effects, outlined text, drop shadows on copy.",
            "- Mandatory: crisp hard text edges, zero softness, zero anti-alias blur on any character.",
            "- If any text is soft, blurry, or illegible, discard and regenerate immediately.",
        ]
    )
    lines.append("")
    lines.append("Keep on-image text minimal and mobile-readable. Avoid dense copy blocks.")
    lines.append("Render CTA as a real filled button chip with rounded corners and strong contrast; never show CTA as standalone plain text.")
    lines.append("Typography must be pin-sharp. If any text appears soft, blurry, or smeared, regenerate.")
    lines.append("Keep text count minimal and increase font size rather than packing more copy.")
    lines.append("Use clean sans typography with strong stroke clarity; no thin/light weights for body text.")
    lines.append("Use Poppins only for on-image text: Headline in Poppins Bold, support/CTA in Poppins Medium or Regular.")
    lines.append("")
    lines.append(safezone_enforcement_block(aspect_ratio))
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def validate_prompt_text(text: str, out_path: Path) -> None:
    if re.search(r"Background\s*seed\s*:\s*\d+", text, flags=re.IGNORECASE) is None:
        raise RuntimeError(f"Missing 'Background seed' in {out_path}")
    if re.search(r"Seeded\s+background\s+direction\s*\(single sentence, exact\)\s*:", text, flags=re.IGNORECASE) is None:
        raise RuntimeError(f"Missing seeded background label in {out_path}")
    if "SAFE-ZONE ENFORCEMENT" not in text:
        raise RuntimeError(f"Missing SAFE-ZONE ENFORCEMENT block in {out_path}")
    non_empty_lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(non_empty_lines) < 45:
        raise RuntimeError(f"Prompt too short ({len(non_empty_lines)} non-empty lines): {out_path}")


def aspect_ratio_folder(aspect_ratio: str) -> str:
    return "96" if aspect_ratio == "9:16" else "45"


def main() -> int:
    args = parse_args()
    copy_path = Path(args.copy_file)
    payload = load_json(copy_path)

    ads = payload.get("ads")
    if not isinstance(ads, list) or not ads:
        raise RuntimeError("copy file must contain non-empty 'ads' array")

    registry = load_json(REGISTRY_PATH)
    backgrounds = load_json(BACKGROUNDS_PATH)

    seed = args.seed if args.seed is not None else random.SystemRandom().randint(10_000_000, 2_147_483_647)
    used = registry_used_text(registry)
    render_langs = ["EN", "HI"] if args.language_mode == "BOTH" else [args.language_mode]

    # Validate copy payload + uniqueness against registry BEFORE consuming background slots.
    collisions: list[str] = []
    for i, ad in enumerate(ads):
        ctx = f"ads[{i}]"
        if not isinstance(ad, dict):
            raise RuntimeError(f"{ctx} must be an object")

        fmt = require_str(ad, "format", ctx).upper()
        if fmt not in SUPPORTED_FORMATS:
            raise RuntimeError(f"{ctx}.format must be one of {sorted(SUPPORTED_FORMATS)}")

        aspect_ratio = (ad.get("aspect_ratio") or payload.get("default_aspect_ratio") or "4:5").strip()
        if aspect_ratio not in {"4:5", "9:16"}:
            raise RuntimeError(f"{ctx}.aspect_ratio must be '4:5' or '9:16'")

        persona = ad.get("persona")
        if not isinstance(persona, dict):
            raise RuntimeError(f"{ctx}.persona must be an object")
        require_int(persona, "number", f"{ctx}.persona")
        require_str(persona, "name", f"{ctx}.persona")
        for k in ["pain_en", "desire_en", "friction_en", "proof_needed_en", "tone_cue_en", "pain_hi", "desire_hi", "friction_hi", "proof_needed_hi", "tone_cue_hi"]:
            require_str(persona, k, f"{ctx}.persona")

        copy = ad.get("copy")
        if not isinstance(copy, dict):
            raise RuntimeError(f"{ctx}.copy must be an object with EN/HI blocks")
        for lang in render_langs:
            if lang not in copy or not isinstance(copy[lang], dict):
                raise RuntimeError(f"{ctx}.copy must include {lang} object")
            cb = parse_copy_block(fmt, lang, copy[lang])

            # format-specific required fields (do not invent)
            if fmt in {"HERO", "UGC"} and not cb.support_line:
                raise RuntimeError(f"{ctx}.copy.{lang}.support_line required for {fmt}")
            if fmt in {"BA", "FEAT"}:
                if not cb.bullets or len(cb.bullets) < 2:
                    raise RuntimeError(f"{ctx}.copy.{lang}.bullets must have >=2 items for {fmt}")
            if fmt == "TEST":
                if not cb.attribution:
                    raise RuntimeError(f"{ctx}.copy.{lang}.attribution required for TEST")
                if not cb.trust_line:
                    raise RuntimeError(f"{ctx}.copy.{lang}.trust_line required for TEST")

            # Registry uniqueness checks (exact string match).
            uniqueness_check(used, "headline_en" if lang == "EN" else "headline_hi", cb.headline, collisions, f"{ctx}.copy.{lang}.headline")

            if fmt in {"HERO", "UGC"}:
                uniqueness_check(used, "support_line_en" if lang == "EN" else "support_line_hi", cb.support_line, collisions, f"{ctx}.copy.{lang}.support_line")
            if fmt in {"BA", "FEAT"}:
                bucket = "bullets_en" if lang == "EN" else "bullets_hi"
                for b in cb.bullets or []:
                    uniqueness_check(used, bucket, b, collisions, f"{ctx}.copy.{lang}.bullets")
            if fmt == "TEST":
                uniqueness_check(used, "support_line_en" if lang == "EN" else "support_line_hi", cb.trust_line, collisions, f"{ctx}.copy.{lang}.trust_line")

    if collisions and not args.skip_uniqueness_check:
        msg = "Copy batch failed uniqueness checks against registry (regenerate via your LLM step):\n- " + "\n- ".join(collisions[:50])
        if len(collisions) > 50:
            msg += f"\n... and {len(collisions)-50} more collisions"
        raise RuntimeError(msg)

    batch_name = args.batch or next_batch_name(OUTPUT_DIR)
    batch_dir = OUTPUT_DIR / batch_name

    if args.dry_run:
        print(f"OK (dry-run). Would write batch: {batch_name}")
        print(f"Seed: {seed}")
        print(f"Ads: {len(ads)}")
        return 0

    batch_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now_utc_iso()

    for i, ad in enumerate(ads):
        fmt = str(ad["format"]).upper()
        aspect_ratio = (ad.get("aspect_ratio") or payload.get("default_aspect_ratio") or "4:5").strip()
        ratio_dir = batch_dir / aspect_ratio_folder(aspect_ratio)
        ratio_dir.mkdir(parents=True, exist_ok=True)
        persona = ad["persona"]
        angle = (ad.get("headline_angle") or "").strip()

        for stale_lang in ["EN", "HI"]:
            if stale_lang in render_langs:
                continue
            stale_path = ratio_dir / f"OUTPUT_{fmt}_{stale_lang}.txt"
            if stale_path.exists():
                stale_path.unlink()

        forced_bg = ad.get("background_slot") or ad.get("background_slot_id")
        if isinstance(forced_bg, str) and forced_bg.strip():
            bg = get_background_by_id(backgrounds, fmt, forced_bg)
        else:
            bg = pick_background_slot(registry, backgrounds, fmt, seed)

        forced_seed = ad.get("background_seed")
        if isinstance(forced_seed, int) and forced_seed > 0:
            bg_seed = forced_seed
        else:
            bg_seed = random.Random(seed + i * 101).randint(1, 2_147_483_647)
        visual_lock = ad.get("visual_lock") if isinstance(ad.get("visual_lock"), dict) else {}
        seeded_sentence = build_seeded_background_sentence(bg, bg_seed, aspect_ratio)
        if isinstance(visual_lock.get("seeded_background_direction"), str) and visual_lock.get("seeded_background_direction").strip():
            seeded_sentence = visual_lock.get("seeded_background_direction").strip()
            if aspect_ratio == "9:16":
                seeded_sentence += "; maintain base scene identity and arrangement, only adapt spacing for 9:16 safe bands"

        rendered: dict[str, str] = {}
        for lang in render_langs:
            cb = parse_copy_block(fmt, lang, ad["copy"][lang])
            out_text = render_prompt(fmt, lang, aspect_ratio, persona, cb, bg, bg_seed, seeded_sentence, visual_lock=visual_lock)
            out_path = ratio_dir / f"OUTPUT_{fmt}_{lang}.txt"
            validate_prompt_text(out_text, out_path)
            out_path.write_text(out_text, encoding="utf-8")
            rendered[lang] = out_text

        if args.no_registry_write:
            continue

        entry_id = next_entry_id(registry)
        entry = {
            "id": entry_id,
            "timestamp": timestamp,
            "format": fmt,
            "persona_number": persona["number"],
            "persona_name": persona["name"],
            "headline_angle": angle or None,
            "headline_en": ad["copy"]["EN"]["headline"],
            "headline_hi": ad["copy"]["HI"]["headline"],
            "support_line_en": ad["copy"]["EN"].get("support_line") or ad["copy"]["EN"].get("trust_line") or "",
            "support_line_hi": ad["copy"]["HI"].get("support_line") or ad["copy"]["HI"].get("trust_line") or "",
            "cta_en": ad["copy"]["EN"]["cta"],
            "cta_hi": ad["copy"]["HI"]["cta"],
            "disclaimer_en": "",
            "disclaimer_hi": "",
            "caption_en": "",
            "caption_hi": "",
            "bullets_en": ad["copy"]["EN"].get("bullets") or [],
            "bullets_hi": ad["copy"]["HI"].get("bullets") or [],
            "background_slot": bg["id"],
            "background_name": bg.get("title", ""),
            "background_source": "catalog",
            "fresh_background_signature": None,
            "language": "BOTH",
            "output_quality": "pending",
            "notes": f"assembled_from={copy_path.name}; batch={batch_name}; aspect_ratio={aspect_ratio}; seed={seed}",
        }

        registry.setdefault("entries", []).append(entry)
        append_background_index(registry, fmt, entry_id, timestamp, bg["id"])

        # used_text updates
        if "EN" in render_langs:
            add_used_text(registry, "headline_en", [ad["copy"]["EN"]["headline"]])
            add_used_text(registry, "cta_en", [ad["copy"]["EN"]["cta"]])
        if "HI" in render_langs:
            add_used_text(registry, "headline_hi", [ad["copy"]["HI"]["headline"]])
            add_used_text(registry, "cta_hi", [ad["copy"]["HI"]["cta"]])

        if fmt in {"HERO", "UGC"}:
            if "EN" in render_langs:
                add_used_text(registry, "support_line_en", [ad["copy"]["EN"]["support_line"]])
            if "HI" in render_langs:
                add_used_text(registry, "support_line_hi", [ad["copy"]["HI"]["support_line"]])
        elif fmt in {"BA", "FEAT"}:
            if "EN" in render_langs:
                add_used_text(registry, "bullets_en", ad["copy"]["EN"]["bullets"])
            if "HI" in render_langs:
                add_used_text(registry, "bullets_hi", ad["copy"]["HI"]["bullets"])
        else:  # TEST trust_line stored in support_line_* buckets for dedupe parity
            if "EN" in render_langs:
                add_used_text(registry, "support_line_en", [ad["copy"]["EN"]["trust_line"]])
            if "HI" in render_langs:
                add_used_text(registry, "support_line_hi", [ad["copy"]["HI"]["trust_line"]])

        if isinstance(registry.get("mode"), dict):
            registry["mode"]["last_updated"] = timestamp

    if not args.no_registry_write:
        write_json(REGISTRY_PATH, registry)

    print(f"Batch: {batch_name}")
    print(f"Seed: {seed}")
    print(f"Wrote: {batch_dir.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
