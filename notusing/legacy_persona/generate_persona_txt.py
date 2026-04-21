#!/usr/bin/env python3
"""Generate PERSONA_DEEP_DIVE text file from persona CSV.

Workflow:
1) Update XLSX in Excel.
2) Export/save as CSV with the same headers.
3) Run this script to refresh the deep-dive TXT.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


HEADER = """OBESITY KILLER KIT - PERSONA DEEP DIVE LIBRARY
Coverage: Personas {min_id}-{max_id} from the playbook persona system

PURPOSE
- This file is the bridge between persona labels and final ad copy.
- It uses a 3-layer system so one persona can be converted into English, Hindi, and Hinglish ads without losing emotional truth.
- All mechanism logic in this file must come from `info/PRODUCT_MECHANISM_V1.txt`.
- If product behavior changes later, update `info/PRODUCT_MECHANISM_V1.txt` first, then update this file.

3-LAYER SYSTEM

LAYER 1 - RAW PERSONA TRUTH
- Raw thoughts, complaints, objections, and phrases the person actually says.
- This layer can be messy, emotional, and Hinglish-heavy.

LAYER 2 - MESSAGE STRATEGY
- Convert raw voice into ad-ready strategy.
- Pull these from each persona: core pain, trigger scenarios, objections, language bank, mechanism match, trust anchors.

LAYER 3 - OUTPUT LANGUAGE RENDERING
- Render the same persona angle into 3 outputs:
- English-ready ad phrasing
- Hindi-ready ad phrasing
- Hinglish-ready ad phrasing

