#!/usr/bin/env python3
"""Submit ad prompt batches to Kie Nano Banana Pro and save generated images.

Flow:
1) Read prompt files from output/vN (EN only by default)
2) Prepend input/startingprompt.txt to each prompt
3) Submit one task per prompt to Kie createTask
4) Poll task status via recordInfo
5) Download generated images to generated_image/vN/<format>/<persona>/
"""

from __future__ import annotations

import argparse
import copy
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CREATE_TASK_URL = "https://api.kie.ai/api/v1/jobs/createTask"
TASK_INFO_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"
DEFAULT_OPENCODE_API_URL = os.getenv("OPENCODE_API_URL", "http://127.0.0.1:4090")

LEGACY_LOGO_INPUT_URLS = {
    "https://res.cloudinary.com/dzhodklsr/image/upload/q_100,f_png/v1776194114/Untitled_design_1_qrtikg.png",
    "https://res.cloudinary.com/dzhodklsr/image/upload/v1776892977/w9p3scte8vcefh4epoe7.jpg",
}


@dataclass
class PromptFile:
    path: Path
    ad_format: str
    language: str
    persona_number: int | None
    variation: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Kie Nano Banana batch from output/vN prompts")
    parser.add_argument("--root", default=".", help="Workspace root (default: current directory)")
    parser.add_argument("--batch", help="Batch folder name like v1, v2 (default: latest under output/)" )
    parser.add_argument("--api-key", default=os.getenv("KIE_API_KEY"), help="Kie API key (or set KIE_API_KEY)")
    parser.add_argument("--callback-url", default=os.getenv("KIE_CALLBACK_URL", ""), help="Optional callback URL")
    parser.add_argument("--aspect-ratio", default="4:5", choices=["1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9", "auto"], help="Output aspect ratio")
    parser.add_argument("--resolution", default="4K", choices=["1K", "2K", "4K"], help="Output resolution (forced to 4K)")
    parser.add_argument("--output-format", default="png", choices=["png", "jpg"], help="Generated image format")
    parser.add_argument("--poll-interval", type=float, default=3.0, help="Status polling interval (seconds)")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="Task timeout (seconds)")
    parser.add_argument("--language", default="EN", choices=["EN", "HI", "BOTH"], help="Which prompt language files to submit")
    parser.add_argument(
        "--image-input-mode",
        default="url",
        choices=["data_uri", "url"],
        help="How to send input images: data_uri (local files inline) or url",
    )
    parser.add_argument(
        "--active-images-file",
        default="input/activeimages.txt",
        help="Text file with one image URL per line for active image_input",
    )
    parser.add_argument(
        "--max-variations-per-format",
        type=int,
        default=1,
        help="How many variations per format/language to submit (default: 1)",
    )
    parser.add_argument(
        "--active-images-base-url",
        default=os.getenv("ACTIVE_IMAGES_BASE_URL", ""),
        help="Public base URL that serves input/active_images files. Example: https://cdn.example.com/active_images",
    )
    parser.add_argument(
        "--prompt-files",
        nargs="*",
        default=[],
        help="Optional prompt files (workspace-relative) to submit instead of all batch prompts",
    )
    parser.add_argument(
        "--prompt-reference-map",
        default="",
        help="Optional JSON file mapping prompt_file -> image_input URL list for per-prompt img2img refs",
    )
    parser.add_argument(
        "--reference-conversion-mode",
        default="none",
        choices=["none", "outpaint_45_to_96"],
        help="Optional conversion lock instructions for reference-driven generation",
    )
    return parser.parse_args()


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def request_json(url: str, method: str, api_key: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {raw[:300]}") from exc


def fetch_latest_batch(output_dir: Path) -> str:
    pattern = re.compile(r"^v(\d+)$")
    candidates: list[tuple[int, str]] = []
    for item in output_dir.iterdir():
        if not item.is_dir():
            continue
        match = pattern.match(item.name)
        if match:
            candidates.append((int(match.group(1)), item.name))
    if not candidates:
        raise RuntimeError(f"No batch folder found in {output_dir}")
    candidates.sort(key=lambda x: x[0])
    return candidates[-1][1]


def image_mime_type(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    raise RuntimeError(f"Unsupported image format: {file_path}")


def build_image_inputs(active_images_dir: Path, mode: str, base_url: str) -> list[str]:
    files = sorted([p for p in active_images_dir.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])
    if not files:
        raise RuntimeError(f"No images found in {active_images_dir}")
    if len(files) > 14:
        raise RuntimeError(f"Kie supports max 14 image_input URLs, found {len(files)}")
    if mode == "data_uri":
        result = []
        for file in files:
            mime = image_mime_type(file)
            encoded = base64.b64encode(file.read_bytes()).decode("ascii")
            result.append(f"data:{mime};base64,{encoded}")
        return result

    if not base_url:
        raise RuntimeError(
            "Missing ACTIVE_IMAGES_BASE_URL (or --active-images-base-url) for url mode."
        )
    normalized_base = base_url.rstrip("/")
    result = []
    for file in files:
        quoted_name = urllib.parse.quote(file.name)
        result.append(f"{normalized_base}/{quoted_name}")
    return result


def load_active_images_config(url_file: Path) -> tuple[list[str], str, str, str]:
    if not url_file.exists():
        raise RuntimeError(f"Image URL file not found: {url_file}")
    lines = [line.strip() for line in url_file.read_text(encoding="utf-8").splitlines()]
    urls: list[str] = []
    light_logo_url = ""
    dark_logo_url = ""
    white_logo_url = ""
    for line in lines:
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            normalized_key = key.strip().upper()
            normalized_value = value.strip()
            if normalized_key == "LIGHT_LOGO_URL":
                light_logo_url = normalized_value
                continue
            if normalized_key == "DARK_LOGO_URL":
                dark_logo_url = normalized_value
                continue
            if normalized_key == "WHITE_LOGO_URL":
                white_logo_url = normalized_value
                continue
        urls.append(line)
    if not urls:
        raise RuntimeError(f"No URLs found in {url_file}")
    if len(urls) > 14:
        raise RuntimeError(f"Kie supports max 14 image_input URLs, found {len(urls)} in {url_file}")
    return urls, light_logo_url, dark_logo_url, white_logo_url


def parse_prompt_files(batch_dir: Path, language_mode: str, root: Path, selected_prompt_files: set[str] | None = None) -> list[PromptFile]:
    pattern = re.compile(r"^OUTPUT_([A-Z]+)(?:_P(\d+))?_(EN|HI)(?:_V(\d+))?\.txt$")
    picked: list[PromptFile] = []
    for item in sorted(batch_dir.rglob("OUTPUT_*.txt")):
        if not item.is_file():
            continue
        rel_path = str(item.relative_to(root))
        if selected_prompt_files and rel_path not in selected_prompt_files:
            continue
        match = pattern.match(item.name)
        if not match:
            continue
        ad_format = match.group(1)
        persona_raw = match.group(2)
        language = match.group(3)
        variation_raw = match.group(4)
        if language_mode == "EN" and language != "EN":
            continue
        if language_mode == "HI" and language != "HI":
            continue
        variation = int(variation_raw) if variation_raw else 1
        persona_number = int(persona_raw) if persona_raw else None
        picked.append(PromptFile(path=item, ad_format=ad_format, language=language, persona_number=persona_number, variation=variation))

    if not picked:
        raise RuntimeError(f"No prompt files found in {batch_dir} for language mode={language_mode}")
    return picked


def conversion_lock_instruction(mode: str) -> str:
    if mode != "outpaint_45_to_96":
        return ""
    return """REFERENCE-LOCKED 4:5 -> 9:16 CONVERSION (NON-NEGOTIABLE)
- Use the provided reference image as absolute ground truth.
- Perform vertical outpainting only to reach 9:16.
- Keep the original 4:5 layout block intact with zero stretch, zero warp, zero recomposition.
- Do not resize products, do not alter product spacing, do not change camera perspective.
- Keep product cluster anchored at the same visual height as reference (~45% vertical).
- Keep headline/support hierarchy and spacing identical to reference; no extra gaps.
- Top extension and bottom extension zones are background only.
- Do not move text or products into extension zones.
- Extend existing background style only (same texture, same lighting direction, same color tone).
- If any distortion/recomposition occurs, reject and regenerate.
""".strip()


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)


def parse_json_object_from_text(content: str) -> dict | None:
    text = (content or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    best: dict | None = None
    best_span = -1
    for match in re.finditer(r"\{", text):
        start = match.start()
        try:
            parsed, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if end > best_span:
            best = parsed
            best_span = end
    return best


def parse_opencode_json_output(stdout: str) -> dict | None:
    chunks: list[str] = []
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
            chunks.append(text.strip())
    if chunks:
        parsed = parse_json_object_from_text("\n".join(chunks).strip())
        if parsed is not None:
            return parsed
    return parse_json_object_from_text((stdout or "").strip())


def opencode_env() -> dict[str, str]:
    env = os.environ.copy()
    default_xdg = Path.home() / ".local" / "share"
    default_auth = default_xdg / "opencode" / "auth.json"

    raw_xdg = env.get("XDG_DATA_HOME", "").strip()
    current_xdg = Path(raw_xdg).expanduser() if raw_xdg else default_xdg
    current_auth = current_xdg / "opencode" / "auth.json"
    if default_auth.exists() and not current_auth.exists():
        env["XDG_DATA_HOME"] = str(default_xdg)
    return env


def discover_minimax_model() -> str:
    result = subprocess.run(["opencode", "models"], text=True, capture_output=True, check=False, env=opencode_env())
    if result.returncode != 0:
        return ""
    preferred = "opencode/minimax-m2.5-free"
    listed = [line.strip() for line in strip_ansi(result.stdout).splitlines() if line.strip()]
    if preferred in listed:
        return preferred
    for model in listed:
        lower = model.lower()
        if "minimax" in lower and "/" in model:
            return model
    return ""


def heuristic_logo_variant(prompt_text: str, prompt_metadata: dict) -> str:
    dark_keywords = ("dark", "night", "black", "navy", "midnight", "dusk", "evening")
    light_keywords = ("light", "bright", "daylight", "sunlight", "morning", "pastel", "cream")
    focus_parts = [
        str(prompt_metadata.get("background_title") or ""),
        str(prompt_metadata.get("seeded_background_prompt") or ""),
    ]
    focus_text = " ".join(part for part in focus_parts if part).lower()
    if any(keyword in focus_text for keyword in dark_keywords):
        return "dark"
    if any(keyword in focus_text for keyword in light_keywords):
        return "light"
    lowered = prompt_text.lower()
    if any(keyword in lowered for keyword in dark_keywords):
        return "dark"
    return "light"


def choose_logo_variant_with_minimax(prompt_text: str, prompt_metadata: dict, model: str, api_url: str, password: str) -> tuple[str, str]:
    fallback = heuristic_logo_variant(prompt_text, prompt_metadata)
    if not model:
        return fallback, "heuristic"
    bg_title = str(prompt_metadata.get("background_title") or "")
    seeded_prompt = str(prompt_metadata.get("seeded_background_prompt") or "")
    classify_prompt = (
        "Classify the ad background brightness as exactly one label: dark or light. "
        "Return strict JSON only with keys label and reason.\n"
        f"background_title: {bg_title}\n"
        f"seeded_background_prompt: {seeded_prompt}\n"
        f"prompt_excerpt: {prompt_text[:1400]}"
    )
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
        classify_prompt,
    ]
    if password:
        cmd.extend(["--password", password])
    result = subprocess.run(cmd, text=True, capture_output=True, check=False, env=opencode_env())
    if result.returncode != 0:
        return fallback, "heuristic"
    parsed = parse_opencode_json_output(strip_ansi(result.stdout))
    if not isinstance(parsed, dict):
        return fallback, "heuristic"
    label = str(parsed.get("label") or "").strip().lower()
    if label in {"dark", "light"}:
        if label == "light" and fallback == "dark":
            return "dark", "heuristic_override"
        return label, "minimax"
    return fallback, "heuristic"


def compose_prompt(
    starting_prompt: str,
    prompt_file: Path,
    conversion_mode: str,
    light_logo_url: str,
) -> str:
    body = prompt_file.read_text(encoding="utf-8").strip()
    lock = conversion_lock_instruction(conversion_mode)
    logo_instruction = (
        "LOGO ASSET RULE (MANDATORY)\n"
        f"- Use LIGHT_LOGO_URL only as the logo reference: {light_logo_url}\n"
        "- Do not use dark-logo or white-logo variants in any scenario.\n"
        "- Never print URLs, file names, or any technical strings on the canvas.\n"
        "- Render only the visual logo mark; no link text, no metadata text.\n"
        "- Do not place any white box, white patch, solid rectangle, badge plate, or background panel behind the logo.\n"
        "- Logo background must stay transparent and blend naturally with the scene."
    )
    big_box_visibility_instruction = (
        "BIG BOX LABEL VISIBILITY (NON-NEGOTIABLE)\n"
        "- Keep the main kit box label text fully visible and readable.\n"
        "- Specifically preserve: 'Panacea for weight loss and obesity related conditions' and 'ISO 9001:2008 Certified'.\n"
        "- Do not let any bottle, sachet, prop, or overlay block these two text regions.\n"
        "- Product overlap is allowed only if it does not occlude any kit-box text."
    )
    if lock:
        return f"{starting_prompt.strip()}\n\n{logo_instruction}\n\n{big_box_visibility_instruction}\n\n{lock}\n\n{body}\n"
    return f"{starting_prompt.strip()}\n\n{logo_instruction}\n\n{big_box_visibility_instruction}\n\n{body}\n"


def _find_line_value(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def extract_prompt_metadata(prompt_text: str) -> dict:
    metadata: dict[str, object] = {}

    persona_line = _find_line_value(r"^-\s*Persona:\s*(.+)$", prompt_text)
    if persona_line:
        metadata["persona_line"] = persona_line
        persona_num_match = re.search(r"\(\s*Persona\s*(\d+)\s*\)", persona_line, flags=re.IGNORECASE)
        if persona_num_match:
            metadata["persona_number"] = int(persona_num_match.group(1))
            metadata["persona_name"] = re.sub(r"\s*\(\s*Persona\s*\d+\s*\)", "", persona_line, flags=re.IGNORECASE).strip()
        else:
            metadata["persona_name"] = persona_line

    bg_line = _find_line_value(r"^-\s*Background\s*slot:\s*(.+)$", prompt_text)
    if bg_line:
        metadata["background_slot_line"] = bg_line
        slot_match = re.search(r"\b(BG-\d{3})\b", bg_line, flags=re.IGNORECASE)
        if slot_match:
            metadata["background_slot"] = slot_match.group(1).upper()
        title_match = re.search(r"BG-\d{3}\s*[—-]\s*\"?([^\"\n]+)\"?", bg_line, flags=re.IGNORECASE)
        if title_match:
            metadata["background_title"] = title_match.group(1).strip()

    seed_value = _find_line_value(r"^-\s*Seed:\s*(\d+)\s*$", prompt_text)
    if seed_value:
        metadata["seed"] = int(seed_value)

    seeded_prompt_block = re.search(
        r"SEEDED BACKGROUND PROMPT:\s*\n([^\n].+?)\n\s*-\s*(?:SAFE-ZONE FIELDS|Subject:|Action:|Composition:)",
        prompt_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if seeded_prompt_block:
        metadata["seeded_background_prompt"] = seeded_prompt_block.group(1).strip()
    else:
        scene_value = _find_line_value(r"^-\s*Scene:\s*(.+)$", prompt_text)
        if scene_value:
            metadata["seeded_background_prompt"] = scene_value

    headline = _find_line_value(r"^-\s*Headline(?:\s*\(EN\))?:\s*\"?([^\n\"]+)\"?\s*$", prompt_text)
    support_line = _find_line_value(r"^-\s*Support\s*line(?:\s*\(EN\))?:\s*\"?([^\n\"]+)\"?\s*$", prompt_text)
    cta = _find_line_value(r"^-\s*CTA(?:\s*\(EN\))?:\s*\"?([^\n\"]+)\"?\s*$", prompt_text)
    if headline:
        metadata["headline"] = headline
    if support_line:
        metadata["support_line"] = support_line
    if cta:
        metadata["cta"] = cta

    return metadata


def create_task(
    api_key: str,
    callback_url: str,
    prompt: str,
    image_input: list[str],
    aspect_ratio: str,
    resolution: str,
    output_format: str,
) -> str:
    resolution = "4K"
    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": prompt,
            "image_input": image_input,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "output_format": output_format,
        },
    }
    if callback_url:
        payload["callBackUrl"] = callback_url

    response = request_json(CREATE_TASK_URL, method="POST", api_key=api_key, payload=payload)
    code = response.get("code")
    if code != 200:
        raise RuntimeError(f"createTask failed: {response}")
    data = response.get("data") or {}
    task_id = data.get("taskId")
    if not task_id:
        raise RuntimeError(f"No taskId in createTask response: {response}")
    return task_id


def get_task_info(api_key: str, task_id: str) -> dict:
    query = urllib.parse.urlencode({"taskId": task_id})
    url = f"{TASK_INFO_URL}?{query}"
    return request_json(url, method="GET", api_key=api_key)


def wait_for_task(api_key: str, task_id: str, poll_interval: float, timeout_seconds: int) -> dict:
    started = time.time()
    while True:
        info = get_task_info(api_key, task_id)
        code = info.get("code")
        if code != 200:
            raise RuntimeError(f"recordInfo failed for task {task_id}: {info}")
        data = info.get("data") or {}
        state = data.get("state")
        if state == "success":
            return data
        if state == "fail":
            fail_code = data.get("failCode", "")
            fail_msg = data.get("failMsg", "")
            raise RuntimeError(f"Task {task_id} failed: {fail_code} {fail_msg}".strip())

        if time.time() - started > timeout_seconds:
            raise TimeoutError(f"Task {task_id} timed out after {timeout_seconds} seconds")
        time.sleep(poll_interval)


def parse_result_urls(task_data: dict) -> list[str]:
    result_json = task_data.get("resultJson")
    if not result_json:
        raise RuntimeError(f"Task has no resultJson: {task_data}")
    parsed = json.loads(result_json)
    urls = parsed.get("resultUrls") or []
    if not urls:
        raise RuntimeError(f"No resultUrls in resultJson: {parsed}")
    return urls


def extension_from_url(url: str, fallback: str) -> str:
    path = urllib.parse.urlparse(url).path
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in {"png", "jpg", "jpeg", "webp"}:
        if suffix == "jpeg":
            return "jpg"
        return suffix
    return fallback


def download_file(url: str, out_path: Path) -> None:
    req = urllib.request.Request(
        url=url,
        method="GET",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://api.kie.ai/",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    out_path.write_bytes(data)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def persona_folder_name(persona_number: int | None) -> str:
    if isinstance(persona_number, int) and persona_number > 0:
        return f"P{persona_number:02d}"
    return "P00"


def sanitize_logo_inputs(image_inputs: list[str], logo_urls: list[str]) -> list[str]:
    blocked = {url for url in (*logo_urls, *LEGACY_LOGO_INPUT_URLS) if url}
    sanitized = [url for url in image_inputs if url not in blocked]
    sanitized = [*logo_urls, *sanitized]
    deduped: list[str] = []
    seen: set[str] = set()
    for url in sanitized:
        if url in seen:
            continue
        deduped.append(url)
        seen.add(url)
    return deduped


def iter_grouped(items: Iterable[PromptFile]) -> dict[tuple[str, str], list[PromptFile]]:
    grouped: dict[tuple[str, str], list[PromptFile]] = {}
    for item in items:
        key = (item.ad_format, item.language)
        grouped.setdefault(key, []).append(item)
    for key in grouped:
        grouped[key].sort(key=lambda pf: pf.variation)
    return grouped


def trim_variations(grouped: dict[tuple[str, str], list[PromptFile]], max_variations: int) -> dict[tuple[str, str], list[PromptFile]]:
    if max_variations <= 0:
        return grouped
    trimmed: dict[tuple[str, str], list[PromptFile]] = {}
    for key, files in grouped.items():
        trimmed[key] = files[:max_variations]
    return trimmed


def load_prompt_reference_map(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        raise RuntimeError(f"Prompt reference map file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Prompt reference map must be a JSON object")
    out: dict[str, list[str]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key.strip():
            continue
        if isinstance(value, str):
            urls = [value.strip()] if value.strip() else []
        elif isinstance(value, list):
            urls = [str(item).strip() for item in value if str(item).strip()]
        else:
            urls = []
        if not urls:
            continue
        if len(urls) > 14:
            raise RuntimeError(f"Prompt reference map for '{key}' has >14 image URLs")
        out[Path(key).as_posix()] = urls
    return out


def main() -> int:
    args = parse_args()

    root = Path(args.root).resolve()
    load_env_file(root / ".env.dashboard")
    if not args.api_key:
        args.api_key = os.getenv("KIE_API_KEY")
    output_root = root / "output"
    generated_root = root / "generated_image"
    active_images_dir = root / "input" / "active_images"
    if not active_images_dir.exists():
        fallback_dir = root / "input" / "activeimages"
        if fallback_dir.exists():
            active_images_dir = fallback_dir
    starting_prompt_file = root / "input" / "startingprompt.txt"
    active_images_file = root / args.active_images_file
    prompt_reference_map_path = Path(args.prompt_reference_map).resolve() if args.prompt_reference_map else None
    prompt_reference_map: dict[str, list[str]] = {}
    if prompt_reference_map_path is not None:
        prompt_reference_map = load_prompt_reference_map(prompt_reference_map_path)

    if not args.api_key:
        print("Error: Missing KIE API key. Set KIE_API_KEY or pass --api-key", file=sys.stderr)
        return 1

    if not output_root.exists():
        print(f"Error: Missing output folder: {output_root}", file=sys.stderr)
        return 1
    if not starting_prompt_file.exists():
        print(f"Error: Missing starting prompt file: {starting_prompt_file}", file=sys.stderr)
        return 1

    has_per_prompt_refs = bool(prompt_reference_map)
    if not has_per_prompt_refs and args.image_input_mode == "url" and not active_images_file.exists() and not args.active_images_base_url:
        print(
            f"Error: Missing URL input source. Provide {active_images_file} or --active-images-base-url",
            file=sys.stderr,
        )
        return 1
    if not has_per_prompt_refs and args.image_input_mode == "data_uri" and not active_images_dir.exists():
        print(f"Error: Missing active images folder: {active_images_dir}", file=sys.stderr)
        return 1

    batch_name = args.batch or fetch_latest_batch(output_root)
    batch_output_dir = output_root / batch_name
    if not batch_output_dir.exists():
        print(f"Error: Batch folder not found: {batch_output_dir}", file=sys.stderr)
        return 1

    ensure_dir(generated_root)
    batch_generated_dir = generated_root / batch_name
    ensure_dir(batch_generated_dir)

    light_logo_url = ""
    dark_logo_url = ""
    white_logo_url = ""
    if has_per_prompt_refs:
        image_input_urls = []
    elif args.image_input_mode == "url" and active_images_file.exists():
        image_input_urls, light_logo_url, dark_logo_url, white_logo_url = load_active_images_config(active_images_file)
    else:
        image_input_urls = build_image_inputs(active_images_dir, args.image_input_mode, args.active_images_base_url)

    selected_prompt_files = {Path(path).as_posix() for path in (args.prompt_files or []) if str(path).strip()}
    prompt_files = parse_prompt_files(batch_output_dir, args.language, root, selected_prompt_files if selected_prompt_files else None)
    grouped = trim_variations(iter_grouped(prompt_files), args.max_variations_per_format)
    starting_prompt = starting_prompt_file.read_text(encoding="utf-8")
    logo_candidates = [light_logo_url] if light_logo_url else []

    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for (ad_format, language), files in grouped.items():
        format_dir = batch_generated_dir / ad_format.upper()
        ensure_dir(format_dir)

        for prompt_file in files:
            prompt_body = prompt_file.path.read_text(encoding="utf-8")
            prompt_metadata = extract_prompt_metadata(prompt_body)
            complete_prompt = compose_prompt(
                starting_prompt,
                prompt_file.path,
                args.reference_conversion_mode,
                light_logo_url,
            )
            prompt_rel_path = str(prompt_file.path.relative_to(root))
            persona_number = prompt_file.persona_number
            if not isinstance(persona_number, int):
                raw_persona_meta = prompt_metadata.get("persona_number")
                if isinstance(raw_persona_meta, int):
                    persona_number = raw_persona_meta
            persona_dir = format_dir / persona_folder_name(persona_number)
            ensure_dir(persona_dir)
            per_prompt_inputs = prompt_reference_map.get(Path(prompt_rel_path).as_posix())
            image_input_for_prompt = per_prompt_inputs if per_prompt_inputs else image_input_urls
            image_input_for_prompt = sanitize_logo_inputs(
                image_input_for_prompt,
                logo_candidates,
            )
            if len(image_input_for_prompt) > 14:
                raise RuntimeError(f"Kie supports max 14 image_input URLs, found {len(image_input_for_prompt)} for prompt: {prompt_rel_path}")
            if not image_input_for_prompt:
                raise RuntimeError(f"No image_input URLs found for prompt: {prompt_rel_path}")
            task_id = create_task(
                api_key=args.api_key,
                callback_url=args.callback_url,
                prompt=complete_prompt,
                image_input=image_input_for_prompt,
                aspect_ratio=args.aspect_ratio,
                resolution=args.resolution,
                output_format=args.output_format,
            )
            print(f"[{ad_format}-{language}] variation {prompt_file.variation}: submitted task {task_id}")

            task_data = wait_for_task(
                api_key=args.api_key,
                task_id=task_id,
                poll_interval=args.poll_interval,
                timeout_seconds=args.timeout_seconds,
            )
            result_urls = parse_result_urls(task_data)

            saved_files = []
            for idx, url in enumerate(result_urls, start=1):
                ext = extension_from_url(url, args.output_format)
                persona_label = persona_folder_name(persona_number).lower()
                filename = f"{ad_format.lower()}-{language.lower()}-{persona_label}-v{prompt_file.variation:02d}-{idx:02d}.{ext}"
                out_file = persona_dir / filename
                download_file(url, out_file)
                saved_files.append(str(out_file.relative_to(root)))

                image_record = {
                    "record_type": "generated_image",
                    "generated_at": generated_at,
                    "model": "nano-banana-pro",
                    "task_id": task_id,
                    "batch": batch_name,
                    "format": ad_format,
                    "language": language,
                    "persona_number": persona_number,
                    "persona_folder": persona_folder_name(persona_number),
                    "variation": prompt_file.variation,
                    "image_index": idx,
                    "prompt_file": prompt_rel_path,
                    "output_prompt": prompt_body,
                    "starting_prompt": starting_prompt.strip(),
                    "complete_prompt": complete_prompt,
                    "bg_used": {
                        "slot": prompt_metadata.get("background_slot"),
                        "title": prompt_metadata.get("background_title"),
                        "seeded_background_prompt": prompt_metadata.get("seeded_background_prompt"),
                    },
                    "bg_variation_used": {
                        "seed": prompt_metadata.get("seed"),
                        "prompt_variation": prompt_file.variation,
                    },
                    "logo_variant": "light",
                    "logo_variant_source": "forced_light",
                    "logo_asset_url": light_logo_url,
                    "logo_candidates": copy.deepcopy(logo_candidates),
                    "prompt_metadata": prompt_metadata,
                    "image_input_urls": copy.deepcopy(image_input_for_prompt),
                    "result_url": url,
                    "saved_file": str(out_file.relative_to(root)),
                    "state": task_data.get("state"),
                    "create_time": task_data.get("createTime"),
                    "complete_time": task_data.get("completeTime"),
                    "cost_time": task_data.get("costTime"),
                }
                image_meta_path = out_file.with_suffix(".json")
                write_json(image_meta_path, image_record)

            print(f"[{ad_format}-{language}] variation {prompt_file.variation}: saved {len(saved_files)} image(s)")

    print(f"Done. Image files and per-image metadata saved under {batch_generated_dir.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
