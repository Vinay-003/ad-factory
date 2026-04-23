#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import time
import urllib.request
import hashlib
import mimetypes
import uuid
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

DEFAULT_PRODUCT_INFO = ROOT / "productinfomain.txt"
DEFAULT_MECHANISM = ROOT / "PRODUCT_MECHANISM_V1.txt"
DEFAULT_FAQ = ROOT / "faq.txt"
DEFAULT_PLAYBOOK = ROOT / "AD_CREATIVE_SYSTEM_PLAYBOOK.md"
DEFAULT_ACTIVE_IMAGES = ROOT / "input" / "activeimages.txt"


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
}

PERSONA_HEADLINE_ANGLE_KEYS: dict[int, str] = {
    1: "cravings_spike",
    2: "packed_days",
    3: "stressful_moments",
    4: "progress_stalls",
    5: "steadier_trust",
    6: "slow_results",
    7: "diet_reset",
    8: "no_drain",
    9: "family_rhythm",
    10: "home_routine",
    11: "office_snack_window",
    12: "late_evening",
    13: "post_disruption",
    14: "clarity_matters",
    15: "digestion_support",
    16: "value_matters",
    17: "deadline_pressure",
    18: "small_wins",
    19: "proof_matters",
    20: "accountability",
    21: "low_guesswork",
    22: "sustainable_after_35",
}

PERSONA_HEADLINE_HOOKS: dict[str, dict[str, str]] = {
    "EN": {
        "cravings_spike": "when cravings spike",
        "packed_days": "on packed days",
        "stressful_moments": "during stressful moments",
        "progress_stalls": "when progress stalls",
        "steadier_trust": "when you want steadier trust",
        "slow_results": "when results feel slow",
        "diet_reset": "after repeated diet resets",
        "no_drain": "without feeling drained",
        "family_rhythm": "inside chaotic family days",
        "home_routine": "inside home routines",
        "office_snack_window": "during office snack windows",
        "late_evening": "when evenings get harder",
        "post_disruption": "after routine disruptions",
        "clarity_matters": "when clarity matters",
        "digestion_support": "when digestion also needs support",
        "value_matters": "when value matters",
        "deadline_pressure": "before a close deadline",
        "small_wins": "when confidence needs small wins",
        "proof_matters": "when proof matters",
        "accountability": "when follow-through needs a check-in",
        "low_guesswork": "when you want almost no guesswork",
        "sustainable_after_35": "when sustainable progress matters after 35",
    },
    "HI": {
        "cravings_spike": "जब cravings अचानक बढ़ें",
        "packed_days": "जब दिन बहुत packed हों",
        "stressful_moments": "तनाव भरे moments में",
        "progress_stalls": "जब progress अटक जाए",
        "steadier_trust": "जब support ज्यादा भरोसेमंद चाहिए",
        "slow_results": "जब results धीमे लगें",
        "diet_reset": "बार-बार diet reset के बाद",
        "no_drain": "बिना थकान महसूस किए",
        "family_rhythm": "उलझे हुए family दिनों में",
        "home_routine": "घर के रूटीन में",
        "office_snack_window": "office snack windows में",
        "late_evening": "शाम देर होने पर",
        "post_disruption": "रूटीन टूटने के बाद",
        "clarity_matters": "जब clarity चाहिए",
        "digestion_support": "जब digestion को भी support चाहिए",
        "value_matters": "जब value सबसे ज़रूरी हो",
        "deadline_pressure": "जब deadline नज़दीक हो",
        "small_wins": "जब confidence को छोटे wins चाहिए",
        "proof_matters": "जब proof ज़रूरी हो",
        "accountability": "जब follow-through को check-in चाहिए",
        "low_guesswork": "जब guesswork लगभग zero चाहिए",
        "sustainable_after_35": "35 के बाद steady progress के लिए",
    },
}

def persona_headline_angle_key(persona_num: int) -> str:
    return PERSONA_HEADLINE_ANGLE_KEYS.get(persona_num, f"persona_{persona_num}")

def persona_headline_hook(persona_num: int, lang: str) -> str:
    lang_key = "HI" if lang == "HI" else "EN"
    angle_key = persona_headline_angle_key(persona_num)
    hooks = PERSONA_HEADLINE_HOOKS.get(lang_key, PERSONA_HEADLINE_HOOKS["EN"])
    return hooks.get(angle_key, "for steadier follow-through" if lang_key == "EN" else "steadier follow-through के लिए")


def normalize_copy_signature(text: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u0900-\u097F]+", " ", (text or "").casefold())
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "just",
        "may",
        "me",
        "more",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "out",
        "so",
        "than",
        "that",
        "the",
        "their",
        "this",
        "to",
        "too",
        "up",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "would",
        "you",
        "your",
    }
    tokens = [token for token in cleaned.split() if token and token not in stopwords]
    return " ".join(tokens[:10])


def copy_too_similar(candidate: str, seen_signatures: set[str]) -> bool:
    signature = normalize_copy_signature(candidate)
    if not signature:
        return False
    if signature in seen_signatures:
        return True
    candidate_tokens = set(signature.split())
    if not candidate_tokens:
        return False
    for existing in seen_signatures:
        existing_tokens = set(existing.split())
        if not existing_tokens:
            continue
        overlap = len(candidate_tokens & existing_tokens) / max(len(candidate_tokens | existing_tokens), 1)
        if overlap >= 0.66:
            return True
    return False


