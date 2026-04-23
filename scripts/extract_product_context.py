#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def slice_blocks(text: str, heading_re: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(heading_re, text, flags=re.MULTILINE))
    if not matches:
        return []

    blocks: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = match.group(0).strip()
        block = text[start:end].strip()
        if block:
            blocks.append((title, block))
    return blocks


def product_sections(text: str) -> dict[int, str]:
    heading_prefixes = [
        "1. What is Obesity Killer Kit?",
        "2. What problem does it solve?",
        "3. What is the customer really hiring this product to",
        "4. Who is it for?",
        "5. Who is it not for?",
        "6. What comes in the kit?",
        "7. What is in the formulation?",
        "8. How does it work?",
        "9. What benefits do users see?",
        "10. What makes it different?",
        "11. What proof supports belief in the product?",
        "12. What exactly is the money-back guarantee?",
        "13. What is the safety position?",
        "14. What is the continuation and repeat logic?",
        "15. What is the maintenance story after the main",
        "16. Who created the product?",
        "17. What is Arogyam’s role in the trust story?",
        "18. What mission sits behind the product?",
        "19. What should the brand not say?",
    ]
    matches: list[tuple[int, int, str]] = []
    for prefix in heading_prefixes:
        match = re.search(rf"^{re.escape(prefix)}$", text, flags=re.MULTILINE)
        if not match:
            continue
        number = int(prefix.split(".", 1)[0])
        matches.append((number, match.start(), prefix))

    out: dict[int, str] = {}
    matches.sort(key=lambda item: item[1])
    for idx, (number, start, _prefix) in enumerate(matches):
        end = matches[idx + 1][1] if idx + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if block:
            out[number] = block
    return out


def mechanism_sections(text: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for title, block in slice_blocks(text, r"^SECTION\s+\d+\s*:\s*.+$"):
        match = re.match(r"^SECTION\s+(\d+)\s*:", title)
        if not match:
            continue
        out[int(match.group(1))] = block
    return out


def faq_categories(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for title, block in slice_blocks(text, r"^\*\*.+\*\*$"):
        out[title.strip()] = block
    return out


def keep_sections(sections: dict[int, str], ordered_ids: list[int]) -> list[str]:
    return [sections[idx] for idx in ordered_ids if idx in sections]


def keep_categories(categories: dict[str, str], ordered_titles: list[str]) -> list[str]:
    return [categories[title] for title in ordered_titles if title in categories]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build verbatim product context chunks for generation")
    parser.add_argument("--product", default="productinfomain.txt")
    parser.add_argument("--mechanism", default="PRODUCT_MECHANISM_V1.txt")
    parser.add_argument("--faq", default="faq.txt")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    product_text = Path(args.product).read_text(encoding="utf-8")
    mechanism_text = Path(args.mechanism).read_text(encoding="utf-8")
    faq_text = Path(args.faq).read_text(encoding="utf-8")

    product = product_sections(product_text)
    mechanism = mechanism_sections(mechanism_text)
    faq = faq_categories(faq_text)

    payload = {
        "product_info": keep_sections(product, [1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]),
        "mechanism": keep_sections(product, [7, 8]) + keep_sections(mechanism, [0, 1, 2, 4, 5, 6, 7, 8]),
        "faq": keep_categories(
            faq,
            [
                "**Product Details**",
                "**Usage Instructions**",
                "**Results & Guarantees**",
                "**Side Effects & Safety**",
                "**Presenting Problem / Issues**",
                "**Support & Follow-up**",
            ],
        ),
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key, values in payload.items():
            print(f"[{key}]")
            for item in values:
                print(item)
                print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
