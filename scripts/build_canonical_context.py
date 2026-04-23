#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
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

CANONICAL_BUCKETS = [
    "positioning",
    "promise_claims",
    "eligibility",
    "exclusions",
    "caution_conditions",
    "protocol_morning",
    "protocol_night",
    "fasting_rules",
    "allowed_items",
    "restricted_items",
    "mechanism_allowed_claims",
    "mechanism_disallowed_claims",
    "safety_public_line",
    "safety_internal_handling",
    "pricing",
    "guarantee",
    "continuation",
    "maintenance",
    "proof_points",
    "messaging_guardrails",
    "on_image_copy_requirements",
    "priority_block",
    "headline_strategy",
    "protected_themes",
    "trigger_rules",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical reconciled context via OpenCode model")
    parser.add_argument("--product", default=default_product_path())
    parser.add_argument("--mechanism", default="PRODUCT_MECHANISM_V1.txt")
    parser.add_argument("--faq", default="faq.txt")
    parser.add_argument("--output", default="runtime/context_canonical.json")
    parser.add_argument("--api-url", default=os.getenv("OPENCODE_API_URL", ""))
    parser.add_argument("--api-key", default=os.getenv("OPENCODE_SERVER_PASSWORD", ""))
    parser.add_argument("--model", required=True)
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


def parse_json_object_from_text(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    best: dict[str, Any] | None = None
    best_span = -1
    for match in re.finditer(r"\{", text):
        try:
            parsed, end = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and end > best_span:
            best = parsed
            best_span = end
    return best


def parse_opencode_stream(stdout: str) -> str:
    chunks: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "text":
            continue
        part = event.get("part") or {}
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n".join(chunks).strip()


def ensure_list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        clean = " ".join(item.split()).strip()
        if not clean or clean in seen:
            continue
        out.append(clean)
        seen.add(clean)
    return out


def normalize_canonical(raw: dict[str, Any]) -> dict[str, list[str]]:
    canonical = raw.get("canonical") if isinstance(raw.get("canonical"), dict) else {}
    out: dict[str, list[str]] = {}
    for bucket in CANONICAL_BUCKETS:
        out[bucket] = ensure_list_of_strings(canonical.get(bucket))
    return out


def build_generation_context(canonical: dict[str, list[str]]) -> dict[str, list[str]]:
    product_info = (
        canonical["priority_block"]
        + canonical["trigger_rules"]
        + canonical["positioning"]
        + canonical["promise_claims"]
        + canonical["headline_strategy"]
        + canonical["protected_themes"]
        + canonical["on_image_copy_requirements"]
        + canonical["protocol_morning"]
        + canonical["protocol_night"]
        + canonical["fasting_rules"]
        + canonical["mechanism_allowed_claims"]
        + canonical["eligibility"]
        + canonical["exclusions"]
        + canonical["caution_conditions"]
        + canonical["safety_public_line"]
        + canonical["safety_internal_handling"]
        + canonical["guarantee"]
        + canonical["continuation"]
        + canonical["maintenance"]
        + canonical["proof_points"]
        + canonical["allowed_items"]
        + canonical["restricted_items"]
        + canonical["messaging_guardrails"]
    )
    mechanism = (
        canonical["mechanism_allowed_claims"]
        + canonical["trigger_rules"]
        + canonical["on_image_copy_requirements"]
        + canonical["protocol_morning"]
        + canonical["protocol_night"]
        + canonical["fasting_rules"]
    )
    faq = (
        canonical["allowed_items"]
        + canonical["restricted_items"]
        + canonical["messaging_guardrails"]
        + [f"Do not claim: {item}" for item in canonical["mechanism_disallowed_claims"]]
    )

    def uniq(lines: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for line in lines:
            if line in seen:
                continue
            out.append(line)
            seen.add(line)
        return out

    return {
        "product_info": uniq(product_info),
        "mechanism": uniq(mechanism),
        "faq": uniq(faq),
        "priority_block": uniq(canonical["priority_block"]),
        "headline_strategy": uniq(canonical["headline_strategy"]),
        "protected_themes": uniq(canonical["protected_themes"]),
        "trigger_rules": uniq(canonical["trigger_rules"]),
    }


def build_prompt(product_text: str, mechanism_text: str, faq_text: str) -> str:
    schema = {
        "metadata": {
            "extractor_model": "string",
            "source_files": ["productinfomain.txt", "PRODUCT_MECHANISM_V1.txt", "faq.txt"],
        },
        "canonical": {bucket: ["string"] for bucket in CANONICAL_BUCKETS},
        "conflicts": [
            {
                "conflict_id": "string",
                "bucket": "string",
                "claim_a": {"text": "string", "source_file": "string", "line_start": 0, "line_end": 0},
                "claim_b": {"text": "string", "source_file": "string", "line_start": 0, "line_end": 0},
                "resolution_status": "resolved|unresolved",
                "chosen_claim": {"text": "string", "source_file": "string", "line_start": 0, "line_end": 0},
                "resolution_reason": "string",
                "risk_level": "high|medium|low",
            }
        ],
        "dropped_claims": [
            {
                "text": "string",
                "reason": "conflict|low_confidence|legacy_override_blocked|ambiguity",
                "source_file": "string",
                "line_start": 0,
                "line_end": 0,
            }
        ],
        "coverage_check": {
            "required_present": {
                "3_to_5kg_15days": True,
                "adults_18plus_bmi_gt_25": True,
                "insulin_exclusion": True,
                "pregnancy_postpartum_exclusion": True,
                "morning_liquid_4h_no_solids": True,
                "night_powder_tablet": True,
                "31_unique_44_total": True,
                "refund_7day_with_tracker": True,
                "not_fat_burner_positioning": True,
                "on_image_copy_explicit_weightloss": True,
                "headline_strategy_preserved": True,
                "am_pm_routine_priority": True,
                "cravings_down_priority": True,
                "support_priority": True,
                "feature_based_headlines": True,
            },
            "missing_required": [],
        },
    }

    instructions = (
        "You are a strict information extraction and reconciliation engine for a regulated ad-copy pipeline.\n"
        "Return ONLY valid JSON with the required schema.\n"
        "Do not invent facts.\n"
        "Prefer detailed preservation over compression. Keep explicit rules, triggers, exclusions, routine steps, hierarchy blocks, proof stacks, benefit ladders, and extraction priority blocks separate when the source provides them.\n"
        "Resolve contradictions with this priority:\n"
        "1) PRODUCT_MECHANISM_V1.txt for mechanism boundaries\n"
        "2) productinfomain.txt CONTEXT SNAPSHOT / EXTRACTOR PRIORITY BLOCK / HEADLINE STRATEGY sections\n"
        "3) productinfomain.txt remaining Single Source of Truth sections\n"
        "4) faq.txt for operational protocol and objection handling\n"
        "If ON-IMAGE COPY MANDATE is present, extract it into on_image_copy_requirements and preserve it in practical form.\n"
        "Treat the headline families AM/PM routine, cravings down, and support as protected priorities in the exact order shown in the source. Do not reorder or abstract them away.\n"
        "The extraction must keep headlines and subheadlines feature-based, tied to product mechanics, and explicitly connected to weight loss or obesity reduction.\n"
        "Do not compress rich product sections into 2-3 summary bullets when the source gives detailed execution rules, feature banks, interpretation rules, or priority ladders.\n"
        "If the product file defines what to trigger, what to use, what not to use, or how headline/subheadline lanes should rotate, preserve those instructions with high fidelity.\n"
        "Do not normalize strong product wording into vague transformation copy.\n"
        "If a source says what to use, what not to use, when to use it, or what to avoid, preserve that as explicit guidance instead of collapsing it into a generic summary.\n"
        "Legacy encyclopedia or training fragments must not override higher-priority claims.\n"
    )

    payload = {
        "schema": schema,
        "sources": {
            "productinfomain.txt": product_text,
            "PRODUCT_MECHANISM_V1.txt": mechanism_text,
            "faq.txt": faq_text,
        },
    }

    return (
        "SYSTEM:\n"
        + instructions
        + "\nUSER_PAYLOAD_JSON:\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nReturn only valid JSON. No markdown."
    )


def main() -> int:
    args = parse_args()

    product_path = Path(args.product)
    mechanism_path = Path(args.mechanism)
    faq_path = Path(args.faq)
    output_path = Path(args.output)

    if not args.api_url.strip():
        raise RuntimeError("Missing --api-url for canonical extraction")

    product_text = merge_product_directives(product_path, product_path.read_text(encoding="utf-8"))
    mechanism_text = mechanism_path.read_text(encoding="utf-8")
    faq_text = faq_path.read_text(encoding="utf-8")

    prompt = build_prompt(product_text, mechanism_text, faq_text)

    prompt_file = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write(prompt)
            prompt_file = handle.name
        cmd = [
            "opencode",
            "run",
            "--pure",
            "--attach",
            args.api_url.strip(),
            "--model",
            args.model.strip(),
            "--format",
            "json",
            "--file",
            prompt_file,
        ]
        if args.api_key.strip():
            cmd.extend(["--password", args.api_key.strip()])
        cmd.extend(["--", "Read the attached prompt file and follow it exactly. Return only valid JSON. No markdown."])
        result = run_cmd(cmd, cwd=ROOT)
    finally:
        if prompt_file:
            Path(prompt_file).unlink(missing_ok=True)
    raw_content = ""
    if result.returncode == 0:
        raw_content = parse_opencode_stream(result.stdout)
        if not raw_content:
            raw_content = (result.stdout or "").strip()
    else:
        raise RuntimeError(f"OpenCode canonical extraction failed: {result.stderr.strip() or result.stdout.strip()}")

    parsed = parse_json_object_from_text(raw_content)
    if not parsed:
        raise RuntimeError("OpenCode canonical extraction returned no parseable JSON")

    canonical = normalize_canonical(parsed)
    generation_context = build_generation_context(canonical)

    final_payload = {
        "metadata": {
            "generated_at": now_iso(),
            "extractor_model": args.model.strip(),
            "source_files": [
                str(product_path),
                str(mechanism_path),
                str(faq_path),
            ],
            "source_sizes": {
                "product_chars": len(product_text),
                "mechanism_chars": len(mechanism_text),
                "faq_chars": len(faq_text),
            },
        },
        "canonical": canonical,
        "conflicts": parsed.get("conflicts") if isinstance(parsed.get("conflicts"), list) else [],
        "dropped_claims": parsed.get("dropped_claims") if isinstance(parsed.get("dropped_claims"), list) else [],
        "coverage_check": parsed.get("coverage_check") if isinstance(parsed.get("coverage_check"), dict) else {},
        "generation_context": generation_context,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(final_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
