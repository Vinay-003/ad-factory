#!/usr/bin/env python3
"""Submit EN ad prompt batches to Kie Nano Banana 2 and save generated images.

Flow:
1) Read prompt files from output/vN (EN only by default)
2) Prepend input/startingprompt.txt to each prompt
3) Submit one task per prompt to Kie createTask
4) Poll task status via recordInfo
5) Download generated images to generated_image/vN/<format>-en/
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CREATE_TASK_URL = "https://api.kie.ai/api/v1/jobs/createTask"
TASK_INFO_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"


@dataclass
class PromptFile:
    path: Path
    ad_format: str
    language: str
    variation: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Kie Nano Banana batch from output/vN prompts")
    parser.add_argument("--root", default=".", help="Workspace root (default: current directory)")
    parser.add_argument("--batch", help="Batch folder name like v1, v2 (default: latest under output/)" )
    parser.add_argument("--api-key", default=os.getenv("KIE_API_KEY"), help="Kie API key (or set KIE_API_KEY)")
    parser.add_argument("--callback-url", default=os.getenv("KIE_CALLBACK_URL", ""), help="Optional callback URL")
    parser.add_argument("--aspect-ratio", default="4:5", choices=["1:1", "1:4", "1:8", "2:3", "3:2", "3:4", "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9", "auto"], help="Output aspect ratio")
    parser.add_argument("--resolution", default="2K", choices=["1K", "2K", "4K"], help="Output resolution")
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


def build_image_inputs_from_file(url_file: Path) -> list[str]:
    if not url_file.exists():
        raise RuntimeError(f"Image URL file not found: {url_file}")
    lines = [line.strip() for line in url_file.read_text(encoding="utf-8").splitlines()]
    urls = [line for line in lines if line and not line.startswith("#")]
    if not urls:
        raise RuntimeError(f"No URLs found in {url_file}")
    if len(urls) > 14:
        raise RuntimeError(f"Kie supports max 14 image_input URLs, found {len(urls)} in {url_file}")
    return urls


def parse_prompt_files(batch_dir: Path, language_mode: str) -> list[PromptFile]:
    pattern = re.compile(r"^OUTPUT_([A-Z]+)_(EN|HI)(?:_V(\d+))?\.txt$")
    picked: list[PromptFile] = []
    for item in sorted(batch_dir.iterdir()):
        if not item.is_file():
            continue
        match = pattern.match(item.name)
        if not match:
            continue
        ad_format, language, variation_raw = match.group(1), match.group(2), match.group(3)
        if language_mode == "EN" and language != "EN":
            continue
        if language_mode == "HI" and language != "HI":
            continue
        variation = int(variation_raw) if variation_raw else 1
        picked.append(PromptFile(path=item, ad_format=ad_format, language=language, variation=variation))

    if not picked:
        raise RuntimeError(f"No prompt files found in {batch_dir} for language mode={language_mode}")
    return picked


def compose_prompt(starting_prompt: str, prompt_file: Path) -> str:
    body = prompt_file.read_text(encoding="utf-8").strip()
    return f"{starting_prompt.strip()}\n\n{body}\n"


def create_task(
    api_key: str,
    callback_url: str,
    prompt: str,
    image_input: list[str],
    aspect_ratio: str,
    resolution: str,
    output_format: str,
) -> str:
    payload = {
        "model": "nano-banana-2",
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


def main() -> int:
    args = parse_args()

    root = Path(args.root).resolve()
    load_env_file(root / "scripts" / ".env")
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

    if not args.api_key:
        print("Error: Missing KIE API key. Set KIE_API_KEY or pass --api-key", file=sys.stderr)
        return 1

    if not output_root.exists():
        print(f"Error: Missing output folder: {output_root}", file=sys.stderr)
        return 1
    if not starting_prompt_file.exists():
        print(f"Error: Missing starting prompt file: {starting_prompt_file}", file=sys.stderr)
        return 1

    if args.image_input_mode == "url" and not active_images_file.exists() and not args.active_images_base_url:
        print(
            f"Error: Missing URL input source. Provide {active_images_file} or --active-images-base-url",
            file=sys.stderr,
        )
        return 1
    if args.image_input_mode == "data_uri" and not active_images_dir.exists():
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

    if args.image_input_mode == "url" and active_images_file.exists():
        image_input_urls = build_image_inputs_from_file(active_images_file)
    else:
        image_input_urls = build_image_inputs(active_images_dir, args.image_input_mode, args.active_images_base_url)

    prompt_files = parse_prompt_files(batch_output_dir, args.language)
    grouped = trim_variations(iter_grouped(prompt_files), args.max_variations_per_format)
    starting_prompt = starting_prompt_file.read_text(encoding="utf-8")

    run_summary = {
        "batch": batch_name,
        "language_mode": args.language,
        "max_variations_per_format": args.max_variations_per_format,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "image_input_count": len(image_input_urls),
        "jobs": [],
    }

    for (ad_format, language), files in grouped.items():
        folder_name = f"{ad_format.lower()}-{language.lower()}"
        format_dir = batch_generated_dir / folder_name
        ensure_dir(format_dir)

        for prompt_file in files:
            complete_prompt = compose_prompt(starting_prompt, prompt_file.path)
            task_id = create_task(
                api_key=args.api_key,
                callback_url=args.callback_url,
                prompt=complete_prompt,
                image_input=image_input_urls,
                aspect_ratio=args.aspect_ratio,
                resolution=args.resolution,
                output_format=args.output_format,
            )
            print(f"[{ad_format}-{language}] variation {prompt_file.variation}: submitted task {task_id}")

            composed_prompt_path = format_dir / f"prompt_task_{task_id}.txt"
            write_text(composed_prompt_path, complete_prompt)

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
                filename = f"{ad_format.lower()}-{language.lower()}-v{prompt_file.variation:02d}-{idx:02d}.{ext}"
                out_file = format_dir / filename
                download_file(url, out_file)
                saved_files.append(str(out_file.relative_to(root)))

            task_record = {
                "task_id": task_id,
                "format": ad_format,
                "language": language,
                "variation": prompt_file.variation,
                "prompt_file": str(prompt_file.path.relative_to(root)),
                "composed_prompt_file": str(composed_prompt_path.relative_to(root)),
                "result_urls": result_urls,
                "saved_files": saved_files,
                "state": task_data.get("state"),
                "create_time": task_data.get("createTime"),
                "complete_time": task_data.get("completeTime"),
                "cost_time": task_data.get("costTime"),
            }
            run_summary["jobs"].append(task_record)

            task_meta_path = format_dir / f"task_{task_id}.json"
            write_json(task_meta_path, task_record)
            print(f"[{ad_format}-{language}] variation {prompt_file.variation}: saved {len(saved_files)} image(s)")

    summary_path = batch_generated_dir / "batch_run_summary.json"
    write_json(summary_path, run_summary)
    print(f"Done. Batch summary saved at {summary_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
