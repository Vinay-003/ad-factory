#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_bullets(block: str, title: str) -> list[str]:
    pattern = rf"{re.escape(title)}\n(?P<body>.*?)(?:\n\n\d+\.|\n\nLAYER|\Z)"
    match = re.search(pattern, block, flags=re.DOTALL)
    if not match:
        return []
    body = match.group("body")
    out: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("- "):
            out.append(line[2:].strip())
    return out


def get_persona_block(content: str, persona_number: int) -> tuple[str, str]:
    pattern = re.compile(r"^PERSONA\s+(\d+):\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(content))
    for idx, match in enumerate(matches):
        number = int(match.group(1))
        if number != persona_number:
            continue
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        return match.group(2).strip(), content[start:end]
    raise RuntimeError(f"Persona {persona_number} not found")


def build_payload(persona_name: str, block: str, persona_number: int) -> dict:
    return {
        "persona_number": persona_number,
        "persona_name": persona_name,
        "pain_points": parse_bullets(block, "1. PAIN POINTS"),
        "trigger_scenarios": parse_bullets(block, "2. TRIGGER SCENARIOS"),
        "objections": parse_bullets(block, "3. OBJECTIONS"),
        "language_bank": parse_bullets(block, "4. LANGUAGE BANK"),
        "core_message": parse_bullets(block, "5. CORE MESSAGE"),
        "grounded_mechanism_map": parse_bullets(block, "6. GROUNDED MECHANISM MAP"),
        "how_kit_solves": parse_bullets(block, "7. HOW THE KIT SOLVES THIS PERSONA'S PROBLEM"),
        "trust_anchors": parse_bullets(block, "8. TRUST ANCHORS"),
        "english_ready": parse_bullets(block, "10. ENGLISH-READY AD PHRASING"),
        "hindi_ready": parse_bullets(block, "11. HINDI-READY AD PHRASING"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract one persona block from PERSONA_DEEP_DIVE file")
    parser.add_argument("--input", default="PERSONA_DEEP_DIVE_01_05.txt", help="Persona deep dive txt path")
    parser.add_argument("--persona", type=int, required=True, help="Persona number")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    content = Path(args.input).read_text(encoding="utf-8")
    persona_name, block = get_persona_block(content, args.persona)
    payload = build_payload(persona_name, block, args.persona)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Persona {payload['persona_number']}: {payload['persona_name']}")
        print("Pain points:")
        for item in payload["pain_points"][:5]:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
