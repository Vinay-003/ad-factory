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


def compact_lines(text: str, max_lines: int, keywords: list[str]) -> list[str]:
    lines = _clean_lines(text)
    out: list[str] = []
    seen: set[str] = set()

    snapshot_start = -1
    snapshot_end = -1
    keep_pattern = re.compile(r"^(-|Q:|A:|\d+\)|RAPID FIRE|ADDITIONAL INTERVIEW)", re.IGNORECASE)
    for i, line in enumerate(lines):
        if "SNAPSHOT (FOR EXTRACTION)" in line.upper():
            snapshot_start = i
            snapshot_end = i
            for j in range(i + 1, len(lines)):
                if keep_pattern.match(lines[j]):
                    snapshot_end = j
                    continue
                break
            break

    for line in extract_snapshot_block(lines):
        _append_unique(out, seen, line)
        if len(out) >= max_lines:
            return out[:max_lines]

    if snapshot_start >= 0:
        for line in lines[snapshot_end + 1 :]:
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
    parser.add_argument("--max-lines", type=int, default=60)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

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
            Path(args.product).read_text(encoding="utf-8"),
            args.max_lines,
            product_keywords,
        ),
        "mechanism": compact_lines(
            Path(args.mechanism).read_text(encoding="utf-8"),
            args.max_lines,
            mechanism_keywords,
        ),
        "faq": compact_lines(
            Path(args.faq).read_text(encoding="utf-8"),
            args.max_lines,
            faq_keywords,
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
