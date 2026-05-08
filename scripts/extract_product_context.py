#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def default_product_path() -> str:
    master = ROOT / "product master doc.txt"
    if master.exists():
        return str(master)
    # fallback for older repo states; kept to avoid hard crashes
    legacy_master = ROOT / "productmaster.txt"
    if legacy_master.exists():
        return str(legacy_master)
    return "productinfomain.txt"


def merge_product_directives(product_path: Path, product_text: str) -> str:
    """
    Single source of truth mode:
    - Do NOT merge from legacy productinfomain/productmaster files.
    - If callers pass a legacy product file, we keep that behavior minimal.
    """
    return product_text


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _append_unique(target: list[str], seen: set[str], item: str) -> None:
    value = item.strip()
    if not value or value in seen:
        return
    target.append(value)
    seen.add(value)


def _unique_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        _append_unique(out, seen, line)
    return out


def extract_snapshot_block(lines: list[str]) -> list[str]:
    out: list[str] = []
    start = -1
    for i, line in enumerate(lines):
        if "SNAPSHOT (FOR EXTRACTION)" in line.upper():
            start = i
            break
    if start < 0:
        return out

    out.append(lines[start])
    keep_pattern = re.compile(r"^(-|Q:|A:|\d+\)|RAPID FIRE|ADDITIONAL INTERVIEW)", re.IGNORECASE)
    for line in lines[start + 1 :]:
        if keep_pattern.match(line):
            out.append(line)
            continue
        break
    return out


def extract_keyword_lines(lines: list[str], keywords: list[str]) -> list[str]:
    if not keywords:
        return []
    pattern = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    return [line for line in lines if pattern.search(line)]


def extract_section_by_title(lines: list[str], title_prefixes: list[str], max_lines: int | None = None) -> list[str]:
    heading_re = re.compile(r"^(\d+)\.\s+(.+)$")
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in lines:
        if heading_re.match(line):
            if current_title:
                sections.append((current_title, current_lines))
            current_title = line
            current_lines = [line]
            continue
        if current_title:
            current_lines.append(line)
    if current_title:
        sections.append((current_title, current_lines))

    out: list[str] = []
    for prefix in title_prefixes:
        match = next((section for title, section in sections if title.lower().startswith(prefix.lower())), None)
        if not match:
            continue
        if max_lines is None:
            out.extend(match)
        else:
            out.extend(match[:max_lines])
    return out


def extract_priority_block(lines: list[str]) -> list[str]:
    """
    New doc format: synthesize priority block from explicit phrases in the master doc.
    """
    out: list[str] = []
    seen: set[str] = set()

    if any("Single Source of Truth" in l for l in lines):
        _append_unique(out, seen, "Single Source of Truth: Product Foundation Document")

    reqs = [
        "lose 3 to 5 kg in 15 days",
        "no side effects",
        "no synthetic ingredients",
        "no chemical preservatives",
        "structured guided system",
        "daily tracker",
        "trained coaches",
        "7-day money-back guarantee",
        "share the daily tracker",
        "works with regular homemade food",
    ]

    text_lower = "\n".join(lines).lower()
    for r in reqs:
        if r in text_lower:
            _append_unique(out, seen, r)

    if not out:
        out = ["Single Source of Truth: Product Foundation Document"]
    return out


def extract_headline_strategy(lines: list[str]) -> list[str]:
    """
    Infer headline strategy from:
    - Interpretation Rules for AI / Team Use (BEN-1..BEN-7 guidance)
    - “What should the brand not say?” exclusions
    """
    out: list[str] = []
    seen: set[str] = set()

    text_lower = "\n".join(lines).lower()

    candidates: list[str] = []
    if "lead with ben-1" in text_lower:
        candidates.append("Lead with BEN-1: fast visible weight loss (3 to 5 kg in 15 days)")
    if "use ben-3" in text_lower:
        candidates.append("Use BEN-3 when addressing safety or side-effect worries (no side effects trust language)")
    if "use ben-4" in text_lower:
        candidates.append("Use BEN-4 when addressing meal prep / family food / time burden (use with regular homemade food)")
    if "use ben-5" in text_lower:
        candidates.append("Use BEN-5 when addressing confusion or decision fatigue (reduced guesswork / structured routine)")
    if "use ben-6" in text_lower:
        candidates.append("Use BEN-6 when reassuring support exists (daily tracker + trained coaches)")
    if "use ben-8 and ben-9" in text_lower:
        candidates.append("Use BEN-8/BEN-9 as supporting benefits, not the main promise")

    # Brand exclusions (keep high-level)
    if "do not ever demean" in text_lower:
        candidates.append("Do not demean competitors / do not body-shame")
    if "do not say that the product will cure" in text_lower or "do not ever say that the product will cure" in text_lower:
        candidates.append("Do not claim cure-all; position as weight-loss system (not a cure-all)")

    # If we couldn’t infer, fall back to a minimal non-empty set
    if not candidates:
        candidates = [
            "Lead with fast visible weight loss (3 to 5 kg in 15 days).",
            "Pair with support from system safety, no side effects trust language, and guided adherence.",
        ]

    for c in candidates:
        _append_unique(out, seen, c)
    return out