def pick_diverse_copy(candidates: list[str], banned: set[str], fallback: str, seen_signatures: set[str]) -> str:
    normalized = [" ".join((candidate or "").split()).strip() for candidate in candidates]
    for candidate in normalized:
        if not candidate or candidate in banned:
            continue
        if not copy_too_similar(candidate, seen_signatures):
            seen_signatures.add(normalize_copy_signature(candidate))
            return candidate
    for candidate in normalized:
        if candidate and not copy_too_similar(candidate, seen_signatures):
            seen_signatures.add(normalize_copy_signature(candidate))
            return candidate
    fallback_clean = " ".join((fallback or "").split()).strip()
    if fallback_clean:
        seen_signatures.add(normalize_copy_signature(fallback_clean))
    return fallback_clean


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
        "headline_angle_key": persona_headline_angle_key(persona_number),
        "headline_hook_en": persona_headline_hook(persona_number, "EN"),
        "headline_hook_hi": persona_headline_hook(persona_number, "HI"),
    }


def read_active_images(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


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
    summary_path = ROOT / "generated_image" / batch / "batch_run_summary.json"
    if not summary_path.exists():
        return []
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


def used_text_bucket(context: dict[str, Any], bucket: str) -> set[str]:
    banlist = context.get("banlist") if isinstance(context, dict) else {}
    buckets = banlist.get("buckets") if isinstance(banlist, dict) else {}
    values = buckets.get(bucket) if isinstance(buckets, dict) else []
    if not isinstance(values, list):
        return set()
    return {str(item).strip() for item in values if isinstance(item, str) and item.strip()}


def pick_unused_copy(candidates: list[str], banned: set[str], fallback: str) -> str:
    for candidate in candidates:
        clean = " ".join((candidate or "").split()).strip()
        if clean and clean not in banned:
            return clean
    return " ".join((fallback or "").split()).strip()


def add_used_text_bucket(bucket: set[str], values: list[str]) -> None:
    for value in values:
        clean = " ".join((value or "").split()).strip()
        if clean:
            bucket.add(clean)


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


def coerce_generated_copy_schema(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    ads = payload.get("ads")
    if not isinstance(ads, list):
        return payload

    default_ratio = str(payload.get("default_aspect_ratio") or "").strip()
    if default_ratio not in {"4:5", "9:16"}:
        payload["default_aspect_ratio"] = "4:5"
    else:
        payload["default_aspect_ratio"] = default_ratio

    for ad in ads:
        if not isinstance(ad, dict):
            continue
        aspect_ratio = str(ad.get("aspect_ratio") or "").strip()
        if aspect_ratio and aspect_ratio not in {"4:5", "9:16"}:
            ad["aspect_ratio"] = payload["default_aspect_ratio"]
        persona = ad.get("persona")
        if not isinstance(persona, dict):
            continue
        if not isinstance(persona.get("number"), int):
            val = persona.get("persona_number")
            if isinstance(val, int):
                persona["number"] = val
            elif isinstance(val, str) and val.strip().isdigit():
                persona["number"] = int(val.strip())
        if not isinstance(persona.get("name"), str) or not persona.get("name", "").strip():
            name = persona.get("persona_name")
            if isinstance(name, str) and name.strip():
                persona["name"] = name.strip()

        pain_points = persona.get("pain_points") if isinstance(persona.get("pain_points"), list) else []
        objections = persona.get("objections") if isinstance(persona.get("objections"), list) else []
        core_message = persona.get("core_message") if isinstance(persona.get("core_message"), list) else []
        trust_anchors = persona.get("trust_anchors") if isinstance(persona.get("trust_anchors"), list) else []
        hindi_ready = persona.get("hindi_ready") if isinstance(persona.get("hindi_ready"), list) else []
        english_ready = persona.get("english_ready") if isinstance(persona.get("english_ready"), list) else []

        if not _clean_str(persona.get("pain_en")):
            persona["pain_en"] = choose_text(pain_points, "Daily routine feels heavy and hard to sustain.")
        if not _clean_str(persona.get("desire_en")):
            persona["desire_en"] = choose_text(core_message, "A practical routine that feels easy to follow.")
        if not _clean_str(persona.get("friction_en")):
            persona["friction_en"] = choose_text(objections, "Past plans felt too strict and difficult to maintain.")
        if not _clean_str(persona.get("proof_needed_en")):
            persona["proof_needed_en"] = choose_text(trust_anchors, "Needs clear structure and believable support.")
        if not _clean_str(persona.get("tone_cue_en")):
            tone_en = choose_text(english_ready, "Tone cue: practical and confidence-building")
            persona["tone_cue_en"] = re.sub(r"^\s*Tone\s+cue\s*:\s*", "", tone_en, flags=re.IGNORECASE).strip() or "practical and confidence-building"

        if not _clean_str(persona.get("pain_hi")):
            persona["pain_hi"] = choose_text(hindi_ready, "रूटीन निभाना मुश्किल लग रहा है।")
        if not _clean_str(persona.get("desire_hi")):
            persona["desire_hi"] = "ऐसा आसान सिस्टम जो रोज निभ सके।"
        if not _clean_str(persona.get("friction_hi")):
            persona["friction_hi"] = "पहले के प्लान बहुत सख्त और मुश्किल थे।"
        if not _clean_str(persona.get("proof_needed_hi")):
            persona["proof_needed_hi"] = "साफ तरीका, भरोसेमंद सपोर्ट और व्यावहारिक प्रूफ चाहिए।"
        if not _clean_str(persona.get("tone_cue_hi")):
            persona["tone_cue_hi"] = "सरल, भरोसेमंद, और व्यावहारिक"

    return payload


def validate_llm_copy_payload(payload: dict[str, Any], context: dict[str, Any]) -> str | None:
    ads = payload.get("ads")
    if not isinstance(ads, list) or not ads:
        return "LLM copy payload is missing a non-empty ads array."
    expected_ads = context.get("ads") if isinstance(context, dict) else None
    if isinstance(expected_ads, list) and len(expected_ads) != len(ads):
        return f"LLM copy payload returned {len(ads)} ads; expected {len(expected_ads)}."
    default_ratio = str(payload.get("default_aspect_ratio") or "").strip()
    if default_ratio not in {"4:5", "9:16"}:
        return "LLM copy payload has invalid default_aspect_ratio (must be 4:5 or 9:16)."
    return None


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
            "Do not mention persona names or persona labels verbatim in headline, support_line, trust_line, or bullets",
        ],
        "collisions": collisions,
        "current_copy": current_copy,
        "context": context,
    }
    prompt = (
        "You are fixing ad copy JSON after uniqueness collisions. "
        "Return only corrected JSON object with keys default_aspect_ratio and ads.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    prompt_path = run_dir / "context" / "opencode_repair_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    cmd = [
        "opencode",
        "run",
        "Read the attached repair payload and return corrected JSON only.",
        "--attach",
        api_url,
        "--model",
        model,
        "--format",
        "json",
        "--file",
        str(prompt_path),
    ]
    password = (config.get("opencode_api_key") or "").strip() or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
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


def persona_label(persona_name: str) -> str:
    base = (persona_name or "").split("(", 1)[0].strip()
    return base or "This routine"


def mentions_persona_label(text: str, persona_name: str) -> bool:
    clean_text = _clean_str(text)
    clean_name = _clean_str(persona_name)
    if not clean_text or not clean_name:
        return False
    candidates = {clean_name.casefold()}
    base_name = persona_label(clean_name)
    if base_name:
        candidates.add(base_name.casefold())
    text_folded = clean_text.casefold()
    return any(candidate and candidate in text_folded for candidate in candidates)


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
    default_ratio = str(generated.get("default_aspect_ratio") or "").strip() if isinstance(generated, dict) else ""
    if default_ratio in {"4:5", "9:16"}:
        base["default_aspect_ratio"] = default_ratio

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

        aspect_ratio = _clean_str(candidate.get("aspect_ratio"))
        if aspect_ratio in {"4:5", "9:16"}:
            ad["aspect_ratio"] = aspect_ratio

        angle = _clean_str(candidate.get("headline_angle"))
        if not angle or angle.lower() == "mechanism":
            angle = persona_headline_angle_key(persona_num)
        if angle:
            ad["headline_angle"] = angle

        cand_copy = candidate.get("copy") if isinstance(candidate.get("copy"), dict) else {}
        for lang in ["EN", "HI"]:
            base_lang = ad["copy"][lang]
            src_lang = cand_copy.get(lang) if isinstance(cand_copy.get(lang), dict) else {}

            headline = _clean_str(src_lang.get("headline"))
            cta = _clean_str(src_lang.get("cta"))
            if headline and not mentions_persona_label(headline, persona_name):
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
                if support and not mentions_persona_label(support, persona_name):
                    base_lang["support_line"] = shorten_copy_line(support)
            elif fmt in {"BA", "FEAT"}:
                bullets = _clean_bullets(src_lang.get("bullets"))
                if len(bullets) >= 2:
                    if fmt == "BA":
                        bullets = [strip_ba_panel_label(b) for b in bullets]
                    filtered_bullets = [b for b in bullets if not mentions_persona_label(b, persona_name)]
                    if len(filtered_bullets) >= 2:
                        base_lang["bullets"] = [shorten_copy_line(b, limit=88) for b in filtered_bullets]
            else:
                trust = _clean_str(src_lang.get("trust_line"))
                if trust and not mentions_persona_label(trust, persona_name):
                    base_lang["trust_line"] = shorten_copy_line(trust)

    return base


def build_template_copy(context: dict[str, Any], run_id: str) -> dict[str, Any]:
    ads: list[dict[str, Any]] = []
    headline_en_banned = set(used_text_bucket(context, "headline_en"))
    headline_hi_banned = set(used_text_bucket(context, "headline_hi"))
    support_en_banned = set(used_text_bucket(context, "support_line_en"))
    support_hi_banned = set(used_text_bucket(context, "support_line_hi"))
    cta_en_banned = set(used_text_bucket(context, "cta_en"))
    cta_hi_banned = set(used_text_bucket(context, "cta_hi"))
    bullets_en_banned = set(used_text_bucket(context, "bullets_en"))
    bullets_hi_banned = set(used_text_bucket(context, "bullets_hi"))
    headline_en_seen: set[str] = set()
    headline_hi_seen: set[str] = set()
    support_en_seen: set[str] = set()
    support_hi_seen: set[str] = set()
    bullets_en_seen: set[str] = set()
    bullets_hi_seen: set[str] = set()
    for idx, item in enumerate(context["ads"], start=1):
        persona = item["persona"]
        fmt = item["format"]
        persona_num = int(persona["persona_number"])
        persona_name = persona["persona_name"]

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

        hero_hook_en = persona_headline_hook(persona_num, "EN")
        hero_hook_hi = persona_headline_hook(persona_num, "HI")
        hero_ugc_headline_en = pick_diverse_copy(
            [
                f"{hero_hook_en.capitalize()}, weight-loss support feels easier.",
                f"{hero_hook_en.capitalize()}, this 15-day routine feels more manageable.",
                f"{hero_hook_en.capitalize()}, this plan keeps weight-loss support practical.",
            ],
            headline_en_banned,
            f"{hero_hook_en.capitalize()}, weight-loss support feels easier.",
            headline_en_seen,
        )
        hero_ugc_headline_hi = pick_diverse_copy(
            [
                f"{hero_hook_hi.capitalize()}, वजन घटाने का support आसान लगता है।",
                f"{hero_hook_hi.capitalize()}, यह 15 दिन का routine ज्यादा manageable लगता है।",
                f"{hero_hook_hi.capitalize()}, यह plan वजन घटाने के support को practical बनाता है।",
            ],
            headline_hi_banned,
            f"{hero_hook_hi.capitalize()}, वजन घटाने का support आसान लगता है।",
            headline_hi_seen,
        )
        hero_ugc_support_en = pick_diverse_copy(
            [
                f"Built for {hero_hook_en}; appetite control and digestion support stay easy to follow.",
                f"A calmer way to keep weight-loss follow-through steady {hero_hook_en}.",
                f"Practical support for daily consistency {hero_hook_en}, without harsh pressure.",
            ],
            support_en_banned,
            f"Practical support for daily consistency {hero_hook_en}.",
            support_en_seen,
        )
        hero_ugc_support_hi = pick_diverse_copy(
            [
                f"{hero_hook_hi} के लिए बनाया गया; appetite control और digestion support follow करना आसान रखते हैं।",
                f"{hero_hook_hi} में weight-loss follow-through steady रखने का calmer तरीका।",
                f"{hero_hook_hi} में daily consistency के लिए practical support, बिना harsh pressure के।",
            ],
            support_hi_banned,
            f"{hero_hook_hi} के लिए practical support।",
            support_hi_seen,
        )

        ba_hook_en = persona_headline_hook(persona_num, "EN")
        ba_hook_hi = persona_headline_hook(persona_num, "HI")
        ba_headline_en = pick_diverse_copy(
            [
                f"From {pain_en.rstrip('.')} to steadier weight-loss progress {ba_hook_en}.",
                f"{ba_hook_en.capitalize()}, this routine turns friction into clearer weight-loss movement.",
                f"Less struggle, more structure {ba_hook_en} for practical weight-loss follow-through.",
            ],
            headline_en_banned,
            f"From {pain_en.rstrip('.')} to steadier weight-loss progress {ba_hook_en}.",
            headline_en_seen,
        )
        ba_headline_hi = pick_diverse_copy(
            [
                f"{pain_hi.rstrip('।')} से {ba_hook_hi} वाली steadier weight-loss progress तक।",
                f"{ba_hook_hi.capitalize()}, यह routine friction को साफ weight-loss movement में बदलता है।",
                f"कम struggle, ज्यादा structure {ba_hook_hi} के साथ practical weight-loss follow-through।",
            ],
            headline_hi_banned,
            f"{pain_hi.rstrip('।')} से {ba_hook_hi} वाली steadier weight-loss progress तक।",
            headline_hi_seen,
        )

        test_hook_en = persona_headline_hook(persona_num, "EN")
        test_hook_hi = persona_headline_hook(persona_num, "HI")
        test_headline_en = pick_diverse_copy(
            [
                f'"{test_hook_en.capitalize()}, this finally felt manageable for weight loss."',
                f'"{test_hook_en.capitalize()}, I could actually stick with this weight-loss routine."',
                f'"{test_hook_en.capitalize()}, I finally found practical weight-loss support."',
            ],
            headline_en_banned,
            f'"{test_hook_en.capitalize()}, this finally felt manageable for weight loss."',
            headline_en_seen,
        )
        test_headline_hi = pick_diverse_copy(
            [
                f'"{test_hook_hi.capitalize()}, यह weight-loss routine आखिर manageable लगा।"',
                f'"{test_hook_hi.capitalize()}, मैं इस weight-loss routine को जारी रख सका।"',
                f'"{test_hook_hi.capitalize()}, मुझे practical weight-loss support आखिर मिला।"',
            ],
            headline_hi_banned,
            f'"{test_hook_hi.capitalize()}, यह weight-loss routine आखिर manageable लगा।"',
            headline_hi_seen,
        )

        feat_hook_en = persona_headline_hook(persona_num, "EN")
        feat_hook_hi = persona_headline_hook(persona_num, "HI")
        feat_headline_en = pick_diverse_copy(
            [
                f"What changes {feat_hook_en} with this 15-day weight-loss system?",
                f"Why this weight-loss system feels easier {feat_hook_en}.",
                f"How this 15-day system supports steadier follow-through {feat_hook_en}.",
            ],
            headline_en_banned,
            f"What changes {feat_hook_en} with this 15-day weight-loss system?",
            headline_en_seen,
        )
        feat_headline_hi = pick_diverse_copy(
            [
                f"{feat_hook_hi} में यह 15-दिन weight-loss system क्या बदलता है?",
                f"{feat_hook_hi} में यह weight-loss system ज्यादा आसान क्यों लगता है?",
                f"{feat_hook_hi} में यह 15-दिन system steadier follow-through कैसे support करता है?",
            ],
            headline_hi_banned,
            f"{feat_hook_hi} में यह 15-दिन weight-loss system क्या बदलता है?",
            headline_hi_seen,
        )
        feat_headline_en = pick_diverse_copy(
            [
                f"What changes {feat_hook_en} with this 15-day weight-loss system?",
                f"Why this weight-loss system feels easier {feat_hook_en}.",
                f"How this 15-day system supports steadier follow-through {feat_hook_en}.",
            ],
            headline_en_banned,
            f"What changes {feat_hook_en} with this 15-day weight-loss system?",
            headline_en_seen,
        )
        feat_headline_hi = pick_diverse_copy(
            [
                f"{feat_hook_hi} में यह 15-दिन weight-loss system क्या बदलता है?",
                f"{feat_hook_hi} में यह weight-loss system ज्यादा आसान क्यों लगता है?",
                f"{feat_hook_hi} में यह 15-दिन system steadier follow-through कैसे support करता है?",
            ],
            headline_hi_banned,
            f"{feat_hook_hi} में यह 15-दिन weight-loss system क्या बदलता है?",
            headline_hi_seen,
        )

        bullets_en = [
            pick_diverse_copy(
                [
                    f"Morning OK Liquid supports appetite control {feat_hook_en}.",
                    f"Morning OK Liquid keeps cravings easier to manage {feat_hook_en}.",
                    f"The AM step gives the day a simpler weight-loss start {feat_hook_en}.",
                ],
                bullets_en_banned,
                f"Morning OK Liquid supports appetite control {feat_hook_en}.",
                bullets_en_seen,
            ),
            pick_diverse_copy(
                [
                    f"Night Tablet and Powder support digestion and routine follow-through {feat_hook_en}.",
                    f"Night support helps the plan feel lighter and easier to continue {feat_hook_en}.",
                    f"The PM step keeps digestion support and routine consistency together {feat_hook_en}.",
                ],
                bullets_en_banned,
                f"Night Tablet and Powder support digestion and routine follow-through {feat_hook_en}.",
                bullets_en_seen,
            ),
            pick_diverse_copy(
                [
                    f"The full 15-day system keeps weight-loss support practical, repeatable, and less overwhelming {feat_hook_en}.",
                    f"This 15-day system keeps the routine simple enough to repeat {feat_hook_en}.",
                    f"Clear structure makes steady follow-through feel more realistic {feat_hook_en}.",
                ],
                bullets_en_banned,
                f"The full 15-day system keeps weight-loss support practical, repeatable, and less overwhelming {feat_hook_en}.",
                bullets_en_seen,
            ),
        ]
        bullets_hi = [
            pick_diverse_copy(
                [
                    f"Morning OK Liquid appetite control को {feat_hook_hi} में support करता है।",
                    f"Morning OK Liquid cravings को {feat_hook_hi} में manage करना आसान बनाता है।",
                    f"AM step दिन की weight-loss शुरुआत को सरल बनाता है {feat_hook_hi} में।",
                ],
                bullets_hi_banned,
                f"Morning OK Liquid appetite control को {feat_hook_hi} में support करता है।",
                bullets_hi_seen,
            ),
            pick_diverse_copy(
                [
                    f"Night Tablet और Powder digestion और routine follow-through को {feat_hook_hi} में support करते हैं।",
                    f"Night support plan को हल्का और जारी रखने योग्य बनाता है {feat_hook_hi} में।",
                    f"PM step digestion support और routine consistency को साथ रखता है {feat_hook_hi} में।",
                ],
                bullets_hi_banned,
                f"Night Tablet और Powder digestion और routine follow-through को {feat_hook_hi} में support करते हैं।",
                bullets_hi_seen,
            ),
            pick_diverse_copy(
                [
                    f"पूरा 15-दिन system weight-loss support को practical, repeatable, और कम overwhelming रखता है {feat_hook_hi} में।",
                    f"यह 15-दिन system routine को इतना simple रखता है कि उसे repeat करना आसान हो {feat_hook_hi} में।",
                    f"Clear structure steady follow-through को ज्यादा realistic बनाता है {feat_hook_hi} में।",
                ],
                bullets_hi_banned,
                f"पूरा 15-दिन system weight-loss support को practical, repeatable, और कम overwhelming रखता है {feat_hook_hi} में।",
                bullets_hi_seen,
            ),
        ]

        cta_en = pick_unused_copy(["See The Steps", "Know The Routine", "Understand The Plan", "Start My Plan"], cta_en_banned, "See The Plan")
        cta_hi = pick_unused_copy(["स्टेप्स देखें", "रूटीन जानें", "प्लान समझें", "मेरा प्लान शुरू करें"], cta_hi_banned, "प्लान देखें")
        test_trust_line_en = pick_diverse_copy(
            [
                f"Structured support for {test_hook_en}; clearer weight-loss follow-through without harsh pressure.",
                f"Practical appetite and digestion support {test_hook_en} for steadier weight-loss progress.",
                f"Built to feel safer, simpler, and easier to continue {test_hook_en}.",
            ],
            support_en_banned,
            f"Structured support for visible weight-loss progress and steadier follow-through {test_hook_en}.",
            support_en_seen,
        )
        test_trust_line_hi = pick_diverse_copy(
            [
                f"{test_hook_hi} के लिए structured support; ज़्यादा clear weight-loss follow-through, बिना harsh pressure के।",
                f"{test_hook_hi} में practical appetite और digestion support steadier weight-loss progress के लिए।",
                f"{test_hook_hi} में इसे safer, simpler, और easy to continue बनाने के लिए।",
            ],
            support_hi_banned,
            f"{test_hook_hi} के लिए structured support; clearer weight-loss follow-through.",
            support_hi_seen,
        )

        copy_en: dict[str, Any]
        copy_hi: dict[str, Any]
        if fmt in {"HERO", "UGC"}:
            copy_en = {"headline": hero_ugc_headline_en, "support_line": hero_ugc_support_en, "cta": cta_en}
            copy_hi = {"headline": hero_ugc_headline_hi, "support_line": hero_ugc_support_hi, "cta": cta_hi}
            add_used_text_bucket(headline_en_banned, [hero_ugc_headline_en])
            add_used_text_bucket(headline_hi_banned, [hero_ugc_headline_hi])
            add_used_text_bucket(support_en_banned, [hero_ugc_support_en])
            add_used_text_bucket(support_hi_banned, [hero_ugc_support_hi])
        elif fmt == "BA":
            bullets_en = [
                pick_unused_copy([f"{pain_en.rstrip('.')} so weight-loss efforts keep feeling stuck.", "Cravings and uneven eating keep weight-loss progress from moving."], bullets_en_banned, f"{pain_en.rstrip('.')} and progress keeps stalling."),
                pick_unused_copy([f"{friction_en.rstrip('.')} so safer weight-loss routines feel hard to trust.", "Harsh methods make steady weight-loss follow-through harder to maintain."], bullets_en_banned, f"{friction_en.rstrip('.')} and consistency drops."),
                pick_unused_copy(["Morning appetite support and night digestion support make weight loss easier to follow.", "The AM-PM structure supports appetite control and steadier weight-loss adherence."], bullets_en_banned, "The two-step structure supports steadier weight-loss follow-through."),
                pick_unused_copy(["That day-by-day follow-through supports visible 15-day weight-loss progress.", "Better routine adherence makes visible 15-day weight-loss movement more believable."], bullets_en_banned, "Steadier follow-through supports visible 15-day weight-loss progress."),
            ]
            bullets_hi = [
                pick_unused_copy(["शाम की cravings और असमान eating pattern से weight-loss progress अटकती है।", "वजन घटाने की कोशिश pain point के कारण बार-बार रुकती है।"], bullets_hi_banned, "cravings और uneven eating से weight-loss progress अटकती है।"),
                pick_unused_copy(["harsh methods का डर safer weight-loss routine पर भरोसा कम करता है।", "कठिन तरीके consistency और trust दोनों को कमजोर करते हैं।"], bullets_hi_banned, "harsh method का डर consistency घटाता है।"),
                pick_unused_copy(["सुबह appetite support और रात digestion support से weight loss निभाना आसान होता है।", "AM-PM structure weight-loss adherence को ज्यादा steady बनाता है।"], bullets_hi_banned, "दो-स्टेप structure weight-loss follow-through को steady बनाता है।"),
                pick_unused_copy(["यही follow-through 15 दिन की visible weight-loss progress को support करता है।", "बेहतर routine adherence से 15 दिन की weight-loss movement ज्यादा believable लगती है।"], bullets_hi_banned, "steady follow-through 15 दिन की visible weight-loss progress को support करता है।"),
            ]
            copy_en = {"headline": ba_headline_en, "bullets": bullets_en, "cta": cta_en}
            copy_hi = {"headline": ba_headline_hi, "bullets": bullets_hi, "cta": cta_hi}
            add_used_text_bucket(headline_en_banned, [ba_headline_en])
            add_used_text_bucket(headline_hi_banned, [ba_headline_hi])
            add_used_text_bucket(bullets_en_banned, bullets_en)
            add_used_text_bucket(bullets_hi_banned, bullets_hi)
        elif fmt == "FEAT":
            bullets_en = [
                pick_unused_copy(["Morning OK Liquid supports fullness and fewer cravings for weight loss.", "OK Liquid helps reduce random eating pressure so weight loss feels more manageable."], bullets_en_banned, "OK Liquid supports appetite control for weight loss."),
                pick_unused_copy(["Night Tablet and Powder support digestion and gut comfort for steadier follow-through.", "Tablet plus Powder support lighter digestion so the routine feels easier to continue."], bullets_en_banned, "Night support helps digestion and routine follow-through."),
                pick_unused_copy(["The full 15-day system is built for visible weight-loss support without harsh pressure.", "This structured plan supports visible weight-loss progress without crash-diet intensity."], bullets_en_banned, "This 15-day system supports visible weight-loss progress."),
            ]
            bullets_hi = [
                pick_unused_copy(["सुबह का OK Liquid fullness और कम cravings के साथ weight loss support देता है।", "OK Liquid random eating pressure घटाकर weight loss को ज्यादा manageable बनाता है।"], bullets_hi_banned, "OK Liquid weight loss के लिए appetite control support देता है।"),
                pick_unused_copy(["रात का Tablet और Powder digestion और gut comfort के साथ better follow-through support देते हैं।", "Tablet plus Powder पाचन को हल्का रखकर routine जारी रखना आसान बनाते हैं।"], bullets_hi_banned, "रात का support digestion और routine follow-through में मदद करता है।"),
                pick_unused_copy(["पूरा 15-दिन system harsh pressure के बिना visible weight-loss support के लिए बना है।", "यह structured plan crash-diet intensity के बिना visible weight-loss progress support करता है।"], bullets_hi_banned, "यह 15-दिन system visible weight-loss progress support करता है।"),
            ]
            copy_en = {"headline": feat_headline_en, "bullets": bullets_en, "cta": cta_en}
            copy_hi = {"headline": feat_headline_hi, "bullets": bullets_hi, "cta": cta_hi}
            add_used_text_bucket(headline_en_banned, [feat_headline_en])
            add_used_text_bucket(headline_hi_banned, [feat_headline_hi])
            add_used_text_bucket(bullets_en_banned, bullets_en)
            add_used_text_bucket(bullets_hi_banned, bullets_hi)
        else:
            copy_en = {
                "headline": test_headline_en,
                "attribution": "Doctor-formulated Ayurvedic weight-loss protocol",
                "trust_line": test_trust_line_en,
                "cta": cta_en,
            }
            copy_hi = {
                "headline": test_headline_hi,
                "attribution": "डॉक्टर-फॉर्मुलेटेड आयुर्वेदिक obesity और weight-loss प्रोटोकॉल",
                "trust_line": test_trust_line_hi,
                "cta": cta_hi,
            }
            add_used_text_bucket(headline_en_banned, [test_headline_en])
            add_used_text_bucket(headline_hi_banned, [test_headline_hi])
            add_used_text_bucket(support_en_banned, [copy_en["trust_line"]])
            add_used_text_bucket(support_hi_banned, [copy_hi["trust_line"]])

        add_used_text_bucket(cta_en_banned, [cta_en])
        add_used_text_bucket(cta_hi_banned, [cta_hi])

        ads.append(
            {
                "format": fmt,
                "headline_angle": persona_headline_angle_key(persona_num),
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
    api_key = (config.get("opencode_api_key") or "").strip()
    model = sanitize_dashboard_model((config.get("opencode_model") or "").strip(), list_opencode_models())
    if not api_url:
        return None

    language_mode = resolve_language_mode(config)
    system = (
        "You generate ad copy JSON only. Return valid JSON with keys default_aspect_ratio and ads. "
        "Each ads item must include format, headline_angle, persona fields and copy.EN/copy.HI fields compatible with assembler. "
        "Return exactly one ads item for each context.ads item, in the same order. Do not omit, merge, or reduce items. "
        "Each persona object must use this exact schema: number, name, pain_en, desire_en, friction_en, proof_needed_en, tone_cue_en, pain_hi, desire_hi, friction_hi, proof_needed_hi, tone_cue_hi. "
        "Every ad unit must make the obesity and weight-loss intent obvious to a first-time viewer. "
        "At minimum, headline or support line must explicitly mention weight loss, obesity reduction, excess-weight reduction, or a direct 15-day result framing. "
        "Avoid abstract lines that hide the product goal. "
        "Use persona fields only as targeting context; never mention the persona name or label verbatim in headline, support_line, trust_line, or bullets. "
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
        "Use each persona's headline_angle_key and headline_hook values so personas in the same format land on clearly different angles, not just lightly reworded templates. "
        "Ensure obesity and weight-loss intent is obvious to someone who has never heard of the product."
    )
    user_payload = {
        "task": "Generate fresh ad copy JSON for provided context.",
        "context": context,
        "constraints": {
            "language": ["EN", "HI"],
            "language_mode": language_mode,
            "formats": FORMATS,
            "required_persona_schema": [
                "number",
                "name",
                "pain_en",
                "desire_en",
                "friction_en",
                "proof_needed_en",
                "tone_cue_en",
                "pain_hi",
                "desire_hi",
                "friction_hi",
                "proof_needed_hi",
                "tone_cue_hi"
            ],
            "return_json_only": True,
        },
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.7,
    }

    cli_prompt = (
        "SYSTEM:\n"
        f"{system}\n\n"
        "USER_PAYLOAD_JSON:\n"
        f"{json.dumps(user_payload, ensure_ascii=False)}\n\n"
        "Return only valid JSON. No markdown. No extra text."
    )
    prompt_path = run_dir / "context" / "opencode_generate_prompt.txt"
    prompt_path.write_text(cli_prompt, encoding="utf-8")

    cli_cmd = [
        "opencode",
        "run",
        "Read the attached generation payload and return valid JSON only.",
        "--attach",
        api_url,
        "--model",
        model,
        "--format",
        "json",
        "--file",
        str(prompt_path),
    ]
    cli_password = api_key or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    if cli_password:
        cli_cmd.extend(["--password", cli_password])

    try:
        cli_result = run_cmd(cli_cmd, cwd=ROOT)
    except OSError as exc:
        cli_result = subprocess.CompletedProcess(cli_cmd, returncode=1, stdout="", stderr=str(exc))
    if cli_result.returncode == 0:
        parsed = parse_opencode_json_output(cli_result.stdout)
        if parsed is not None:
            return parsed

        (run_dir / "logs" / "opencode_error.txt").write_text(
            "OpenCode CLI returned no parseable JSON text block.\n"
            f"STDOUT:\n{cli_result.stdout}\n\nSTDERR:\n{cli_result.stderr}",
            encoding="utf-8",
        )
        return None

    cli_error = (
        "OpenCode CLI attach call failed.\n"
        f"Command: {' '.join(cli_cmd[:-1])} <prompt>\n"
        f"Return code: {cli_result.returncode}\n"
        f"STDOUT:\n{cli_result.stdout}\n\nSTDERR:\n{cli_result.stderr}"
    )

    req = urllib.request.Request(
        url=api_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read().decode("utf-8")
        parsed = json.loads(raw)
        content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return None
        return parse_json_object_from_text(content)
    except Exception as exc:
        (run_dir / "logs" / "opencode_error.txt").write_text(
            cli_error + "\n\nOpenAI-style HTTP fallback failed:\n" + str(exc),
            encoding="utf-8",
        )
        return None


def collect_run_result(run_dir: Path, batch_name: str, image_generated: bool) -> dict[str, Any]:
    output_dir = ROOT / "output" / batch_name
    prompt_files = []
    if output_dir.exists():
        for file in sorted(output_dir.glob("**/OUTPUT_*.txt")):
            prompt_files.append(str(file.relative_to(ROOT)))

    image_files: list[str] = []
    if image_generated:
        image_dir = ROOT / "generated_image" / batch_name
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
    image_dir = ROOT / "generated_image" / batch_name
    image_files: list[str] = []
    if not image_dir.exists():
        return image_files
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
        "active_images": read_active_images(DEFAULT_ACTIVE_IMAGES),
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
    seen_batches: set[str] = set()
    for run_dir in sorted(RUNS_ROOT.glob("run_*"), reverse=True):
        manifest = run_dir / "manifest.json"
        if manifest.exists():
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            refreshed = refresh_manifest_file_state(run_dir, payload)
            batch_name = str(refreshed.get("batch") or "").strip()
            if refreshed.get("prompt_files") and (not batch_name or batch_name not in seen_batches):
                runs.append(refreshed)
                if batch_name:
                    seen_batches.add(batch_name)
            if len(runs) >= 5:
                break
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

    kie_api_key = str(os.getenv("KIE_API_KEY") or "").strip()
    if not kie_api_key:
        raise HTTPException(status_code=400, detail="KIE_API_KEY missing. Set it in root .env.dashboard")

    prompt_files = payload.get("prompt_files")
    if not isinstance(prompt_files, list) or not prompt_files:
        raise HTTPException(status_code=400, detail="prompt_files must be a non-empty array")

    selected_45 = validate_selected_45_prompts(batch, prompt_files)
    if not selected_45:
        raise HTTPException(status_code=400, detail="No valid 4:5 prompt files selected")

    active_images_file = str(manifest.get("active_images_file") or DEFAULT_ACTIVE_IMAGES)
    cmd = [
        "python3",
        "scripts/kie_nano_batch.py",
        "--batch",
        batch,
        "--api-key",
        kie_api_key,
        "--active-images-file",
        active_images_file,
        "--language",
        "BOTH",
        "--aspect-ratio",
        "4:5",
        "--max-variations-per-format",
        "999",
        "--prompt-files",
        *selected_45,
    ]
    result = run_cmd(cmd, cwd=ROOT)
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "image_generation_45_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"Image generation failed (4:5): {short_error}")

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

    kie_api_key = str(os.getenv("KIE_API_KEY") or "").strip()
    if not kie_api_key:
        raise HTTPException(status_code=400, detail="KIE_API_KEY missing. Set it in root .env.dashboard")

    cloudinary_cloud_name = str(os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip()
    cloudinary_api_key = str(os.getenv("CLOUDINARY_API_KEY") or "").strip()
    cloudinary_api_secret = str(os.getenv("CLOUDINARY_API_SECRET") or "").strip()
    if not cloudinary_cloud_name or not cloudinary_api_key or not cloudinary_api_secret:
        raise HTTPException(
            status_code=400,
            detail="Cloudinary credentials missing. Set CLOUDINARY_CLOUD_NAME/CLOUDINARY_API_KEY/CLOUDINARY_API_SECRET in root .env.dashboard",
        )

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
    uploaded_refs: dict[str, str] = {}
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
        cloudinary_url = upload_image_to_cloudinary(image_path, cloudinary_cloud_name, cloudinary_api_key, cloudinary_api_secret)
        prompt_reference_map[prompt_96] = [cloudinary_url]
        uploaded_refs[prompt_96] = cloudinary_url

    if not prompt_reference_map:
        raise HTTPException(status_code=400, detail="Could not build 9:16 reference images from selected 4:5 outputs")

    map_path = run_dir / "context" / "prompt_reference_map_916.json"
    map_path.write_text(json.dumps(prompt_reference_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cmd = [
        "python3",
        "scripts/kie_nano_batch.py",
        "--batch",
        batch,
        "--api-key",
        kie_api_key,
        "--language",
        "BOTH",
        "--aspect-ratio",
        "9:16",
        "--max-variations-per-format",
        "999",
        "--prompt-files",
        *sorted(prompt_reference_map.keys()),
        "--prompt-reference-map",
        str(map_path),
        "--reference-conversion-mode",
        "outpaint_45_to_96",
    ]
    result = run_cmd(cmd, cwd=ROOT)
    if result.returncode != 0:
        error_text = result.stderr or result.stdout
        (run_dir / "logs" / "image_generation_916_from_45_error.txt").write_text(error_text, encoding="utf-8")
        short_error = "\n".join([line for line in error_text.splitlines() if line.strip()][-12:])
        raise HTTPException(status_code=500, detail=f"Image generation failed (9:16 from 4:5 refs): {short_error}")

    refreshed = collect_run_result(run_dir, batch, True)
    refreshed["generated_images_for_prompts_916"] = sorted(prompt_reference_map.keys())
    refreshed["uploaded_reference_urls_916"] = uploaded_refs
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
    active_images_file: UploadFile | None = File(None),
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
    active_images_path = save_upload(run_dir / "inputs" / "activeimages.txt", active_images_file)

    product_file = coalesce_path(product_path, DEFAULT_PRODUCT_INFO)
    mechanism_file_path = coalesce_path(mechanism_path, DEFAULT_MECHANISM)
    faq_file_path = coalesce_path(faq_path, DEFAULT_FAQ)

    if not active_images_path:
        override_urls = cfg.get("active_image_urls") or []
        if override_urls:
            lines = [line.strip() for line in override_urls if str(line).strip()]
            active_images_path = run_dir / "inputs" / "activeimages.txt"
            active_images_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    active_images_file_path = coalesce_path(active_images_path, DEFAULT_ACTIVE_IMAGES)

    try:
        plan = resolve_format_plan(cfg)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    product_ctx_source = "verbatim_source_chunks"
    extractor_model = "none"
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
    (run_dir / "context" / "product_context_chunks.json").write_text(
        json.dumps(product_ctx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    persona_library = parse_persona_library(DEFAULT_PLAYBOOK)
    ads_context: list[dict[str, Any]] = []
    for item in plan:
        persona_no = item["persona"]
        fmt = item["format"]
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
        ads_context.append({"persona": persona_payload, "format_rules": format_payload, "format": fmt})

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
    if copy_json is None:
        raise HTTPException(status_code=500, detail="LLM generation failed: no parseable copy payload returned")
    llm_mode = "opencode"
    copy_json = coerce_generated_copy_schema(copy_json, full_context)
    payload_error = validate_llm_copy_payload(copy_json, full_context)
    if payload_error:
        raise HTTPException(status_code=500, detail=payload_error)
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
                copy_json = coerce_generated_copy_schema(repaired, full_context)
                payload_error = validate_llm_copy_payload(copy_json, full_context)
                if payload_error:
                    raise HTTPException(status_code=500, detail=payload_error)
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
                    str(active_images_file_path),
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
    manifest["active_images_file"] = str(active_images_file_path)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


app.mount("/storage", StaticFiles(directory=str(STORAGE_ROOT)), name="storage")
app.mount("/output", StaticFiles(directory=str(ROOT / "output")), name="output")
app.mount("/generated_image", StaticFiles(directory=str(ROOT / "generated_image")), name="generated_image")
app.mount("/", StaticFiles(directory=str(ROOT / "dashboard" / "frontend"), html=True), name="frontend")
