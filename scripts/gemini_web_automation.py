#!/usr/bin/env python3
"""Automate Gemini web image generation with manual login handoff.

Workflow per prompt:
1) Open Gemini in Brave (or Chrome).
2) Pause for manual login in the same browser window.
3) Start a new chat, switch to Pro model, and pick "Create image" tool.
4) Upload reference images.
4) Paste prompt text and send.
5) Wait for generated image.
6) Download generated image.

Example:
  python3 scripts/gemini_web_automation.py \
    --prompt-dir output/v11/final_prompt/HERO \
    --prompt-glob 'FINAL_HERO_P*_EN.txt' \
    --upload-dir '/home/mylappy/Downloads/Untitled design' \
    --out-dir generated_image/v11/HERO_GEMINI
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    InvalidSessionIdException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


GEMINI_URL = "https://gemini.google.com/app"


@dataclass
class PromptJob:
    prompt_path: Path
    persona_id: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini web image generation automation")
    parser.add_argument("--prompt-dir", required=True, help="Directory containing prompt files")
    parser.add_argument("--prompt-glob", default="FINAL_HERO_P*_EN.txt", help="Prompt file pattern")
    parser.add_argument(
        "--image-source-file",
        default="",
        help="Text file with local image paths and/or URLs (supports KEY=URL lines)",
    )
    parser.add_argument(
        "--upload-dir",
        default="/home/mylappy/Downloads/Untitled design",
        help="Directory containing images to upload on every prompt",
    )
    parser.add_argument(
        "--logo-key",
        default="LIGHT_LOGO_URL",
        help="If KEY=URL logo entries exist, choose this key as the logo",
    )
    parser.add_argument("--out-dir", required=True, help="Where downloaded outputs will be saved")
    parser.add_argument("--timeout", type=int, default=420, help="Wait timeout per prompt (seconds)")
    parser.add_argument(
        "--user-data-dir",
        default="",
        help="Optional Chrome profile directory to keep login sessions",
    )
    parser.add_argument(
        "--profile-directory",
        default="",
        help="Optional Chrome profile name (e.g. 'Default')",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless (not recommended for manual login flow)",
    )
    parser.add_argument(
        "--browser",
        choices=["brave", "chrome"],
        default="brave",
        help="Browser to launch",
    )
    parser.add_argument(
        "--attach-debugger-address",
        default="",
        help="Attach to an already-running Chromium browser via host:port (e.g. 127.0.0.1:9222)",
    )
    parser.add_argument(
        "--debug-user-data-dir",
        default="/home/mylappy/.chrome-selenium-profile",
        help="User data dir used when auto-launching browser for debugger attach",
    )
    parser.add_argument(
        "--manual-login-timeout",
        type=int,
        default=180,
        help="Seconds to wait for Gemini to become ready after browser opens",
    )
    parser.add_argument(
        "--login-wait-mode",
        choices=["auto", "strict"],
        default="auto",
        help="auto: continue even if readiness check times out; strict: fail on timeout",
    )
    parser.add_argument(
        "--require-pro-model",
        action="store_true",
        default=True,
        help="Fail current prompt if Pro model selection could not be confirmed",
    )
    return parser.parse_args()


def discover_prompt_jobs(prompt_dir: Path, pattern: str) -> List[PromptJob]:
    jobs = []
    for path in sorted(prompt_dir.glob(pattern)):
        m = re.search(r"P(\d+)", path.name)
        persona_num = m.group(1) if m else "00"
        jobs.append(PromptJob(prompt_path=path, persona_id=f"P{persona_num}"))
    if not jobs:
        raise FileNotFoundError(f"No prompt files found in {prompt_dir} with pattern {pattern}")
    return jobs


def parse_image_source_file(path: Path, logo_key: str) -> List[str]:
    logo_map = {}
    regular_sources = []

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
    if selected_logo:
        return [selected_logo] + regular_sources
    return regular_sources


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


def build_local_image_paths(sources: List[str], temp_dir: Path) -> List[Path]:
    paths: List[Path] = []
    for src in sources:
        if is_url(src):
            paths.append(download_to_temp(src, temp_dir))
        else:
            p = Path(src)
            if not p.is_absolute():
                p = Path.cwd() / p
            if not p.exists():
                raise FileNotFoundError(f"Image path not found: {p}")
            paths.append(p)
    if not paths:
        raise ValueError("No images resolved for upload")
    return paths


def collect_upload_images_from_dir(upload_dir: Path) -> List[Path]:
    if not upload_dir.exists():
        raise FileNotFoundError(f"Upload directory not found: {upload_dir}")
    if not upload_dir.is_dir():
        raise NotADirectoryError(f"Upload path is not a directory: {upload_dir}")

    allowed = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    images = [p for p in sorted(upload_dir.iterdir()) if p.is_file() and p.suffix.lower() in allowed]
    if not images:
        raise FileNotFoundError(f"No image files found in {upload_dir}")
    return images


def resolve_browser_binary(args: argparse.Namespace) -> str:
    if args.browser == "brave":
        brave_candidates = [
            "/usr/bin/brave-browser",
            "/usr/bin/brave",
            "/snap/bin/brave",
        ]
        for candidate in brave_candidates:
            if Path(candidate).exists():
                return candidate
        return ""

    chrome_candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/snap/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    for candidate in chrome_candidates:
        if Path(candidate).exists():
            return candidate
    return ""


def debugger_endpoint_reachable(address: str) -> bool:
    if not address:
        return False
    url = f"http://{address}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
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
        raise RuntimeError(f"Could not resolve {args.browser} binary for auto-launch")

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
    ]
    print("Debugger endpoint not reachable. Auto-launching browser for attach...")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    deadline = time.time() + 20
    while time.time() < deadline:
        if debugger_endpoint_reachable(args.attach_debugger_address):
            print(f"Debugger endpoint is live at {args.attach_debugger_address}")
            return
        time.sleep(0.5)
    raise RuntimeError(
        f"Auto-launched browser, but debugger endpoint still not reachable at {args.attach_debugger_address}"
    )


def build_driver(args: argparse.Namespace) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if args.attach_debugger_address:
        options.add_experimental_option("debuggerAddress", args.attach_debugger_address)
    selected_binary = ""
    if not args.attach_debugger_address:
        selected_binary = resolve_browser_binary(args)
        if selected_binary:
            options.binary_location = selected_binary
    options.add_experimental_option(
        "prefs",
        {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        },
    )
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
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
        print(f"Using Brave binary: {selected_binary}")
    try:
        driver.set_page_load_timeout(120)
    except Exception:
        pass
    return driver


def _is_fresh_chat_url(url: str) -> bool:
    """Return True if the URL is a blank new-chat (no conversation ID).

    Fresh chat:  https://gemini.google.com/app
                 https://gemini.google.com/app/
    Old chat:    https://gemini.google.com/app/0085a5f7943d0d69
                 https://gemini.google.com/app/c/abc123
                 https://gemini.google.com/app/a/xyz
    """
    # Strip protocol + domain, keep path only
    path = url.split("gemini.google.com")[-1].rstrip("/")
    # /app with nothing after it == fresh
    return path in ("/app", "") or path == "/app"


def open_gemini_new_chat(driver: webdriver.Chrome) -> None:
    """Open Gemini in a new browser tab/window for each prompt, then ensure composer is ready.

    User preference: do NOT close previous tabs. This function will:
      1) Trigger "new chat" using Ctrl+Shift+O.
      2) Wait for at least one new window handle; switch to the newest handle.
      3) Validate URL freshness (best-effort) and retry navigation if needed.
      4) Wait for composer presence.
    """
    composer_css = (
        "rich-textarea div[contenteditable='true'], "
        "div[contenteditable='true'][role='textbox'], "
        "div[contenteditable='true'], "
        "textarea"
    )

    before_handles = set(driver.window_handles)

    # Ensure focus on body before shortcut.
    try:
        driver.find_element(By.TAG_NAME, "body").click()
    except Exception:
        pass
    time.sleep(0.3)

    # Ctrl+Shift+O — can open a new tab (preferred workflow)
    print("  [new-chat] Triggering Ctrl+Shift+O to open new Gemini chat tab…")
    _send_ctrl_shift_o(driver)
    time.sleep(1.5)
    _send_ctrl_shift_o(driver)
    time.sleep(2.5)

    # Switch to newest handle (if a tab was opened)
    after_handles = set(driver.window_handles)
    new_handles = list(after_handles - before_handles)
    if new_handles:
        # Newest is typically the last handle discovered; best-effort
        new_handle = sorted(new_handles, key=lambda h: driver.window_handles.index(h))[-1]
        driver.switch_to.window(new_handle)
        time.sleep(2.0)
        print(f"  [new-chat] Switched to new handle: {new_handle}")
    else:
        print("  [new-chat] No new handle detected; staying in current tab.")

    for attempt in range(1, 4):
        print(f"  [new-chat] Attempt {attempt}: navigating to {GEMINI_URL}")
        try:
            driver.get(GEMINI_URL)
        except Exception:
            pass
        time.sleep(5.0)

        current_url = driver.current_url or ""
        print(f"  [new-chat] URL after load: {current_url}")
        if _is_fresh_chat_url(current_url):
            print("  [new-chat] Fresh chat confirmed by URL ✓")
            break
        if attempt == 3:
            print("  [new-chat] URL still looks old; proceeding anyway after retries.")

    dismiss_open_overlays(driver)

    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, composer_css))
        )
        print("  [new-chat] Composer ready.")
    except TimeoutException:
        print("  [new-chat] Composer not detected, continuing anyway.")

    print(f"  [new-chat] Final URL: {driver.current_url}")


def _send_ctrl_shift_o(driver: webdriver.Chrome) -> None:
    """Send Ctrl+Shift+O to the page, with a JS fallback."""
    # Refocus body first so the shortcut lands on the right element.
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.click()
        time.sleep(0.2)
        # selenium Keys: combine as a chord
        body.send_keys(Keys.CONTROL + Keys.SHIFT + "o")
        return
    except Exception:
        pass
    # JS fallback — dispatch on document
    try:
        driver.execute_script(
            "document.dispatchEvent(new KeyboardEvent('keydown', "
            "{key: 'o', code: 'KeyO', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true}));"
        )
    except Exception:
        pass


def click_text_options(
    driver: webdriver.Chrome,
    labels: List[str],
    timeout: int = 10,
    fail_silently: bool = False,
) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        for label in labels:
            xpath = (
                "//*[self::button or self::a or @role='button' or self::div]"
                f"[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label.lower()}')]"
            )
            elements = driver.find_elements(By.XPATH, xpath)
            for el in elements:
                try:
                    if not el.is_displayed():
                        continue
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    el.click()
                    return True
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        return True
                    except Exception:
                        continue
        time.sleep(0.5)
    if fail_silently:
        return False
    raise TimeoutException(f"Could not click any label from {labels}")


def click_first_visible_css(driver: webdriver.Chrome, selectors: List[str], timeout: int = 8) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        for sel in selectors:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if not el.is_displayed() or not el.is_enabled():
                        continue
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    el.click()
                    return True
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        return True
                    except Exception:
                        continue
        time.sleep(0.3)
    return False


def _find_file_input_anywhere(driver: webdriver.Chrome):
    # Direct lookup first.
    direct = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
    for el in direct:
        try:
            if el.is_enabled():
                return el
        except Exception:
            continue

    script = """
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
        // Prefer enabled elements; visibility is not required for send_keys.
        const candidate = out.find(el => !el.disabled) || out[0] || null;
        return candidate;
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

    def search_frames(depth: int) -> object:
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