USE RULE
- Do not write ads directly from raw lines.
- First identify the emotional angle from Layer 1.
- Then choose the mechanism and proof from Layer 2.
- Then render the final copy in the requested language using Layer 3.
"""


def split_items(value: str, sep: str = ";") -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(sep) if part.strip()]


def split_sources(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("|") if part.strip()]


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "Persona_ID",
            "Persona_Name",
            "Layer1_Raw_Pain_Forum_Verbatim",
            "Layer1_Trigger_Scenarios_Forum",
            "Layer1_Objections_Forum",
            "Layer2_Core_Message",
            "Layer2_Grounded_Mechanism_Map",
            "Layer2_How_Kit_Solves",
            "Layer2_Trust_Anchors",
            "Layer3_English_Ready_Phrasing",
            "Layer3_Hindi_Ready_Phrasing",
            "Layer3_Hinglish_Ready_Phrasing",
            "Primary_Sources",
        }
        headers = set(reader.fieldnames or [])
        missing = sorted(required - headers)
        if missing:
            raise ValueError(f"Missing required columns in CSV: {', '.join(missing)}")

        rows = [dict(r) for r in reader]

    if not rows:
        raise ValueError("CSV has no persona rows.")

    rows.sort(key=lambda r: int(r["Persona_ID"].strip()))
    return rows


def extract_existing_snapshots(existing_text: str) -> dict[int, list[str]]:
    """Extract Basic snapshot bullet lines from existing persona file.

    Keeps existing snapshot metadata stable while regenerating the rest.
    """
    snapshots: dict[int, list[str]] = {}
    matches = list(re.finditer(r"^PERSONA\s+(\d+):.*$", existing_text, flags=re.M))
    for i, match in enumerate(matches):
        persona_id = int(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(existing_text)
        block = existing_text[start:end]

        basic_idx = block.find("Basic snapshot:")
        layer_idx = block.find("\nLAYER 1")
        if basic_idx == -1 or layer_idx == -1 or layer_idx <= basic_idx:
            continue

        basic_section = block[basic_idx:layer_idx]
        bullets = []
        for line in basic_section.splitlines():
            line = line.rstrip()
            if line.startswith("- "):
                bullets.append(line[2:].strip())
        if bullets:
            snapshots[persona_id] = bullets
    return snapshots


def fallback_snapshot(name: str) -> list[str]:
    return [
        f"Persona label: {name}",
        "Source basis: Forum-grounded signals from spreadsheet",
    ]


def make_language_bank(pain_items: list[str], max_items: int = 8) -> list[str]:
    bank = []
    seen = set()
    for item in pain_items:
        cleaned = item.strip().strip('"').strip("'")
        if not cleaned:
            continue
        words = cleaned.split()
        phrase = " ".join(words[:5]) if len(words) > 5 else cleaned
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        bank.append(phrase)
        if len(bank) >= max_items:
            break
    return bank


def add_list(lines: list[str], items: list[str]) -> None:
    for item in items:
        lines.append(f"- {item}")


def render(rows: list[dict[str, str]], existing_output_text: str | None = None) -> str:
    snapshots = extract_existing_snapshots(existing_output_text or "")
    min_id = int(rows[0]["Persona_ID"])
    max_id = int(rows[-1]["Persona_ID"])

    lines: list[str] = [HEADER.format(min_id=min_id, max_id=max_id).rstrip(), ""]

    for row in rows:
        pid = int(row["Persona_ID"].strip())
        persona_name = (row["Persona_Name"] or "").strip()
        heading_name = persona_name.upper()
        if "FORUM-GROUNDED" not in heading_name:
            heading_name += " (FORUM-GROUNDED)"

        pain_items = split_items(row["Layer1_Raw_Pain_Forum_Verbatim"])
        trigger_items = split_items(row["Layer1_Trigger_Scenarios_Forum"])
        objection_items = split_items(row["Layer1_Objections_Forum"])
        language_bank_items = make_language_bank(pain_items)
        core_items = split_items(row["Layer2_Core_Message"])
        mechanism_items = split_items(row["Layer2_Grounded_Mechanism_Map"])
        kit_solves_items = split_items(row["Layer2_How_Kit_Solves"])
        trust_items = split_items(row["Layer2_Trust_Anchors"])
        english_items = split_items(row["Layer3_English_Ready_Phrasing"])
        hindi_items = split_items(row["Layer3_Hindi_Ready_Phrasing"])
        hinglish_items = split_items(row["Layer3_Hinglish_Ready_Phrasing"])
        source_items = split_sources(row["Primary_Sources"])

        lines.extend(
            [
                "=====================================================================",
                f"PERSONA {pid}: {heading_name}",
                "=====================================================================",
                "",
                "Basic snapshot:",
            ]
        )
        add_list(lines, snapshots.get(pid, fallback_snapshot(persona_name)))

        lines.extend(
            [
                "",
                "LAYER 1 - RAW PERSONA TRUTH (VERBATIM FORUM SIGNALS)",
                "",
                "1. PAIN POINTS",
            ]
        )
        add_list(lines, pain_items)

        lines.extend(["", "2. TRIGGER SCENARIOS"])
        add_list(lines, trigger_items)

        lines.extend(["", "3. OBJECTIONS"])
        add_list(lines, objection_items)

        lines.extend(["", "4. LANGUAGE BANK"])
        add_list(lines, language_bank_items)

        lines.extend(["", "LAYER 2 - MESSAGE STRATEGY", "", "5. CORE MESSAGE"])
        add_list(lines, core_items)

        lines.extend(["", "6. GROUNDED MECHANISM MAP"])
        add_list(lines, mechanism_items)

        lines.extend(["", "7. HOW THE KIT SOLVES THIS PERSONA'S PROBLEM"])
        add_list(lines, kit_solves_items)

        lines.extend(["", "8. TRUST ANCHORS"])
        add_list(lines, trust_items)

        lines.extend(["", "9. SOURCE EVIDENCE (USED)"])
        add_list(lines, source_items)

        lines.extend(["", "LAYER 3 - OUTPUT LANGUAGE RENDERING", "", "10. ENGLISH-READY AD PHRASING"])
        add_list(lines, english_items)

        lines.extend(["", "11. HINDI-READY AD PHRASING"])
        add_list(lines, hindi_items)

        lines.extend(["", "12. HINGLISH-READY AD PHRASING"])
        add_list(lines, hinglish_items)
        lines.append("")

    lines.extend(
        [
            "END OF COVERAGE",
            f"- Included personas: {min_id}-{max_id}",
            "- Structure supports English, Hindi, and Hinglish ad rendering from the same persona brief",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate persona deep-dive TXT from CSV")
    parser.add_argument(
        "--csv",
        default="PERSONA_DEEP_DIVE_FIRST5_FORUM_GROUNDED.csv",
        help="Input CSV path",
    )
    parser.add_argument(
        "--output",
        default="PERSONA_DEEP_DIVE_01_05.txt",
        help="Output TXT path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if output content differs from file on disk",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv).resolve()
    output_path = Path(args.output).resolve()

    rows = load_rows(csv_path)
    existing_text = output_path.read_text(encoding="utf-8") if output_path.exists() else None
    rendered = render(rows, existing_output_text=existing_text)

    if args.check:
        if existing_text is None:
            print(f"[DIFF] Missing output file: {output_path}")
            return 1
        if existing_text != rendered:
            print(f"[DIFF] {output_path} is out of date with {csv_path}")
            return 1
        print(f"[OK] {output_path} matches {csv_path}")
        return 0

    output_path.write_text(rendered, encoding="utf-8")
    print(f"[OK] Wrote {output_path} from {csv_path} ({len(rows)} personas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
