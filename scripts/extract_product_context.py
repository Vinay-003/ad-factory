#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def default_product_path() -> str:
    master = ROOT / "productmaster.txt"
    if master.exists():
        return str(master)
    return "productinfomain.txt"


def merge_product_directives(product_path: Path, product_text: str) -> str:
    legacy = ROOT / "productinfomain.txt"
    if not legacy.exists():
        return product_text
    if product_path.resolve() == legacy.resolve():
        return product_text

    legacy_text = legacy.read_text(encoding="utf-8")

    def extract_block(start_marker: str) -> str:
        pattern = re.compile(rf"(^|\n)({re.escape(start_marker)}.*?)(?=\n\d+\.\s+|\Z)", re.DOTALL)
        match = pattern.search(legacy_text)
        if not match:
            return ""
        return match.group(2).strip()

    snapshot_match = re.search(r"^CONTEXT SNAPSHOT \(FOR EXTRACTION\).*?(?=\nSingle Source of Truth: Product Foundation Document|\Z)", legacy_text, re.DOTALL | re.MULTILINE)
    supplements = []
    if snapshot_match and "CONTEXT SNAPSHOT (FOR EXTRACTION)" not in product_text:
        supplements.append(snapshot_match.group(0).strip())
    for marker in ["0. EXTRACTOR PRIORITY BLOCK", "24. HEADLINE STRATEGY AND PROTECTED THEMES"]:
        if marker not in product_text:
            block = extract_block(marker)
            if block:
                supplements.append(block)
    if not supplements:
        return product_text
    return "\n\n".join(supplements + [product_text])


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
    out: list[str] = []
    start = -1
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("0. EXTRACTOR PRIORITY BLOCK"):
            start = i
            break
    if start < 0:
        return out

    out.append(lines[start])
    for line in lines[start + 1 :]:
        if re.match(r"^\d+\.\s+", line):
            break
        out.append(line)
    return out


def extract_headline_strategy(lines: list[str]) -> list[str]:
    out: list[str] = []
    start = -1
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("24. HEADLINE STRATEGY AND PROTECTED THEMES"):
            start = i
            break
    if start < 0:
        return out

    out.append(lines[start])
    for line in lines[start + 1 :]:
        if re.match(r"^\d+\.\s+", line):
            break
        out.append(line)
    return out