def _open_attachment_ui(driver: webdriver.Chrome) -> None:
    # Open attachment tray/menu from plus or attach icon.
    click_text_options(driver, ["+"], timeout=2, fail_silently=True)
    click_first_visible_css(
        driver,
        [
            "button[aria-label*='Add files']",
            "button[aria-label*='Attach']",
            "button[aria-label*='Upload']",
            "button[aria-label*='Add']",
            "button[title*='Add']",
            "button[title*='Attach']",
        ],
        timeout=3,
    )

    # If menu opened, pick Upload explicitly.
    click_text_options(driver, ["Upload files", "Upload", "From computer"], timeout=4, fail_silently=True)

    # Multiple fallback clicks to reveal hidden file input in Gemini UI.
    click_text_options(
        driver,
        [
            "Add files",
            "Upload",
            "Attach",
            "Insert files",
            "Add media",
            "Add photos",
            "Files",
            "+",
        ],
        timeout=5,
        fail_silently=True,
    )

    # aria-label fallback for icon-only buttons
    selectors = [
        "button[aria-label*='Attach']",
        "button[aria-label*='Upload']",
        "button[aria-label*='Add']",
        "button[aria-label*='Insert']",
        "button[aria-label*='file']",
    ]
    for sel in selectors:
        for btn in driver.find_elements(By.CSS_SELECTOR, sel):
            try:
                if btn.is_displayed():
                    btn.click()
                    return
            except Exception:
                continue


