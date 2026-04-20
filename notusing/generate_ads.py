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
    parser.add_argument("--no-registry-write", action="store_true", help="Skip writing AD_GENERATION_REGISTRY.JSON updates")
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
    return chosen


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

    if aspect_ratio == "9:16":
        format_clause = (
            "designed for 9:16 vertical placement with key subject content constrained to the 14-65 percent safe band, positioned slightly above center, and with the lower 35 percent kept visually quiet for overlays"
        )
    else:
        format_clause = (
            "designed for 4:5 feed framing with key content held inside the central safe field, centered to slightly above center, while top 10 percent, bottom 15 percent, and side edge zones remain low-priority"
        )

    return (
        f"{base} on a {surface}, with {environment}, lit by {lighting}, conveying {mood}; "
        f"{camera}, {composition}, {layout_intent}, {cta_safe_space}, {crop_safety}, {color_tone}, "
        f"{format_clause}, clean premium studio ad photography, ultra-detailed, flawless commercial finish."
    )


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
    return CopyBlock(
        headline=headline,
        cta=cta,
        support_line=support_line,
        trust_line=trust_line,
        attribution=attribution,
        bullets=bullets,
    )


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
) -> str:
    if fmt == "HERO":
        style = "HERO, polished enough for paid ad deployment."
    elif fmt == "BA":
        style = "BA (before/after journey without body-shaming visuals)."
    elif fmt == "TEST":
        style = "TEST (trust-first proof framing, no fabricated quotes)."
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
            "- Camera framing: eye-level medium shot with natural perspective and stable horizon.",
            "- Lighting: soft, directional, premium, and clean enough to preserve label readability.",
            "- Spacing: strong whitespace between product and copy blocks; clear grid alignment; no floating elements.",
        ]
    elif fmt == "BA":
        layout_lines = [
            "- Format: BA.",
            "- Build a split behavior story: left side = struggle context, right side = control/routine clarity.",
            "- Keep products grouped near lower center bridging both halves (inside safe field).",
            "- Place headline at top center; keep it large and simple.",
            "- Place 2 to 3 short bullets on the right panel only; keep left panel mostly visual.",
            "- Put CTA under bullets; keep footer area clean for platform overlays.",
            "- Camera framing: medium lifestyle-product hybrid; premium and realistic.",
            "- Lighting: left side slightly messier/dimmer, right side cleaner/brighter (subtle, not dramatic).",
        ]
    elif fmt == "TEST":
        layout_lines = [
            "- Format: TEST.",
            "- Do not fabricate customer quotes. Use proof framing (user volume, protocol clarity, support structure).",
            "- Layout: headline at top, trust line mid, CTA at bottom.",
            "- Attribution line under headline to ground credibility.",
            "- Product cluster anchored bottom-center with kit box as primary; keep all labels readable.",
            "- Text zones must be flat and low-noise; prioritize legibility over decoration.",
            "- Camera framing: editorial product clarity shot with gentle lifestyle context.",
            "- Lighting: clean, warm, premium; no harsh shadows; preserve label sharpness.",
        ]
    elif fmt == "FEAT":
        layout_lines = [
            "- Format: FEAT.",
            "- Build a clean information hierarchy: headline top-left, 3-4 feature bullets mid-left, CTA lower-left.",
            "- Product cluster stays center-right with kit box as anchor; all 5 products visible.",
            "- Keep spacing generous and grid aligned; avoid dense paragraphs.",
            "- Bullets must be functional benefits only; short, concrete, and readable.",
            "- Camera framing: medium editorial product shot with crisp detail.",
            "- Lighting: neutral-warm, confidence-led, label-safe highlights.",
            "- Background stays premium and low-noise; never compete with text.",
        ]
    else:  # UGC
        layout_lines = [
            "- Format: UGC.",
            "- Creator-style authenticity with premium cleanliness; avoid stock-template look.",
            "- Subject holds the kit toward camera while remaining natural and unposed; all 5 products still visible.",
            "- Headline top, support line mid, CTA bottom; keep on-image text minimal.",
            "- Hands must look anatomically correct; no extra fingers or warped nails.",
            "- Camera framing: handheld close-to-medium, phone-like realism with stable focus on product labels.",
            "- Lighting: soft indoor daylight or warm ambient; avoid ring-light glow.",
            "- Background props minimal and non-competing; keep text zones flat and clean.",
        ]

    # Copy block: render EXACTLY what was provided.
    copy_lines: list[str] = []
    if fmt in {"HERO", "UGC"}:
        copy_lines = [
            f"- Headline: {copy.headline}",
            f"- Support line: {copy.support_line}",
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

    subject_line = "Indian woman 27-35, natural unposed expression." if fmt == "UGC" else "No human subject, products only."
    action_line = (
        "Hold the kit box toward camera with one hand; the other products arranged on a clean surface in-frame."
        if fmt == "UGC"
        else "Arrange all 5 products as a cohesive premium cluster; kit box acts as anchor."
    )
    camera_line = "Handheld close-to-medium framing, phone-like realism, stable focus on labels." if fmt == "UGC" else "Eye-level medium framing with clean edge discipline."
    realism_line = (
        "True-to-life proportions; no stock-template look; natural skin and correct hand anatomy."
        if fmt == "UGC"
        else "True-to-life proportions; no stock-template look."
    )

    lines: list[str] = []
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
            f"- Canvas: 1080 x 1350 pixels. Portrait. {aspect_ratio} ratio.",
            f"- Style: {style}",
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
        "- Do not make medical cure claims of any kind.",
        "- Do not use ring light, studio flash, or overproduced lighting.",
    ]
    if fmt == "UGC":
        negative.insert(8, "- Do not render unnatural or anatomically incorrect hands.")
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
            "- Lighting: Warm, soft, directional (top-left) and label-safe.",
            "- Props: Minimal, non-competing; keep edge zones quiet.",
            "- Surfaces: Premium, clean texture; avoid busy patterns under text.",
            "- Mood: Calm confidence and practical consistency; no hype.",
            f"- Realism: {realism_line}",
        ]
    )
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
        for lang in ["EN", "HI"]:
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

    if collisions:
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
        persona = ad["persona"]
        angle = (ad.get("headline_angle") or "").strip()

        bg = pick_background_slot(registry, backgrounds, fmt, seed)
        bg_seed = random.Random(seed + i * 101).randint(1, 2_147_483_647)
        seeded_sentence = build_seeded_background_sentence(bg, bg_seed, aspect_ratio)

        rendered: dict[str, str] = {}
        for lang in ["EN", "HI"]:
            cb = parse_copy_block(fmt, lang, ad["copy"][lang])
            out_text = render_prompt(fmt, lang, aspect_ratio, persona, cb, bg, bg_seed, seeded_sentence)
            out_path = batch_dir / f"OUTPUT_{fmt}_{lang}.txt"
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
        add_used_text(registry, "headline_en", [ad["copy"]["EN"]["headline"]])
        add_used_text(registry, "headline_hi", [ad["copy"]["HI"]["headline"]])
        add_used_text(registry, "cta_en", [ad["copy"]["EN"]["cta"]])
        add_used_text(registry, "cta_hi", [ad["copy"]["HI"]["cta"]])

        if fmt in {"HERO", "UGC"}:
            add_used_text(registry, "support_line_en", [ad["copy"]["EN"]["support_line"]])
            add_used_text(registry, "support_line_hi", [ad["copy"]["HI"]["support_line"]])
        elif fmt in {"BA", "FEAT"}:
            add_used_text(registry, "bullets_en", ad["copy"]["EN"]["bullets"])
            add_used_text(registry, "bullets_hi", ad["copy"]["HI"]["bullets"])
        else:  # TEST trust_line stored in support_line_* buckets for dedupe parity
            add_used_text(registry, "support_line_en", [ad["copy"]["EN"]["trust_line"]])
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
