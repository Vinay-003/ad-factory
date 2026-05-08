#!/usr/bin/env python3
"""Strict Gemini web image-generation automation for Selenium 4.32.

Per prompt:
  1. Use one real tab for that prompt. The first prompt reuses Selenium's blank
     tab when safe, so there is no extra empty Gemini tab at startup.
  2. Navigate to a fresh Gemini chat only. Never click old chat rows or their
     three-dot menus.
  3. Optionally select Pro/Create image using guarded selectors only.
  4. Upload references, wait for attachments to settle, paste the prompt with
     CDP/clipboard input events, verify full prompt integrity, and confirm Send
     actually submitted.
  5. Wait for a large image in the latest assistant/model response.
  6. Download the exact generated image and wait until the file is complete.
  7. Move to the next prompt tab without closing previous prompt tabs.

This file intentionally avoids broad "click any button/div containing text"
helpers because those were the source of Temporary chat / Share conversation /
old-chat menu misclicks.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import textwrap
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    InvalidSessionIdException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


GEMINI_URL = "https://gemini.google.com/app"
FORMAT_ORDER = ["BA", "FEAT", "HERO", "TEST", "UGC"]
UNSAFE_CLICK_WORDS = (
    "share conversation",
    "share",
    "rename",
    "delete",
    "remove",
    "archive",
    "more options",
    "recent",
    "activity",
    "settings",
    "help",
    "temporary chat",
)
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
DOWNLOAD_TEMP_EXTS = {".crdownload", ".tmp", ".part"}


@dataclass(frozen=True)
class PromptJob:
    prompt_path: Path
    format_id: str
    persona_id: str
    job_key: str
    output_stem: str


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini web image generation automation")
    parser.add_argument("--prompt-dir", required=True, help="Directory containing prompt files")
    parser.add_argument(
        "--prompt-glob",
        default="FINAL_*_P*_EN.txt",
        help="Prompt glob. Use 'FINAL_HERO_P*_EN.txt' for HERO only.",
    )
    parser.add_argument("--image-source-file", default="")
    parser.add_argument("--upload-dir", default="/home/mylappy/Downloads/Untitled design")
    parser.add_argument("--logo-key", default="LIGHT_LOGO_URL")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--timeout", type=int, default=420, help="Generation timeout per prompt")
    parser.add_argument("--download-timeout", type=int, default=180)
    parser.add_argument("--sleep-after-download", type=float, default=3.0)
    parser.add_argument("--min-image-bytes", type=int, default=20_000)
    parser.add_argument("--max-attempts", type=int, default=1, help="Default 1 avoids accidental repeat tabs")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved prompt jobs and exit")

    parser.add_argument(
        "--expected-formats",
        default="",
        help="Comma-separated expected format IDs, e.g. BA,FEAT,HERO,TEST,UGC",
    )
    parser.add_argument(
        "--strict-expected-formats",
        action="store_true",
        help="Fail if --expected-formats are missing for any persona",
    )
    parser.add_argument(
        "--allow-duplicate-prompt-keys",
        action="store_true",
        help="Do not skip duplicate FORMAT/Pxx prompt files",
    )

    parser.add_argument("--user-data-dir", default="")
    parser.add_argument("--profile-directory", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--browser", choices=["brave", "chrome"], default="brave")
    parser.add_argument("--attach-debugger-address", default="")
    parser.add_argument("--debug-user-data-dir", default="/home/mylappy/.chrome-selenium-profile")
    parser.add_argument("--manual-login-timeout", type=int, default=180)
    parser.add_argument("--login-wait-mode", choices=["auto", "strict"], default="auto")
    parser.add_argument("--browser-download-dir", default="")
    parser.add_argument(
        "--first-tab-mode",
        choices=["reuse-blank", "new"],
        default="reuse-blank",
        help="reuse-blank prevents an extra empty Gemini tab at startup",
    )

    parser.add_argument(
        "--skip-model-selection",
        action="store_true",
        help="Do not touch Gemini model/tool controls",
    )
    parser.add_argument(
        "--require-pro-model",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use --no-require-pro-model if Gemini UI changed and selection cannot be confirmed",
    )
    parser.add_argument(
        "--require-create-image-tool",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Fail if Create image tool cannot be confirmed",
    )
    parser.add_argument(
        "--prompt-paste-method",
        choices=["auto", "cdp", "clipboard", "js"],
        default="auto",
        help="How to insert long prompts. auto tries CDP insertText, then clipboard paste. JS must be requested explicitly.",
    )
    parser.add_argument(
        "--prompt-paste-timeout",
        type=int,
        default=35,
        help="Seconds to wait for the full prompt to appear in Gemini after paste",
    )
    parser.add_argument(
        "--prompt-integrity-ratio",
        type=float,
        default=0.98,
        help="Minimum compact-text ratio required before the script is allowed to click Send",
    )
    parser.add_argument(
        "--prompt-settle-wait",
        type=float,
        default=5.0,
        help="Seconds to wait after the prompt is pasted before the final completeness check and Send",
    )
    parser.add_argument(
        "--send-submit-method",
        choices=["enter", "click", "auto"],
        default="auto",
        help="How to submit after the prompt is complete. auto uses the real composer Send/Submit button first, then Enter fallbacks.",
    )
    parser.add_argument(
        "--send-confirm-timeout",
        type=float,
        default=35.0,
        help="Seconds to wait for proof that Gemini accepted the prompt after a submit attempt",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Prompt discovery and dedupe
# ---------------------------------------------------------------------------


def _format_sort_key(fmt: str) -> tuple[int, str]:
    fmt_up = fmt.upper()
    if fmt_up in FORMAT_ORDER:
        return (FORMAT_ORDER.index(fmt_up), fmt_up)
    return (999, fmt_up)


def _parse_prompt_name(path: Path) -> tuple[str, str]:
    stem = path.stem
    patterns = [
        r"^FINAL_(?P<fmt>[A-Za-z0-9]+)_P(?P<num>\d+)(?:_[A-Za-z0-9]+)?$",
        r"^(?P<fmt>[A-Za-z0-9]+)_P(?P<num>\d+)(?:_[A-Za-z0-9]+)?$",
        r"^(?P<fmt>[A-Za-z0-9]+).*?P(?P<num>\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, stem)
        if m:
            return m.group("fmt").upper(), f"P{int(m.group('num')):02d}"

    m = re.search(r"P(\d+)", stem, flags=re.IGNORECASE)
    persona_id = f"P{int(m.group(1)):02d}" if m else "P00"
    fmt = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").upper() or "PROMPT"
    return fmt, persona_id


def discover_prompt_jobs(prompt_dir: Path, pattern: str, allow_duplicates: bool) -> tuple[list[PromptJob], list[PromptJob]]:
    raw_paths = [p for p in prompt_dir.glob(pattern) if p.is_file()]
    if not raw_paths:
        raise FileNotFoundError(f"No prompt files found in {prompt_dir} with pattern {pattern!r}")

    raw_jobs: list[PromptJob] = []
    for path in raw_paths:
        fmt, persona = _parse_prompt_name(path)
        key = f"{fmt}_{persona}"
        safe_stem = f"gemini-{fmt.lower()}-{persona.lower()}"
        raw_jobs.append(
            PromptJob(
                prompt_path=path.resolve(),
                format_id=fmt,
                persona_id=persona,
                job_key=key,
                output_stem=safe_stem,
            )
        )

    raw_jobs.sort(
        key=lambda j: (
            int(re.search(r"\d+", j.persona_id).group(0)) if re.search(r"\d+", j.persona_id) else 0,
            _format_sort_key(j.format_id),
            j.prompt_path.name,
        )
    )

    if allow_duplicates:
        return raw_jobs, []

    seen: set[str] = set()
    jobs: list[PromptJob] = []
    duplicates: list[PromptJob] = []
    for job in raw_jobs:
        if job.job_key in seen:
            duplicates.append(job)
            continue
        seen.add(job.job_key)
        jobs.append(job)
    return jobs, duplicates


def print_job_manifest(jobs: list[PromptJob], duplicates: list[PromptJob]) -> None:
    print("\nResolved prompt jobs:")
    for idx, job in enumerate(jobs, start=1):
        print(f"  {idx:03d}. {job.job_key:<12} -> {job.prompt_path.name}")
    if duplicates:
        print("\nSkipped duplicate FORMAT/Pxx prompt files:")
        for job in duplicates:
            print(f"  duplicate {job.job_key:<12} -> {job.prompt_path.name}")
        print("Use --allow-duplicate-prompt-keys only if these duplicates are intentional.")


def validate_expected_formats(jobs: list[PromptJob], expected_csv: str, strict: bool) -> None:
    expected = [x.strip().upper() for x in expected_csv.split(",") if x.strip()]
    if not expected:
        return
    by_persona: dict[str, set[str]] = {}
    for job in jobs:
        by_persona.setdefault(job.persona_id, set()).add(job.format_id.upper())
    problems: list[str] = []
    for persona, present in sorted(by_persona.items()):
        missing = [fmt for fmt in expected if fmt not in present]
        if missing:
            problems.append(f"{persona}: missing {', '.join(missing)}")
    if problems:
        msg = "Expected-format check failed/warned:\n  " + "\n  ".join(problems)
        if strict:
            raise RuntimeError(msg)
        print("\nWARNING: " + msg)


# ---------------------------------------------------------------------------
# Image sources for upload
# ---------------------------------------------------------------------------


def parse_image_source_file(path: Path, logo_key: str) -> list[str]:
    logo_map: dict[str, str] = {}
    regular_sources: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                logo_map[key] = value
            continue
        regular_sources.append(line)
    selected_logo = logo_map.get(logo_key, "")
    return ([selected_logo] + regular_sources) if selected_logo else regular_sources


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def download_to_temp(source: str, temp_dir: Path) -> Path:
    parsed = urllib.parse.urlparse(source)
    suffix = Path(parsed.path).suffix or ".png"
    filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", Path(parsed.path).stem) or "image"
    out_path = temp_dir / f"{filename}{suffix}"
    req = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        out_path.write_bytes(resp.read())
    return out_path


def build_local_image_paths(sources: list[str], temp_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for src in sources:
        if is_url(src):
            paths.append(download_to_temp(src, temp_dir))
        else:
            p = Path(src).expanduser()
            if not p.is_absolute():
                p = Path.cwd() / p
            if not p.exists():
                raise FileNotFoundError(f"Image path not found: {p}")
            paths.append(p.resolve())
    if not paths:
        raise ValueError("No images resolved for upload")
    return paths


def collect_upload_images_from_dir(upload_dir: Path) -> list[Path]:
    if not upload_dir.exists():
        raise FileNotFoundError(f"Upload directory not found: {upload_dir}")
    if not upload_dir.is_dir():
        raise NotADirectoryError(f"Upload path is not a directory: {upload_dir}")
    images = [p.resolve() for p in sorted(upload_dir.iterdir()) if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    if not images:
        raise FileNotFoundError(f"No image files found in {upload_dir}")
    return images


# ---------------------------------------------------------------------------
# Browser setup
# ---------------------------------------------------------------------------


def resolve_browser_binary(args: argparse.Namespace) -> str:
    if args.browser == "brave":
        for candidate in ["/usr/bin/brave-browser", "/usr/bin/brave", "/snap/bin/brave"]:
            if Path(candidate).exists():
                return candidate
        return ""
    for candidate in [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]:
        if Path(candidate).exists():
            return candidate
    return ""


def debugger_endpoint_reachable(address: str) -> bool:
    if not address:
        return False
    try:
        with urllib.request.urlopen(f"http://{address}/json/version", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def auto_launch_debug_browser(args: argparse.Namespace) -> None:
    if not args.attach_debugger_address:
        return
    if debugger_endpoint_reachable(args.attach_debugger_address):
        return

    binary = resolve_browser_binary(args)
    if not binary:
        raise RuntimeError(f"Could not resolve {args.browser} binary for debugger attach")
    host, _, port = args.attach_debugger_address.partition(":")
    if not host or not port:
        raise ValueError("--attach-debugger-address must look like host:port")

    user_data_dir = Path(args.debug_user_data_dir).expanduser()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        binary,
        f"--remote-debugging-address={host}",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={str(user_data_dir)}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    print("Debugger endpoint not reachable. Auto-launching browser for attach...")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    deadline = time.time() + 20
    while time.time() < deadline:
        if debugger_endpoint_reachable(args.attach_debugger_address):
            print(f"Debugger endpoint is live at {args.attach_debugger_address}")
            return
        time.sleep(0.5)
    raise RuntimeError(f"Browser launched, but debugger endpoint is not reachable at {args.attach_debugger_address}")


def build_driver(args: argparse.Namespace, download_dir: Path) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if args.attach_debugger_address:
        options.add_experimental_option("debuggerAddress", args.attach_debugger_address)
    selected_binary = ""
    if not args.attach_debugger_address:
        selected_binary = resolve_browser_binary(args)
        if selected_binary:
            options.binary_location = selected_binary

    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-dev-shm-usage")
    if args.user_data_dir:
        options.add_argument(f"--user-data-dir={args.user_data_dir}")
    if args.profile_directory:
        options.add_argument(f"--profile-directory={args.profile_directory}")
    if args.headless:
        options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    if selected_binary:
        print(f"Using browser binary: {selected_binary}")
    try:
        driver.set_page_load_timeout(120)
        driver.set_script_timeout(180)
    except Exception:
        pass
    return driver


def configure_download_dir(driver: webdriver.Chrome, download_dir: Path) -> None:
    download_dir.mkdir(parents=True, exist_ok=True)
    for command in ["Page.setDownloadBehavior", "Browser.setDownloadBehavior"]:
        try:
            params = {"behavior": "allow", "downloadPath": str(download_dir)}
            if command.startswith("Browser"):
                params = {"behavior": "allow", "downloadPath": str(download_dir), "eventsEnabled": True}
            driver.execute_cdp_cmd(command, params)
            return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# App readiness and fresh chat navigation
# ---------------------------------------------------------------------------


def is_blankish_url(url: str) -> bool:
    lower = (url or "").lower()
    return lower in ("", "about:blank") or lower.startswith("chrome://newtab") or lower.startswith("data:")


def gemini_app_ready(driver: webdriver.Chrome) -> bool:
    try:
        current = (driver.current_url or "").lower()
    except Exception:
        return False
    if "gemini.google.com" not in current:
        return False
    selectors = [
        "rich-textarea div[contenteditable='true']",
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
        "textarea[aria-label*='message']",
        "textarea",
        "button[aria-label*='New chat']",
    ]
    for selector in selectors:
        try:
            if any(el.is_displayed() for el in driver.find_elements(By.CSS_SELECTOR, selector)):
                return True
        except Exception:
            continue
    return False


def wait_for_manual_login(driver: webdriver.Chrome, timeout: int, strict: bool) -> None:
    print("Waiting for Gemini login/readiness...")
    deadline = time.time() + timeout
    next_log = time.time() + 5
    while time.time() < deadline:
        if gemini_app_ready(driver):
            print(f"Gemini UI looks ready at {driver.current_url}. Continuing.")
            return
        if time.time() >= next_log:
            try:
                current = driver.current_url
            except Exception:
                current = "<unavailable>"
            print(f"Still waiting for Gemini UI readiness... current URL: {current}")
            next_log = time.time() + 5
        time.sleep(1.0)
    msg = f"Timed out after {timeout}s waiting for Gemini readiness"
    if strict:
        raise TimeoutException(msg)
    print(f"{msg}; continuing in auto mode.")


def _url_is_base_app(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if "gemini.google.com" not in parsed.netloc:
        return False
    path = parsed.path.rstrip("/")
    return path == "/app"


def _url_looks_like_old_conversation(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if "gemini.google.com" not in parsed.netloc:
        return False
    path = parsed.path.rstrip("/")
    return path.startswith("/app/") and path != "/app"


def _url_looks_temporary(url: str) -> bool:
    lower = (url or "").lower()
    return "temporary" in lower or "temp_chat" in lower or "tempchat" in lower


def dismiss_open_overlays(driver: webdriver.Chrome) -> None:
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    selectors = [
        ".mat-drawer-backdrop",
        ".cdk-overlay-backdrop",
        "[role='dialog'] [aria-label='Close']",
        "button[aria-label*='Close']",
    ]
    for selector in selectors:
        for el in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                if el.is_displayed():
                    el.click()
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", el)
                except Exception:
                    pass


def page_heading_looks_temporary(driver: webdriver.Chrome) -> bool:
    script = r"""
        const headings = Array.from(document.querySelectorAll('main h1, main h2, header h1, header h2, [role="heading"]'));
        for (const h of headings) {
            const t = (h.innerText || h.textContent || '').trim().toLowerCase();
            const r = h.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && t === 'temporary chat') return true;
        }
        const title = (document.title || '').toLowerCase();
        return title.includes('temporary chat');
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def assert_not_temporary_chat(driver: webdriver.Chrome) -> None:
    url = ""
    try:
        url = driver.current_url or ""
    except Exception:
        pass
    if _url_looks_temporary(url) or page_heading_looks_temporary(driver):
        raise RuntimeError(
            "Gemini appears to be in Temporary chat mode. The script will not continue "
            "because you asked not to use temporary chats. Turn Temporary chat off manually "
            "and re-run."
        )