def select_pro_model_and_create_image_tool(driver: webdriver.Chrome) -> None:
    for _ in range(3):
        # Open current model chip/menu.
        click_text_options(driver, ["Fast", "Flash", "Model"], timeout=2, fail_silently=True)
        click_first_visible_css(
            driver,
            [
                "button[aria-label*='Model']",
                "button[aria-label*='model']",
                "button[aria-label*='Gemini']",
                "button[aria-label*='Flash']",
                "button[aria-label*='Fast']",
            ],
            timeout=2,
        )

        # Exact menu-item selection for current Gemini model picker.
        click_text_options(driver, ["Gemini 3"], timeout=1, fail_silently=True)
        click_first_visible_css(
            driver,
            [
                "[role='menuitemradio']",
                "[role='option']",
                "mat-option",
                "button",
                "div[role='button']",
            ],
            timeout=1,
        )

        # Click model picker container to open dropdown (contains current model like "Fast")
        try:
            picker = driver.find_element(By.CSS_SELECTOR, ".model-picker-container")
            picker.click()
            time.sleep(1.5)
        except Exception:
            pass

        # Select "Pro" from dropdown - click exact text "Pro" (title case, not PRO uppercase)
        driver.execute_script("""
            var buttons = document.querySelectorAll('button, div, span');
            for (var b of buttons) {
                var txt = (b.textContent || '').trim();
                if (txt === 'Pro' || txt === '2.0 Pro') {
                    b.click();
                    return;
                }
            }
        """)
        time.sleep(1.5)

        # Open tools and pick create-image mode.
        click_text_options(driver, ["Tools"], timeout=2, fail_silently=True)
        click_first_visible_css(
            driver,
            [
                "button[aria-label*='Tools']",
                "button[aria-label*='tools']",
                "button[title*='Tools']",
            ],
            timeout=2,
        )
        click_text_options(
            driver,
            ["Create image", "Image generation", "Generate image"],
            timeout=5,
            fail_silently=True,
        )

        if pro_model_selected(driver):
            return
        time.sleep(0.8)


