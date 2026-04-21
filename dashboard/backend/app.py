#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = ROOT / "dashboard_storage"
RUNS_ROOT = STORAGE_ROOT / "runs"
RUNTIME_ROOT = ROOT / "runtime"

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


def build_persona_payload(persona_number: int, personas: list[dict[str, Any]]) -> dict[str, Any]:
    persona_name = f"Persona {persona_number}"
    for item in personas:
        if int(item.get("number") or 0) == persona_number:
            name = str(item.get("name") or "").strip()
            if name:
                persona_name = name
            break
    return {
        "persona_number": persona_number,
        "persona_name": persona_name,
        "pain_points": [],
        "trigger_scenarios": [],
        "objections": [],
        "language_bank": [],
        "core_message": [],
        "grounded_mechanism_map": [],
        "how_kit_solves": [],
        "trust_anchors": [],
        "english_ready": [],
        "hindi_ready": [],
    }


def read_active_images(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


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


def build_opencode_catalog() -> dict[str, Any]:
    models = list_opencode_models()
    provider_labels = list_opencode_provider_labels()
    provider_ids = {line.split("/", 1)[0] for line in models}

    known_providers = ["opencode", "github-copilot"]
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

    providers = sorted(provider_ids)
    grouped: dict[str, list[str]] = {provider: [] for provider in providers}
    for model in models:
        provider = model.split("/", 1)[0]
        grouped.setdefault(provider, []).append(model)
    for provider in grouped:
        grouped[provider] = sorted(grouped[provider])
    default_model = ""
    if models:
        default_model = "github-copilot/gpt-5.3-codex" if "github-copilot/gpt-5.3-codex" in models else models[0]
    return {
        "api_url": DEFAULT_OPENCODE_API_URL,
        "providers": providers,
        "provider_labels": provider_labels,
        "models_by_provider": grouped,
        "default_model": default_model,
    }


def choose_extractor_model(config: dict[str, Any]) -> str:
    explicit = (config.get("opencode_extractor_model") or "").strip()
    if explicit:
        return explicit

    models = list_opencode_models()
    if models:
        preferred_checks = [
            lambda m: "bigpickle" in m,
            lambda m: "minimax" in m and "free" in m,
            lambda m: "minimax" in m,
        ]
        lowered = [m.lower() for m in models]
        for check in preferred_checks:
            for idx, lower in enumerate(lowered):
                if check(lower):
                    return models[idx]

    selected = (config.get("opencode_model") or "").strip()
    return selected or "gpt-5.3-codex"


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
                    block[key] = strip_internal_marker(block[key])
            if isinstance(block.get("bullets"), list):
                block["bullets"] = [strip_internal_marker(x) for x in block["bullets"] if isinstance(x, str)]
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


def call_opencode_repair_copy(
    config: dict[str, Any],
    context: dict[str, Any],
    current_copy: dict[str, Any],
    collisions: list[dict[str, Any]],
    run_dir: Path,
) -> dict[str, Any] | None:
    api_url = (config.get("opencode_api_url") or "").strip()
    model = (config.get("opencode_model") or "gpt-5.3-codex").strip()
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
        "context": context,
    }
    prompt = (
        "You are fixing ad copy JSON after uniqueness collisions. "
        "Return only corrected JSON object with keys default_aspect_ratio and ads.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    cmd = [
        "opencode",
        "run",
        "--attach",
        api_url,
        "--model",
        model,
        "--format",
        "json",
        prompt,
    ]
    password = (config.get("opencode_api_key") or "").strip() or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    if password:
        cmd.extend(["--password", password])

    result = run_cmd(cmd, cwd=ROOT)
    if result.returncode != 0:
        (run_dir / "logs" / "opencode_repair_error.txt").write_text(
            f"Repair command failed\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}", encoding="utf-8"
        )
        return None

    text_chunks: list[str] = []
    for raw_line in result.stdout.splitlines():
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

    if not text_chunks:
        return None

    content = "\n".join(text_chunks)
    return parse_json_object_from_text(content)


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

            if fmt in {"HERO", "UGC"}:
                support = _clean_str(src_lang.get("support_line"))
                if support:
                    base_lang["support_line"] = shorten_copy_line(support)
            elif fmt in {"BA", "FEAT"}:
                bullets = _clean_bullets(src_lang.get("bullets"))
                if len(bullets) >= 2:
                    base_lang["bullets"] = [shorten_copy_line(b, limit=88) for b in bullets]
            else:
                attribution = _clean_str(src_lang.get("attribution"))
                trust = _clean_str(src_lang.get("trust_line"))
                if attribution:
                    base_lang["attribution"] = shorten_copy_line(attribution, limit=86)
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
            headline_en = f"From craving-led eating to steadier daily control {unique}."
            headline_hi = f"बार-बार cravings से रोज़ाना बेहतर नियंत्रण तक {unique}।"
        else:
            headline_en = f"{persona_name}: build a simpler weight routine today {unique}."
            headline_hi = f"{persona_name}: आज से सरल वजन रूटीन शुरू करें {unique}।"
        cta_en = f"Start Now {unique}"
        cta_hi = f"अभी शुरू करें {unique}"

        copy_en: dict[str, Any]
        copy_hi: dict[str, Any]
        if fmt in {"HERO", "UGC"}:
            support_en = f"Ayurvedic hunger and digestion support helps weight control consistency {unique}."
            support_hi = f"आयुर्वेदिक भूख और पाचन सपोर्ट वजन नियंत्रण की निरंतरता में सहायक है {unique}।"
            copy_en = {"headline": headline_en, "support_line": support_en, "cta": cta_en}
            copy_hi = {"headline": headline_hi, "support_line": support_hi, "cta": cta_hi}
        elif fmt in {"BA", "FEAT"}:
            bullets_en = [
                f"Morning step supports calmer appetite control {unique}.",
                f"Night step supports lighter digestion consistency {unique}.",
                f"No crash diet, no heavy workout pressure {unique}.",
            ]
            bullets_hi = [
                f"सुबह का स्टेप भूख को अधिक स्थिर रखने में सहायक है {unique}।",
                f"रात का स्टेप पाचन की नियमितता को सपोर्ट करता है {unique}।",
                f"न crash diet, न भारी workout दबाव {unique}।",
            ]
            copy_en = {"headline": headline_en, "bullets": bullets_en, "cta": cta_en}
            copy_hi = {"headline": headline_hi, "bullets": bullets_hi, "cta": cta_hi}
        else:
            copy_en = {
                "headline": headline_en,
                "attribution": "Ayurvedic routine with structured daily protocol",
                "trust_line": f"Trusted framework with clear morning and night usage steps {unique}.",
                "cta": cta_en,
            }
            copy_hi = {
                "headline": headline_hi,
                "attribution": "संरचित दैनिक प्रोटोकॉल वाला आयुर्वेदिक रूटीन",
                "trust_line": f"सुबह और रात के साफ स्टेप्स के साथ भरोसेमंद रूटीन {unique}।",
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
    api_key = (config.get("opencode_api_key") or "").strip()
    model = (config.get("opencode_model") or "gpt-5.3-codex").strip()
    if not api_url:
        return None

    language_mode = resolve_language_mode(config)
    system = (
        "You generate ad copy JSON only. Return valid JSON with keys default_aspect_ratio and ads. "
        "Each ads item must include format, headline_angle, persona fields and copy.EN/copy.HI fields compatible with assembler."
    )
    user_payload = {
        "task": "Generate fresh ad copy JSON for provided context.",
        "context": context,
        "constraints": {
            "language": ["EN", "HI"],
            "language_mode": language_mode,
            "formats": FORMATS,
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

    cli_cmd = [
        "opencode",
        "run",
        "--attach",
        api_url,
        "--model",
        model,
        "--format",
        "json",
        cli_prompt,
    ]
    cli_password = api_key or os.getenv("OPENCODE_SERVER_PASSWORD", "").strip()
    if cli_password:
        cli_cmd.extend(["--password", cli_password])

    cli_result = run_cmd(cli_cmd, cwd=ROOT)
    if cli_result.returncode == 0:
        text_chunks: list[str] = []
        for raw_line in cli_result.stdout.splitlines():
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
            content = "\n".join(text_chunks).strip()
            parsed = parse_json_object_from_text(content)
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


def collect_45_visual_locks(batch: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    ratio_dir = ROOT / "output" / batch / "45"
    if not ratio_dir.exists():
        return out
    for prompt_file in sorted(ratio_dir.glob("OUTPUT_*_EN.txt")) + sorted(ratio_dir.glob("OUTPUT_*_HI.txt")):
        match = re.match(r"^OUTPUT_([A-Z]+)_(EN|HI)\.txt$", prompt_file.name)
        if not match:
            continue
        fmt = match.group(1)
        current = out.get(fmt, {})
        text = prompt_file.read_text(encoding="utf-8", errors="ignore")
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
            out[fmt] = current
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
        lock = locks.get(fmt) or {}
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
    runs = []
    for run_dir in sorted(RUNS_ROOT.glob("run_*"), reverse=True):
        manifest = run_dir / "manifest.json"
        if manifest.exists():
            runs.append(json.loads(manifest.read_text(encoding="utf-8")))
    return {"runs": runs}


@app.get("/api/runs/{run_id}")
def api_run(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_ROOT / run_id
    manifest = run_dir / "manifest.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    return json.loads(manifest.read_text(encoding="utf-8"))


@app.post("/api/runs/{run_id}/generate-916")
def api_run_generate_916(run_id: str) -> dict[str, Any]:
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

    copy_json = json.loads(copy_path.read_text(encoding="utf-8"))
    copy_916 = force_aspect_ratio(copy_json, "9:16")
    visual_locks = collect_45_visual_locks(batch)
    if visual_locks:
        copy_916 = apply_visual_locks(copy_916, visual_locks)
    copy_916_path = run_dir / "context" / "copy_batch_916.json"
    copy_916_path.write_text(json.dumps(copy_916, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    run_context_path = run_dir / "context" / "run_context.json"
    assembler_mode = "BOTH"
    if run_context_path.exists():
        try:
            run_context = json.loads(run_context_path.read_text(encoding="utf-8"))
            lang_mode = str(run_context.get("language_mode") or "ALL").upper()
            if lang_mode == "EN":
                assembler_mode = "EN"
            elif lang_mode == "HI":
                assembler_mode = "HI"
        except Exception:
            pass

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

    updated = collect_run_result(run_dir, batch, bool(manifest.get("image_generated", False)))
    updated["generated_variant"] = "9:16"
    return updated


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
                product_ctx = {
                    "product_info": generated_ctx.get("product_info") if isinstance(generated_ctx.get("product_info"), list) else [],
                    "mechanism": generated_ctx.get("mechanism") if isinstance(generated_ctx.get("mechanism"), list) else [],
                    "faq": generated_ctx.get("faq") if isinstance(generated_ctx.get("faq"), list) else [],
                }
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
    llm_mode = "opencode" if copy_json else "template"
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

    generate_images = bool(cfg.get("generate_images"))
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