def click_dedicated_new_chat(driver: webdriver.Chrome) -> bool:
    """Click only a real New chat button/link. Never click history rows or 3-dot menus."""
    script = r"""
        function visible(el) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
        }
        function unsafe(el) {
            const txt = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).toLowerCase();
            const bad = ['share', 'rename', 'delete', 'archive', 'more options'];
            return bad.some(x => txt.includes(x));
        }
        const nodes = Array.from(document.querySelectorAll('a,button,[role="button"]'));
        const candidates = nodes.filter(el => {
            if (!visible(el) || unsafe(el)) return false;
            const txt = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).trim().toLowerCase();
            if (!(txt.includes('new chat') || txt.includes('new conversation'))) return false;
            const r = el.getBoundingClientRect();
            // Sidebar/top-left New chat is acceptable. Old-chat rows are usually not named New chat.
            return r.left < 520 || txt.includes('new chat') || txt.includes('new conversation');
        });
        if (!candidates.length) return false;
        candidates.sort((a, b) => {
            const ar = a.getBoundingClientRect();
            const br = b.getBoundingClientRect();
            return (ar.left - br.left) || (ar.top - br.top);
        });
        candidates[0].click();
        return true;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def open_prompt_tab(driver: webdriver.Chrome, job_index: int, first_tab_mode: str, download_dir: Path) -> None:
    """Open/switch to the tab that will own this prompt."""
    use_current = False
    if job_index == 1 and first_tab_mode == "reuse-blank":
        try:
            use_current = is_blankish_url(driver.current_url or "")
        except Exception:
            use_current = False

    if use_current:
        print("  [tab] Reusing Selenium's initial blank tab for the first prompt.")
    else:
        print("  [tab] Opening a new tab for this prompt.")
        try:
            driver.switch_to.new_window("tab")
        except Exception:
            handles_before = set(driver.window_handles)
            driver.execute_script("window.open('about:blank', '_blank');")
            time.sleep(0.5)
            new_handles = set(driver.window_handles) - handles_before
            driver.switch_to.window(list(new_handles)[0] if new_handles else driver.window_handles[-1])
    configure_download_dir(driver, download_dir)


def navigate_to_fresh_chat(driver: webdriver.Chrome, manual_login_timeout: int, strict_login: bool) -> None:
    """Navigate to a fresh Gemini chat without touching old chat rows."""
    last_url = ""
    for attempt in range(1, 4):
        print(f"  [fresh] Navigation attempt {attempt}: {GEMINI_URL}")
        try:
            driver.get(GEMINI_URL)
        except Exception as exc:
            print(f"  [fresh] driver.get raised: {exc}")
        wait_for_manual_login(driver, timeout=manual_login_timeout, strict=strict_login)
        dismiss_open_overlays(driver)
        time.sleep(1.0)
        try:
            last_url = driver.current_url or ""
        except Exception:
            last_url = ""
        print(f"  [fresh] Current URL: {last_url}")
        assert_not_temporary_chat(driver)

        if _url_is_base_app(last_url):
            find_composer(driver, timeout=30)
            print("  [fresh] Fresh base /app chat confirmed.")
            return

        if _url_looks_like_old_conversation(last_url):
            print("  [fresh] Gemini redirected to an old conversation. Clicking only dedicated New chat.")
            if click_dedicated_new_chat(driver):
                time.sleep(2.0)
                dismiss_open_overlays(driver)
                try:
                    last_url = driver.current_url or ""
                except Exception:
                    last_url = ""
                assert_not_temporary_chat(driver)
                if _url_is_base_app(last_url) or not _url_looks_like_old_conversation(last_url):
                    find_composer(driver, timeout=30)
                    print("  [fresh] New chat opened using dedicated New chat control.")
                    return
            print("  [fresh] Dedicated New chat did not produce a fresh page; retrying base URL.")
            continue

        try:
            find_composer(driver, timeout=10)
            print("  [fresh] Composer present on Gemini page; continuing.")
            return
        except Exception:
            pass

    raise RuntimeError(f"Could not guarantee a fresh Gemini chat. Last URL: {last_url}")


# ---------------------------------------------------------------------------
# Safe UI clicking helpers
# ---------------------------------------------------------------------------


def _safe_click_js(driver: webdriver.Chrome, labels: Iterable[str], exact: bool = False, timeout: float = 8.0) -> bool:
    labels_list = [x.lower().strip() for x in labels if x.strip()]
    deadline = time.time() + timeout
    while time.time() < deadline:
        clicked = driver.execute_script(
            r"""
            const labels = arguments[0];
            const exact = arguments[1];
            const badWords = arguments[2];
            function visible(el) {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
            }
            function inForbiddenArea(el) {
                return !!el.closest('nav, [role="navigation"], [aria-label*="Recent"], [aria-label*="Conversation history"], .conversation-list, .history');
            }
            function bad(el) {
                const txt = ((el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '') + ' ' + (el.innerText || '')).toLowerCase();
                if (badWords.some(w => txt.includes(w))) return true;
                return false;
            }
            const roots = Array.from(document.querySelectorAll('main, header, [role="dialog"], .cdk-overlay-container, body'));
            const nodes = [];
            for (const root of roots) {
                for (const el of root.querySelectorAll('button,a,[role="button"],[role="menuitem"],[role="option"],[role="menuitemradio"],mat-option')) {
                    if (!nodes.includes(el)) nodes.push(el);
                }
            }
            const candidates = [];
            for (const el of nodes) {
                if (!visible(el) || bad(el)) continue;
                // Do not click sidebar/history unless it is explicitly New chat (handled elsewhere).
                if (inForbiddenArea(el)) continue;
                const txt = ((el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '') + ' ' + (el.innerText || '')).trim().toLowerCase();
                if (!txt) continue;
                for (const label of labels) {
                    if ((exact && txt === label) || (!exact && txt.includes(label))) {
                        candidates.push(el);
                        break;
                    }
                }
            }
            if (!candidates.length) return false;
            candidates.sort((a,b) => {
                const ar = a.getBoundingClientRect();
                const br = b.getBoundingClientRect();
                // Prefer lower/right side controls for composer/tool buttons, then visible menu items.
                return (br.top - ar.top) || (br.left - ar.left);
            });
            candidates[0].scrollIntoView({block:'center', inline:'center'});
            candidates[0].click();
            return true;
            """,
            labels_list,
            exact,
            list(UNSAFE_CLICK_WORDS),
        )
        if clicked:
            return True
        time.sleep(0.3)
    return False


def safe_click_labels(driver: webdriver.Chrome, labels: Iterable[str], timeout: float = 8.0, exact: bool = False) -> bool:
    try:
        return _safe_click_js(driver, labels, exact=exact, timeout=timeout)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Composer, model/tool, upload, and send
# ---------------------------------------------------------------------------


def find_composer(driver: webdriver.Chrome, timeout: int = 30):
    wait = WebDriverWait(driver, timeout)
    selectors = [
        "rich-textarea div[contenteditable='true']",
        "div[contenteditable='true'][role='textbox']",
        "main div[contenteditable='true']",
        "textarea[aria-label*='message']",
        "textarea",
    ]
    last_error: Exception | None = None
    for selector in selectors:
        try:
            elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            if elem.is_displayed():
                return elem
        except Exception as exc:
            last_error = exc
    raise TimeoutException(f"Could not find Gemini composer. Last error: {last_error}")


def get_composer_text(driver: webdriver.Chrome, composer: Any) -> str:
    """Read text from Gemini's real composer, not old messages or upload chips."""
    script = r"""
        const root = arguments[0];
        function readText(el) {
            if (!el) return '';
            const tag = (el.tagName || '').toLowerCase();
            if (tag === 'textarea' || tag === 'input') return el.value || '';
            if (el.isContentEditable || el.getAttribute('contenteditable') === 'true') {
                return el.innerText || el.textContent || '';
            }
            if (el.querySelector) {
                const child = el.querySelector('textarea, input, [contenteditable="true"], [role="textbox"]');
                if (child) return readText(child);
            }
            return el.innerText || el.textContent || '';
        }
        return readText(root);
    """
    try:
        return driver.execute_script(script, composer) or ""
    except Exception:
        return ""