def force_fast_to_pro(driver: webdriver.Chrome) -> None:
    # Explicitly switch model chip from Fast/Flash to Pro.
    for _ in range(3):
        click_text_options(driver, ["Fast", "Flash"], timeout=2, fail_silently=True)
        click_text_options(driver, ["Gemini 2.5 Pro", "2.5 Pro", "Pro"], timeout=5, fail_silently=True)
        click_text_options(driver, ["Model"], timeout=2, fail_silently=True)
        click_text_options(driver, ["Gemini 2.5 Pro", "2.5 Pro", "Pro"], timeout=5, fail_silently=True)
        driver.execute_script(
            "const nodes=[...document.querySelectorAll('[role=menuitemradio],[role=option],button,div[role=button],mat-option')];"
            "const match=nodes.find(n=>{const t=(n.innerText||'').trim().toLowerCase(); return t==='pro' || t.startsWith('pro ') || t.includes('3.1 pro') || t.includes('advanced math and code');});"
            "if (match) match.click();"
        )
        if pro_model_selected(driver):
            return
        time.sleep(0.8)


def pro_model_selected(driver: webdriver.Chrome) -> bool:
    checks = [
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '2.5 pro')]",
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'gemini pro')]",
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pro') and not(contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'project'))]",
        "//*[self::button or self::div][contains(@class,'chip') or contains(@class,'select') or contains(@class,'trigger')][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pro')]",
    ]
    for xp in checks:
        for el in driver.find_elements(By.XPATH, xp):
            try:
                if el.is_displayed():
                    return True
            except Exception:
                continue
    return False


def find_composer(driver: webdriver.Chrome, timeout: int = 30):
    wait = WebDriverWait(driver, timeout)
    selectors = [
        "rich-textarea div[contenteditable='true']",
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
        "textarea[aria-label*='message']",
        "textarea",
    ]
    last_error = None
    for sel in selectors:
        try:
            return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
        except Exception as exc:
            last_error = exc
    raise TimeoutException(f"Could not find Gemini composer. Last error: {last_error}")


