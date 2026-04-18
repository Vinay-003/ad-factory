#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "background_variant.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add safe-zone controls to structured backgrounds and generate seeded prompt")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input structured background JSON")
    parser.add_argument("--output", default=str(DEFAULT_INPUT), help="Output JSON path")
    parser.add_argument("--seed", type=int, help="Deterministic seed for prompt generation")
    parser.add_argument("--id", dest="background_id", help="Background id to use for final prompt")
    parser.add_argument("--format", dest="image_format", choices=["9:16", "4:5"], default="4:5", help="Target output format")
    parser.add_argument("--prompt-only", action="store_true", help="Only print final prompt and skip writing JSON")
    return parser.parse_args()


def detect_layout_mode(formats: list[str]) -> str:
    has_vertical = any(fmt in {"HERO", "FEAT"} for fmt in formats)
    has_feed = "BA" in formats
    if has_vertical and has_feed:
        return "hybrid"
    if has_vertical:
        return "9:16"
    if has_feed:
        return "4:5"
    return "hybrid"


def composition_variants(mode: str) -> list[str]:
    if mode == "9:16":
        return [
            "subject anchored slightly above center within the central vertical safe band, with lower-frame detail intentionally minimized for CTA clearance",
            "tight central containment in the middle-safe zone with a subtle upward bias, preserving a clean low-detail bottom region",
            "primary subject held in the upper-middle 14-65% band, avoiding top UI overlap and maintaining quiet visual weight below",
            "balanced vertical composition centered in the safe corridor with controlled bottom whitespace and no edge drift",
            "clean central stack with subject emphasis above midpoint and strong lower-third simplicity for overlays",
            "stable mid-column framing that keeps key elements in the safe middle while preserving unobtrusive bottom space",
        ]
    if mode == "4:5":
        return [
            "subject centered with a slight above-center lift, maintaining equal margin breathing room across all edges",
            "balanced feed composition inside the central safe field, with top and bottom risk bands kept visually quiet",
            "core subject contained within the inner 80% frame area, avoiding side-edge tension and preserving clean perimeter margins",
            "center-weighted layout with soft upward emphasis, ensuring no important detail touches edge risk zones",
            "symmetrical commercial framing with stable side spacing and restrained detail near top and bottom limits",
            "clean middle-focused arrangement with deliberate edge clearance for robust feed placement safety",
        ]
    return [
        "subject contained in the central 50-60% of the frame with slight above-center bias for cross-placement safety",
        "hybrid-safe middle composition with strong vertical containment and balanced side margins for feed and stories",
        "key visual locked to the central safe core, keeping top, bottom, and side edges low priority and uncluttered",
        "cross-format centered arrangement with gentle upward weighting and protected lower-frame emptiness",
        "stable central block composition that survives vertical and feed crops without edge-dependent detail",
        "clean ad layout using central containment and controlled surrounding negative space for multi-placement reliability",
    ]


def layout_intent_variants(mode: str) -> list[str]:
    base = [
        "keep the subject mass fully inside the central safe region with no edge-anchored focal detail",
        "enforce central placement lock so all high-importance detail remains away from frame boundaries",
        "maintain controlled negative space around the subject to prevent drift into crop-risk zones",
        "preserve a stable center-of-interest corridor with consistent margin protection on every side",
        "prioritize central hierarchy and avoid any composition that relies on top, bottom, or side edge information",
    ]
    if mode == "9:16":
        return base + [
            "bias the focal center slightly upward while keeping the lower region open for captions and CTA overlays",
        ]
    if mode == "4:5":
        return base + [
            "keep visual weight centered with mild upward lift and balanced side margins for feed-safe framing",
        ]
    return base + [
        "use hybrid-safe central positioning that remains valid in both vertical-safe and feed-safe crops",
    ]