def _normalize_prompt_compare(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    # Gemini's rich textarea may collapse indentation but should not remove words.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def _compact_prompt_compare(text: str) -> str:
    return re.sub(r"\s+", " ", _normalize_prompt_compare(text)).strip()


def _sample_chunks(text: str, chunk_size: int = 96) -> list[str]:
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    positions = [0, int(len(text) * 0.25), int(len(text) * 0.50), int(len(text) * 0.75), max(0, len(text) - chunk_size)]
    chunks: list[str] = []
    seen: set[str] = set()
    for pos in positions:
        pos = min(max(0, pos), max(0, len(text) - chunk_size))
        chunk = text[pos : pos + chunk_size].strip()
        if len(chunk) < 24:
            continue
        if chunk not in seen:
            seen.add(chunk)
            chunks.append(chunk)
    return chunks


def prompt_integrity_report(expected: str, actual: str, min_ratio: float = 0.98) -> dict[str, Any]:
    expected_compact = _compact_prompt_compare(expected)
    actual_compact = _compact_prompt_compare(actual)
    expected_len = len(expected_compact)
    actual_len = len(actual_compact)
    ratio = (actual_len / expected_len) if expected_len else 1.0

    prefix_len = min(160, expected_len)
    suffix_len = min(160, expected_len)
    prefix_ok = bool(expected_len == 0 or actual_compact.startswith(expected_compact[:prefix_len]))
    suffix_ok = bool(expected_len == 0 or actual_compact.endswith(expected_compact[-suffix_len:]))

    chunks = _sample_chunks(expected_compact)
    found_chunks = sum(1 for chunk in chunks if chunk in actual_compact)
    chunks_ok = found_chunks == len(chunks)
    ok = bool(ratio >= min_ratio and prefix_ok and suffix_ok and chunks_ok)

    return {
        "ok": ok,
        "expected_len": expected_len,
        "actual_len": actual_len,
        "ratio": ratio,
        "prefix_ok": prefix_ok,
        "suffix_ok": suffix_ok,
        "chunks_found": found_chunks,
        "chunks_total": len(chunks),
        "actual_preview_start": actual_compact[:180],
        "actual_preview_end": actual_compact[-180:] if actual_compact else "",
    }


def format_prompt_integrity(report: dict[str, Any]) -> str:
    return (
        f"expected={report.get('expected_len')} compact chars, "
        f"actual={report.get('actual_len')} compact chars, "
        f"ratio={report.get('ratio', 0.0):.1%}, "
        f"prefix={report.get('prefix_ok')}, suffix={report.get('suffix_ok')}, "
        f"chunks={report.get('chunks_found')}/{report.get('chunks_total')}"
    )


def write_prompt_debug_file(path: Path | None, expected: str, actual: str, report: dict[str, Any], method: str) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = [
            "PROMPT PASTE / SEND INTEGRITY FAILURE",
            f"method: {method}",
            format_prompt_integrity(report),
            "",
            "--- ACTUAL COMPOSER TEXT START ---",
            actual or "",
            "--- ACTUAL COMPOSER TEXT END ---",
            "",
            "--- EXPECTED PROMPT START ---",
            expected or "",
            "--- EXPECTED PROMPT END ---",
            "",
        ]
        path.write_text("\n".join(body), encoding="utf-8")
        print(f"  [prompt] Wrote composer debug file: {path}")
    except Exception as exc:
        print(f"  [prompt] Could not write debug file {path}: {exc}")


def focus_composer(driver: webdriver.Chrome, composer: Any) -> None:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", composer)
    except Exception:
        pass
    for _ in range(3):
        try:
            composer.click()
            break
        except ElementClickInterceptedException:
            dismiss_open_overlays(driver)
            time.sleep(0.3)
        except Exception:
            try:
                driver.execute_script("arguments[0].focus();", composer)
                break
            except Exception:
                pass
    try:
        driver.execute_script("arguments[0].focus();", composer)
    except Exception:
        pass
    time.sleep(0.15)


def clear_composer_keyboard(driver: webdriver.Chrome, composer: Any) -> None:
    focus_composer(driver, composer)
    try:
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
    except Exception:
        try:
            composer.send_keys(Keys.CONTROL, "a")
            composer.send_keys(Keys.BACKSPACE)
        except Exception:
            pass
    time.sleep(0.25)


def paste_prompt_via_cdp(driver: webdriver.Chrome, text: str) -> bool:
    """Use Chrome DevTools Input.insertText so newlines are inserted as text, not Enter keypresses."""
    try:
        composer = find_composer(driver, timeout=10)
        clear_composer_keyboard(driver, composer)
        composer = find_composer(driver, timeout=5)
        focus_composer(driver, composer)
        driver.execute_cdp_cmd("Input.insertText", {"text": text})
        return True
    except Exception as exc:
        print(f"  [prompt] CDP insertText failed: {exc}")
        return False


def grant_clipboard_permissions(driver: webdriver.Chrome) -> None:
    for permissions in (["clipboardReadWrite", "clipboardSanitizedWrite"], ["clipboardReadWrite"]):
        try:
            driver.execute_cdp_cmd(
                "Browser.grantPermissions",
                {"origin": "https://gemini.google.com", "permissions": list(permissions)},
            )
            return
        except Exception:
            continue


def write_browser_clipboard(driver: webdriver.Chrome, text: str) -> bool:
    try:
        grant_clipboard_permissions(driver)
        try:
            driver.set_script_timeout(60)
        except Exception:
            pass
        result = driver.execute_async_script(
            r"""
            const text = arguments[0];
            const done = arguments[arguments.length - 1];
            if (!navigator.clipboard || !navigator.clipboard.writeText) {
                done({ok:false, error:'navigator.clipboard.writeText unavailable'});
                return;
            }
            navigator.clipboard.writeText(text)
                .then(() => done({ok:true}))
                .catch(err => done({ok:false, error:String(err)}));
            """,
            text,
        )
        if isinstance(result, dict) and result.get("ok"):
            return True
        print(f"  [prompt] Browser clipboard write failed: {result}")
        return False
    except Exception as exc:
        print(f"  [prompt] Browser clipboard write error: {exc}")
        return False


def paste_prompt_via_clipboard(driver: webdriver.Chrome, text: str) -> bool:
    """Paste through the browser clipboard; this updates Gemini like a real user paste."""
    if not write_browser_clipboard(driver, text):
        return False
    try:
        composer = find_composer(driver, timeout=10)
        clear_composer_keyboard(driver, composer)
        composer = find_composer(driver, timeout=5)
        focus_composer(driver, composer)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
        return True
    except Exception as exc:
        print(f"  [prompt] Clipboard paste failed: {exc}")
        return False


def paste_prompt_via_js_last_resort(driver: webdriver.Chrome, text: str) -> bool:
    """Last-resort DOM insertion. It is verified strictly before Send is allowed."""
    script = r"""
        const el = arguments[0];
        const text = arguments[1];
        el.scrollIntoView({block:'center', inline:'center'});
        el.focus();
        const tag = (el.tagName || '').toLowerCase();
        if (tag === 'textarea' || tag === 'input') {
            el.value = '';
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.value = text;
            el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertFromPaste', data:text}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
            return true;
        }
        const dt = new DataTransfer();
        dt.setData('text/plain', text);
        const pasteEvent = new ClipboardEvent('paste', {bubbles:true, cancelable:true, clipboardData:dt});
        el.dispatchEvent(pasteEvent);
        if ((el.innerText || '').trim().length < 10) {
            el.textContent = '';
            document.execCommand('insertText', false, text);
        }
        el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertFromPaste', data:text}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        return true;
    """
    try:
        composer = find_composer(driver, timeout=10)
        clear_composer_keyboard(driver, composer)
        composer = find_composer(driver, timeout=5)
        focus_composer(driver, composer)
        return bool(driver.execute_script(script, composer, text))
    except Exception as exc:
        print(f"  [prompt] JS last-resort insert failed: {exc}")
        return False


def wait_for_prompt_integrity(
    driver: webdriver.Chrome,
    expected: str,
    timeout: float,
    min_ratio: float,
) -> tuple[Any, str, dict[str, Any]]:
    deadline = time.time() + timeout
    last_composer: Any = None
    last_actual = ""
    last_report = prompt_integrity_report(expected, "", min_ratio)
    while time.time() < deadline:
        try:
            last_composer = find_composer(driver, timeout=3)
            last_actual = get_composer_text(driver, last_composer)
            last_report = prompt_integrity_report(expected, last_actual, min_ratio)
            if last_report["ok"]:
                return last_composer, last_actual, last_report
        except Exception:
            pass
        time.sleep(0.5)
    if last_composer is None:
        last_composer = find_composer(driver, timeout=5)
    return last_composer, last_actual, last_report


def _prompt_methods_for(method: str) -> list[str]:
    if method == "auto":
        # Do not silently fall back to DOM/JS insertion in auto mode. JS can make
        # the composer look full while Gemini's internal editor state is stale.
        # Failing is safer than sending a partial prompt.
        return ["cdp", "clipboard"]
    return [method]


def set_prompt_text(
    driver: webdriver.Chrome,
    text: str,
    method: str = "auto",
    verify_timeout: float = 35,
    min_integrity_ratio: float = 0.98,
    debug_path: Path | None = None,
) -> Any:
    print(f"  [prompt] Expected prompt: {len(text)} chars, {text.count(chr(10)) + 1} lines")
    last_actual = ""
    last_report = prompt_integrity_report(text, "", min_integrity_ratio)
    last_method = method

    for selected_method in _prompt_methods_for(method):
        last_method = selected_method
        print(f"  [prompt] Inserting with method: {selected_method}")
        if selected_method == "cdp":
            inserted = paste_prompt_via_cdp(driver, text)
        elif selected_method == "clipboard":
            inserted = paste_prompt_via_clipboard(driver, text)
        elif selected_method == "js":
            inserted = paste_prompt_via_js_last_resort(driver, text)
        else:
            inserted = False

        if not inserted:
            continue

        composer, actual, report = wait_for_prompt_integrity(
            driver,
            expected=text,
            timeout=verify_timeout,
            min_ratio=min_integrity_ratio,
        )
        last_actual = actual
        last_report = report
        print(f"  [prompt] Verify after {selected_method}: {format_prompt_integrity(report)}")
        if report["ok"]:
            print("  [prompt] Full prompt integrity confirmed before Send.")
            return composer

    write_prompt_debug_file(debug_path, text, last_actual, last_report, last_method)
    raise TimeoutException(
        "Prompt was not inserted completely; refusing to send partial prompt. "
        + format_prompt_integrity(last_report)
        + " | actual_start="
        + repr(last_report.get("actual_preview_start", "")[:120])
        + " | actual_end="
        + repr(last_report.get("actual_preview_end", "")[-120:])
    )


def _send_button_diagnostics(driver: webdriver.Chrome, composer: Any | None = None) -> list[str]:
    """Return a short list of visible composer-area buttons for debugging."""
    script = r"""
        const composer = arguments[0] || null;
        function visible(el) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
        }
        const cr = composer && composer.getBoundingClientRect ? composer.getBoundingClientRect() : null;
        const out = [];
        const nodes = Array.from(document.querySelectorAll('main button, main [role="button"]'));
        for (const b of nodes) {
            if (!visible(b)) continue;
            const r = b.getBoundingClientRect();
            if (cr) {
                const nearY = r.top < cr.bottom + 220 && r.bottom > cr.top - 120;
                if (!nearY) continue;
            } else if (r.top < window.innerHeight * 0.45) {
                continue;
            }
            const txt = ((b.getAttribute('aria-label') || '') + ' | ' + (b.getAttribute('title') || '') + ' | ' + (b.innerText || '')).replace(/\s+/g, ' ').trim();
            out.push(`${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}x${Math.round(r.height)} disabled=${!!b.disabled || b.getAttribute('aria-disabled') === 'true'} :: ${txt.slice(0, 140)}`);
            if (out.length >= 12) break;
        }
        return out;
    """
    try:
        return list(driver.execute_script(script, composer) or [])
    except Exception:
        return []


def find_enabled_send_button(driver: webdriver.Chrome, composer: Any | None = None, loose: bool = False):
    """
    Find Gemini's actual composer Send/Submit control.

    The earlier versions looked only for aria-label text containing "Send".
    Gemini often exposes the submit control as an icon-only button, or changes
    the label to "Submit prompt". This finder scores visible enabled buttons by
    text/icon AND position relative to the composer, while avoiding sidebar,
    upload, tools, mic, model, share, and old-chat controls.
    """
    script = r"""
        const composer = arguments[0] || null;
        const loose = !!arguments[1];

        function visible(el) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
        }
        function disabled(el) {
            return !!el.disabled || el.getAttribute('aria-disabled') === 'true' || el.classList.contains('disabled');
        }
        function textOf(el) {
            const iconText = Array.from(el.querySelectorAll('mat-icon, .material-icons, .material-symbols-outlined, svg title'))
                .map(x => x.textContent || '').join(' ');
            return ((el.getAttribute('aria-label') || '') + ' ' +
                    (el.getAttribute('title') || '') + ' ' +
                    (el.getAttribute('data-testid') || '') + ' ' +
                    (el.getAttribute('data-test-id') || '') + ' ' +
                    (el.innerText || '') + ' ' + iconText).replace(/\s+/g, ' ').trim().toLowerCase();
        }
        function inForbiddenArea(el) {
            return !!el.closest('nav, [role="navigation"], [aria-label*="Recent"], [aria-label*="Conversation history"], .conversation-list, .history');
        }

        const badWords = [
            'add files', 'attach', 'attachment', 'upload', 'insert', 'image', 'photo',
            'microphone', 'mic', 'voice', 'tools', 'tool', 'model', 'flash', 'fast', 'pro',
            'close', 'cancel', 'menu', 'more options', 'share', 'new chat', 'temporary chat',
            'settings', 'apps', 'account', 'help', 'delete', 'rename', 'archive'
        ];
        const sendWords = ['send', 'submit', 'arrow_upward', 'arrow_forward', 'paper_plane', 'send_message'];

        const cr = composer && composer.getBoundingClientRect ? composer.getBoundingClientRect() : null;
        const nodes = Array.from(document.querySelectorAll('main button, main [role="button"], button[aria-label*="Send"], button[aria-label*="Submit"]'));
        const seen = new Set();
        const candidates = [];

        for (const el of nodes) {
            if (!el || seen.has(el)) continue;
            seen.add(el);
            if (!visible(el) || disabled(el) || inForbiddenArea(el)) continue;
            const t = textOf(el);
            const r = el.getBoundingClientRect();
            const named = sendWords.some(w => t.includes(w)) || ((el.getAttribute('type') || '').toLowerCase() === 'submit');
            if (badWords.some(w => t.includes(w)) && !named) continue;

            let score = 0;
            if (t.includes('send message')) score += 260;
            if (t.includes('send')) score += 230;
            if (t.includes('submit')) score += 220;
            if (t.includes('arrow_upward') || t.includes('send_message') || t.includes('paper_plane')) score += 180;
            if ((el.getAttribute('type') || '').toLowerCase() === 'submit') score += 150;

            let nearComposer = false;
            if (cr) {
                const midY = (r.top + r.bottom) / 2;
                const compMidY = (cr.top + cr.bottom) / 2;
                const vertical = r.top < cr.bottom + 220 && r.bottom > cr.top - 140;
                const rightSide = r.left > cr.left + cr.width * 0.52 || r.right > window.innerWidth * 0.66;
                nearComposer = vertical && rightSide;
                if (nearComposer) score += 140;
                score += Math.max(0, 45 - Math.abs(midY - compMidY) / 6);
                score += Math.max(0, (r.left - cr.left) / 25);
            } else {
                if (r.top > window.innerHeight * 0.55 && r.left > window.innerWidth * 0.55) score += 80;
            }

            // Strict mode requires a name/icon/type. Loose mode permits a highly
            // positioned bottom-right enabled button near the composer.
            if (!named && !(loose && nearComposer && score >= 120)) continue;

            // Avoid very large container buttons.
            if (r.width > 360 || r.height > 120) score -= 120;
            candidates.push({el, score, top: r.top, left: r.left, text: t});
        }

        if (!candidates.length) return null;
        candidates.sort((a, b) => (b.score - a.score) || (b.top - a.top) || (b.left - a.left));
        return candidates[0].el;
    """
    try:
        return driver.execute_script(script, composer, loose)
    except Exception:
        return None


def wait_until_send_enabled(driver: webdriver.Chrome, composer: Any | None = None, timeout: float = 20.0, loose: bool = False):
    deadline = time.time() + timeout
    while time.time() < deadline:
        btn = find_enabled_send_button(driver, composer=composer, loose=loose)
        if btn is not None:
            return btn
        time.sleep(0.35)
    return None


def generation_in_progress(driver: webdriver.Chrome) -> bool:
    script = r"""
        const main = document.querySelector('main') || document.body;
        const txt = (main.innerText || '').toLowerCase();
        if (txt.includes('generating') || txt.includes('creating image') || txt.includes('creating your image') || txt.includes('working on it')) return true;
        for (const el of main.querySelectorAll('[role="progressbar"], mat-progress-spinner, .spinner, .loading, .progress')) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            if (r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden') return true;
        }
        for (const b of main.querySelectorAll('button, [role="button"]')) {
            const t = ((b.getAttribute('aria-label') || '') + ' ' + (b.getAttribute('title') || '') + ' ' + (b.innerText || '')).toLowerCase();
            if (t.includes('stop') || t.includes('cancel generation') || t.includes('stop response')) return true;
        }
        return false;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def _submission_needles(expected_prompt: str | None) -> list[str]:
    if not expected_prompt:
        return []
    lines = []
    for raw in expected_prompt.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) < 14:
            continue
        # Prefer distinctive headings and exact-copy lines; avoid generic bullets first.
        lines.append(line)
    needles: list[str] = []
    for line in lines[:12]:
        if line not in needles:
            needles.append(line[:110])
        if len(line) > 34:
            short = line[:34].strip()
            if short not in needles:
                needles.append(short)
        if len(needles) >= 8:
            break
    compact = _compact_prompt_compare(expected_prompt)
    if compact:
        for size in (80, 48, 32):
            chunk = compact[:size].strip()
            if len(chunk) >= 14 and chunk not in needles:
                needles.append(chunk)
    return needles[:10]


def prompt_visible_outside_composer_count(driver: webdriver.Chrome, expected_prompt: str | None) -> int:
    """Count text-node matches for the prompt outside the editable composer."""
    needles = _submission_needles(expected_prompt)
    if not needles:
        return 0
    script = r"""
        const needles = arguments[0].map(x => (x || '').replace(/\s+/g, ' ').trim().toLowerCase()).filter(Boolean);
        if (!needles.length) return 0;
        const main = document.querySelector('main') || document.body;
        function visible(el) {
            if (!el) return false;
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
        }
        function skipParent(el) {
            if (!el) return true;
            if (el.closest('rich-textarea, [contenteditable="true"], textarea, input, nav, [role="navigation"], header, button, [role="button"]')) return true;
            return !visible(el);
        }
        let count = 0;
        const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
            const parent = node.parentElement;
            if (skipParent(parent)) continue;
            const txt = (node.nodeValue || '').replace(/\s+/g, ' ').trim().toLowerCase();
            if (!txt) continue;
            if (needles.some(n => txt.includes(n) || n.includes(txt))) count++;
        }
        return count;
    """
    try:
        return int(driver.execute_script(script, needles) or 0)
    except Exception:
        return 0


def wait_for_send_confirmation(
    driver: webdriver.Chrome,
    expected_prompt: str | None = None,
    before_marker_count: int = 0,
    timeout: float = 35.0,
    allow_progress_marker: bool = True,
) -> bool:
    """
    Confirm Gemini accepted the prompt.

    Important: an empty composer alone is NOT accepted as success anymore,
    because Gemini can clear/mutate the rich editor without actually starting
    the request. We require either a generation/progress signal or the prompt
    appearing as a submitted user message outside the composer.
    """
    deadline = time.time() + timeout
    saw_empty_composer = False
    while time.time() < deadline:
        if allow_progress_marker and generation_in_progress(driver):
            print("  [send] Prompt accepted; generation/progress indicator is active.")
            return True

        if expected_prompt:
            marker_count = prompt_visible_outside_composer_count(driver, expected_prompt)
            if marker_count > before_marker_count:
                print("  [send] Prompt accepted; user prompt is visible in the conversation.")
                return True

        try:
            current_composer = find_composer(driver, timeout=1)
            current_text = get_composer_text(driver, current_composer).strip()
        except Exception:
            current_text = ""
        if not current_text and not saw_empty_composer:
            print("  [send] Composer is empty, but waiting for a real submit/progress marker...")
            saw_empty_composer = True
        time.sleep(0.55)
    return False


def press_enter_to_send(driver: webdriver.Chrome, composer: Any) -> None:
    """Focus Gemini composer and perform a real Selenium Enter keypress."""
    composer = find_composer(driver, timeout=5)
    focus_composer(driver, composer)
    try:
        ActionChains(driver).move_to_element(composer).click(composer).pause(0.15).send_keys(Keys.ENTER).perform()
        return
    except Exception:
        pass
    try:
        composer.send_keys(Keys.ENTER)
        return
    except Exception:
        pass
    # Final keyboard fallback for Chrome. rawKeyDown is more reliable than keyDown here.
    driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})


def press_cdp_enter_to_send(driver: webdriver.Chrome, composer: Any) -> None:
    composer = find_composer(driver, timeout=5)
    focus_composer(driver, composer)
    driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})
    driver.execute_cdp_cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13})


def press_ctrl_enter_to_send(driver: webdriver.Chrome, composer: Any) -> None:
    composer = find_composer(driver, timeout=5)
    focus_composer(driver, composer)
    try:
        ActionChains(driver).move_to_element(composer).click(composer).pause(0.1).key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
        return
    except Exception:
        pass
    composer.send_keys(Keys.CONTROL, Keys.ENTER)


def click_send_button(driver: webdriver.Chrome, composer: Any | None = None, loose: bool = False) -> bool:
    try:
        composer = composer or find_composer(driver, timeout=3)
    except Exception:
        pass
    btn = wait_until_send_enabled(driver, composer=composer, timeout=12, loose=loose)
    if btn is None:
        diag = _send_button_diagnostics(driver, composer)
        if diag:
            print("  [send] Visible composer-area buttons when Send was not found:")
            for row in diag:
                print(f"  [send]   {row}")
        return False
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", btn)
        time.sleep(0.1)
    except Exception:
        pass
    try:
        ActionChains(driver).move_to_element(btn).pause(0.05).click(btn).perform()
        return True
    except Exception:
        pass
    try:
        btn.click()
        return True
    except Exception:
        pass
    try:
        driver.execute_script("arguments[0].click();", btn)
        return True
    except Exception:
        return False


def click_send_and_confirm(
    driver: webdriver.Chrome,
    composer: Any,
    expected_prompt: str | None = None,
    min_integrity_ratio: float = 0.98,
    debug_path: Path | None = None,
    settle_wait: float = 5.0,
    submit_method: str = "auto",
    confirm_timeout: float = 35.0,
) -> None:
    # Gemini's editor can take a moment to synchronize long pasted prompts.
    # The user asked for this small wait before the final completeness check.
    if settle_wait > 0:
        print(f"  [send] Waiting {settle_wait:g}s for Gemini composer to settle before final prompt check...")
        time.sleep(settle_wait)

    try:
        composer = find_composer(driver, timeout=5)
    except Exception:
        pass

    before_text = get_composer_text(driver, composer).strip()
    if expected_prompt is not None:
        report = prompt_integrity_report(expected_prompt, before_text, min_integrity_ratio)
        print(f"  [send] Final prompt check after settle wait: {format_prompt_integrity(report)}")
        if not report["ok"]:
            write_prompt_debug_file(debug_path, expected_prompt, before_text, report, "before-send-after-settle")
            raise TimeoutException(
                "Refusing to send because Gemini composer does not contain the complete prompt after the settle wait. "
                + format_prompt_integrity(report)
            )
    elif not before_text:
        raise TimeoutException("Cannot send because Gemini composer is empty")

    before_marker_count = prompt_visible_outside_composer_count(driver, expected_prompt)
    before_progress_active = generation_in_progress(driver)
    print(f"  [send] Existing submitted-prompt markers before Send: {before_marker_count}")
    if before_progress_active:
        print("  [send] A progress indicator was already active before submit; progress alone will not be accepted as confirmation.")

    submit_method = (submit_method or "auto").lower().strip()
    if submit_method == "enter":
        attempts = ["enter", "button", "cdp_enter", "ctrl_enter", "button_loose"]
    elif submit_method == "click":
        attempts = ["button", "button_loose", "enter", "cdp_enter", "ctrl_enter"]
    else:
        # Auto prioritizes the real Gemini submit button because long rich-text
        # prompts often treat Enter as newline/no-op.
        attempts = ["button", "enter", "cdp_enter", "ctrl_enter", "button_loose"]

    last_error = ""
    for method in attempts:
        print(f"  [send] Trying submit method: {method}")
        try:
            if method == "enter":
                press_enter_to_send(driver, composer)
            elif method == "cdp_enter":
                press_cdp_enter_to_send(driver, composer)
            elif method == "click":
                # Backward-compatible alias; not used in the attempts list.
                if not click_send_button(driver, composer=composer, loose=False):
                    last_error = "enabled Send/Submit button was not found/clickable"
                    continue
            elif method == "button":
                if not click_send_button(driver, composer=composer, loose=False):
                    last_error = "strict Send/Submit button was not found/clickable"
                    continue
            elif method == "button_loose":
                if not click_send_button(driver, composer=composer, loose=True):
                    last_error = "loose bottom-right composer submit button was not found/clickable"
                    continue
            elif method == "ctrl_enter":
                press_ctrl_enter_to_send(driver, composer)
            else:
                continue
        except Exception as exc:
            last_error = str(exc)
            continue

        if wait_for_send_confirmation(
            driver,
            expected_prompt=expected_prompt,
            before_marker_count=before_marker_count,
            timeout=confirm_timeout,
            allow_progress_marker=not before_progress_active,
        ):
            return

        # If Enter only inserted a newline or did nothing, reacquire composer and try next method.
        try:
            composer = find_composer(driver, timeout=3)
        except Exception:
            pass
        last_error = f"{method} did not produce a real submit/progress marker within {confirm_timeout:g}s"

    raise TimeoutException(
        "Gemini did not accept the prompt after button/Enter/Ctrl+Enter attempts. "
        + last_error
        + " | The script is stopping this prompt instead of moving on silently."
    )


def pro_model_selected(driver: webdriver.Chrome) -> bool:
    script = r"""
        const roots = Array.from(document.querySelectorAll('header, main'));
        for (const root of roots) {
            for (const el of root.querySelectorAll('button,[role="button"],.chip,.model-picker-container')) {
                const r = el.getBoundingClientRect();
                if (r.width <= 0 || r.height <= 0) continue;
                const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).toLowerCase();
                if (t.includes('pro') && !t.includes('project')) return true;
            }
        }
        return false;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def select_pro_model(driver: webdriver.Chrome) -> bool:
    if pro_model_selected(driver):
        return True
    # Open the model picker using safe labels. No generic button fallback.
    opened = safe_click_labels(driver, ["model", "fast", "flash", "gemini"], timeout=4)
    if not opened:
        return pro_model_selected(driver)
    time.sleep(0.8)
    safe_click_labels(driver, ["gemini 2.5 pro", "2.5 pro", "gemini pro", "pro"], timeout=5)
    time.sleep(1.0)
    dismiss_open_overlays(driver)
    return pro_model_selected(driver)