def dismiss_open_overlays(driver: webdriver.Chrome) -> None:
    # Close menus/drawers/backdrops that can block composer clicks.
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ESCAPE)
    except Exception:
        pass

    selectors = [
        ".mat-drawer-backdrop",
        ".cdk-overlay-backdrop",
        "[role='dialog'] [aria-label='Close']",
        "button[aria-label*='Close']",
    ]
    for sel in selectors:
        for el in driver.find_elements(By.CSS_SELECTOR, sel):
            try:
                if el.is_displayed():
                    el.click()
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", el)
                except Exception:
                    pass


def set_prompt_text(driver: webdriver.Chrome, composer, text: str) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", composer)
    for _ in range(3):
        try:
            composer.click()
            break
        except ElementClickInterceptedException:
            dismiss_open_overlays(driver)
            time.sleep(0.4)
    tag = composer.tag_name.lower()
    if tag == "textarea":
        driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            composer,
            text,
        )
        return

    driver.execute_script(
        "arguments[0].innerText = arguments[1];"
        "arguments[0].dispatchEvent(new InputEvent('input', {bubbles: true, data: arguments[1]}));",
        composer,
        text,
    )


def upload_images(driver: webdriver.Chrome, image_paths: List[Path], timeout: int = 30) -> None:
    end = time.time() + timeout
    file_input = None

    # Open upload UI once, then wait for file input to appear.
    _open_attachment_ui(driver)
    while time.time() < end:
        file_input = _find_file_input_across_frames(driver)
        if file_input is not None:
            break
        time.sleep(0.6)

    payload = "\n".join(str(p) for p in image_paths)
    if file_input is not None:
        file_input.send_keys(payload)
        time.sleep(3.0)
        return

    # Fallback: synthetic drag-drop using a temporary input element.
    driver.switch_to.default_content()
    try:
        drop_target = find_composer(driver, timeout=5)
    except Exception:
        drop_target = None
    if drop_target is None:
        candidates = driver.find_elements(By.CSS_SELECTOR, "main, body")
        if not candidates:
            raise TimeoutException("Could not find Gemini upload target")
        drop_target = candidates[0]

    temp_input = driver.execute_script(
        "const i=document.createElement('input');"
        "i.type='file';i.multiple=true;i.style.display='none';"
        "document.body.appendChild(i);return i;"
    )
    temp_input.send_keys(payload)
    driver.execute_script(
        "const target=arguments[0],input=arguments[1];"
        "const dt=new DataTransfer();"
        "for(const f of input.files){dt.items.add(f);}"
        "for(const ev of ['dragenter','dragover','drop']){"
        " target.dispatchEvent(new DragEvent(ev,{bubbles:true,cancelable:true,dataTransfer:dt}));"
        "}"
        "target.dispatchEvent(new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:dt}));"
        "input.remove();",
        drop_target,
        temp_input,
    )
    time.sleep(3.0)


def click_send(driver: webdriver.Chrome, composer) -> None:
    selectors = [
        "button[aria-label*='Send message']",
        "button[aria-label='Send']",
        "button[aria-label*='Send']",
    ]
    for sel in selectors:
        buttons = driver.find_elements(By.CSS_SELECTOR, sel)
        if buttons:
            try:
                buttons[-1].click()
                return
            except Exception:
                pass

    try:
        composer.send_keys(Keys.ENTER)
    except Exception:
        composer.send_keys(Keys.CONTROL, Keys.ENTER)


def build_cookie_header(driver: webdriver.Chrome) -> str:
    try:
        cookies = driver.get_cookies()
        return "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    except Exception:
        return ""


def get_image_sources(driver: webdriver.Chrome) -> List[str]:
    """Collect all candidate generated-image URLs from the current tab."""
    script = """
        const imgs = Array.from(document.querySelectorAll('main img, img'));
        const out = [];
        for (const img of imgs) {
          const src = img.currentSrc || img.src || '';
          if (!src) continue;
          // Skip Google UI chrome
          if (src.includes('gstatic.com') || src.includes('googlelogo') ||
              src.includes('googleapis.com/download') === false && src.includes('accounts.google')) continue;
          if (src.startsWith('http') || src.startsWith('data:image/') || src.startsWith('blob:')) out.push(src);
        }
        return Array.from(new Set(out));
    """
    try:
        return driver.execute_script(script) or []
    except Exception:
        return []


