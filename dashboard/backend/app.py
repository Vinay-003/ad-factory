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

DEFAULT_PRODUCT_INFO = ROOT / "productinfomain.txt"
DEFAULT_MECHANISM = ROOT / "PRODUCT_MECHANISM_V1.txt"
DEFAULT_FAQ = ROOT / "faq.txt"
DEFAULT_PERSONA_TXT = ROOT / "PERSONA_DEEP_DIVE_01_05.txt"
DEFAULT_PERSONA_CSV = ROOT / "PERSONA_DEEP_DIVE_FIRST5_FORUM_GROUNDED.csv"
DEFAULT_PLAYBOOK = ROOT / "AD_CREATIVE_SYSTEM_PLAYBOOK.md"
DEFAULT_ACTIVE_IMAGES = ROOT / "input" / "activeimages.txt"


FORMATS = ["HERO", "BA", "TEST", "FEAT", "UGC"]
DEFAULT_OPENCODE_API_URL = os.getenv("OPENCODE_API_URL", "http://127.0.0.1:4090")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_run_id() -> str:
    return f"run_{int(time.time())}_{random.randint(1000, 9999)}"


def ensure_dirs() -> None:
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)


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


def read_active_images(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)


def list_opencode_models() -> list[str]:
    result = run_cmd(["opencode", "models"], cwd=ROOT)
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in strip_ansi(result.stdout).splitlines()]
    return [line for line in lines if line and "/" in line]


def list_opencode_provider_labels() -> list[str]:
    result = run_cmd(["opencode", "providers", "list"], cwd=ROOT)
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in strip_ansi(result.stdout).splitlines()]
    labels: list[str] = []
    for line in lines:
        match = re.search(r"[●•]\s+(.+?)\s+(oauth|api|token|key)\b", line, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        if value:
            labels.append(value)
    return labels


def provider_id_from_label(label: str) -> str:
    known = {
        "github copilot": "github-copilot",
        "opencode": "opencode",
    }
    key = label.strip().lower()
    if key in known:
        return known[key]
    return re.sub(r"[^a-z0-9]+", "-", key).strip("-")


def list_models_for_provider(provider: str) -> list[str]:
    result = run_cmd(["opencode", "models", provider], cwd=ROOT)
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

    providers_from_models = sorted({line.split("/", 1)[0] for line in models})
    grouped: dict[str, list[str]] = {}
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
        "providers": providers_from_models,
        "provider_labels": provider_labels,
        "models_by_provider": grouped,
        "default_model": default_model,
    }


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
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    clipped = clean[:limit].rstrip(" ,;:-")
    last_space = clipped.rfind(" ")
    if last_space > 24:
        clipped = clipped[:last_space]
    return clipped + "..."


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