def create_image_tool_selected(driver: webdriver.Chrome) -> bool:
    script = r"""
        const roots = Array.from(document.querySelectorAll('header, main'));
        for (const root of roots) {
            const txt = (root.innerText || '').toLowerCase();
            if (txt.includes('create image') || txt.includes('image generation') || txt.includes('generate image')) return true;
        }
        return false;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def select_create_image_tool(driver: webdriver.Chrome) -> bool:
    if create_image_tool_selected(driver):
        return True
    opened = safe_click_labels(driver, ["tools"], timeout=4)
    if not opened:
        return create_image_tool_selected(driver)
    time.sleep(0.8)
    safe_click_labels(driver, ["create image", "image generation", "generate image"], timeout=5)
    time.sleep(0.8)
    dismiss_open_overlays(driver)
    return create_image_tool_selected(driver)


def select_model_and_tool_if_requested(driver: webdriver.Chrome, args: argparse.Namespace) -> None:
    if args.skip_model_selection:
        print("  [model] Skipping model/tool selection by request.")
        return
    pro_ok = select_pro_model(driver)
    print(f"  [model] Pro selected/confirmed: {pro_ok}")
    if args.require_pro_model and not pro_ok:
        raise TimeoutException("Could not confirm Pro model selection. Use --no-require-pro-model to continue anyway.")
    tool_ok = select_create_image_tool(driver)
    print(f"  [tool] Create image selected/confirmed: {tool_ok}")
    if args.require_create_image_tool and not tool_ok:
        raise TimeoutException("Could not confirm Create image tool. Use --no-require-create-image-tool to continue anyway.")


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------


def _find_file_input_anywhere(driver: webdriver.Chrome):
    direct = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
    for el in direct:
        try:
            if el.is_enabled():
                return el
        except Exception:
            continue
    script = r"""
        function gather(root, out) {
            if (!root) return;
            const nodes = root.querySelectorAll ? root.querySelectorAll('input[type="file"]') : [];
            for (const n of nodes) out.push(n);
            const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
            for (const el of all) {
                if (el.shadowRoot) gather(el.shadowRoot, out);
            }
        }
        const out = [];
        gather(document, out);
        return out.find(el => !el.disabled) || out[0] || null;
    """
    try:
        return driver.execute_script(script)
    except Exception:
        return None


def _find_file_input_across_frames(driver: webdriver.Chrome):
    driver.switch_to.default_content()
    root_candidate = _find_file_input_anywhere(driver)
    if root_candidate is not None:
        return root_candidate

    def search_frames(depth: int):
        if depth > 4:
            return None
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
        for idx in range(len(frames)):
            try:
                frame_ref = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")[idx]
                driver.switch_to.frame(frame_ref)
                candidate = _find_file_input_anywhere(driver)
                if candidate is not None:
                    return candidate
                nested = search_frames(depth + 1)
                if nested is not None:
                    return nested
            except Exception:
                pass
            finally:
                try:
                    driver.switch_to.parent_frame()
                except Exception:
                    driver.switch_to.default_content()
        return None

    result = search_frames(0)
    if result is None:
        driver.switch_to.default_content()
    return result


def click_attach_button_near_composer(driver: webdriver.Chrome) -> bool:
    script = r"""
        function visible(el) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
        }
        const composer = document.querySelector("rich-textarea div[contenteditable='true'], div[contenteditable='true'][role='textbox'], main div[contenteditable='true'], textarea");
        const cr = composer ? composer.getBoundingClientRect() : {left:0, right:window.innerWidth, top:window.innerHeight/2, bottom:window.innerHeight};
        const main = document.querySelector('main') || document.body;
        const nodes = Array.from(main.querySelectorAll('button,[role="button"]'));
        const candidates = nodes.filter(el => {
            if (!visible(el)) return false;
            const r = el.getBoundingClientRect();
            const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.title || '') + ' ' + (el.innerText || '')).toLowerCase();
            const nameOk = t.includes('add files') || t.includes('attach') || t.includes('upload') || t.includes('insert') || t.trim() === '+';
            if (!nameOk) return false;
            if (t.includes('temporary') || t.includes('share') || t.includes('conversation')) return false;
            const nearComposer = r.top > cr.top - 140 && r.bottom < cr.bottom + 140;
            return nearComposer;
        });
        if (!candidates.length) return false;
        candidates.sort((a,b) => {
            const ar = a.getBoundingClientRect();
            const br = b.getBoundingClientRect();
            return Math.abs(ar.top - cr.top) - Math.abs(br.top - cr.top);
        });
        candidates[0].click();
        return true;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def open_attachment_ui(driver: webdriver.Chrome) -> None:
    if _find_file_input_across_frames(driver) is not None:
        return
    click_attach_button_near_composer(driver)
    time.sleep(0.7)
    # If a menu opened, pick only upload-related items from the dialog/overlay/main, never sidebar/history.
    safe_click_labels(driver, ["upload files", "upload", "from computer", "add files"], timeout=3)
    time.sleep(0.7)


