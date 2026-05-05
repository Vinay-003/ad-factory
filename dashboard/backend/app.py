#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import hashlib
import mimetypes
import uuid
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = ROOT / "dashboard_storage"
RUNS_ROOT = STORAGE_ROOT / "runs"
RUNTIME_ROOT = ROOT / "runtime"
ENV_PATH = ROOT / ".env.dashboard"

LEGACY_PRODUCT_INFO = ROOT / "productinfomain.txt"
MASTER_PRODUCT_INFO = ROOT / "productmaster.txt"
DEFAULT_PRODUCT_INFO = MASTER_PRODUCT_INFO if MASTER_PRODUCT_INFO.exists() else LEGACY_PRODUCT_INFO
DEFAULT_MECHANISM = ROOT / "PRODUCT_MECHANISM_V1.txt"
DEFAULT_FAQ = ROOT / "faq.txt"
DEFAULT_PLAYBOOK = ROOT / "AD_CREATIVE_SYSTEM_PLAYBOOK.md"
DEFAULT_IMAGE_SOURCES_FILE = ROOT / "input" / "image_sources.txt"
LEGACY_ACTIVE_IMAGES_FILE = ROOT / "input" / "activeimages.txt"
INPUT_IMAGES_DIR = ROOT / "input" / "images"
GENERATED_IMAGES_ROOT = ROOT / "generated_images"
LEGACY_GENERATED_IMAGE_ROOT = ROOT / "generated_image"


FORMATS = ["HERO", "BA", "TEST", "FEAT", "UGC"]
DEFAULT_OPENCODE_API_URL = os.getenv("OPENCODE_API_URL", "http://127.0.0.1:4090")


def resolve_language_mode(config: dict[str, Any]) -> str:
    mode = str(config.get("language_mode") or "ALL").strip().upper()
    if mode in {"EN", "HI", "HINGLISH", "ALL"}:
        return mode
    return "ALL"


def assembler_language_mode(config: dict[str, Any]) -> str:
    mode = resolve_language_mode(config)
    if mode == "EN":
        return "EN"
    if mode == "HI":
        return "HI"
    return "BOTH"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    return f"run_{int(time.time())}_{random.randint(1000, 9999)}"


def ensure_dirs() -> None:
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    INPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_persona_library(playbook_path: Path) -> list[dict[str, Any]]:
    text = playbook_path.read_text(encoding="utf-8")
    start = text.find("Persona library (select by number):")
    if start < 0:
        return []
    end = text.find("For each persona", start)
    block = text[start:end if end > start else len(text)]
    out: list[dict[str, Any]] = []
    pattern = re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE)
    for m in pattern.finditer(block):
        out.append({"number": int(m.group(1)), "name": m.group(2).strip()})
    return out


PERSONA_SEED_INPUTS: dict[int, dict[str, str]] = {
    1: {"pain": "Daily cravings break every weight plan.", "desire": "Steady appetite control without feeling deprived.", "friction": "Willpower-only plans collapse by evening.", "proof": "Needs visible early control over snack urges.", "tone": "practical and reassuring"},
    2: {"pain": "Work schedule leaves no room for complex routines.", "desire": "Simple weight routine that fits packed days.", "friction": "Meal prep and long workouts are not sustainable.", "proof": "Needs a low-effort protocol that still shows progress.", "tone": "efficient and confidence-building"},
    3: {"pain": "Stress triggers emotional snacking at random times.", "desire": "Calmer eating with fewer stress-led cravings.", "friction": "Plans fail during stressful moments.", "proof": "Needs believable support during emotional triggers.", "tone": "empathetic and non-judgmental"},
    4: {"pain": "Weight loss plateaus despite repeated effort.", "desire": "Break stagnation with a clear daily system.", "friction": "Repeated plateaus kill motivation.", "proof": "Needs a trackable, structured restart path.", "tone": "direct and motivating"},
    5: {"pain": "PCOD-related weight gain feels harder to reverse.", "desire": "Steadier weight progress with manageable routine.", "friction": "Fear of harsh or unsafe methods.", "proof": "Needs non-cure, compliant weight-support framing.", "tone": "careful and trust-led"},
    6: {"pain": "Thyroid-linked weight gain feels stubborn and slow.", "desire": "Consistent progress without extreme restrictions.", "friction": "Low confidence after slow previous results.", "proof": "Needs realistic, compliant support expectations.", "tone": "measured and credible"},
    7: {"pain": "Multiple failed diets created low confidence.", "desire": "A restart that actually feels doable.", "friction": "Past strict plans felt impossible to continue.", "proof": "Needs simple steps and visible early wins.", "tone": "encouraging and reset-focused"},
    8: {"pain": "Wants weight loss but fears weakness and fatigue.", "desire": "Lighter body with stable daily energy.", "friction": "Skeptical of plans that feel draining.", "proof": "Needs assurance of practical energy support.", "tone": "calm and evidence-led"},
    9: {"pain": "Parent schedule causes rushed meals and random snacking.", "desire": "A routine that works even on chaotic days.", "friction": "No time for rigid diets or long workouts.", "proof": "Needs a simple protocol that fits family life.", "tone": "real-life and practical"},
    10: {"pain": "Self-care is postponed while handling household priorities.", "desire": "A manageable routine that can be sustained at home.", "friction": "Complex plans don't fit daily responsibilities.", "proof": "Needs a low-friction system for homemaker schedules.", "tone": "supportive and respectful"},
    11: {"pain": "Tea-time office snacking derails daily intake control.", "desire": "Fewer impulse snacks during work breaks.", "friction": "Social snack cues are hard to resist.", "proof": "Needs practical control over recurring snack windows.", "tone": "conversational and specific"},
    12: {"pain": "Late-night hunger leads to repeated overeating.", "desire": "Calmer nights with better eating control.", "friction": "Evening cravings undo daytime discipline.", "proof": "Needs night-routine support that feels realistic.", "tone": "steady and habit-focused"},
    13: {"pain": "Weight rebounds after festivals and travel periods.", "desire": "Quick reset back to steady routine.", "friction": "Irregular days break consistency easily.", "proof": "Needs a restart protocol that works after disruptions.", "tone": "reset-oriented and practical"},
    14: {"pain": "Worry that metabolism has slowed permanently.", "desire": "Believable progress through structured daily consistency.", "friction": "Confusion from too many conflicting theories.", "proof": "Needs clear mechanism logic without hype claims.", "tone": "clear and science-grounded"},
    15: {"pain": "Digestive discomfort and weight concerns occur together.", "desire": "Lighter digestion with better intake control.", "friction": "Discomfort makes routines hard to follow.", "proof": "Needs digestion-support plus weight-management framing.", "tone": "gentle and practical"},
    16: {"pain": "Budget concerns reduce trust in expensive plans.", "desire": "Reliable progress from a practical system.", "friction": "Fear of paying without results.", "proof": "Needs strong value and risk-reduction cues.", "tone": "transparent and outcome-focused"},
    17: {"pain": "Event deadline creates pressure and urgency.", "desire": "Visible progress in a short, realistic window.", "friction": "Panic-driven plans often backfire.", "proof": "Needs structured short-term milestone framing.", "tone": "urgent but controlled"},
    18: {"pain": "Low confidence from body discomfort and low energy.", "desire": "Feel lighter, sharper, and more confident daily.", "friction": "Inconsistent routines reduce momentum.", "proof": "Needs confidence-building early progress signals.", "tone": "uplifting and grounded"},
    19: {"pain": "Only trusts doctor-backed, evidence-grounded solutions.", "desire": "Safe-feeling system with clear proof signals.", "friction": "Distrust of generic internet claims.", "proof": "Needs founder credibility and structured protocol proof.", "tone": "authoritative and factual"},
    20: {"pain": "Struggles to stay consistent without accountability.", "desire": "Daily support that keeps follow-through high.", "friction": "Drops routines when guidance is missing.", "proof": "Needs tracker-led support and coach cues.", "tone": "coach-like and motivating"},
    21: {"pain": "Hates complicated plans and too many rules.", "desire": "Simple steps with almost no guesswork.", "friction": "Complexity causes early drop-off.", "proof": "Needs a very clear, easy-to-follow structure.", "tone": "simple and direct"},
    22: {"pain": "Progress feels slower after 35 despite effort.", "desire": "Steady sustainable progress without extreme routines.", "friction": "Frustration from slow visible change.", "proof": "Needs realistic milestones and consistency proof.", "tone": "reassuring and practical"},
    23: {"pain": "Routine changed after childbirth and time is limited.", "desire": "A gentle return to steady progress that fits daily life.", "friction": "Harsh or complex plans feel unrealistic right now.", "proof": "Needs practical, supportive steps for a changed routine.", "tone": "gentle and encouraging"},
    24: {"pain": "Weight feels harder to manage during menopause.", "desire": "Visible progress with a manageable, sustainable routine.", "friction": "Usual methods feel harsher and harder to continue.", "proof": "Needs doctor-led credibility and real-life usability.", "tone": "respectful and practical"},
    25: {"pain": "Wants a natural path and avoids harsh methods.", "desire": "Natural weight-loss support that still feels effective.", "friction": "Worries natural options may be vague or weak.", "proof": "Needs clear Ayurvedic, no-synthetic trust cues.", "tone": "clear and trust-led"},
    26: {"pain": "Past quick losses came back too fast.", "desire": "A more sustainable path without bounce-back anxiety.", "friction": "Short-term fixes feel temporary and hard to maintain.", "proof": "Needs non-dependency and maintainability framing.", "tone": "steady and realistic"},
}


FEATURE_LANES: dict[str, dict[str, str]] = {
    "am_routine": {
        "label": "AM routine",
        "headline_driver": "morning OK Liquid, empty stomach start, 4-hour no-solid-food window",
        "support_driver": "weight-loss routine gets easier when mornings are structured",
    },
    "pm_routine": {
        "label": "PM routine",
        "headline_driver": "night OK Tablet + OK Powder before sleep for digestion-support-led weight-loss routine",
        "support_driver": "lighter nights and better next-day adherence",
    },
    "cravings_down": {
        "label": "Cravings down",
        "headline_driver": "reduced hunger, fewer cravings, easier appetite control for weight loss",
        "support_driver": "lower snacking friction and steadier calorie-deficit follow-through",
    },
    "guided_support": {
        "label": "Guided support",
        "headline_driver": "daily tracker, WhatsApp guidance, and coach-led follow-through for weight loss",
        "support_driver": "support system helps users stay consistent instead of guessing",
    },
    "structured_system": {
        "label": "Structured system",
        "headline_driver": "day-wise protocol, low guesswork, and practical obesity-management structure",
        "support_driver": "clear routine replaces random trial-and-error",
    },
    "homemade_food": {
        "label": "Homemade-food fit",
        "headline_driver": "weight-loss support that works with regular homemade food",
        "support_driver": "less meal-prep burden makes daily adherence more realistic",
    },
    "natural_safe": {
        "label": "Natural safe-feeling",
        "headline_driver": "all-natural Ayurvedic weight-loss support with no-side-effects positioning",
        "support_driver": "trust-led framing for users avoiding harsh methods",
    },
    "proof_guarantee": {
        "label": "Proof and guarantee",
        "headline_driver": "3 to 5 kg in 15 days, tracker-backed support, and 7-day refund conditions",
        "support_driver": "result proof and risk-reversal make the routine more believable",
    },
}


FORMAT_FEATURE_ROTATION: dict[str, list[str]] = {
    "HERO": ["am_routine", "cravings_down", "guided_support", "structured_system", "natural_safe", "proof_guarantee", "homemade_food"],
    "BA": ["cravings_down", "am_routine", "structured_system", "guided_support", "pm_routine", "proof_guarantee"],
    "TEST": ["guided_support", "cravings_down", "structured_system", "natural_safe", "proof_guarantee", "am_routine"],
    "FEAT": ["am_routine", "pm_routine", "cravings_down", "guided_support", "structured_system", "homemade_food", "natural_safe"],
    "UGC": ["cravings_down", "am_routine", "guided_support", "homemade_food", "structured_system", "proof_guarantee"],
}