def cta_safe_space_variants(mode: str) -> list[str]:
    if mode == "9:16":
        return [
            "reserve the lower 35% of the frame as a low-detail quiet zone for CTA and caption overlays",
            "keep bottom-frame textures soft and unobtrusive, with no key content entering the CTA band",
            "maintain strong lower-frame clearance by placing all focal elements above the visual midpoint",
            "ensure the bottom area remains clean and overlay-friendly with minimal contrast concentration",
            "avoid any high-importance object detail in the lower region to protect conversion UI legibility",
        ]
    if mode == "4:5":
        return [
            "keep the bottom 15% visually calm and free of critical detail for CTA flexibility",
            "maintain subtle low-contrast space near the lower edge to protect feed overlay readability",
            "avoid placing focal edges or high-frequency texture near the bottom risk band",
            "preserve a quiet footer zone while keeping the subject comfortably within central margins",
        ]
    return [
        "preserve a quiet lower-frame buffer with no critical details entering likely CTA regions",
        "keep bottom visual activity restrained so overlays remain legible across placements",
        "maintain clear lower-zone breathing room while holding focal detail in the central safe core",
        "avoid bottom-heavy composition to ensure robust story and feed CTA compatibility",
        "protect lower-frame clarity with soft texture and low contrast in overlay-prone space",
    ]


def crop_safety_variants(mode: str) -> list[str]:
    common = [
        "ensure all critical visual information remains within the center so 1:1 center crop retains full message",
        "avoid edge-dependent framing; composition must survive moderate side and vertical trimming",
        "keep focal hierarchy compact and central so multi-placement crops preserve premium readability",
    ]
    if mode == "hybrid":
        return common + [
            "validate composition against vertical, feed, and square center crops with no loss of key subject emphasis",
        ]
    return common + [
        "maintain protected margin buffers so alternate crops do not clip meaningful scene structure",
    ]


def choose_seed(seed: int | None) -> int:
    if seed is not None:
        return seed
    secure = random.SystemRandom().randint(10_000_000, 2_147_483_647)
    return secure ^ (time.time_ns() & 0x7FFFFFFF)


def upgraded_variant(variant: dict) -> dict:
    out = dict(variant)
    mode = detect_layout_mode(variant.get("formats", []))
    out["composition"] = composition_variants(mode)
    out["layout_intent"] = layout_intent_variants(mode)
    out["cta_safe_space"] = cta_safe_space_variants(mode)
    out["crop_safety"] = crop_safety_variants(mode)
    return out


def pick_background(variants: list[dict], seed: int, background_id: str | None) -> dict:
    if background_id:
        for item in variants:
            if item.get("id") == background_id:
                return item
        raise RuntimeError(f"Background id not found: {background_id}")
    return variants[seed % len(variants)]


def build_final_prompt(bg: dict, seed: int, image_format: str) -> str:
    rng = random.Random(seed)
    base = bg["base"]
    lighting = rng.choice(bg["lighting"])
    surface = rng.choice(bg["surface"])
    environment = rng.choice(bg["environment"])
    mood = rng.choice(bg["mood"])
    camera = rng.choice(bg["camera"])
    color_tone = rng.choice(bg["color_tone"])
    if image_format == "9:16":
        runtime_mode = "9:16"
    elif image_format == "4:5":
        runtime_mode = "4:5"
    else:
        runtime_mode = "4:5"

    composition = rng.choice(composition_variants(runtime_mode))
    layout_intent = rng.choice(layout_intent_variants(runtime_mode))
    cta_safe_space = rng.choice(cta_safe_space_variants(runtime_mode))
    crop_safety = rng.choice(crop_safety_variants(runtime_mode))

    if image_format == "9:16":
        format_clause = (
            "designed for 9:16 vertical placement with key subject content constrained to the 14-65 percent safe band, positioned slightly above center, and with the lower 35 percent kept visually quiet for overlays"
        )
    elif image_format == "4:5":
        format_clause = (
            "designed for 4:5 feed framing with key content held inside the central safe field, centered to slightly above center, while top 10 percent, bottom 15 percent, and side edge zones remain low-priority"
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


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    variants = data.get("variants", [])
    upgraded = [upgraded_variant(v) for v in variants]

    if not args.prompt_only:
        out = dict(data)
        out["version"] = "3.2-safezone"
        out["variants"] = upgraded
        output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    seed = choose_seed(args.seed)
    selected = pick_background(upgraded, seed, args.background_id)
    final_prompt = build_final_prompt(selected, seed, args.image_format)
    print(final_prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