def get_all_image_srcs(driver: webdriver.Chrome) -> set[str]:
    script = r"""
        const out = new Set();
        for (const img of document.querySelectorAll('img')) {
            const src = img.currentSrc || img.src || '';
            if (src) out.add(src);
        }
        return Array.from(out);
    """
    try:
        return set(driver.execute_script(script) or [])
    except Exception:
        return set()


def upload_activity_present(driver: webdriver.Chrome) -> bool:
    script = r"""
        const main = document.querySelector('main') || document.body;
        const txt = (main.innerText || '').toLowerCase();
        if (txt.includes('uploading') || txt.includes('attaching')) return true;
        for (const el of main.querySelectorAll('[role="progressbar"], mat-progress-bar, mat-progress-spinner')) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) return true;
        }
        return false;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def wait_for_uploads_to_settle(driver: webdriver.Chrome, before_srcs: set[str], timeout: int = 90) -> None:
    deadline = time.time() + timeout
    saw_new_image_or_chip = False
    while time.time() < deadline:
        current = get_all_image_srcs(driver)
        if len(current - before_srcs) > 0:
            saw_new_image_or_chip = True
        try:
            chipish = driver.execute_script(
                r"""
                const main = document.querySelector('main') || document.body;
                const txt = (main.innerText || '').toLowerCase();
                return txt.includes('image') || txt.includes('attached') || txt.includes('file');
                """
            )
            if chipish:
                saw_new_image_or_chip = True
        except Exception:
            pass
        if saw_new_image_or_chip and not upload_activity_present(driver):
            return
        time.sleep(1.0)
    raise TimeoutException("Upload did not appear to settle before timeout")


def upload_images(driver: webdriver.Chrome, image_paths: list[Path], timeout: int = 45) -> None:
    for p in image_paths:
        if not p.exists():
            raise FileNotFoundError(f"Upload image not found: {p}")

    before_srcs = get_all_image_srcs(driver)
    open_attachment_ui(driver)
    end = time.time() + timeout
    file_input = None
    while time.time() < end:
        file_input = _find_file_input_across_frames(driver)
        if file_input is not None:
            break
        open_attachment_ui(driver)
        time.sleep(0.6)

    payload = "\n".join(str(p) for p in image_paths)
    if file_input is not None:
        file_input.send_keys(payload)
        wait_for_uploads_to_settle(driver, before_srcs, timeout=90)
        return

    # Last resort: synthetic drag/drop onto composer/main. This does not click any sidebar UI.
    driver.switch_to.default_content()
    try:
        drop_target = find_composer(driver, timeout=5)
    except Exception:
        candidates = driver.find_elements(By.CSS_SELECTOR, "main, body")
        if not candidates:
            raise TimeoutException("Could not find Gemini upload target")
        drop_target = candidates[0]

    temp_input = driver.execute_script(
        "const i=document.createElement('input');"
        "i.type='file'; i.multiple=true; i.style.display='none';"
        "document.body.appendChild(i); return i;"
    )
    temp_input.send_keys(payload)
    driver.execute_script(
        r"""
        const target = arguments[0], input = arguments[1];
        const dt = new DataTransfer();
        for (const f of input.files) dt.items.add(f);
        for (const ev of ['dragenter', 'dragover', 'drop']) {
            target.dispatchEvent(new DragEvent(ev, {bubbles:true, cancelable:true, dataTransfer:dt}));
        }
        target.dispatchEvent(new ClipboardEvent('paste', {bubbles:true, cancelable:true, clipboardData:dt}));
        input.remove();
        """,
        drop_target,
        temp_input,
    )
    wait_for_uploads_to_settle(driver, before_srcs, timeout=90)


# ---------------------------------------------------------------------------
# Generated image detection
# ---------------------------------------------------------------------------


def _image_candidates(driver: webdriver.Chrome, baseline_srcs: set[str]) -> list[dict[str, Any]]:
    script = r"""
        const baseline = new Set(arguments[0]);
        function visible(el) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 120 && r.height > 120 && s.display !== 'none' && s.visibility !== 'hidden';
        }
        function forbidden(el) {
            return !!el.closest('rich-textarea, textarea, form, nav, [role="navigation"], header, user-query, .user-query, [data-author="user"], [class*="user-query"], [aria-label*="Recent"], [aria-label*="Conversation history"]');
        }
        function inAssistantArea(el) {
            return !!el.closest('model-response, .model-response, .response-container, [data-response-index], [data-chunk-index], [data-testid*="response"], [class*="response"]');
        }
        function srcBad(src) {
            const s = (src || '').toLowerCase();
            if (!s) return true;
            if (s.includes('googlelogo') || s.includes('gstatic.com')) return true;
            if (s.includes('/a-/') || s.includes('avatar') || s.includes('profile')) return true;
            return false;
        }
        const imgs = Array.from(document.querySelectorAll('main img'));
        const out = [];
        for (const img of imgs) {
            const src = img.currentSrc || img.src || '';
            if (baseline.has(src)) continue;
            if (srcBad(src)) continue;
            if (!visible(img)) continue;
            if (forbidden(img)) continue;
            const r = img.getBoundingClientRect();
            out.push({
                src,
                top: r.top,
                left: r.left,
                width: r.width,
                height: r.height,
                naturalWidth: img.naturalWidth || 0,
                naturalHeight: img.naturalHeight || 0,
                assistantArea: inAssistantArea(img)
            });
        }
        out.sort((a,b) => {
            // Prefer assistant response images, then lower/later images, then larger area.
            if (a.assistantArea !== b.assistantArea) return a.assistantArea ? -1 : 1;
            const areaDiff = (b.width*b.height) - (a.width*a.height);
            if (Math.abs(areaDiff) > 5000) return areaDiff;
            return b.top - a.top;
        });
        return out;
    """
    try:
        rows = driver.execute_script(script, list(baseline_srcs)) or []
        return list(rows)
    except Exception:
        return []


def wait_for_generated_image(driver: webdriver.Chrome, baseline_srcs: set[str], timeout: int) -> str:
    print("  [wait-img] Waiting for a new generated image in the assistant response...")
    deadline = time.time() + timeout
    next_log = time.time() + 15
    last_seen_count = 0
    while time.time() < deadline:
        candidates = _image_candidates(driver, baseline_srcs)
        last_seen_count = len(candidates)
        assistant_candidates = [c for c in candidates if c.get("assistantArea")]
        if assistant_candidates:
            chosen = assistant_candidates[0]
            # Prefer true assistant/model-response images. If a spinner is still active,
            # give Gemini a little time to finish, then re-check in case a higher-res
            # final image replaced the preview.
            if generation_in_progress(driver):
                time.sleep(5.0)
                refreshed = [c for c in _image_candidates(driver, baseline_srcs) if c.get("assistantArea")]
                if refreshed:
                    chosen = refreshed[0]
            print(
                "  [wait-img] Found generated assistant image: "
                f"{int(chosen.get('width', 0))}x{int(chosen.get('height', 0))}, "
                f"assistantArea={chosen.get('assistantArea')}."
            )
            return str(chosen["src"])

        # Do not accept a non-assistant image while generation is active; that is
        # usually an uploaded reference thumbnail that moved from the composer
        # into the user turn after Send. Only use this fallback after generation
        # has ended and no assistant-specific container could be detected.
        if candidates and not generation_in_progress(driver):
            time.sleep(3.0)
            refreshed = _image_candidates(driver, baseline_srcs)
            assistant_candidates = [c for c in refreshed if c.get("assistantArea")]
            chosen = assistant_candidates[0] if assistant_candidates else refreshed[0]
            print(
                "  [wait-img] Found generated image fallback: "
                f"{int(chosen.get('width', 0))}x{int(chosen.get('height', 0))}, "
                f"assistantArea={chosen.get('assistantArea')}."
            )
            return str(chosen["src"])

        if time.time() >= next_log:
            print(f"  [wait-img] Still waiting... candidate count={last_seen_count}")
            next_log = time.time() + 15
        time.sleep(2.0)
    raise TimeoutException(f"No generated image appeared within {timeout}s")


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def infer_ext_from_src(src: str, content_type: str = "") -> str:
    if src.startswith("data:image/"):
        m = re.match(r"data:image/([a-zA-Z0-9.+-]+);", src)
        if m:
            return mimetypes.guess_extension(f"image/{m.group(1)}") or ".png"
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if ext:
            return ext
    ext = Path(urllib.parse.urlparse(src).path).suffix
    return ext if ext else ".png"


def _save_data_url(data_url: str, out_path_no_ext: Path, min_bytes: int) -> Path | None:
    if not (isinstance(data_url, str) and data_url.startswith("data:image/")):
        return None
    try:
        header, b64data = data_url.split(",", 1)
        ext = infer_ext_from_src(header)
        out_path = out_path_no_ext.with_suffix(ext)
        raw = base64.b64decode(b64data)
        if len(raw) < min_bytes:
            print(f"  [dl] fetch produced only {len(raw)} bytes; rejecting as too small.")
            return None
        out_path.write_bytes(raw)
        print(f"  [dl] Saved via fetch/base64: {out_path} ({out_path.stat().st_size} bytes)")
        return out_path
    except Exception as exc:
        print(f"  [dl] Could not save data URL: {exc}")
        return None


def snapshot_download_dir(download_dir: Path) -> dict[Path, tuple[float, int]]:
    download_dir.mkdir(parents=True, exist_ok=True)
    out: dict[Path, tuple[float, int]] = {}
    for p in download_dir.iterdir():
        if p.is_file():
            try:
                st = p.stat()
                out[p] = (st.st_mtime, st.st_size)
            except Exception:
                pass
    return out


def wait_for_completed_download(
    download_dir: Path,
    before: dict[Path, tuple[float, int]],
    started_at: float,
    timeout: int,
) -> Path | None:
    deadline = time.time() + timeout
    last_candidate: Path | None = None
    stable_since: float | None = None
    last_size: int | None = None

    while time.time() < deadline:
        active_temp = [p for p in download_dir.iterdir() if p.is_file() and p.suffix.lower() in DOWNLOAD_TEMP_EXTS]
        candidates: list[Path] = []
        for p in download_dir.iterdir():
            if not p.is_file() or p.suffix.lower() in DOWNLOAD_TEMP_EXTS:
                continue
            try:
                st = p.stat()
            except Exception:
                continue
            old = before.get(p)
            changed = old is None or st.st_mtime > old[0] + 0.5 or st.st_size != old[1]
            recent = st.st_mtime >= started_at - 1
            if changed and recent and st.st_size > 0:
                candidates.append(p)

        if candidates and not active_temp:
            newest = max(candidates, key=lambda p: p.stat().st_mtime)
            size = newest.stat().st_size
            if newest == last_candidate and size == last_size:
                if stable_since is None:
                    stable_since = time.time()
                if time.time() - stable_since >= 2.0:
                    return newest
            else:
                last_candidate = newest
                last_size = size
                stable_since = time.time()
        time.sleep(1.0)
    return None


def click_exact_image_and_download(driver: webdriver.Chrome, src: str, download_dir: Path, timeout: int) -> Path | None:
    before = snapshot_download_dir(download_dir)
    started_at = time.time()
    clicked = driver.execute_script(
        r"""
        const src = arguments[0];
        function visible(el) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 50 && r.height > 50 && s.display !== 'none' && s.visibility !== 'hidden';
        }
        const img = Array.from(document.querySelectorAll('main img')).find(i => (i.currentSrc || i.src || '') === src && visible(i));
        if (!img) return false;
        img.scrollIntoView({block:'center', inline:'center'});
        img.click();
        return true;
        """,
        src,
    )
    if not clicked:
        return None
    time.sleep(2.0)

    button_clicked = driver.execute_script(
        r"""
        function visible(el) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
        }
        const roots = Array.from(document.querySelectorAll('[role="dialog"], .cdk-overlay-container, main'));
        for (const root of roots) {
            const buttons = Array.from(root.querySelectorAll('button,a[href]')).reverse();
            for (const b of buttons) {
                if (!visible(b)) continue;
                const t = ((b.getAttribute('aria-label') || '') + ' ' + (b.title || '') + ' ' + (b.innerText || '')).trim().toLowerCase();
                if (t === 'download' || t.startsWith('download')) {
                    b.click();
                    return true;
                }
            }
        }
        return false;
        """
    )
    if not button_clicked:
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        return None

    downloaded = wait_for_completed_download(download_dir, before, started_at, timeout)
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    return downloaded


def screenshot_exact_image(driver: webdriver.Chrome, src: str, out_path_no_ext: Path, min_bytes: int) -> Path | None:
    try:
        img_el = driver.execute_script(
            r"""
            const src = arguments[0];
            return Array.from(document.querySelectorAll('main img')).find(i => (i.currentSrc || i.src || '') === src) || null;
            """,
            src,
        )
        if not img_el:
            return None
        out_path = out_path_no_ext.with_suffix(".png")
        img_el.screenshot(str(out_path))
        if out_path.exists() and out_path.stat().st_size >= min_bytes:
            print(f"  [dl] Saved exact image screenshot: {out_path} ({out_path.stat().st_size} bytes)")
            return out_path
        if out_path.exists():
            print(f"  [dl] Screenshot was too small ({out_path.stat().st_size} bytes); rejecting.")
    except Exception as exc:
        print(f"  [dl] Screenshot fallback failed: {exc}")
    return None


def download_generated_image(
    driver: webdriver.Chrome,
    src: str,
    out_path_no_ext: Path,
    download_dir: Path,
    min_bytes: int,
    download_timeout: int,
) -> Path:
    out_path_no_ext.parent.mkdir(parents=True, exist_ok=True)
    configure_download_dir(driver, download_dir)

    print(f"  [dl] Strategy 1: fetch exact src: {src[:100]}...")
    try:
        data_url = driver.execute_async_script(
            r"""
            const src = arguments[0];
            const done = arguments[arguments.length - 1];
            fetch(src, {credentials: 'include'})
                .then(r => r.blob())
                .then(blob => {
                    const reader = new FileReader();
                    reader.onloadend = () => done(reader.result);
                    reader.onerror = () => done(null);
                    reader.readAsDataURL(blob);
                })
                .catch(() => done(null));
            """,
            src,
        )
        saved = _save_data_url(data_url, out_path_no_ext, min_bytes=min_bytes)
        if saved:
            return saved
    except Exception as exc:
        print(f"  [dl] fetch strategy failed: {exc}")

    print("  [dl] Strategy 2: click exact generated image, then its Download button.")
    try:
        downloaded = click_exact_image_and_download(driver, src, download_dir, timeout=download_timeout)
        if downloaded and downloaded.exists() and downloaded.stat().st_size >= min_bytes:
            ext = downloaded.suffix if downloaded.suffix else ".png"
            out_path = out_path_no_ext.with_suffix(ext)
            shutil.copy2(downloaded, out_path)
            print(f"  [dl] Saved browser download: {out_path} ({out_path.stat().st_size} bytes)")
            return out_path
        if downloaded:
            print(f"  [dl] Browser download too small: {downloaded} ({downloaded.stat().st_size} bytes)")
    except Exception as exc:
        print(f"  [dl] button strategy failed: {exc}")

    print("  [dl] Strategy 3: screenshot the exact generated image element.")
    saved = screenshot_exact_image(driver, src, out_path_no_ext, min_bytes=min_bytes)
    if saved:
        return saved

    raise RuntimeError("All download strategies failed for the exact generated image")


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def save_debug_snapshot(driver: webdriver.Chrome, base: Path, label: str) -> dict[str, str | None]:
    base.parent.mkdir(parents=True, exist_ok=True)
    png = base.with_name(base.name + f".{label}.png")
    html = base.with_name(base.name + f".{label}.html")
    current_url = None
    try:
        current_url = driver.current_url
    except Exception:
        pass
    try:
        driver.save_screenshot(str(png))
    except Exception:
        png = None  # type: ignore[assignment]
    try:
        html.write_text(driver.page_source, encoding="utf-8", errors="replace")
    except Exception:
        html = None  # type: ignore[assignment]
    return {
        "screenshot": str(png) if png else None,
        "html": str(html) if html else None,
        "current_url": current_url,
    }


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------


def run() -> None:
    args = parse_args()
    prompt_dir = Path(args.prompt_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    upload_dir = Path(args.upload_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs, duplicates = discover_prompt_jobs(
        prompt_dir=prompt_dir,
        pattern=args.prompt_glob,
        allow_duplicates=args.allow_duplicate_prompt_keys,
    )
    print_job_manifest(jobs, duplicates)
    validate_expected_formats(jobs, args.expected_formats, args.strict_expected_formats)
    if args.dry_run:
        print("\nDry run complete. Browser was not started.")
        return

    browser_download_dir = Path(args.browser_download_dir).expanduser().resolve() if args.browser_download_dir else out_dir / ".browser_downloads"
    browser_download_dir.mkdir(parents=True, exist_ok=True)

    auto_launch_debug_browser(args)

    with tempfile.TemporaryDirectory(prefix="gemini_uploads_") as tmp:
        temp_dir = Path(tmp)
        if args.image_source_file:
            source_file = Path(args.image_source_file).expanduser().resolve()
            image_sources = parse_image_source_file(source_file, args.logo_key)
            upload_paths = build_local_image_paths(image_sources, temp_dir)
        else:
            upload_paths = collect_upload_images_from_dir(upload_dir)

        print(f"\nUpload images: {len(upload_paths)}")
        for p in upload_paths[:10]:
            print(f"  - {p}")
        if len(upload_paths) > 10:
            print(f"  ... {len(upload_paths) - 10} more")
        if len(upload_paths) > 20:
            print("WARNING: Gemini may reject very large attachment batches.")

        driver = build_driver(args, download_dir=browser_download_dir)
        try:
            strict_login = args.login_wait_mode == "strict"
            for idx, job in enumerate(jobs, start=1):
                print("\n" + "=" * 72)
                print(f"[{idx}/{len(jobs)}] {job.job_key}: {job.prompt_path.name}")
                print("=" * 72)
                prompt_text = job.prompt_path.read_text(encoding="utf-8")
                out_base = out_dir / job.output_stem
                print(f"  Prompt file stats: {len(prompt_text)} chars, {prompt_text.count(chr(10)) + 1} lines")

                success = False
                last_exc: Exception | None = None
                attempts = max(1, int(args.max_attempts))
                for attempt in range(1, attempts + 1):
                    if attempts > 1:
                        print(f"  Attempt {attempt}/{attempts}")
                    try:
                        open_prompt_tab(driver, idx if attempt == 1 else 999999, args.first_tab_mode, browser_download_dir)
                        navigate_to_fresh_chat(
                            driver,
                            manual_login_timeout=args.manual_login_timeout,
                            strict_login=strict_login,
                        )
                        configure_download_dir(driver, browser_download_dir)

                        print("  Selecting model/tool before typing prompt...")
                        select_model_and_tool_if_requested(driver, args)

                        print("  Uploading reference images...")
                        upload_images(driver, upload_paths)
                        dismiss_open_overlays(driver)
                        time.sleep(1.0)

                        print("  Typing prompt with strict integrity check...")
                        composer = set_prompt_text(
                            driver,
                            prompt_text,
                            method=args.prompt_paste_method,
                            verify_timeout=args.prompt_paste_timeout,
                            min_integrity_ratio=args.prompt_integrity_ratio,
                            debug_path=out_base.with_suffix(".prompt-paste-debug.txt"),
                        )
                        time.sleep(0.5)

                        baseline_srcs = get_all_image_srcs(driver)
                        print(f"  Baseline image src count before Send: {len(baseline_srcs)}")

                        print("  Sending prompt...")
                        click_send_and_confirm(
                            driver,
                            composer,
                            expected_prompt=prompt_text,
                            min_integrity_ratio=args.prompt_integrity_ratio,
                            debug_path=out_base.with_suffix(".prompt-before-send-debug.txt"),
                            settle_wait=args.prompt_settle_wait,
                            submit_method=args.send_submit_method,
                            confirm_timeout=args.send_confirm_timeout,
                        )

                        image_src = wait_for_generated_image(driver, baseline_srcs, timeout=args.timeout)

                        print("  Downloading generated image and waiting for completion...")
                        saved_path = download_generated_image(
                            driver,
                            image_src,
                            out_base,
                            download_dir=browser_download_dir,
                            min_bytes=args.min_image_bytes,
                            download_timeout=args.download_timeout,
                        )
                        if not saved_path.exists() or saved_path.stat().st_size < args.min_image_bytes:
                            raise RuntimeError(f"Saved file is missing or too small: {saved_path}")

                        metadata = {
                            "status": "success",
                            "prompt_file": str(job.prompt_path),
                            "format_id": job.format_id,
                            "persona_id": job.persona_id,
                            "job_key": job.job_key,
                            "generated_image_src": image_src,
                            "saved_file": str(saved_path),
                            "saved_size": saved_path.stat().st_size,
                            "timestamp": int(time.time()),
                        }
                        out_base.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
                        print(f"  SUCCESS: saved {saved_path} ({saved_path.stat().st_size} bytes)")
                        if args.sleep_after_download > 0:
                            print(f"  Waiting {args.sleep_after_download:g}s before next prompt tab...")
                            time.sleep(args.sleep_after_download)
                        success = True
                        break

                    except (InvalidSessionIdException, WebDriverException) as exc:
                        last_exc = exc
                        print(f"  Driver/session error: {exc}")
                        if attempt < attempts:
                            auto_launch_debug_browser(args)
                            driver = build_driver(args, download_dir=browser_download_dir)
                            continue
                        break
                    except Exception as exc:
                        last_exc = exc
                        print(f"  ERROR: {exc}")
                        if attempt < attempts:
                            continue
                        break

                if success:
                    if idx < len(jobs):
                        print("  [next] Moving to next prompt; a new tab will be opened and this tab will stay open.")
                    continue

                diag = save_debug_snapshot(driver, out_base, "error")
                metadata = {
                    "status": "error",
                    "prompt_file": str(job.prompt_path),
                    "format_id": job.format_id,
                    "persona_id": job.persona_id,
                    "job_key": job.job_key,
                    "error": str(last_exc),
                    "timestamp": int(time.time()),
                    **diag,
                }
                out_base.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
                print(f"  FAILED: {job.job_key}. Continuing to next prompt.")

            print("\nAll prompt jobs finished.")
        finally:
            print("Browser left open for inspection. Close it manually when done.")


if __name__ == "__main__":
    run()