def extract_theme_lines(lines: list[str]) -> list[str]:
    keywords = [
        "AM/PM routine",
        "cravings down",
        "support",
        "weight loss support",
        "obesity management support",
        "lose weight",
        "reduce excess weight",
        "3 to 5 kg in 15 days",
        "appetite control for weight loss",
        "morning OK Liquid",
        "night OK Tablet",
        "night OK Powder",
        "tracker",
        "WhatsApp",
        "4-hour fasting window",
        "empty stomach",
        "bedtime routine",
    ]
    return extract_keyword_lines(lines, keywords)


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
    preferred = [
        "0. EXTRACTOR PRIORITY BLOCK",
        "1. WHAT IS OBESITY KILLER KIT?",
        "2. WHAT PROBLEM DOES IT SOLVE?",
        "3. WHAT IS THE CUSTOMER HIRING THE PRODUCT TO DO?",
        "4. WHO IS IT FOR?",
        "5. WHO IS IT NOT FOR?",
        "6. WHAT COMES IN THE KIT?",
        "7. WHAT IS IN THE FORMULATION?",
        "8. HOW DOES IT WORK?",
        "9. WHAT BENEFITS DO USERS SEE?",
        "10. WHAT MAKES IT DIFFERENT?",
        "11. WHAT PROOF SUPPORTS BELIEF?",
        "12. MONEY-BACK GUARANTEE DETAILS",
        "13. SAFETY POSITION",
        "14. CONTINUATION AND REPEAT LOGIC",
        "15. MAINTENANCE AFTER MAIN COURSE",
        "16. WHO CREATED THE PRODUCT?",
        "17. PARENT BRAND CONTEXT",
        "18. DETAILED EXECUTION PROTOCOL",
        "19. DIET SYSTEM AND LIFESTYLE REQUIREMENTS",
        "20. SUPPORT, PSYCHOLOGY, AND COMMUNICATION",
        "21. MESSAGING STRATEGY AND MARKET CONTEXT",
        "22. BRAND DESIGN SYSTEM",
        "23. FINAL EXCLUSIONS AND GUARDRAILS",
        "24. HEADLINE STRATEGY AND PROTECTED THEMES",
    ]
    out: list[str] = []
    for wanted in preferred:
        if wanted.startswith("0."):
            out.extend(extract_priority_block(lines))
            continue
        if wanted.startswith("24."):
            out.extend(extract_headline_strategy(lines))
            continue
        match = next((section for section in split_numbered_sections(lines) if section[0].lower().startswith(wanted.lower())), None)
        if not match:
            continue
        out.extend(match[1])
    return _unique_lines(out)


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
    parser = argparse.ArgumentParser(description="Extract compact product context for generation")
    parser.add_argument("--product", default=default_product_path())
    parser.add_argument("--mechanism", default="PRODUCT_MECHANISM_V1.txt")
    parser.add_argument("--faq", default="faq.txt")
    parser.add_argument("--max-lines", type=int, default=0, help="Optional global cap for all sources")
    parser.add_argument("--max-lines-product", type=int, default=1200)
    parser.add_argument("--max-lines-mechanism", type=int, default=320)
    parser.add_argument("--max-lines-faq", type=int, default=420)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    product_limit = args.max_lines if args.max_lines > 0 else args.max_lines_product
    mechanism_limit = args.max_lines if args.max_lines > 0 else args.max_lines_mechanism
    faq_limit = args.max_lines if args.max_lines > 0 else args.max_lines_faq

    product_path = Path(args.product)
    product_text = merge_product_directives(product_path, product_path.read_text(encoding="utf-8"))
    mechanism_text = Path(args.mechanism).read_text(encoding="utf-8")
    faq_text = Path(args.faq).read_text(encoding="utf-8")

    product_lines = _clean_lines(product_text)
    mechanism_lines = _clean_lines(mechanism_text)
    faq_lines = _clean_lines(faq_text)

    product_keywords = [
        "core promise",
        "3 to 5 kg",
        "who is it for",
        "who is it not for",
        "insulin",
        "pregnan",
        "postpartum",
        "31 unique",
        "44 total",
        "no synthetic",
        "no chemical preservatives",
        "guarantee",
        "refund",
        "continuation",
        "maintenance",
        "dr. arun",
        "arogyam",
        "on-image copy",
        "weight loss support",
        "obesity management support",
        "appetite control for weight loss",
        "AM/PM routine",
        "cravings down",
        "support",
        "tracker",
        "WhatsApp",
        "morning OK Liquid",
        "night OK Tablet",
        "night OK Powder",
        "4-hour fasting window",
        "empty stomach",
        "bedtime routine",
        "feature-based",
        "headline",
    ]
    mechanism_keywords = [
        "mechanism",
        "appetite",
        "craving",
        "digestion",
        "core flow",
        "claim boundaries",
        "not allowed",
        "positioning",
        "not a",
    ]
    faq_keywords = [
        "refund",
        "guarantee",
        "who can",
        "who should avoid",
        "insulin",
        "price",
        "side effect",
        "protocol",
        "3 to 5 kg",
        "31 unique",
        "no synthetic",
        "no chemical preservatives",
        "adults (18+)",
    ]

    payload = {
        "product_info": compact_lines(
            product_text,
            product_limit,
            product_keywords,
            extract_product_sections(product_lines),
        ),
        "mechanism": compact_lines(
            mechanism_text,
            mechanism_limit,
            mechanism_keywords,
            extract_mechanism_sections(mechanism_lines),
        ),
        "faq": compact_lines(
            faq_text,
            faq_limit,
            faq_keywords,
            extract_faq_sections(faq_lines),
        ),
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