def _save_debug_screenshot(driver: webdriver.Chrome, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(out_path))
    print(f"  [debug] screenshot → {out_path}")


def _upload_appears_ok(driver: webdriver.Chrome) -> bool:
    """Best-effort check that uploads have been attached in Gemini UI.

    We look for:
      - file name chips / upload thumbnails
      - any <img> in main content that likely corresponds to attachments
      - presence of common aria-label patterns
    """
    try:
        # Thumbnails/images inside main area are a strong signal uploads started.
        img_count = driver.execute_script(
            """
            const main = document.querySelector('main') || document.body;
            const imgs = Array.from(main.querySelectorAll('img'));
            // Filter out obvious Gemini UI/logo/gstatic by size heuristics.
            let kept = 0;
            for (const i of imgs) {
              const r = i.getBoundingClientRect();
              if (r && r.width > 24 && r.height > 24) kept++;
            }
            return kept;
            """
        )
        if isinstance(img_count, (int, float)) and img_count >= 1:
            return True
    except Exception:
        pass

    try:
        # Look for attachment/file chips text.
        exists = driver.execute_script(
            """
            const txt = (s)=> (s||'').toLowerCase();
            const needles = ['upload', 'attached', 'file', 'image'];
            const els = Array.from(document.querySelectorAll('*'));
            for (const el of els) {
              const t = txt(el.getAttribute('aria-label')) || txt(el.innerText);
              if (!t) continue;
              if (needles.some(n => t.includes(n))) return true;
            }
            return false;
            """
        )
        return bool(exists)
    except Exception:
        return False


def wait_for_new_generated_image(driver: webdriver.Chrome, before_sources: List[str], timeout: int) -> str:
    """Wait until a new image appears in the page that wasn't there before sending."""
    before = set(before_sources)
    start = time.time()
    while time.time() - start < timeout:
        # Check current tab first
        current = get_image_sources(driver)
        fresh = [src for src in current if src not in before]
        if fresh:
            print(f"  [wait-img] Found new image src: {fresh[-1][:80]}…")
            return fresh[-1]
        time.sleep(2.0)
    raise TimeoutException("Timed out waiting for generated image")


def infer_ext_from_src(src: str, content_type: str = "") -> str:
    if src.startswith("data:image/"):
        m = re.match(r"data:image/([a-zA-Z0-9.+-]+);", src)
        if m:
            ext = mimetypes.guess_extension(f"image/{m.group(1)}")
            return ext or ".png"
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext
    parsed = urllib.parse.urlparse(src)
    ext = Path(parsed.path).suffix
    return ext if ext else ".png"


