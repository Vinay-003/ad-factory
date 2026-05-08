#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def default_product_path() -> str:
    return str(ROOT / "product master doc.txt")


def merge_product_directives(product_path: Path, product_text: str) -> str:
    """
    Single source of truth mode:
    - Do NOT merge from legacy product files.
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
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    current_id = -1

    for line in lines:
        m = re.match(r"^(\d+)\.\s+(.+)$", line)
        section_id = int(m.group(1)) if m else -1
        if m and section_id > current_id:
            if current_title:
                sections.append((current_title, current_lines))
            current_id = section_id
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
    Extract an explicit priority block only when the master doc defines one.
    """
    out: list[str] = []
    seen: set[str] = set()

    for title, section in split_numbered_sections(lines):
        if title.lower().startswith("0. extractor priority block"):
            for line in section:
                _append_unique(out, seen, line)
            return out
    return []


def extract_headline_strategy(lines: list[str]) -> list[str]:
    """
    Preserve explicit interpretation rules from the master doc. Do not synthesize strategy.
    """
    out: list[str] = []
    seen: set[str] = set()
    for _, section_lines in split_numbered_sections(lines):
        for i, line in enumerate(section_lines):
            if line not in {"Interpretation Rules for AI / Team Use", "Interpretation Rule"}:
                continue
            _append_unique(out, seen, line)
            for item in section_lines[i + 1 :]:
                if item in {"Full Answer", "Full Explanation", "AI Reference Notes"}:
                    break
                _append_unique(out, seen, item)
    return out


def extract_theme_lines(lines: list[str]) -> list[str]:
    """
    Preserve explicit theme/reference lines from the master doc. Do not synthesize labels.
    """
    out: list[str] = []
    seen: set[str] = set()
    stop_headers = {
        "Full Answer",
        "Full Explanation",
        "Interpretation Rules for AI / Team Use",
        "Interpretation Rule",
    }
    for _, section_lines in split_numbered_sections(lines):
        for i, line in enumerate(section_lines):
            if line not in {"Brand Truths This Product Should Own", "AI Reference Notes"}:
                continue
            _append_unique(out, seen, line)
            for item in section_lines[i + 1 :]:
                if item in stop_headers:
                    break
                _append_unique(out, seen, item)
    return out


def extract_trigger_rules(lines: list[str]) -> list[str]:
    """Return only source lines containing explicit rule/strategy language."""
    keywords = [
        "lead with",
        "do not",
        "should not",
        "must",
        "interpretation rule",
        "interpretation rules",
        "guardrail",
        "exclusion",
        "not for",
    ]
    return extract_keyword_lines(lines, keywords)


def extract_product_sections(lines: list[str]) -> list[str]:
    """Extract source sections exactly as written in the master doc."""
    sections = split_numbered_sections(lines)

    out: list[str] = []
    seen: set[str] = set()

    # Add top header content exactly as written.
    for l in lines[:20]:
        _append_unique(out, seen, l)

    # Add all numbered sections from the master doc. The doc may grow as product strategy evolves.
    for title, sec_lines in sections:
        m = re.match(r"^(\d+)\.\s+", title)
        if not m:
            continue
        for l in sec_lines:
            _append_unique(out, seen, l)

    # Add explicit rule sections by scanning for exact headings.
    markers = [
        "Interpretation Rules for AI / Team Use",
        "What should the brand not say?",
    ]
    text = "\n".join(lines)
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
    current_id = -1

    for line in lines:
        m = heading_re.match(line)
        section_id = int(m.group(1)) if m else -1
        if m and section_id > current_id:
            if current_title:
                sections.append((current_title, current_lines))
            current_id = section_id
            current_title = line
            current_lines = [line]
            continue
        if current_title:
            current_lines.append(line)
    if current_title:
        sections.append((current_title, current_lines))
    return sections


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

    # Keep downstream schema keys, but do not synthesize mechanism/FAQ content.
    payload = {
        "product_info": compact_lines(
            product_text,
            product_limit,
            keywords=[],  # rely on extract_product_sections + keyword-specific groups
            section_lines=extract_product_sections(product_lines),
        ),
        "mechanism": [],
        "faq": [],
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