def extract_theme_lines(lines: list[str]) -> list[str]:
    """
    Protected themes: choose the most explicit “core truths” from the master doc.
    """
    out: list[str] = []
    seen: set[str] = set()
    text_lower = "\n".join(lines).lower()

    def has(needle: str) -> bool:
        return needle.lower() in text_lower

    themes: list[str] = []
    if has("fast visible weight loss") or has("3 to 5 kg in 15 days"):
        themes.append("BEN-1: fast visible weight loss (3 to 5 kg in 15 days)")
    if has("no side effects"):
        themes.append("BEN-3: no side effects (public trust language; first-3-days adjustment note internally)")
    if has("regular homemade food") or has("no separate meal prep"):
        themes.append("BEN-4: works with regular homemade food (reduce meal-prep friction)")
    if has("reduced guesswork") or has("structured routine") or has("decision fatigue"):
        themes.append("BEN-5: reduced guesswork + structured daily routine (low decision fatigue)")
    if has("daily tracker") or has("whatsapp") or has("trained coaches") or has("coach"):
        themes.append("BEN-6: daily tracker + trained coaches guidance")
    if has("all-natural") or has("ayurvedic") or has("ayurveda"):
        themes.append("DIFF: all-natural Ayurvedic formulation (system, not one-claim supplement)")
    if has("7-day money-back guarantee"):
        themes.append("PRF: 7-day money-back guarantee (risk reversal; follow course + share tracker)")
    if has("no synthetic ingredients") or has("no chemical preservatives"):
        themes.append("Core truth: no synthetic ingredients + no chemical preservatives")
    if has("maintenance") or has("break after every 30 days") or has("bmi of 25"):
        themes.append("Continuation/maintenance: sustainable (not dehydration-driven); repeat/cycle logic after main course")

    if not themes:
        themes = ["Single source of truth themes inferred from master doc."]
    for t in themes:
        _append_unique(out, seen, t)
    return out


def extract_trigger_rules(lines: list[str]) -> list[str]:
    keywords = [
        "lead with",
        "do not transform",
        "do not replace",
        "feature-based",
        "weight loss",
        "obesity reduction",
        "subheadlines",
        "headline",
        "priority order",
        "protected order",
        "AM/PM routine",
        "cravings down",
        "support",
        "morning",
        "night",
    ]
    return extract_keyword_lines(lines, keywords)


def extract_product_sections(lines: list[str]) -> list[str]:
    """
    New doc format: extract numbered sections + key labeled blocks (Section ID: ... / Interpretation Rules / exclusions).
    This is the main source that should populate product_info.
    """
    sections = split_numbered_sections(lines)

    out: list[str] = []
    seen: set[str] = set()

    # Add top header-ish content (first ~20 non-empty lines)
    for l in lines[:20]:
        _append_unique(out, seen, l)

    # Add numbered sections 1..19 (your current master doc ends at 19)
    for title, sec_lines in sections:
        m = re.match(r"^(\d+)\.\s+", title)
        if not m:
            continue
        idx = int(m.group(1))
        if 1 <= idx <= 19:
            # keep the whole section but avoid excessive duplication
            for l in sec_lines:
                _append_unique(out, seen, l)

    # Add the explicit “Interpretation Rules for AI / Team Use” and “What should the brand not say?”
    # by scanning for their exact headings.
    markers = [
        "Interpretation Rules for AI / Team Use",
        "What should the brand not say?",
    ]
    text = "\n".join(lines)
    # If markers exist, append around them by simple line scanning
    for marker in markers:
        marker_lower = marker.lower()
        for i, l in enumerate(lines):
            if marker_lower in l.lower():
                for l2 in lines[i : i + 120]:
                    _append_unique(out, seen, l2)
                break

    return out