def build_copy_requirements(persona_number: int, fmt: str, format_sequence_index: int) -> dict[str, Any]:
    order = FORMAT_FEATURE_ROTATION.get(fmt, ["am_routine", "cravings_down", "guided_support"])
    primary_idx = (format_sequence_index - 1) % len(order)
    secondary_idx = (primary_idx + 1) % len(order)
    primary_key = order[primary_idx]
    secondary_key = order[secondary_idx]
    primary = FEATURE_LANES[primary_key]
    secondary = FEATURE_LANES[secondary_key]
    return {
        "primary_feature": primary["label"],
        "primary_feature_key": primary_key,
        "headline_driver": primary["headline_driver"],
        "secondary_feature": secondary["label"],
        "secondary_feature_key": secondary_key,
        "support_driver": secondary["support_driver"],
        "must_mention": "Headline or paired support copy must explicitly mention weight loss, obesity reduction, excess-weight reduction, or a 15-day weight outcome.",
        "variation_rule": "Do not reuse the same headline skeleton, support-line skeleton, or persuasion angle as other ads in the same format for this batch.",
        "format_specific_rule": {
            "HERO": "Lead headline with one concrete product feature lane. Support line must add a second feature, not paraphrase the headline.",
            "UGC": "Make it sound like a creator-style practical observation, but still tie the copy to a concrete product feature lane.",
            "BA": "Left-side bullets must show the struggle state. Right-side bullets must show a specific product-feature-led shift in the weight-loss routine.",
            "TEST": "Quote/review line should mention a specific feature or result driver, not a vague generic compliment.",
            "FEAT": "Each bullet must cover a different feature. Do not repeat the same feature idea across all bullets.",
        }.get(fmt, "Use feature-led copy instead of generic transformation language."),
    }


def build_generation_payload_for_llm(context: dict[str, Any]) -> dict[str, Any]:
    product_context = context.get("product_context") if isinstance(context.get("product_context"), dict) else {}
    compact_product_context: dict[str, list[str]] = {}
    for key, value in product_context.items():
        if isinstance(value, list):
            compact_product_context[key] = [str(item).strip() for item in value[:40] if str(item).strip()]

    compact_ads: list[dict[str, Any]] = []
    for item in context.get("ads") or []:
        if not isinstance(item, dict):
            continue
        persona = item.get("persona") if isinstance(item.get("persona"), dict) else {}
        format_rules = item.get("format_rules") if isinstance(item.get("format_rules"), dict) else {}
        compact_ads.append(
            {
                "format": item.get("format"),
                "persona": {
                    "persona_number": persona.get("persona_number"),
                    "persona_name": persona.get("persona_name"),
                    "pain_points": persona.get("pain_points") or [],
                    "objections": persona.get("objections") or [],
                    "core_message": persona.get("core_message") or [],
                    "trust_anchors": persona.get("trust_anchors") or [],
                    "english_ready": persona.get("english_ready") or [],
                    "hindi_ready": persona.get("hindi_ready") or [],
                },
                "format_rules": {
                    "format": format_rules.get("format"),
                    "rules": [str(rule).strip() for rule in (format_rules.get("rules") or [])[:18] if str(rule).strip()],
                },
                "copy_requirements": item.get("copy_requirements") or {},
            }
        )

    requested_plan = []
    for item in compact_ads:
        persona = item.get("persona") if isinstance(item.get("persona"), dict) else {}
        requested_plan.append(
            {
                "format": item.get("format"),
                "persona_number": persona.get("persona_number"),
                "persona_name": persona.get("persona_name"),
                "primary_feature": (item.get("copy_requirements") or {}).get("primary_feature"),
            }
        )

    return {
        "generated_at": context.get("generated_at"),
        "run_id": context.get("run_id"),
        "language_mode": context.get("language_mode"),
        "context_source": context.get("context_source"),
        "context_extractor_model": context.get("context_extractor_model"),
        "requested_ad_count": len(compact_ads),
        "requested_plan": requested_plan,
        "product_context": compact_product_context,
        "ads": compact_ads,
    }


def validate_generated_copy_payload(copy_json: dict[str, Any], planned_ads: list[dict[str, Any]]) -> str | None:
    ads = copy_json.get("ads") if isinstance(copy_json, dict) else None
    if not isinstance(ads, list):
        return "Generated payload did not include an ads array"
    if len(ads) < len(planned_ads):
        return f"Generated ads count {len(ads)} is lower than planned count {len(planned_ads)}"

    planned_keys = {
        (str(item.get("format") or "").strip().upper(), int((item.get("persona") or {}).get("persona_number") or 0))
        for item in planned_ads
        if isinstance(item, dict) and isinstance(item.get("persona"), dict)
    }
    seen_keys: set[tuple[str, int]] = set()
    for ad in ads:
        if not isinstance(ad, dict):
            return "Generated ads payload contains a non-object item"
        fmt = str(ad.get("format") or "").strip().upper()
        persona = ad.get("persona") if isinstance(ad.get("persona"), dict) else {}
        persona_number = persona.get("number")
        if not isinstance(persona_number, int):
            persona_number = persona.get("persona_number")
        if not isinstance(persona_number, int):
            return f"Generated ad for format {fmt or '?'} is missing persona number"
        seen_keys.add((fmt, persona_number))
        copy = ad.get("copy") if isinstance(ad.get("copy"), dict) else {}
        for lang in ["EN", "HI"]:
            block = copy.get(lang) if isinstance(copy.get(lang), dict) else {}
            if not str(block.get("headline") or "").strip():
                return f"Generated ad {fmt}/P{persona_number} is missing {lang} headline"
            if fmt in {"HERO", "UGC"} and not str(block.get("support_line") or "").strip():
                return f"Generated ad {fmt}/P{persona_number} is missing {lang} support line"
            if fmt in {"BA", "FEAT"}:
                bullets = block.get("bullets") if isinstance(block.get("bullets"), list) else []
                if len([item for item in bullets if isinstance(item, str) and item.strip()]) < 2:
                    return f"Generated ad {fmt}/P{persona_number} has insufficient {lang} bullets"
            if fmt == "TEST" and not str(block.get("attribution") or "").strip():
                return f"Generated ad {fmt}/P{persona_number} is missing {lang} attribution"

    missing = sorted(planned_keys - seen_keys)
    if missing:
        return "Generated payload is missing planned ads: " + ", ".join(f"{fmt}/P{persona}" for fmt, persona in missing)
    return None