def download_generated_image(driver: webdriver.Chrome, src: str, out_path_no_ext: Path) -> Path:
    """Save the generated image to out_path_no_ext + inferred extension.

    Strategy (in order):
      1. fetch() the src inside the page → FileReader → base64 → write directly to out_dir.
         Works for blob: and data: URLs.  Fast, no ~/Downloads involved.
      2. Click the Gemini "Download" button (works for http URLs served by Google).
         Snapshot ~/Downloads before clicking, wait for a NEW file, copy to out_dir.
      3. Element screenshot — last resort, lower quality but always works.
    """

    def _save_data_url(data_url: str) -> "Path | None":
        if not (isinstance(data_url, str) and data_url.startswith("data:image/")):
            return None
        try:
            header, b64data = data_url.split(",", 1)
            ext = infer_ext_from_src(header)
            out = out_path_no_ext.with_suffix(ext)
            out.write_bytes(base64.b64decode(b64data))
            print(f"  [dl] ✓ data-URL  {out.stat().st_size // 1024} KB → {out.name}")
            return out
        except Exception as exc:
            print(f"  [dl] data-URL decode error: {exc}")
            return None

    # ── 1. fetch() inside page (blob / data / http) ───────────────────────────
    print(f"  [dl] Trying fetch() for src type: {src[:10]}…")
    try:
        data_url = driver.execute_async_script(
            """
            const src  = arguments[0];
            const done = arguments[arguments.length - 1];
            fetch(src, {credentials: 'include'})
                .then(r  => r.blob())
                .then(b  => { const fr = new FileReader();
                              fr.onloadend = () => done(fr.result);
                              fr.onerror   = () => done(null);
                              fr.readAsDataURL(b); })
                .catch(()  => done(null));
            """,
            src,
        )
        result = _save_data_url(data_url)
        if result:
            return result
    except Exception as exc:
        print(f"  [dl] fetch() threw: {exc}")

    # ── 2. Gemini Download button → ~/Downloads ───────────────────────────────
    print("  [dl] Trying Gemini download button…")
    dl_dir = Path.home() / "Downloads"
    dl_dir.mkdir(exist_ok=True)
    existing_files = {p for p in dl_dir.iterdir() if p.is_file()}

    # Click the image to open the full-size viewer / dialog
    try:
        img_el = driver.execute_script(
            """
            const imgs = Array.from(document.querySelectorAll('img'));
            // Prefer the image matching our src; fall back to largest visible img
            return imgs.find(i => (i.currentSrc||i.src) === arguments[0])
                || imgs.filter(i => i.getBoundingClientRect().width > 150)
                       .sort((a,b) => b.getBoundingClientRect().width - a.getBoundingClientRect().width)[0]
                || null;
            """,
            src,
        )
        if img_el:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img_el)
            time.sleep(0.5)
            img_el.click()
            time.sleep(2.5)
    except Exception as exc:
        print(f"  [dl] img click: {exc}")

    # Find and click the Download button
    dl_clicked = False
    try:
        dl_clicked = driver.execute_script(
            """
            const candidates = [
                document.querySelector('[role="dialog"]'),
                document.body
            ];
            for (const root of candidates) {
                if (!root) continue;
                for (const el of root.querySelectorAll('button, a[href]')) {
                    const t = (el.getAttribute('aria-label')||el.innerText||'').trim().toLowerCase();
                    if (t === 'download' || t.startsWith('download')) {
                        el.click(); return true;
                    }
                }
            }
            return false;
            """
        )
    except Exception as exc:
        print(f"  [dl] download btn: {exc}")

    if dl_clicked:
        print("  [dl] Download button clicked, waiting for file…")
        deadline = time.time() + 45
        while time.time() < deadline:
            time.sleep(2.0)
            current_files = {p for p in dl_dir.iterdir() if p.is_file()}
            new_files = [
                p for p in (current_files - existing_files)
                if p.suffix.lower() not in (".crdownload", ".tmp", ".part")
            ]
            if new_files:
                newest = max(new_files, key=lambda p: p.stat().st_mtime)
                out = out_path_no_ext.with_suffix(newest.suffix)
                shutil.copy2(newest, out)
                print(f"  [dl] ✓ download-btn  {out.stat().st_size // 1024} KB → {out.name}")
                return out
        print("  [dl] No new file in ~/Downloads after 45 s.")
    else:
        print("  [dl] Download button not found.")

    # ── 3. Element screenshot ────────────────────────────────────────────────
    print("  [dl] Trying element screenshot…")
    try:
        img_el = driver.execute_script(
            """
            const imgs = Array.from(document.querySelectorAll('img'));
            return imgs.find(i => (i.currentSrc||i.src) === arguments[0])
                || imgs.filter(i => i.getBoundingClientRect().width > 150)
                       .sort((a,b) => b.getBoundingClientRect().width - a.getBoundingClientRect().width)[0]
                || null;
            """,
            src,
        )
        if img_el:
            out = out_path_no_ext.with_suffix(".png")
            img_el.screenshot(str(out))
            if out.exists() and out.stat().st_size > 0:
                print(f"  [dl] ✓ screenshot  {out.stat().st_size // 1024} KB → {out.name}")
                return out
    except Exception as exc:
        print(f"  [dl] screenshot error: {exc}")

    raise RuntimeError(
        f"All 3 download strategies failed for src={src[:80]!r}. "
        "The image is visible in the browser — save it manually if needed."
    )