def split_numbered_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    heading_re = re.compile(r"^(\d+)\.\s+(.+)$")
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in lines:
        if heading_re.match(line):
            if current_title:
                sections.append((current_title, current_lines))
            current_title = line
            current_lines = [line]
            continue
        if current_title:
            current_lines.append(line)
    if current_title:
        sections.append((current_title, current_lines))
    return sections


def extract_mechanism_sections(lines: list[str]) -> list[str]:
    heading_re = re.compile(r"^SECTION\s+(\d+)\s*:\s*(.+)$", re.IGNORECASE)
    sections: list[tuple[int, list[str]]] = []
    current_id = -1
    current_lines: list[str] = []

    title = lines[0] if lines else ""
    for line in lines:
        m = heading_re.match(line)
        if m:
            if current_id >= 0:
                sections.append((current_id, current_lines))
            current_id = int(m.group(1))
            current_lines = [line]
            continue
        if current_id >= 0:
            current_lines.append(line)
    if current_id >= 0:
        sections.append((current_id, current_lines))

    preferred_ids = [0, 1, 2, 3, 4, 6, 7, 8, 10, 11, 12]
    out: list[str] = [title] if title else []
    for wanted_id in preferred_ids:
        match = next((section for section_id, section in sections if section_id == wanted_id), None)
        if not match:
            continue
        out.extend(match[:30])
    return _unique_lines(out)


def extract_faq_sections(lines: list[str]) -> list[str]:
    start = 0
    marker = "### Frequently Asked Questions (FAQs)"
    for i, line in enumerate(lines):
        if line == marker:
            start = i
            break
    body = lines[start:]

    category_re = re.compile(r"^\*\*.+\*\*$")
    categories: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in body:
        if category_re.match(line):
            if current_title:
                categories.append((current_title, current_lines))
            current_title = line
            current_lines = [line]
            continue
        if current_title:
            current_lines.append(line)
    if current_title:
        categories.append((current_title, current_lines))

    preferred = [
        "**Product Details**",
        "**Usage Instructions**",
        "**Results & Guarantees**",
        "**Side Effects & Safety**",
        "**Presenting Problem / Issues**",
        "**Support & Follow-up**",
    ]

    out: list[str] = []
    for wanted in preferred:
        match = next((section for title, section in categories if title.lower() == wanted.lower()), None)
        if not match:
            continue
        out.extend(match[:40])
    return _unique_lines(out)


def compact_lines(text: str, max_lines: int, keywords: list[str], section_lines: list[str]) -> list[str]:
    lines = _clean_lines(text)
    out: list[str] = []
    seen: set[str] = set()

    for line in extract_snapshot_block(lines):
        _append_unique(out, seen, line)
        if len(out) >= max_lines:
            return out[:max_lines]

    for line in section_lines:
        _append_unique(out, seen, line)
        if len(out) >= max_lines:
            return out[:max_lines]

    for line in extract_keyword_lines(lines, keywords):
        _append_unique(out, seen, line)
        if len(out) >= max_lines:
            return out[:max_lines]

    for line in lines:
        _append_unique(out, seen, line)
        if len(out) >= max_lines:
            break
    return out[:max_lines]


def extract_line_groups(lines: list[str]) -> dict[str, list[str]]:
    return {
        "headline_strategy": extract_headline_strategy(lines),
        "protected_themes": extract_theme_lines(lines),
        "trigger_rules": extract_trigger_rules(lines),
        "priority_block": extract_priority_block(lines),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract compact product context (single source of truth)")
    parser.add_argument("--product", default=default_product_path())
    parser.add_argument("--max-lines", type=int, default=0, help="Optional global cap for all sources")
    parser.add_argument("--max-lines-product", type=int, default=1400)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    product_limit = args.max_lines if args.max_lines > 0 else args.max_lines_product

    product_path = Path(args.product)
    product_text = merge_product_directives(product_path, product_path.read_text(encoding="utf-8"))

    product_lines = _clean_lines(product_text)

    # For compatibility with downstream schemas, keep mechanism/faq fields but derive them from the product master doc only.
    # (We intentionally do not load PRODUCT_MECHANISM_V1.txt or faq.txt.)
    payload = {
        "product_info": compact_lines(
            product_text,
            product_limit,
            keywords=[],  # rely on extract_product_sections + keyword-specific groups
            section_lines=extract_product_sections(product_lines),
        ),
        "mechanism": [],  # derived elsewhere from product_info if needed
        "faq": [],  # derived elsewhere from product_info if needed
    }
    payload.update(extract_line_groups(product_lines))
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key, values in payload.items():
            print(f"[{key}]")
            for item in values:
                print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
