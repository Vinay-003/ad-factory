#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _append_unique(target: list[str], seen: set[str], item: str) -> None:
    value = item.strip()
    if not value or value in seen:
        return
    target.append(value)
    seen.add(value)


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


def extract_product_sections(lines: list[str]) -> list[str]:
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

    preferred = [
        "1. What is Obesity Killer Kit",
        "2. What problem does it solve",
        "3. What is the customer really hiring",
        "4. Who is it for",
        "5. Who is it not for",
        "6. What comes in the kit",
        "7. What is in the formulation",
        "8. How does it work",
        "9. What benefits do users see",
        "10. What makes it different",
        "11. What proof supports belief",
        "12. What exactly is the money-back guarantee",
        "13. What is the safety position",
        "14. What is the continuation and repeat logic",
        "15. What is the maintenance story",
        "16. Who created the product",
        "19. What should the brand not say",
    ]

    out: list[str] = []
    for wanted in preferred:
        match = next((section for title, section in sections if title.lower().startswith(wanted.lower())), None)
        if not match:
            continue
        out.extend(match[:10])
    return out


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
        out.extend(match[:8])
    return out


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
        out.extend(match[:16])
    return out


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract compact product context for generation")
    parser.add_argument("--product", default="productinfomain.txt")
    parser.add_argument("--mechanism", default="PRODUCT_MECHANISM_V1.txt")
    parser.add_argument("--faq", default="faq.txt")
    parser.add_argument("--max-lines", type=int, default=0, help="Optional global cap for all sources")
    parser.add_argument("--max-lines-product", type=int, default=70)
    parser.add_argument("--max-lines-mechanism", type=int, default=45)
    parser.add_argument("--max-lines-faq", type=int, default=55)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    product_limit = args.max_lines if args.max_lines > 0 else args.max_lines_product
    mechanism_limit = args.max_lines if args.max_lines > 0 else args.max_lines_mechanism
    faq_limit = args.max_lines if args.max_lines > 0 else args.max_lines_faq

    product_text = Path(args.product).read_text(encoding="utf-8")
    mechanism_text = Path(args.mechanism).read_text(encoding="utf-8")
    faq_text = Path(args.faq).read_text(encoding="utf-8")

    product_lines = _clean_lines(product_text)
    mechanism_lines = _clean_lines(mechanism_text)
    faq_lines = _clean_lines(faq_text)

    product_keywords = [
        "core promise",
        "3 to 5 kg",
        "who it is for",
        "not for",
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