def extract_generated_ad_candidate(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
        cloned = json.loads(json.dumps(candidate, ensure_ascii=False))
        persona = cloned.get("persona") if isinstance(cloned.get("persona"), dict) else {}
        if not isinstance(persona, dict):
            persona = {}
        if not isinstance(persona.get("persona_number"), int) and isinstance(cloned.get("persona_number"), int):
            persona["persona_number"] = cloned.get("persona_number")
        if not isinstance(persona.get("number"), int) and isinstance(cloned.get("persona_number"), int):
            persona["number"] = cloned.get("persona_number")
        if not isinstance(persona.get("persona_name"), str) and isinstance(cloned.get("persona_name"), str):
            persona["persona_name"] = cloned.get("persona_name")
        if not isinstance(persona.get("name"), str) and isinstance(cloned.get("persona_name"), str):
            persona["name"] = cloned.get("persona_name")
        if persona:
            cloned["persona"] = persona
        return cloned

    ads = payload.get("ads")
    if isinstance(ads, list):
        for item in ads:
            if isinstance(item, dict) and item.get("copy"):
                return normalize_candidate(item)
    if payload.get("format") and payload.get("copy"):
        return normalize_candidate(payload)
    return None


def hydrate_generated_ad_candidate(candidate: dict[str, Any], planned_ad: dict[str, Any]) -> dict[str, Any]:
    hydrated = json.loads(json.dumps(candidate, ensure_ascii=False))

    planned_format = str(planned_ad.get("format") or "").strip().upper()
    candidate_format = str(hydrated.get("format") or "").strip().upper()
    hydrated["format"] = candidate_format or planned_format

    planned_persona = planned_ad.get("persona") if isinstance(planned_ad.get("persona"), dict) else {}
    candidate_persona = hydrated.get("persona") if isinstance(hydrated.get("persona"), dict) else {}

    persona_number = candidate_persona.get("number")
    if not isinstance(persona_number, int):
        persona_number = candidate_persona.get("persona_number")
    if not isinstance(persona_number, int):
        planned_number = planned_persona.get("persona_number")
        if isinstance(planned_number, int):
            persona_number = planned_number

    persona_name = candidate_persona.get("name")
    if not isinstance(persona_name, str) or not persona_name.strip():
        persona_name = candidate_persona.get("persona_name")
    if not isinstance(persona_name, str) or not persona_name.strip():
        planned_name = planned_persona.get("persona_name")
        if isinstance(planned_name, str):
            persona_name = planned_name

    merged_persona = dict(candidate_persona)
    if isinstance(persona_number, int):
        merged_persona["number"] = persona_number
        merged_persona["persona_number"] = persona_number
    if isinstance(persona_name, str) and persona_name.strip():
        clean_name = persona_name.strip()
        merged_persona["name"] = clean_name
        merged_persona["persona_name"] = clean_name
    if merged_persona:
        hydrated["persona"] = merged_persona

    copy_payload = hydrated.get("copy") if isinstance(hydrated.get("copy"), dict) else {}
    normalized_copy: dict[str, Any] = {}
    for lang in ["EN", "HI"]:
        lang_block = copy_payload.get(lang)
        normalized_copy[lang] = lang_block if isinstance(lang_block, dict) else {}
    hydrated["copy"] = normalized_copy

    return hydrated


def build_persona_payload(persona_number: int, personas: list[dict[str, Any]]) -> dict[str, Any]:
    persona_name = f"Persona {persona_number}"
    for item in personas:
        if int(item.get("number") or 0) == persona_number:
            name = str(item.get("name") or "").strip()
            if name:
                persona_name = name
            break
    seed = PERSONA_SEED_INPUTS.get(persona_number, {})
    pain = seed.get("pain", "Daily routine feels heavy and hard to sustain.")
    desire = seed.get("desire", "A practical routine that feels easy to follow.")
    friction = seed.get("friction", "Past plans felt too strict and difficult to maintain.")
    proof = seed.get("proof", "Needs clear structure and believable support.")
    tone = seed.get("tone", "practical and confidence-building")

    return {
        "persona_number": persona_number,
        "persona_name": persona_name,
        "pain_points": [pain],
        "trigger_scenarios": [],
        "objections": [friction],
        "language_bank": [],
        "core_message": [desire],
        "grounded_mechanism_map": [],
        "how_kit_solves": [],
        "trust_anchors": [proof],
        "english_ready": [f"Tone cue: {tone}"],
        "hindi_ready": ["टोन संकेत: सरल, भरोसेमंद, व्यावहारिक"],
    }


def read_active_images(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def default_image_sources_file() -> Path:
    if DEFAULT_IMAGE_SOURCES_FILE.exists():
        return DEFAULT_IMAGE_SOURCES_FILE
    return LEGACY_ACTIVE_IMAGES_FILE


def list_input_images() -> list[str]:
    if not INPUT_IMAGES_DIR.exists():
        return []
    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    items = [
        p for p in sorted(INPUT_IMAGES_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in allowed
    ]
    return [str(p.relative_to(ROOT)).replace("\\", "/") for p in items]


def store_uploaded_input_images(files: list[UploadFile], clear_existing: bool) -> list[str]:
    ensure_dirs()
    if clear_existing and INPUT_IMAGES_DIR.exists():
        for existing in INPUT_IMAGES_DIR.iterdir():
            if existing.is_file():
                existing.unlink(missing_ok=True)

    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    saved: list[str] = []
    for upload in files:
        filename = Path(upload.filename or "").name
        if not filename:
            continue
        ext = Path(filename).suffix.lower()
        if ext not in allowed:
            continue
        target = INPUT_IMAGES_DIR / filename
        counter = 1
        while target.exists():
            target = INPUT_IMAGES_DIR / f"{Path(filename).stem}_{counter}{ext}"
            counter += 1
        data = upload.file.read()
        target.write_bytes(data)
        saved.append(str(target.relative_to(ROOT)).replace("\\", "/"))
    return saved


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


def generated_image_roots() -> list[Path]:
    return [GENERATED_IMAGES_ROOT, LEGACY_GENERATED_IMAGE_ROOT]


def image_static_route_for_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("generated_images/"):
        return f"/generated_images/{normalized.removeprefix('generated_images/')}"
    if normalized.startswith("generated_image/"):
        return f"/generated_image/{normalized.removeprefix('generated_image/')}"
    return f"/generated_images/{normalized}"


def gemini_debugger_args() -> list[str]:
    address = resolve_gemini_debugger_address()
    return ["--attach-debugger-address", address]


def debugger_endpoint_reachable(address: str) -> bool:
    if not address:
        return False
    url = f"http://{address}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def resolve_gemini_debugger_address() -> str:
    configured = str(os.getenv("GEMINI_DEBUGGER_ADDRESS") or "").strip()
    candidates = [configured] if configured else []
    candidates.extend(["127.0.0.1:9222", "localhost:9222", "127.0.0.1:9223", "localhost:9223"])
    for candidate in candidates:
        if candidate and debugger_endpoint_reachable(candidate):
            return candidate
    # No reachable endpoint now: return preferred default so automation script
    # can auto-launch a debuggable Chrome session and continue.
    return configured or "127.0.0.1:9222"


def run_gemini_generation(
    *,
    batch: str,
    prompt_files: list[str],
    aspect_ratio: str,
    image_sources_file: str | None,
    prompt_reference_map: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    debugger_args = gemini_debugger_args()
    aspect_folder = "9_16" if aspect_ratio == "9:16" else "4_5"
    prompt_work_dir = RUNTIME_ROOT / "gemini_selected_prompts" / f"{batch}_{aspect_folder}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    prompt_work_dir.mkdir(parents=True, exist_ok=True)

    starting_prompt_path = ROOT / "input" / "startingprompt.txt"
    starting_prompt = starting_prompt_path.read_text(encoding="utf-8").strip() if starting_prompt_path.exists() else ""
    for prompt_file in prompt_files:
        source = Path(prompt_file)
        if not source.is_absolute():
            source = ROOT / source
        source = source.resolve()
        if not source.exists():
            raise RuntimeError(f"Prompt file not found: {source}")
        prompt_text = source.read_text(encoding="utf-8")
        combined = f"{starting_prompt}\n\n{prompt_text.strip()}\n" if starting_prompt else prompt_text
        (prompt_work_dir / source.name).write_text(combined, encoding="utf-8")

    out_dir = LEGACY_GENERATED_IMAGE_ROOT / batch / f"GEMINI_{aspect_folder}"
    image_source_arg = image_sources_file
    if prompt_reference_map is not None:
        try:
            reference_payload = json.loads(prompt_reference_map.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Could not read prompt reference map: {exc}") from exc
        flattened_sources: list[str] = []
        if isinstance(reference_payload, dict):
            for value in reference_payload.values():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.strip() and item.strip() not in flattened_sources:
                            flattened_sources.append(item.strip())
        if flattened_sources:
            source_file = prompt_work_dir / "image_sources.txt"
            source_file.write_text("\n".join(flattened_sources) + "\n", encoding="utf-8")
            image_source_arg = str(source_file)

    cmd = [
        sys.executable,
        "scripts/gemini_web_automation.py",
        "--prompt-dir",
        str(prompt_work_dir),
        "--prompt-glob",
        "*.txt",
        "--out-dir",
        str(out_dir),
        "--timeout",
        str(int(os.getenv("GEMINI_GENERATION_TIMEOUT_SECONDS") or "420")),
        "--manual-login-timeout",
        str(int(os.getenv("GEMINI_MANUAL_LOGIN_TIMEOUT_SECONDS") or "180")),
        "--browser",
        "chrome",
        "--upload-dir",
        str(INPUT_IMAGES_DIR),
        *debugger_args,
    ]
    if image_source_arg:
        cmd.extend(["--image-source-file", image_source_arg])
    return run_cmd(cmd, cwd=ROOT)


def build_multipart_form(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----dashboard{uuid.uuid4().hex}"
    lines: list[bytes] = []

    for key, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        lines.append(f"{value}\r\n".encode("utf-8"))

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    lines.append(f"--{boundary}\r\n".encode("utf-8"))
    lines.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
    )
    lines.append(file_path.read_bytes())
    lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))

    body = b"".join(lines)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def upload_image_to_cloudinary(image_path: Path, cloud_name: str, api_key: str, api_secret: str) -> str:
    if not image_path.exists() or not image_path.is_file():
        raise RuntimeError(f"Image not found for upload: {image_path}")

    timestamp = str(int(time.time()))
    signature_base = f"timestamp={timestamp}{api_secret}"
    signature = hashlib.sha1(signature_base.encode("utf-8")).hexdigest()

    fields = {
        "api_key": api_key,
        "timestamp": timestamp,
        "signature": signature,
    }
    body, content_type = build_multipart_form(fields, "file", image_path)
    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    req = urllib.request.Request(
        url=upload_url,
        data=body,
        method="POST",
        headers={"Content-Type": content_type},
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    secure_url = str(payload.get("secure_url") or "").strip()
    if not secure_url:
        raise RuntimeError(f"Cloudinary upload did not return secure_url: {payload}")
    return secure_url


def load_batch_image_summary(batch: str) -> list[dict[str, Any]]:
    summary_path = LEGACY_GENERATED_IMAGE_ROOT / batch / "batch_run_summary.json"
    if not summary_path.exists():
        jobs_by_prompt: dict[str, dict[str, Any]] = {}
        for generated_root in generated_image_roots():
            generated_batch_dir = generated_root / batch
            if not generated_batch_dir.exists():
                continue
            for meta_file in sorted(generated_batch_dir.glob("**/*.json")):
                try:
                    payload = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("record_type") or "").strip() != "generated_image":
                    continue

                prompt_file = str(payload.get("prompt_file_relative") or payload.get("prompt_file") or "").strip().replace("\\", "/")
                saved_file = str(payload.get("saved_file") or "").strip().replace("\\", "/")
                if not prompt_file or not saved_file:
                    continue

                existing = jobs_by_prompt.get(prompt_file)
                if not existing:
                    existing = {
                        "prompt_file": prompt_file,
                        "saved_files": [],
                        "format": payload.get("format"),
                        "language": payload.get("language"),
                        "variation": payload.get("variation"),
                        "task_id": payload.get("task_id"),
                        "prompt_metadata": payload.get("prompt_metadata") or {},
                    }
                    jobs_by_prompt[prompt_file] = existing
                saved_files = existing.get("saved_files")
                if not isinstance(saved_files, list):
                    saved_files = []
                    existing["saved_files"] = saved_files
                if saved_file not in saved_files:
                    saved_files.append(saved_file)

        return list(jobs_by_prompt.values())
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    jobs = summary.get("jobs")
    if isinstance(jobs, list):
        return [job for job in jobs if isinstance(job, dict)]
    return []


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)


def opencode_discovery_env() -> dict[str, str]:
    env = os.environ.copy()
    default_xdg = Path.home() / ".local" / "share"
    default_auth = default_xdg / "opencode" / "auth.json"

    raw_xdg = env.get("XDG_DATA_HOME", "").strip()
    current_xdg = Path(raw_xdg).expanduser() if raw_xdg else default_xdg
    current_auth = current_xdg / "opencode" / "auth.json"

    if default_auth.exists() and not current_auth.exists():
        env["XDG_DATA_HOME"] = str(default_xdg)
    return env


def run_opencode_discovery_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, check=False, env=opencode_discovery_env())


def list_opencode_models() -> list[str]:
    result = run_opencode_discovery_cmd(["opencode", "models"])
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in strip_ansi(result.stdout).splitlines()]
    return [line for line in lines if line and "/" in line]


def list_opencode_provider_labels() -> list[str]:
    result = run_opencode_discovery_cmd(["opencode", "providers", "list"])
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in strip_ansi(result.stdout).splitlines()]
    labels: list[str] = []
    for line in lines:
        match = re.search(r"[●•]\s+(.+?)\s+(oauth|api|token|key)\b", line, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
        else:
            fallback = re.search(r"^[│\s]*[●•]\s+(.+)$", line)
            if not fallback:
                continue
            value = re.sub(r"\s+(oauth|api|token|key)\b.*$", "", fallback.group(1), flags=re.IGNORECASE).strip()
        if value:
            labels.append(value)
    return labels


def provider_id_from_label(label: str) -> str:
    known = {
        "github copilot": "github-copilot",
        "github-copilot": "github-copilot",
        "opencode": "opencode",
    }
    key = label.strip().lower()
    if key in known:
        return known[key]
    return re.sub(r"[^a-z0-9]+", "-", key).strip("-")


def list_models_for_provider(provider: str) -> list[str]:
    result = run_opencode_discovery_cmd(["opencode", "models", provider])
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in strip_ansi(result.stdout).splitlines()]
    return [line for line in lines if line and line.startswith(provider + "/")]


def choose_openai_gpt52(models: list[str]) -> str:
    preferred = "openai/gpt-5.2"
    if preferred in models:
        return preferred
    for model in models:
        lower = model.lower()
        if lower.startswith("openai/") and "gpt-5.2" in lower:
            return model
    for model in models:
        if model.lower().startswith("openai/"):
            return model
    non_copilot = [m for m in models if not m.lower().startswith("github-copilot/")]
    if non_copilot:
        return non_copilot[0]
    return preferred


def sanitize_dashboard_model(selected: str, models: list[str]) -> str:
    chosen = (selected or "").strip()
    if chosen and not chosen.lower().startswith("github-copilot/"):
        return chosen
    return choose_openai_gpt52(models)


def build_opencode_catalog() -> dict[str, Any]:
    models = list_opencode_models()
    provider_labels = list_opencode_provider_labels()
    provider_ids = {line.split("/", 1)[0] for line in models}

    known_providers = ["opencode", "openai"]
    for provider in known_providers:
        provider_ids.add(provider)
    for label in provider_labels:
        pid = provider_id_from_label(label)
        if pid:
            provider_ids.add(pid)

    for provider in sorted(provider_ids):
        if any(model.startswith(provider + "/") for model in models):
            continue
        models.extend(list_models_for_provider(provider))

    providers = sorted(provider for provider in provider_ids if provider.lower() != "github-copilot")
    grouped: dict[str, list[str]] = {provider: [] for provider in providers}
    for model in models:
        provider = model.split("/", 1)[0]
        if provider.lower() == "github-copilot":
            continue
        grouped.setdefault(provider, []).append(model)
    for provider in grouped:
        grouped[provider] = sorted(grouped[provider])
    default_model = ""
    if models:
        default_model = choose_openai_gpt52(models)
    return {
        "api_url": DEFAULT_OPENCODE_API_URL,
        "providers": providers,
        "provider_labels": provider_labels,
        "models_by_provider": grouped,
        "default_model": default_model,
    }


def choose_extractor_model(config: dict[str, Any]) -> str:
    models = list_opencode_models()
    explicit = (config.get("opencode_extractor_model") or "").strip()
    if explicit:
        return sanitize_dashboard_model(explicit, models)

    selected = (config.get("opencode_model") or "").strip()
    if selected:
        return sanitize_dashboard_model(selected, models)
    return choose_openai_gpt52(models)


def parse_json_stdout(result: subprocess.CompletedProcess[str], context: str) -> Any:
    if result.returncode != 0:
        raise RuntimeError(f"{context} failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} returned invalid JSON") from exc


def save_upload(target: Path, upload: UploadFile | None) -> Path | None:
    if upload is None or not upload.filename:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    data = upload.file.read()
    target.write_bytes(data)
    return target


def coalesce_path(uploaded: Path | None, default_path: Path) -> Path:
    return uploaded if uploaded and uploaded.exists() else default_path


def resolve_safe_path(relative_path: str) -> Path:
    candidate = (ROOT / relative_path).resolve()
    if str(candidate).startswith(str(ROOT.resolve())):
        return candidate
    raise HTTPException(status_code=400, detail="Invalid path")


def choose_text(items: list[str], fallback: str) -> str:
    for item in items:
        clean = item.strip()
        if clean:
            return clean
    return fallback


def shorten_copy_line(text: str, limit: int = 92) -> str:
    _ = limit
    return " ".join((text or "").split()).strip()