def apply_local_collision_patch(copy_json: dict[str, Any], collisions: list[dict[str, Any]], tag: str) -> dict[str, Any]:
    ads = copy_json.get("ads")
    if not isinstance(ads, list):
        return copy_json
    for item in collisions:
        idx = item.get("ad_index")
        lang = item.get("language")
        field = item.get("field")
        if not isinstance(idx, int) or idx < 0 or idx >= len(ads):
            continue
        ad = ads[idx]
        if not isinstance(ad, dict):
            continue
        copy = ad.get("copy")
        if not isinstance(copy, dict):
            continue
        block = copy.get(lang)
        if not isinstance(block, dict):
            continue

        if field == "bullets" and isinstance(block.get("bullets"), list):
            patched = []
            for i, bullet in enumerate(block.get("bullets", []), start=1):
                if isinstance(bullet, str) and bullet.strip():
                    if lang == "HI":
                        patched.append(f"{bullet.strip()} और निरंतरता बेहतर रहे")
                    else:
                        patched.append(f"{bullet.strip()} for steadier consistency")
            if patched:
                block["bullets"] = patched
            continue

        if field in {"headline", "support_line", "trust_line", "attribution"}:
            current = block.get(field)
            if isinstance(current, str) and current.strip():
                current_text = current.strip()
                if field == "support_line":
                    if lang == "HI":
                        block[field] = f"{current_text} जिससे निरंतरता बनी रहे"
                    else:
                        block[field] = f"{current_text} for sustained consistency"
                elif field == "trust_line":
                    if lang == "HI":
                        block[field] = f"{current_text} ताकि प्रगति टिक सके"
                    else:
                        block[field] = f"{current_text} to sustain progress"
                elif field == "attribution":
                    if lang == "HI":
                        block[field] = f"{current_text} (सत्यापित)"
                    else:
                        block[field] = f"{current_text} (verified)"
                else:
                    if lang == "HI":
                        block[field] = f"{current_text} - नया एंगल"
                    else:
                        block[field] = f"{current_text} - new angle"
    return copy_json


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
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


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
                base_lang["headline"] = headline
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

    system = (
        "You generate ad copy JSON only. Return valid JSON with keys default_aspect_ratio and ads. "
        "Each ads item must include format, headline_angle, persona fields and copy.EN/copy.HI fields compatible with assembler."
    )
    user_payload = {
        "task": "Generate fresh ad copy JSON for provided context.",
        "context": context,
        "constraints": {
            "language": ["EN", "HI"],
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
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", content, flags=re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        pass

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
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                return None
            return json.loads(match.group(0))
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
        for file in sorted(output_dir.glob("OUTPUT_*.txt")):
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
            "persona_txt": str(DEFAULT_PERSONA_TXT.relative_to(ROOT)),
            "persona_csv": str(DEFAULT_PERSONA_CSV.relative_to(ROOT)),
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
    persona_txt_file: UploadFile | None = File(None),
    persona_csv_file: UploadFile | None = File(None),
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
    persona_txt_path = save_upload(run_dir / "inputs" / "PERSONA_DEEP_DIVE_01_05.txt", persona_txt_file)
    persona_csv_path = save_upload(run_dir / "inputs" / "PERSONA_DEEP_DIVE_FIRST5_FORUM_GROUNDED.csv", persona_csv_file)
    active_images_path = save_upload(run_dir / "inputs" / "activeimages.txt", active_images_file)

    if persona_csv_path and not persona_txt_path:
        result = run_cmd(
            [
                "python3",
                "scripts/generate_persona_txt.py",
                "--csv",
                str(persona_csv_path),
                "--output",
                str(run_dir / "inputs" / "PERSONA_DEEP_DIVE_01_05.txt"),
            ],
            cwd=ROOT,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"persona conversion failed: {result.stderr.strip()}")
        persona_txt_path = run_dir / "inputs" / "PERSONA_DEEP_DIVE_01_05.txt"

    product_file = coalesce_path(product_path, DEFAULT_PRODUCT_INFO)
    mechanism_file_path = coalesce_path(mechanism_path, DEFAULT_MECHANISM)
    faq_file_path = coalesce_path(faq_path, DEFAULT_FAQ)
    persona_file = coalesce_path(persona_txt_path, DEFAULT_PERSONA_TXT)

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

    ads_context: list[dict[str, Any]] = []
    for item in plan:
        persona_no = item["persona"]
        fmt = item["format"]

        persona_result = run_cmd(
            [
                "python3",
                "scripts/extract_persona.py",
                "--input",
                str(persona_file),
                "--persona",
                str(persona_no),
                "--json",
            ],
            cwd=ROOT,
        )
        persona_payload = parse_json_stdout(persona_result, f"extract_persona({persona_no})")

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

    assembler_result = run_cmd(["python3", "scripts/generate_ads.py", "--copy-file", str(copy_file)], cwd=ROOT)
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

                retry = run_cmd(["python3", "scripts/generate_ads.py", "--copy-file", str(copy_file)], cwd=ROOT)
                if retry.returncode == 0:
                    assembler_result = retry
                else:
                    retry_error = retry.stderr or retry.stdout
                    (run_dir / "logs" / "assembler_retry_error.txt").write_text(retry_error, encoding="utf-8")

            if assembler_result.returncode != 0:
                copy_json = apply_local_collision_patch(copy_json, collisions, tag=run_id[-6:])
                copy_json = strip_internal_markers_from_payload(copy_json)
                copy_file.write_text(json.dumps(copy_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                retry2 = run_cmd(["python3", "scripts/generate_ads.py", "--copy-file", str(copy_file)], cwd=ROOT)
                if retry2.returncode == 0:
                    assembler_result = retry2
                else:
                    retry2_error = retry2.stderr or retry2.stdout
                    (run_dir / "logs" / "assembler_retry2_error.txt").write_text(retry2_error, encoding="utf-8")

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
    manifest["active_images_file"] = str(active_images_file_path)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


app.mount("/storage", StaticFiles(directory=str(STORAGE_ROOT)), name="storage")
app.mount("/output", StaticFiles(directory=str(ROOT / "output")), name="output")
app.mount("/generated_image", StaticFiles(directory=str(ROOT / "generated_image")), name="generated_image")
app.mount("/", StaticFiles(directory=str(ROOT / "dashboard" / "frontend"), html=True), name="frontend")