def run() -> None:
    args = parse_args()
    prompt_dir = Path(args.prompt_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    upload_dir = Path(args.upload_dir).expanduser().resolve()

    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = discover_prompt_jobs(prompt_dir, args.prompt_glob)

    auto_launch_debug_browser(args)

    with tempfile.TemporaryDirectory(prefix="gemini_uploads_") as tmp:
        temp_dir = Path(tmp)
        if args.image_source_file:
            source_file = Path(args.image_source_file).resolve()
            image_sources = parse_image_source_file(source_file, args.logo_key)
            upload_paths = build_local_image_paths(image_sources, temp_dir)
        else:
            upload_paths = collect_upload_images_from_dir(upload_dir)

        if len(upload_paths) > 20:
            print(
                f"Warning: {len(upload_paths)} upload images found. Gemini may reject very large attachment batches."
            )

        driver = build_driver(args)
        try:
            for idx, job in enumerate(jobs, start=1):
                print(f"\n[{idx}/{len(jobs)}] Processing {job.prompt_path.name}")
                prompt_text = job.prompt_path.read_text(encoding="utf-8")

                out_base = out_dir / f"gemini-hero-{job.persona_id.lower()}"
                try:
                    success = False
                    last_exc: Exception | None = None
                    for attempt in range(1, 3):
                        try:
                            open_gemini_new_chat(driver)
                            before_sources = get_image_sources(driver)

                            upload_images(driver, upload_paths)

                            # Upload verification (best-effort): thumbnails/chips should appear.
                            # If not, capture screenshot and retry attempt.
                            if not _upload_appears_ok(driver):
                                # Save a diagnostic screenshot immediately (best-effort).
                                diag = out_base.with_name(out_base.name + "-upload-failed.png")
                                try:
                                    _save_debug_screenshot(driver, diag)
                                except Exception:
                                    pass
                                raise TimeoutException("Upload verification failed (no upload UI evidence found)")

                            time.sleep(2.0)
                            dismiss_open_overlays(driver)

                            # Composer + prompt
                            composer = find_composer(driver)
                            set_prompt_text(driver, composer, prompt_text)

                            # Switch model/tool AFTER typing prompt selection steps can re-render composer UI,
                            # so we re-find composer right before sending.
                            force_fast_to_pro(driver)
                            select_pro_model_and_create_image_tool(driver)
                            if args.require_pro_model and not pro_model_selected(driver):
                                raise TimeoutException("Could not confirm Pro model selection in Gemini UI")

                            dismiss_open_overlays(driver)
                            composer = find_composer(driver)  # re-find to avoid stale element issues

                            click_send(driver, composer)
                            time.sleep(2.0)
                            print("Waiting for image generation...")
                            image_src = wait_for_new_generated_image(driver, before_sources, args.timeout)
                            saved_path = download_generated_image(driver, image_src, out_base)
                            print("Waiting after download...")
                            time.sleep(30)

                            metadata = {
                                "status": "success",
                                "prompt_file": str(job.prompt_path),
                                "persona_id": job.persona_id,
                                "generated_image_src": image_src,
                                "saved_file": str(saved_path),
                                "timestamp": int(time.time()),
                            }
                            (out_base.with_suffix(".json")).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
                            print(f"Saved: {saved_path}")
                            success = True
                            break
                        except (InvalidSessionIdException, WebDriverException) as exc:
                            last_exc = exc
                            print(f"Driver/session issue on attempt {attempt}: {exc}")
                            if attempt == 2:
                                break
                            auto_launch_debug_browser(args)
                            driver = build_driver(args)
                        except Exception as exc:
                            last_exc = exc
                            break
                    if success:
                        continue
                    raise last_exc if last_exc else RuntimeError("Unknown prompt processing failure")
                except Exception as exc:
                    screenshot = out_base.with_suffix(".png")
                    try:
                        driver.save_screenshot(str(screenshot))
                    except Exception:
                        screenshot = None

                    current_url = None
                    try:
                        current_url = driver.current_url
                    except Exception:
                        current_url = None

                    metadata = {
                        "status": "error",
                        "prompt_file": str(job.prompt_path),
                        "persona_id": job.persona_id,
                        "error": str(exc),
                        "screenshot": str(screenshot) if screenshot else None,
                        "current_url": current_url,
                        "timestamp": int(time.time()),
                    }
                    (out_base.with_suffix(".json")).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
                    print(f"Error on {job.persona_id}: {exc}")
                    print("Continuing to next prompt...")

            print("\nAll prompts processed.")
        finally:
            print("Leaving browser open for inspection. Close it manually when done.")


if __name__ == "__main__":
    run()