def strip_internal_marker(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r"\s*\b\d{4}-\d{2}-(hero|ba|test|feat|ugc)\.?\b", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\(\s*\d+[_-]\d+\s*\)", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def strip_price_tokens(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text
    cleaned = re.sub(r"\bINR\b\s*\d+[\d,]*(?:\.\d+)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[₹$]\s*\d+[\d,]*(?:\.\d+)?", "", cleaned)
    cleaned = re.sub(r"\b\d+[\d,]*(?:\.\d+)?\s*(?:INR|Rs\.?|rupees?)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:price|only|discount|off|mrp)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;:-")
    return cleaned


def strip_ba_panel_label(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*(?:before|after)\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*(?:पहले|बाद|पहले\s*में|बाद\s*में)\s*[:\-]\s*", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def strip_internal_markers_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ads = payload.get("ads")
    if not isinstance(ads, list):
        return payload

    for ad in ads:
        if not isinstance(ad, dict):
            continue
        copy = ad.get("copy")
        if not isinstance(copy, dict):
            continue
        for lang in ["EN", "HI"]:
            block = copy.get(lang)
            if not isinstance(block, dict):
                continue
            for key in ["headline", "support_line", "cta", "trust_line", "attribution"]:
                if key in block and isinstance(block.get(key), str):
                    value = strip_internal_marker(block[key])
                    block[key] = strip_price_tokens(value)
            if isinstance(block.get("bullets"), list):
                cleaned_bullets = []
                for item in block["bullets"]:
                    if not isinstance(item, str):
                        continue
                    value = strip_price_tokens(strip_internal_marker(item))
                    if value:
                        cleaned_bullets.append(value)
                block["bullets"] = cleaned_bullets
    return payload


def parse_uniqueness_collisions(error_text: str) -> list[dict[str, Any]]:
    collisions: list[dict[str, Any]] = []
    for raw_line in error_text.splitlines():
        line = raw_line.strip()
        match = re.search(r"ads\[(\d+)\]\.copy\.(EN|HI)\.([a-z_]+)", line)
        if not match:
            continue
        collisions.append(
            {
                "ad_index": int(match.group(1)),
                "language": match.group(2),
                "field": match.group(3),
                "line": line,
            }
        )
    return collisions


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
        start = match.start()
        try:
            parsed, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        span = end
        if span > best_span:
            best = parsed
            best_span = span
    return best


def parse_opencode_json_output(stdout: str) -> dict[str, Any] | None:
    text_chunks: list[str] = []
    for raw_line in (stdout or "").splitlines():
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
            text_chunks.append(text.strip())

    if text_chunks:
        parsed = parse_json_object_from_text("\n".join(text_chunks).strip())
        if parsed is not None:
            return parsed

    return parse_json_object_from_text((stdout or "").strip())


def call_opencode_repair_copy(
    config: dict[str, Any],
    context: dict[str, Any],
    current_copy: dict[str, Any],
    collisions: list[dict[str, Any]],
    run_dir: Path,
) -> dict[str, Any] | None:
    api_url = (config.get("opencode_api_url") or "").strip()
    model = sanitize_dashboard_model((config.get("opencode_model") or "").strip(), list_opencode_models())
    if not api_url:
        return None

    payload = {
        "task": "Repair uniqueness collisions only",
        "rules": [
            "Return valid JSON only",
            "Keep existing structure and fields",
            "Only change collided fields",
            "Do not use generic repeated support lines",
            "Do not add internal tags or IDs",
        ],
        "collisions": collisions,
        "current_copy": current_copy,
        "context": build_generation_payload_for_llm(context),
    }
    prompt = (
        "You are fixing ad copy JSON after uniqueness collisions. "
        "Return only corrected JSON object with keys default_aspect_ratio and ads.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    password = (config.get("opencode_api_key") or "").strip() or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    cmd = [
        "opencode",
        "run",
        "--pure",
        "--attach",
        api_url,
        "--model",
        model,
        "--format",
        "json",
        prompt,
    ]
    if password:
        cmd.extend(["--password", password])
    try:
        result = run_cmd(cmd, cwd=ROOT)
    except OSError as exc:
        (run_dir / "logs" / "opencode_repair_error.txt").write_text(
            f"Repair command launch failed: {exc}", encoding="utf-8"
        )
        return None
    if result.returncode != 0:
        (run_dir / "logs" / "opencode_repair_error.txt").write_text(
            f"Repair command failed\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}", encoding="utf-8"
        )
        return None

    return parse_opencode_json_output(result.stdout)


def _clean_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clean_bullets(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def ensure_testimonial_headline(headline: str, lang: str, persona: dict[str, Any]) -> str:
    clean = shorten_copy_line(headline, limit=90)
    if lang == "EN":
        if re.search(r"\b(i|i'm|i’ve|i'd|my|me)\b", clean, flags=re.IGNORECASE):
            if re.search(r"\b(weight|obesity|excess\s*weight|kg|kilo)\b", clean, flags=re.IGNORECASE):
                return clean
            return shorten_copy_line(f'{clean.rstrip(".")}. It finally fit my weight-loss routine.', limit=90)
        desire = _clean_str(persona.get("desire_en")).rstrip(".")
        if desire:
            desire_phrase = desire[:1].lower() + desire[1:] if len(desire) > 1 else desire.lower()
            return shorten_copy_line(f'"I finally found {desire_phrase} for my weight-loss goal."', limit=90)
        return '"I finally found a routine I can follow for weight loss every day."'

    if re.search(r"(मैं|मेरी|मेरा|मुझे|मैंने)", clean):
        if re.search(r"(वजन|मोटापा|किलो|kg)", clean):
            return clean
        return shorten_copy_line(f'{clean.rstrip("।")}। यह मेरे वजन घटाने के लिए काम आया।', limit=90)
    desire_hi = _clean_str(persona.get("desire_hi")).rstrip("।")
    if desire_hi:
        return shorten_copy_line(f'"मुझे आखिर {desire_hi} वाला रूटीन मिला जो वजन घटाने में मदद करता है।"', limit=90)
    return '"मुझे आखिर ऐसा रूटीन मिला जिसे मैं रोज निभा सकूं और वजन घटा सकूं।"'


def ensure_testimonial_attribution(attribution: str, lang: str, persona: dict[str, Any], headline: str, trust_line: str) -> str:
    if lang == "EN":
        variants = [
            "Verified routine user feedback",
            "15-day adherence feedback snapshot",
            "Community obesity-care review",
            "Early weight-loss routine review",
            "Structured-plan user feedback",
            "Repeat-user experience note",
        ]
    else:
        variants = [
            "रूटीन-फॉलो यूजर फीडबैक",
            "15-दिन adherence फीडबैक स्नैपशॉट",
            "कम्युनिटी obesity-care रिव्यू",
            "शुरुआती वजन-घटाने रूटीन रिव्यू",
            "स्ट्रक्चर्ड-प्लान यूजर फीडबैक",
            "रीपीट-यूजर अनुभव नोट",
        ]

    current = _clean_str(attribution)
    seed_input = (
        f"{persona.get('number', '')}|{persona.get('name', '')}|{headline}|{trust_line}|{persona.get('pain_en', '')}|{persona.get('pain_hi', '')}"
    )
    digest = hashlib.sha1(seed_input.encode("utf-8", errors="ignore")).hexdigest()
    idx = int(digest[:8], 16) % len(variants)
    chosen = variants[idx]

    if not current:
        return chosen

    # For TEST attribution we avoid personal names and generic repeated labels.
    if re.search(r"\brepresentative\s+user\s+review\b", current, flags=re.IGNORECASE):
        return chosen
    if re.search(r"\b(user|customer)\s+review\b", current, flags=re.IGNORECASE):
        return chosen
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", current):
        return chosen
    if re.search(r"[\u0900-\u097F]{2,}\s+[\u0900-\u097F]{2,}", current):
        return chosen
    return shorten_copy_line(current, limit=86)


def _persona_number_from_candidate(candidate: dict[str, Any]) -> int | None:
    persona = candidate.get("persona") if isinstance(candidate, dict) else None
    if not isinstance(persona, dict):
        return None
    val = persona.get("number")
    if isinstance(val, int):
        return val
    val = persona.get("persona_number")
    if isinstance(val, int):
        return val
    if isinstance(val, str) and val.strip().isdigit():
        return int(val.strip())
    return None


def _persona_name_from_candidate(candidate: dict[str, Any]) -> str:
    persona = candidate.get("persona") if isinstance(candidate, dict) else None
    if not isinstance(persona, dict):
        return ""
    return _clean_str(persona.get("name") or persona.get("persona_name") or "")


def normalize_generated_copy(
    generated: dict[str, Any] | None,
    context: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    base = build_template_copy(context, run_id)
    ads_generated = generated.get("ads") if isinstance(generated, dict) else None
    candidates = ads_generated if isinstance(ads_generated, list) else []
    used_indices: set[int] = set()

    def pick_candidate(fmt: str, persona_num: int, persona_name: str) -> dict[str, Any] | None:
        for idx, cand in enumerate(candidates):
            if idx in used_indices or not isinstance(cand, dict):
                continue
            cand_fmt = _clean_str(cand.get("format")).upper()
            if cand_fmt != fmt:
                continue
            cand_num = _persona_number_from_candidate(cand)
            cand_name = _persona_name_from_candidate(cand)
            if cand_num == persona_num or (cand_name and cand_name.lower() == persona_name.lower()):
                used_indices.add(idx)
                return cand

        for idx, cand in enumerate(candidates):
            if idx in used_indices or not isinstance(cand, dict):
                continue
            cand_fmt = _clean_str(cand.get("format")).upper()
            if cand_fmt == fmt:
                used_indices.add(idx)
                return cand
        return None

    for ad in base.get("ads", []):
        fmt = _clean_str(ad.get("format")).upper()
        persona = ad.get("persona") or {}
        persona_num = int(persona.get("number"))
        persona_name = _clean_str(persona.get("name"))
        candidate = pick_candidate(fmt, persona_num, persona_name)
        if not candidate:
            continue

        angle = _clean_str(candidate.get("headline_angle"))
        if angle:
            ad["headline_angle"] = angle

        cand_copy = candidate.get("copy") if isinstance(candidate.get("copy"), dict) else {}
        for lang in ["EN", "HI"]:
            base_lang = ad["copy"][lang]
            src_lang = cand_copy.get(lang) if isinstance(cand_copy.get(lang), dict) else {}

            headline = _clean_str(src_lang.get("headline"))
            cta = _clean_str(src_lang.get("cta"))
            if headline:
                base_lang["headline"] = shorten_copy_line(headline, limit=90)
            if cta:
                base_lang["cta"] = cta

            if fmt == "TEST":
                base_lang["headline"] = ensure_testimonial_headline(base_lang.get("headline", ""), lang, persona)
                base_lang["attribution"] = ensure_testimonial_attribution(
                    _clean_str(src_lang.get("attribution")),
                    lang,
                    persona,
                    base_lang.get("headline", ""),
                    _clean_str(src_lang.get("trust_line")) or base_lang.get("trust_line", ""),
                )

            if fmt in {"HERO", "UGC"}:
                support = _clean_str(src_lang.get("support_line"))
                if support:
                    base_lang["support_line"] = shorten_copy_line(support)
            elif fmt in {"BA", "FEAT"}:
                bullets = _clean_bullets(src_lang.get("bullets"))
                if len(bullets) >= 2:
                    if fmt == "BA":
                        bullets = [strip_ba_panel_label(b) for b in bullets]
                    base_lang["bullets"] = [shorten_copy_line(b, limit=88) for b in bullets]
            else:
                trust = _clean_str(src_lang.get("trust_line"))
                if trust:
                    base_lang["trust_line"] = shorten_copy_line(trust)

    return base


def build_template_copy(context: dict[str, Any], run_id: str) -> dict[str, Any]:
    ads: list[dict[str, Any]] = []
    token = run_id[-4:]
    for idx, item in enumerate(context["ads"], start=1):
        persona = item["persona"]
        fmt = item["format"]
        persona_num = int(persona["persona_number"])
        persona_name = persona["persona_name"]
        unique = f"{token}-{idx:02d}-{fmt.lower()}"

        pain_en = choose_text(persona.get("pain_points", []), f"Daily routine feels heavy and hard to sustain for persona {persona_num}.")
        desire_en = choose_text(persona.get("core_message", []), "A practical routine that feels easy to follow.")
        friction_en = choose_text(persona.get("objections", []), "Past plans felt too strict and difficult to maintain.")
        proof_en = choose_text(persona.get("trust_anchors", []), "Needs proof through clear structure and believable support.")
        tone_en = "Practical, empathetic, and confidence-building"

        pain_hi = choose_text(persona.get("hindi_ready", []), "रूटीन निभाना मुश्किल लग रहा है।")
        desire_hi = "ऐसा आसान सिस्टम जो रोज निभ सके।"
        friction_hi = "पहले के प्लान बहुत सख्त और मुश्किल थे।"
        proof_hi = "साफ तरीका, भरोसेमंद सपोर्ट और व्यावहारिक प्रूफ चाहिए।"
        tone_hi = "सरल, भरोसेमंद, और व्यावहारिक"

        if fmt == "BA":
            headline_en = f"From \"nothing works\" to visible 15-day weight-loss progress {unique}."
            headline_hi = f"\"कुछ काम नहीं करता\" से 15 दिन में दिखने वाली वजन घटाने की प्रगति तक {unique}।"
        else:
            headline_en = f"{persona_name}: start your 15-day obesity and weight-loss routine {unique}."
            headline_hi = f"{persona_name}: आज से 15-दिन का obesity और वजन घटाने का रूटीन शुरू करें {unique}।"
        cta_en = f"Start Now {unique}"
        cta_hi = f"अभी शुरू करें {unique}"

        copy_en: dict[str, Any]
        copy_hi: dict[str, Any]
        if fmt in {"HERO", "UGC"}:
            support_en = f"Helps reduce cravings and supports digestion so excess-weight reduction feels practical {unique}."
            support_hi = f"यह cravings कम करने और पाचन सपोर्ट से अतिरिक्त वजन घटाने को व्यावहारिक बनाता है {unique}।"
            copy_en = {"headline": headline_en, "support_line": support_en, "cta": cta_en}
            copy_hi = {"headline": headline_hi, "support_line": support_hi, "cta": cta_hi}
        elif fmt == "BA":
            bullets_en = [
                f"Evening cravings and unplanned snacking keep weight-loss efforts stuck {unique}.",
                f"Mornings start heavy, so the obesity routine feels hard to repeat {unique}.",
                f"Morning-liquid + night-support structure gives better appetite control for weight loss {unique}.",
                f"Day-by-day consistency builds visible 15-day obesity-management momentum {unique}.",
            ]
            bullets_hi = [
                f"शाम की cravings और बिना प्लान स्नैकिंग से वजन घटाने की कोशिश अटक जाती है {unique}।",
                f"सुबह भारी लगती है, इसलिए obesity रूटीन दोहराना मुश्किल होता है {unique}।",
                f"सुबह-liquid और रात-support की संरचना से वजन घटाने के लिए appetite control बेहतर होता है {unique}।",
                f"रोज की consistency से 15 दिन में obesity management की दिखने वाली momentum बनती है {unique}।",
            ]
            copy_en = {"headline": headline_en, "bullets": bullets_en, "cta": cta_en}
            copy_hi = {"headline": headline_hi, "bullets": bullets_hi, "cta": cta_hi}
        elif fmt == "FEAT":
            bullets_en = [
                f"Morning OK Liquid helps reduce hunger and random snacking for weight loss {unique}.",
                f"Night Tablet + Powder support digestion and lighter mornings in obesity routine {unique}.",
                f"Built for visible 15-day weight-loss support without crash-diet pressure {unique}.",
            ]
            bullets_hi = [
                f"सुबह का OK Liquid वजन घटाने के लिए भूख और स्नैकिंग कम करने में सहायक है {unique}।",
                f"रात का Tablet + Powder obesity रूटीन में पाचन और हल्की सुबह के लिए सपोर्ट देता है {unique}।",
                f"crash diet दबाव के बिना 15 दिन की visible weight-loss support के लिए बनाया गया {unique}।",
            ]
            copy_en = {"headline": headline_en, "bullets": bullets_en, "cta": cta_en}
            copy_hi = {"headline": headline_hi, "bullets": bullets_hi, "cta": cta_hi}
        else:
            copy_en = {
                "headline": headline_en,
                "attribution": "Doctor-formulated Ayurvedic obesity and weight-loss protocol",
                "trust_line": f"Structured morning-night steps for visible weight-loss progress and obesity control {unique}.",
                "cta": cta_en,
            }
            copy_hi = {
                "headline": headline_hi,
                "attribution": "डॉक्टर-फॉर्मुलेटेड आयुर्वेदिक obesity और weight-loss प्रोटोकॉल",
                "trust_line": f"सुबह-रात के स्पष्ट स्टेप्स से visible वजन घटाने और obesity नियंत्रण का भरोसेमंद सपोर्ट {unique}।",
                "cta": cta_hi,
            }

        ads.append(
            {
                "format": fmt,
                "headline_angle": "mechanism",
                "persona": {
                    "number": persona_num,
                    "name": persona_name,
                    "pain_en": pain_en,
                    "desire_en": desire_en,
                    "friction_en": friction_en,
                    "proof_needed_en": proof_en,
                    "tone_cue_en": tone_en,
                    "pain_hi": pain_hi,
                    "desire_hi": desire_hi,
                    "friction_hi": friction_hi,
                    "proof_needed_hi": proof_hi,
                    "tone_cue_hi": tone_hi,
                },
                "copy": {"EN": copy_en, "HI": copy_hi},
            }
        )

    return {"default_aspect_ratio": "4:5", "ads": ads}


def call_opencode_compatible(config: dict[str, Any], context: dict[str, Any], run_dir: Path) -> dict[str, Any] | None:
    api_url = (config.get("opencode_api_url") or "").strip()
    api_key = (config.get("opencode_api_key") or "").strip() or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    model = sanitize_dashboard_model((config.get("opencode_model") or "").strip(), list_opencode_models())
    if not api_url:
        return None

    language_mode = resolve_language_mode(config)
    system = (
        "You generate ad copy JSON only. Return valid JSON with keys default_aspect_ratio and ads. "
        "Each ads item must include format, headline_angle, persona fields and copy.EN/copy.HI fields compatible with assembler. "
        "Every ad unit must make the obesity and weight-loss intent obvious to a first-time viewer. "
        "At minimum, headline or support line must explicitly mention weight loss, obesity reduction, excess-weight reduction, or a direct 15-day result framing. "
        "Avoid abstract lines that hide the product goal. "
        "Never include price in any on-image copy field (headline/support_line/trust_line/bullets/cta/attribution). "
        "Do not use currency symbols or words like INR, price, only, discount, off, MRP in on-image copy. "
        "For BA format, never prefix copy with BEFORE:/AFTER: labels (or Hindi equivalents). "
        "For BA format, write explicit split contrast copy: bullet 1/2 = left-side struggle state, bullet 3/4 = right-side fix/progress state. "
        "Use 2 or 4 BA bullets total (if 2, bullet 1 = struggle and bullet 2 = fix). "
        "For TEST format, headline must read like a first-person review line suitable for quote card (not generic 'highly rated' phrasing). "
        "For TEST format, attribution must be role/source-based without personal names; avoid repeating generic text like 'Representative user review' across ads. "
        "If no real quote is provided in context, create one believable representative review line grounded in persona pain/desire and safe claims. "
        "Keep each format's core shape intact, but vary headline/support/trust framing using persona pain, desire, friction, proof needed, and tone cue. "
        "For the same format across runs, rotate variation lane and wording rhythm while preserving format-specific structure. "
        "Each ad item includes copy_requirements; treat primary_feature/headline_driver as the headline lane and secondary_feature/support_driver as the supporting lane. "
        "Within the same format in a single batch, do not reuse the same headline skeleton or subheadline skeleton across personas. "
        "Follow the master-doc benefit hierarchy first: fast visible results, cravings down, natural safe-feeling, homemade-food fit, structured low-guesswork system, guided support, emotional control, then secondary digestive benefits. "
        "Use AM routine or PM routine only when the chosen feature lane genuinely needs mechanism detail. Do not default to AM/PM wording in every ad. "
        "Do not flatten multiple ads under a format into near-duplicate headlines with only minor wording swaps. "
        "For FEAT, make each bullet a different product feature. For HERO and UGC, support line must add a second feature instead of restating the headline. "
        "Do not make homemade-food compatibility the center of brand positioning even when you use it as a benefit lane. "
        "Do not let secondary digestive or emotional benefits overshadow the main promise of fast visible weight loss with a safer, easier, more guided experience. "
        "Ensure obesity and weight-loss intent is obvious to someone who has never heard of the product."
    )
    cli_password = api_key or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    generated_ads: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, ad_item in enumerate(context.get("ads") or [], start=1):
        previous_same_format: list[dict[str, Any]] = []
        target_format = str(ad_item.get("format") or "").strip().upper()
        for prev in generated_ads:
            if not isinstance(prev, dict):
                continue
            if str(prev.get("format") or "").strip().upper() != target_format:
                continue
            prev_copy = prev.get("copy") if isinstance(prev.get("copy"), dict) else {}
            prev_en = prev_copy.get("EN") if isinstance(prev_copy.get("EN"), dict) else {}
            previous_same_format.append(
                {
                    "persona": (prev.get("persona") or {}).get("name") if isinstance(prev.get("persona"), dict) else "",
                    "headline_angle": prev.get("headline_angle"),
                    "headline": prev_en.get("headline"),
                    "support_line": prev_en.get("support_line"),
                    "bullets": prev_en.get("bullets") if isinstance(prev_en.get("bullets"), list) else [],
                }
            )
        single_context = {
            **context,
            "ads": [ad_item],
        }
        user_payload = {
            "task": "Generate fresh ad copy JSON for provided context.",
            "context": build_generation_payload_for_llm(single_context),
            "generated_same_format_so_far": previous_same_format,
            "constraints": {
                "language": ["EN", "HI"],
                "language_mode": language_mode,
                "formats": FORMATS,
                "return_json_only": True,
            },
        }
        cli_prompt = (
            "SYSTEM:\n"
            f"{system}\n\n"
            "USER_PAYLOAD_JSON:\n"
            f"{json.dumps(user_payload, ensure_ascii=False)}\n\n"
            "Return only valid JSON. No markdown. No extra text.\n"
            "Return one ad only. You may return either a single ad object or an object with default_aspect_ratio and a one-item ads array.\n"
            "The current ad must use a new persuasion angle in both the headline and the support line / right-side shift / feature stack compared with generated_same_format_so_far.\n"
            "Do not reuse the same angle family such as guided support, structured system, cravings control, proof, natural-safe, homemade-food fit, or AM/PM mechanism as the lead angle if it already appeared in generated_same_format_so_far for this format.\n"
            "Do not reuse the same sentence pattern or opening structure from generated_same_format_so_far.\n"
            "Do not return example text. Do not return explanations."
        )
        cli_cmd = [
            "opencode",
            "run",
            "--pure",
            "--attach",
            api_url,
            "--model",
            model,
            "--format",
            "json",
            cli_prompt,
        ]
        if cli_password:
            cli_cmd.extend(["--password", cli_password])
        try:
            cli_result = run_cmd(cli_cmd, cwd=ROOT)
        except OSError as exc:
            errors.append(f"Ad {index}: launch failed: {exc}")
            continue

        if cli_result.returncode != 0:
            errors.append(
                f"Ad {index}: return code {cli_result.returncode}\nSTDOUT:\n{cli_result.stdout}\nSTDERR:\n{cli_result.stderr}"
            )
            continue

        parsed = parse_opencode_json_output(cli_result.stdout)
        candidate = extract_generated_ad_candidate(parsed) if parsed else None
        if not candidate:
            errors.append(f"Ad {index}: returned no usable ad JSON\nSTDOUT:\n{cli_result.stdout}\nSTDERR:\n{cli_result.stderr}")
            continue
        generated_ads.append(hydrate_generated_ad_candidate(candidate, ad_item))

    if errors:
        (run_dir / "logs" / "opencode_error.txt").write_text("\n\n---\n\n".join(errors), encoding="utf-8")
        return None

    return {"default_aspect_ratio": "4:5", "ads": generated_ads}


def collect_run_result(run_dir: Path, batch_name: str, image_generated: bool) -> dict[str, Any]:
    output_dir = ROOT / "output" / batch_name
    prompt_files = []
    if output_dir.exists():
        for file in sorted(output_dir.glob("**/OUTPUT_*.txt")):
            prompt_files.append(str(file.relative_to(ROOT)))

    image_files: list[str] = []
    if image_generated:
        for generated_root in generated_image_roots():
            image_dir = generated_root / batch_name
            if image_dir.exists():
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                    for file in sorted(image_dir.glob(f"**/{ext}")):
                        image_files.append(str(file.relative_to(ROOT)))

    result = {
        "run_id": run_dir.name,
        "batch": batch_name,
        "prompt_files": prompt_files,
        "image_files": image_files,
        "image_generated": image_generated,
        "updated_at": now_iso(),
    }
    (run_dir / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def scan_prompt_files_for_batch(batch_name: str) -> list[str]:
    output_dir = ROOT / "output" / batch_name
    prompt_files: list[str] = []
    if not output_dir.exists():
        return prompt_files
    for file in sorted(output_dir.glob("**/OUTPUT_*.txt")):
        prompt_files.append(str(file.relative_to(ROOT)))
    return prompt_files


def scan_image_files_for_batch(batch_name: str) -> list[str]:
    image_files: list[str] = []
    for generated_root in generated_image_roots():
        image_dir = generated_root / batch_name
        if not image_dir.exists():
            continue
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            for file in sorted(image_dir.glob(f"**/{ext}")):
                image_files.append(str(file.relative_to(ROOT)))
    return image_files


def refresh_manifest_file_state(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    batch_name = str(manifest.get("batch") or "").strip()
    if not batch_name:
        return manifest

    prompt_files = scan_prompt_files_for_batch(batch_name)
    image_files = scan_image_files_for_batch(batch_name)
    refreshed = {
        "run_id": run_dir.name,
        "batch": batch_name,
        "prompt_files": prompt_files,
        "image_files": image_files,
        "image_generated": bool(image_files) or bool(manifest.get("image_generated", False)),
        "updated_at": now_iso(),
    }
    merged = {**manifest, **refreshed}
    (run_dir / "manifest.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return merged


def force_aspect_ratio(copy_json: dict[str, Any], aspect_ratio: str) -> dict[str, Any]:
    cloned = json.loads(json.dumps(copy_json, ensure_ascii=False))
    cloned["default_aspect_ratio"] = aspect_ratio
    ads = cloned.get("ads")
    if isinstance(ads, list):
        for ad in ads:
            if isinstance(ad, dict):
                ad["aspect_ratio"] = aspect_ratio
    return cloned


def _parse_prompt_field(prompt_text: str, label: str) -> str:
    match = re.search(rf"^\s*-\s*{re.escape(label)}:\s*(.+)$", prompt_text, flags=re.MULTILINE)
    return (match.group(1).strip() if match else "")


def parse_background_lock_from_prompt(prompt_text: str) -> tuple[str, int] | None:
    slot_match = re.search(r"^\s*-\s*Background\s+slot:\s*(BG-\d{3})\b", prompt_text, flags=re.MULTILINE | re.IGNORECASE)
    seed_match = re.search(r"^\s*-\s*Background\s+seed:\s*(\d+)\s*$", prompt_text, flags=re.MULTILINE | re.IGNORECASE)
    if not slot_match or not seed_match:
        return None
    return (slot_match.group(1).upper(), int(seed_match.group(1)))


def parse_prompt_filename(prompt_path: str) -> tuple[str, str, int | None] | None:
    name = Path(prompt_path).name
    match = re.match(r"^OUTPUT_([A-Z]+)(?:_P(\d+))?_(EN|HI)(?:_V\d+)?\.txt$", name)
    if not match:
        return None
    persona_raw = match.group(2)
    persona_number = int(persona_raw) if persona_raw else None
    return (match.group(1), match.group(3), persona_number)


def parse_persona_number_from_prompt(prompt_text: str) -> int | None:
    match = re.search(r"\(\s*Persona\s*(\d+)\s*\)", prompt_text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def extract_on_image_copy_lines(prompt_text: str) -> list[dict[str, str]]:
    block = re.search(
        r"EXACT ON-IMAGE COPY - DO NOT ALTER ANYTHING\s*\n(.+?)\n\s*Render every character exactly as written",
        prompt_text,
        flags=re.DOTALL,
    )
    if not block:
        return []

    out: list[dict[str, str]] = []
    for line in block.group(1).splitlines():
        raw = line.strip()
        if not raw:
            continue
        parsed = re.match(r"^-\s*([^:]+):\s*(.*)$", raw)
        if not parsed:
            continue
        out.append({"label": parsed.group(1).strip(), "value": parsed.group(2).strip()})
    return out


def load_run_language_mode(run_dir: Path) -> str:
    run_context_path = run_dir / "context" / "run_context.json"
    assembler_mode = "BOTH"
    if not run_context_path.exists():
        return assembler_mode
    try:
        run_context = json.loads(run_context_path.read_text(encoding="utf-8"))
        lang_mode = str(run_context.get("language_mode") or "ALL").upper()
        if lang_mode == "EN":
            return "EN"
        if lang_mode == "HI":
            return "HI"
    except Exception:
        return assembler_mode
    return assembler_mode


def rerender_prompts_for_run(run_dir: Path, batch: str, copy_file: Path, language_mode: str) -> None:
    result = run_cmd(
        [
            "python3",
            "scripts/generate_ads.py",
            "--copy-file",
            str(copy_file),
            "--batch",
            batch,
            "--language-mode",
            language_mode,
            "--no-registry-write",
            "--skip-uniqueness-check",
        ],
        cwd=ROOT,
    )
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "assembler_edit_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"Prompt regeneration failed: {short_error}")


def merge_manifest(run_dir: Path, previous_manifest: dict[str, Any], refreshed: dict[str, Any]) -> dict[str, Any]:
    merged = {**previous_manifest, **refreshed}
    (run_dir / "manifest.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return merged


def generate_916_for_run(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    copy_path = run_dir / "context" / "copy_batch.json"
    if not copy_path.exists():
        raise HTTPException(status_code=404, detail="copy_batch.json not found for run")

    batch = (manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    copy_json = json.loads(copy_path.read_text(encoding="utf-8"))
    copy_916 = force_aspect_ratio(copy_json, "9:16")
    visual_locks = collect_45_visual_locks(batch)
    if visual_locks:
        copy_916 = apply_visual_locks(copy_916, visual_locks)
    copy_916_path = run_dir / "context" / "copy_batch_916.json"
    copy_916_path.write_text(json.dumps(copy_916, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    assembler_mode = load_run_language_mode(run_dir)
    result = run_cmd(
        [
            "python3",
            "scripts/generate_ads.py",
            "--copy-file",
            str(copy_916_path),
            "--batch",
            batch,
            "--language-mode",
            assembler_mode,
            "--no-registry-write",
            "--skip-uniqueness-check",
        ],
        cwd=ROOT,
    )

    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "assembler_916_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"9:16 generation failed: {short_error}")

    refreshed = collect_run_result(run_dir, batch, bool(manifest.get("image_generated", False)))
    refreshed["generated_variant"] = "9:16"
    return merge_manifest(run_dir, manifest, refreshed)


def collect_45_visual_locks(batch: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    ratio_dir = ROOT / "output" / batch / "45"
    if not ratio_dir.exists():
        return out
    for prompt_file in sorted(ratio_dir.glob("OUTPUT_*_EN.txt")) + sorted(ratio_dir.glob("OUTPUT_*_HI.txt")):
        parsed = parse_prompt_filename(prompt_file.name)
        if not parsed:
            continue
        fmt, _lang, persona_number = parsed
        key = f"{fmt}::P{persona_number}" if isinstance(persona_number, int) else fmt
        current = out.get(key, {})
        text = prompt_file.read_text(encoding="utf-8", errors="ignore")
        if persona_number is None:
            inferred = parse_persona_number_from_prompt(text)
            if isinstance(inferred, int):
                persona_number = inferred
                key = f"{fmt}::P{persona_number}"
                current = out.get(key, current)
        lock = parse_background_lock_from_prompt(text)
        if lock:
            current["background_slot"] = lock[0]
            current["background_seed"] = lock[1]

        visual_lock = {
            "seeded_background_direction": _parse_prompt_field(text, "Seeded background direction (single sentence, exact)"),
            "subject": _parse_prompt_field(text, "Subject"),
            "action": _parse_prompt_field(text, "Action"),
            "camera": _parse_prompt_field(text, "Camera"),
            "lighting": _parse_prompt_field(text, "Lighting"),
            "props": _parse_prompt_field(text, "Props"),
            "surfaces": _parse_prompt_field(text, "Surfaces"),
            "mood": _parse_prompt_field(text, "Mood"),
            "realism": _parse_prompt_field(text, "Realism"),
        }
        visual_lock = {k: v for k, v in visual_lock.items() if v}
        if visual_lock:
            current["visual_lock"] = visual_lock

        if current:
            out[key] = current
    return out


def apply_visual_locks(copy_json: dict[str, Any], locks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(copy_json, ensure_ascii=False))
    ads = cloned.get("ads")
    if not isinstance(ads, list):
        return cloned
    for ad in ads:
        if not isinstance(ad, dict):
            continue
        fmt = str(ad.get("format") or "").strip().upper()
        persona_no = None
        persona = ad.get("persona")
        if isinstance(persona, dict):
            raw_no = persona.get("number")
            if isinstance(raw_no, int):
                persona_no = raw_no
        lock_key = f"{fmt}::P{persona_no}" if isinstance(persona_no, int) else ""
        lock = (locks.get(lock_key) if lock_key else None) or locks.get(fmt) or {}
        if not lock:
            continue
        if isinstance(lock.get("background_slot"), str):
            ad["background_slot"] = lock["background_slot"]
        if isinstance(lock.get("background_seed"), int):
            ad["background_seed"] = lock["background_seed"]
        if isinstance(lock.get("visual_lock"), dict):
            ad["visual_lock"] = lock["visual_lock"]
    return cloned


def resolve_format_plan(config: dict[str, Any]) -> list[dict[str, Any]]:
    personas = config.get("selected_personas") or []
    if not personas:
        raise RuntimeError("selected_personas is required")

    all_formats = [fmt for fmt in (config.get("global_formats") or []) if fmt in FORMATS]
    format_map = config.get("formats_by_persona") or {}

    out: list[dict[str, Any]] = []
    for raw_persona in personas:
        persona_num = int(raw_persona)
        per_formats = [fmt for fmt in (format_map.get(str(persona_num)) or format_map.get(persona_num) or []) if fmt in FORMATS]
        formats = per_formats if per_formats else all_formats
        if not formats:
            formats = ["HERO"]
        for fmt in formats:
            out.append({"persona": persona_num, "format": fmt})
    return out


app = FastAPI(title="Ad Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    load_env_file(ENV_PATH)
    ensure_dirs()


@app.get("/api/defaults")
def api_defaults() -> dict[str, Any]:
    personas = parse_persona_library(DEFAULT_PLAYBOOK)
    opencode = build_opencode_catalog()
    return {
        "personas": personas,
        "formats": FORMATS,
        "image_sources": read_active_images(default_image_sources_file()),
        "input_images": list_input_images(),
        "default_files": {
            "product_info": str(DEFAULT_PRODUCT_INFO.relative_to(ROOT)),
            "mechanism": str(DEFAULT_MECHANISM.relative_to(ROOT)),
            "faq": str(DEFAULT_FAQ.relative_to(ROOT)),
            "playbook": str(DEFAULT_PLAYBOOK.relative_to(ROOT)),
        },
        "opencode": opencode,
    }


@app.get("/api/opencode/catalog")
def api_opencode_catalog() -> dict[str, Any]:
    return build_opencode_catalog()


@app.get("/api/runs")
def api_runs() -> dict[str, Any]:
    ensure_dirs()
    runs: list[dict[str, Any]] = []
    for run_dir in sorted(RUNS_ROOT.glob("run_*"), reverse=True):
        manifest = run_dir / "manifest.json"
        if manifest.exists():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            refreshed = refresh_manifest_file_state(run_dir, payload)
            if refreshed.get("prompt_files"):
                runs.append(refreshed)

    def batch_sort_key(run: dict[str, Any]) -> tuple[int, float]:
        batch = str(run.get("batch") or "").strip().lower()
        match = re.match(r"^v(\d+)$", batch)
        batch_num = int(match.group(1)) if match else -1
        updated = str(run.get("updated_at") or "")
        ts = 0.0
        if updated:
            try:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
            except Exception:
                ts = 0.0
        return (batch_num, ts)

    runs.sort(key=batch_sort_key, reverse=True)
    return {"runs": runs}


@app.get("/api/runs/{run_id}")
def api_run(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest = run_dir / "manifest.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return refresh_manifest_file_state(run_dir, payload)


@app.get("/api/runs/{run_id}/prompt-copies")
def api_run_prompt_copies(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prompt_files_all = manifest.get("prompt_files") or []
    prompt_files = [path for path in prompt_files_all if "/45/" in str(path)] or prompt_files_all
    records: list[dict[str, Any]] = []
    for rel_path in prompt_files:
        prompt_path = ROOT / rel_path
        if not prompt_path.exists() or not prompt_path.is_file():
            continue
        text = prompt_path.read_text(encoding="utf-8", errors="ignore")
        parsed_name = parse_prompt_filename(rel_path)
        persona_number = parsed_name[2] if parsed_name else None
        if persona_number is None:
            persona_number = parse_persona_number_from_prompt(text)
        records.append(
            {
                "prompt_file": rel_path,
                "format": parsed_name[0] if parsed_name else "",
                "language": parsed_name[1] if parsed_name else "",
                "persona_number": persona_number,
                "review_url": "/output/" + rel_path.replace("output/", ""),
                "copy_lines": extract_on_image_copy_lines(text),
            }
        )

    return {"run_id": run_id, "batch": manifest.get("batch"), "prompts": records}


@app.post("/api/runs/{run_id}/prompt-copies")
def api_run_update_prompt_copies(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    copy_path = run_dir / "context" / "copy_batch.json"

    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    if not copy_path.exists():
        raise HTTPException(status_code=404, detail="copy_batch.json not found for run")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batch = (manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise HTTPException(status_code=400, detail="edits must be a non-empty array")

    copy_json = json.loads(copy_path.read_text(encoding="utf-8"))
    ads = copy_json.get("ads")
    if not isinstance(ads, list) or not ads:
        raise HTTPException(status_code=400, detail="Invalid copy batch payload")

    updated_count = 0
    for entry in edits:
        if not isinstance(entry, dict):
            continue
        prompt_file = str(entry.get("prompt_file") or "").strip()
        if not prompt_file:
            continue
        parsed_name = parse_prompt_filename(prompt_file)
        if not parsed_name:
            continue
        fmt, lang, parsed_persona = parsed_name
        persona_number = entry.get("persona_number")
        if not isinstance(persona_number, int):
            persona_number = parsed_persona
        line_items = entry.get("copy_lines")
        if not isinstance(line_items, list) or not line_items:
            continue

        target_ad = None
        for ad in ads:
            if not isinstance(ad, dict):
                continue
            if str(ad.get("format") or "").strip().upper() != fmt:
                continue
            if isinstance(persona_number, int):
                persona = ad.get("persona")
                ad_persona_no = None
                if isinstance(persona, dict) and isinstance(persona.get("number"), int):
                    ad_persona_no = int(persona.get("number"))
                if ad_persona_no != persona_number:
                    continue
            target_ad = ad
            break
        if not isinstance(target_ad, dict):
            continue

        ad_copy = target_ad.setdefault("copy", {})
        if not isinstance(ad_copy, dict):
            continue
        lang_copy = ad_copy.setdefault(lang, {})
        if not isinstance(lang_copy, dict):
            continue

        for line_item in line_items:
            if not isinstance(line_item, dict):
                continue
            label = str(line_item.get("label") or "").strip()
            value = str(line_item.get("value") or "").strip()
            if not label:
                continue
            key = label.lower()

            if key == "headline":
                lang_copy["headline"] = value
            elif key == "support line":
                lang_copy["support_line"] = value
            elif key == "context line":
                lang_copy["context_line"] = value
            elif key == "cta":
                lang_copy["cta"] = value
            elif key == "attribution":
                lang_copy["attribution"] = value
            elif key == "trust line":
                lang_copy["trust_line"] = value
            elif key.startswith("bullet "):
                match = re.match(r"^bullet\s+(\d+)$", key)
                if not match:
                    continue
                index = int(match.group(1)) - 1
                if index < 0:
                    continue
                bullets = lang_copy.get("bullets")
                if not isinstance(bullets, list):
                    bullets = []
                while len(bullets) <= index:
                    bullets.append("")
                bullets[index] = value
                lang_copy["bullets"] = bullets
            elif key.startswith("left situation ") or key.startswith("right shift "):
                match = re.match(r"^(left situation|right shift)\s+(\d+)$", key)
                if not match:
                    continue
                side = match.group(1)
                ordinal = int(match.group(2))
                if ordinal <= 0:
                    continue
                if side == "left situation":
                    index = ordinal - 1
                else:
                    index = ordinal + 1
                bullets = lang_copy.get("bullets")
                if not isinstance(bullets, list):
                    bullets = []
                while len(bullets) <= index:
                    bullets.append("")
                bullets[index] = value
                lang_copy["bullets"] = bullets

        updated_count += 1

    if updated_count == 0:
        raise HTTPException(status_code=400, detail="No valid prompt edits were provided")

    copy_path.write_text(json.dumps(copy_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rerender_prompts_for_run(run_dir, batch, copy_path, load_run_language_mode(run_dir))

    has_916 = any("/96/" in str(path) for path in (manifest.get("prompt_files") or []))
    if has_916:
        manifest = generate_916_for_run(run_dir, manifest)

    refreshed = collect_run_result(run_dir, batch, bool(manifest.get("image_generated", False)))
    refreshed["copy_edits_applied"] = updated_count
    merged = merge_manifest(run_dir, manifest, refreshed)
    return merged


@app.post("/api/runs/{run_id}/generate-916")
def api_run_generate_916(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"

    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return generate_916_for_run(run_dir, manifest)


@app.post("/api/runs/{run_id}/generate-916-selected")
def api_run_generate_916_selected(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    copy_path = run_dir / "context" / "copy_batch.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    if not copy_path.exists():
        raise HTTPException(status_code=404, detail="copy_batch.json not found for run")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batch = str(manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    prompt_files = payload.get("prompt_files")
    if not isinstance(prompt_files, list) or not prompt_files:
        raise HTTPException(status_code=400, detail="prompt_files must be a non-empty array")

    selected_45 = validate_selected_45_prompts(batch, prompt_files)
    if not selected_45:
        raise HTTPException(status_code=400, detail="No valid 4:5 prompt files selected")

    selected_keys = extract_selected_ad_keys_from_45_prompts(selected_45)
    if not selected_keys:
        raise HTTPException(status_code=400, detail="Could not resolve selected persona/format keys")

    copy_json = json.loads(copy_path.read_text(encoding="utf-8"))
    selected_copy = filter_copy_json_for_selected_ads(copy_json, selected_keys)
    ads = selected_copy.get("ads")
    if not isinstance(ads, list) or not ads:
        raise HTTPException(status_code=400, detail="No ads matched selected prompts")

    copy_916 = force_aspect_ratio(selected_copy, "9:16")
    visual_locks = collect_45_visual_locks(batch)
    if visual_locks:
        copy_916 = apply_visual_locks(copy_916, visual_locks)
    copy_916_path = run_dir / "context" / "copy_batch_916_selected.json"
    copy_916_path.write_text(json.dumps(copy_916, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = run_cmd(
        [
            "python3",
            "scripts/generate_ads.py",
            "--copy-file",
            str(copy_916_path),
            "--batch",
            batch,
            "--language-mode",
            load_run_language_mode(run_dir),
            "--no-registry-write",
            "--skip-uniqueness-check",
        ],
        cwd=ROOT,
    )
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "assembler_916_selected_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"Selective 9:16 generation failed: {short_error}")

    refreshed = collect_run_result(run_dir, batch, bool(manifest.get("image_generated", False)))
    refreshed["generated_variant"] = "9:16"
    refreshed["generated_916_for_prompts"] = selected_45
    return merge_manifest(run_dir, manifest, refreshed)


def validate_selected_45_prompts(batch: str, prompt_files: list[Any]) -> list[str]:
    valid_prompt_files: list[str] = []
    for prompt_file in prompt_files:
        rel = str(prompt_file or "").strip().replace("\\", "/")
        if not rel or not rel.startswith("output/"):
            continue
        if "/45/" not in rel:
            continue
        candidate = ROOT / rel
        if not candidate.exists() or not candidate.is_file():
            continue
        if f"output/{batch}/" not in rel:
            continue
        valid_prompt_files.append(rel)
    return valid_prompt_files


def map_45_to_96_prompts(selected_45: list[str]) -> list[str]:
    out: list[str] = []
    for rel in selected_45:
        rel_96 = rel.replace("/45/", "/96/")
        file_96 = ROOT / rel_96
        if file_96.exists() and file_96.is_file():
            out.append(rel_96)
    return out


def extract_selected_ad_keys_from_45_prompts(selected_45: list[str]) -> set[tuple[str, int | None]]:
    keys: set[tuple[str, int | None]] = set()
    for rel in selected_45:
        parsed = parse_prompt_filename(rel)
        if not parsed:
            continue
        fmt, _lang, persona_number = parsed
        keys.add((fmt, persona_number))
    return keys


def filter_copy_json_for_selected_ads(copy_json: dict[str, Any], selected_keys: set[tuple[str, int | None]]) -> dict[str, Any]:
    ads = copy_json.get("ads")
    if not isinstance(ads, list):
        return copy_json
    selected_ads: list[dict[str, Any]] = []
    for ad in ads:
        if not isinstance(ad, dict):
            continue
        fmt = str(ad.get("format") or "").strip().upper()
        persona_number = None
        persona = ad.get("persona")
        if isinstance(persona, dict) and isinstance(persona.get("number"), int):
            persona_number = int(persona.get("number"))
        if (fmt, persona_number) in selected_keys or (fmt, None) in selected_keys:
            selected_ads.append(ad)
    cloned = json.loads(json.dumps(copy_json, ensure_ascii=False))
    cloned["ads"] = selected_ads
    return cloned


@app.post("/api/runs/{run_id}/generate-images-45")
def api_run_generate_images_45(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batch = str(manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    prompt_files = payload.get("prompt_files")
    if not isinstance(prompt_files, list) or not prompt_files:
        raise HTTPException(status_code=400, detail="prompt_files must be a non-empty array")

    selected_45 = validate_selected_45_prompts(batch, prompt_files)
    if not selected_45:
        raise HTTPException(status_code=400, detail="No valid 4:5 prompt files selected")

    try:
        result = run_gemini_generation(
            batch=batch,
            prompt_files=selected_45,
            aspect_ratio="4:5",
            image_sources_file=None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "image_generation_45_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"Gemini image generation failed (4:5): {short_error}")

    refreshed = collect_run_result(run_dir, batch, True)
    refreshed["generated_images_for_prompts_45"] = selected_45
    merged = merge_manifest(run_dir, manifest, refreshed)
    return merged


@app.post("/api/runs/{run_id}/generate-images-916-from-45")
def api_run_generate_images_916_from_45(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    batch = str(manifest.get("batch") or "").strip()
    if not batch:
        raise HTTPException(status_code=400, detail="Run has no batch folder")

    prompt_files = payload.get("prompt_files")
    if not isinstance(prompt_files, list) or not prompt_files:
        raise HTTPException(status_code=400, detail="prompt_files must be a non-empty array")

    selected_45 = validate_selected_45_prompts(batch, prompt_files)
    if not selected_45:
        raise HTTPException(status_code=400, detail="No valid 4:5 prompt files selected")

    selected_96 = map_45_to_96_prompts(selected_45)
    if not selected_96:
        raise HTTPException(status_code=400, detail="No matching 9:16 prompt files found for selected 4:5 prompts")

    jobs = load_batch_image_summary(batch)
    job_by_prompt: dict[str, dict[str, Any]] = {}
    for job in jobs:
        prompt_file = str(job.get("prompt_file") or "").strip().replace("\\", "/")
        if prompt_file:
            job_by_prompt[prompt_file] = job

    prompt_reference_map: dict[str, list[str]] = {}
    for prompt_45 in selected_45:
        prompt_96 = prompt_45.replace("/45/", "/96/")
        if prompt_96 not in selected_96:
            continue
        job = job_by_prompt.get(prompt_45)
        if not job:
            continue
        saved_files = job.get("saved_files")
        if not isinstance(saved_files, list) or not saved_files:
            continue
        image_rel = str(saved_files[0]).strip().replace("\\", "/")
        image_path = ROOT / image_rel
        if not image_path.exists() or not image_path.is_file():
            continue
        prompt_reference_map[prompt_96] = [str(image_path)]

    if not prompt_reference_map:
        raise HTTPException(status_code=400, detail="Could not build 9:16 reference images from selected 4:5 outputs")

    map_path = run_dir / "context" / "prompt_reference_map_916.json"
    map_path.write_text(json.dumps(prompt_reference_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        result = run_gemini_generation(
            batch=batch,
            prompt_files=sorted(prompt_reference_map.keys()),
            aspect_ratio="9:16",
            image_sources_file=None,
            prompt_reference_map=map_path,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "image_generation_916_from_45_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"Gemini image generation failed (9:16 from 4:5 refs): {short_error}")

    refreshed = collect_run_result(run_dir, batch, True)
    refreshed["generated_images_for_prompts_916"] = sorted(prompt_reference_map.keys())
    refreshed["reference_images_916"] = prompt_reference_map
    merged = merge_manifest(run_dir, manifest, refreshed)
    return merged


@app.get("/api/file-content")
def api_file_content(path: str, max_lines: int = 400) -> dict[str, Any]:
    file_path = resolve_safe_path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    clipped = lines[:max_lines]
    return {
        "path": str(file_path.relative_to(ROOT)),
        "total_lines": len(lines),
        "shown_lines": len(clipped),
        "content": "\n".join(clipped),
    }


@app.post("/api/runs/execute")
async def api_run_execute(
    config: str = Form(...),
    product_info_file: UploadFile | None = File(None),
    mechanism_file: UploadFile | None = File(None),
    faq_file: UploadFile | None = File(None),
    image_source_file: UploadFile | None = File(None),
    input_image_files: list[UploadFile] | None = File(None),
    clear_input_images: bool = Form(False),
) -> dict[str, Any]:
    ensure_dirs()
    try:
        cfg = json.loads(config)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid config JSON") from exc

    run_id = make_run_id()
    run_dir = RUNS_ROOT / run_id
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "context").mkdir(parents=True, exist_ok=True)

    product_path = save_upload(run_dir / "inputs" / "productinfomain.txt", product_info_file)
    mechanism_path = save_upload(run_dir / "inputs" / "PRODUCT_MECHANISM_V1.txt", mechanism_file)
    faq_path = save_upload(run_dir / "inputs" / "faq.txt", faq_file)
    image_sources_path = save_upload(run_dir / "inputs" / "image_sources.txt", image_source_file)
    saved_input_images = store_uploaded_input_images(input_image_files or [], clear_input_images)

    product_file = coalesce_path(product_path, DEFAULT_PRODUCT_INFO)
    mechanism_file_path = coalesce_path(mechanism_path, DEFAULT_MECHANISM)
    faq_file_path = coalesce_path(faq_path, DEFAULT_FAQ)

    image_sources_file_path = coalesce_path(image_sources_path, default_image_sources_file())

    try:
        plan = resolve_format_plan(cfg)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    product_ctx: dict[str, Any]
    product_ctx_source = "extract_product_context"
    extractor_model = choose_extractor_model(cfg)
    canonical_path = RUNTIME_ROOT / "context_canonical.json"
    canonical_cmd = [
        "python3",
        "scripts/build_canonical_context.py",
        "--product",
        str(product_file),
        "--mechanism",
        str(mechanism_file_path),
        "--faq",
        str(faq_file_path),
        "--output",
        str(canonical_path),
        "--api-url",
        str((cfg.get("opencode_api_url") or DEFAULT_OPENCODE_API_URL)).strip(),
        "--model",
        extractor_model,
    ]
    extractor_key = (cfg.get("opencode_api_key") or "").strip() or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    if extractor_key:
        canonical_cmd.extend(["--api-key", extractor_key])

    canonical_result = run_cmd(canonical_cmd, cwd=ROOT)
    if canonical_result.returncode == 0 and canonical_path.exists():
        try:
            canonical_payload = json.loads(canonical_path.read_text(encoding="utf-8"))
            generated_ctx = canonical_payload.get("generation_context")
            if isinstance(generated_ctx, dict):
                product_ctx = generated_ctx
                product_ctx_source = "canonical_llm"
                (run_dir / "context" / "context_canonical.json").write_text(
                    json.dumps(canonical_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            else:
                raise RuntimeError("Missing generation_context in canonical payload")
        except Exception as exc:
            (run_dir / "logs" / "canonical_context_error.txt").write_text(
                f"Canonical context parse failed: {exc}\nSTDOUT:\n{canonical_result.stdout}\n\nSTDERR:\n{canonical_result.stderr}",
                encoding="utf-8",
            )
            product_ctx = {}
    else:
        (run_dir / "logs" / "canonical_context_error.txt").write_text(
            f"Canonical context generation failed\nSTDOUT:\n{canonical_result.stdout}\n\nSTDERR:\n{canonical_result.stderr}",
            encoding="utf-8",
        )
        product_ctx = {}

    if not product_ctx:
        product_ctx_result = run_cmd(
            [
                "python3",
                "scripts/extract_product_context.py",
                "--product",
                str(product_file),
                "--mechanism",
                str(mechanism_file_path),
                "--faq",
                str(faq_file_path),
                "--json",
            ],
            cwd=ROOT,
        )
        product_ctx = parse_json_stdout(product_ctx_result, "extract_product_context")

    persona_library = parse_persona_library(DEFAULT_PLAYBOOK)
    ads_context: list[dict[str, Any]] = []
    format_seen_counts: dict[str, int] = {}
    for item in plan:
        persona_no = item["persona"]
        fmt = item["format"]
        format_seen_counts[fmt] = format_seen_counts.get(fmt, 0) + 1
        persona_payload = build_persona_payload(persona_no, persona_library)

        format_result = run_cmd(
            [
                "python3",
                "scripts/extract_format_rules.py",
                "--playbook",
                str(DEFAULT_PLAYBOOK),
                "--format",
                fmt,
                "--json",
            ],
            cwd=ROOT,
        )
        format_payload = parse_json_stdout(format_result, f"extract_format_rules({fmt})")
        ads_context.append(
            {
                "persona": persona_payload,
                "format_rules": format_payload,
                "format": fmt,
                "copy_requirements": build_copy_requirements(persona_no, fmt, format_seen_counts[fmt]),
            }
        )

    banlist_result = run_cmd(["python3", "scripts/registry_banlist.py", "--last", "150"], cwd=ROOT)
    banlist_payload = parse_json_stdout(banlist_result, "registry_banlist")

    full_context = {
        "generated_at": now_iso(),
        "run_id": run_id,
        "language_mode": resolve_language_mode(cfg),
        "context_source": product_ctx_source,
        "context_extractor_model": extractor_model,
        "ads": ads_context,
        "product_context": product_ctx,
        "banlist": banlist_payload,
    }
    (run_dir / "context" / "run_context.json").write_text(
        json.dumps(full_context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    copy_json = call_opencode_compatible(cfg, full_context, run_dir)
    if not copy_json:
        raise HTTPException(status_code=502, detail="OpenCode copy generation failed. Prompt production stopped; check run logs.")
    generated_copy_error = validate_generated_copy_payload(copy_json, ads_context)
    if generated_copy_error:
        (run_dir / "logs" / "opencode_error.txt").write_text(
            generated_copy_error + "\n\nGenerated payload:\n" + json.dumps(copy_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise HTTPException(status_code=502, detail="OpenCode copy generation returned incomplete copy. Prompt production stopped; check run logs.")
    llm_mode = "opencode"
    copy_json = normalize_generated_copy(copy_json, full_context, run_id)
    copy_json = strip_internal_markers_from_payload(copy_json)

    copy_file = run_dir / "context" / "copy_batch.json"
    copy_file.write_text(json.dumps(copy_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    assembler_result = run_cmd(
        [
            "python3",
            "scripts/generate_ads.py",
            "--copy-file",
            str(copy_file),
            "--language-mode",
            assembler_language_mode(cfg),
        ],
        cwd=ROOT,
    )
    if assembler_result.returncode != 0:
        assembler_error = assembler_result.stderr or assembler_result.stdout
        (run_dir / "logs" / "assembler_error.txt").write_text(assembler_error, encoding="utf-8")

        collisions = parse_uniqueness_collisions(assembler_error)
        if collisions:
            repaired = call_opencode_repair_copy(cfg, full_context, copy_json, collisions, run_dir)
            if repaired:
                copy_json = normalize_generated_copy(repaired, full_context, run_id)
                copy_json = strip_internal_markers_from_payload(copy_json)
                copy_file.write_text(json.dumps(copy_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

                retry = run_cmd(
                    [
                        "python3",
                        "scripts/generate_ads.py",
                        "--copy-file",
                        str(copy_file),
                        "--language-mode",
                        assembler_language_mode(cfg),
                    ],
                    cwd=ROOT,
                )
                if retry.returncode == 0:
                    assembler_result = retry
                else:
                    retry_error = retry.stderr or retry.stdout
                    (run_dir / "logs" / "assembler_retry_error.txt").write_text(retry_error, encoding="utf-8")

        if assembler_result.returncode != 0:
            raise HTTPException(status_code=500, detail="Prompt assembly failed after automatic retry. Check run logs.")

    batch_match = re.search(r"Batch:\s*(v\d+)", assembler_result.stdout)
    if not batch_match:
        raise HTTPException(status_code=500, detail="Could not parse batch from assembler output")
    batch_name = batch_match.group(1)

    generate_images = False
    image_generated = False
    if generate_images:
        kie_api_key = (cfg.get("kie_api_key") or "").strip()
        if not kie_api_key:
            (run_dir / "logs" / "image_blocker.txt").write_text(
                "generate_images was true but kie_api_key is missing", encoding="utf-8"
            )
        else:
            image_result = run_cmd(
                [
                    "python3",
                    "scripts/kie_nano_batch.py",
                    "--batch",
                    batch_name,
                    "--api-key",
                    kie_api_key,
                    "--active-images-file",
                    str(image_sources_file_path),
                    "--language",
                    cfg.get("image_language", "EN"),
                    "--max-variations-per-format",
                    str(int(cfg.get("max_variations_per_format", 1))),
                ],
                cwd=ROOT,
            )
            (run_dir / "logs" / "image_generation.log").write_text(
                (image_result.stdout or "") + "\n" + (image_result.stderr or ""), encoding="utf-8"
            )
            image_generated = image_result.returncode == 0

    manifest = collect_run_result(run_dir, batch_name, image_generated)
    manifest["llm_mode"] = llm_mode
    manifest["context_source"] = product_ctx_source
    manifest["context_extractor_model"] = extractor_model
    manifest["image_sources_file"] = str(image_sources_file_path)
    manifest["input_images_dir"] = str(INPUT_IMAGES_DIR.relative_to(ROOT)).replace("\\", "/")
    manifest["input_images_uploaded"] = saved_input_images
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


app.mount("/storage", StaticFiles(directory=str(STORAGE_ROOT)), name="storage")
app.mount("/output", StaticFiles(directory=str(ROOT / "output")), name="output")
GENERATED_IMAGES_ROOT.mkdir(parents=True, exist_ok=True)
LEGACY_GENERATED_IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/generated_images", StaticFiles(directory=str(GENERATED_IMAGES_ROOT)), name="generated_images")
app.mount("/generated_image", StaticFiles(directory=str(LEGACY_GENERATED_IMAGE_ROOT)), name="generated_image")
app.mount("/", StaticFiles(directory=str(ROOT / "dashboard" / "frontend"), html=True), name="frontend")
