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


def open_gemini_with_retry(driver: webdriver.Chrome, retries: int = 3) -> None:
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            driver.get(GEMINI_URL)
            time.sleep(1.5)
            current = (driver.current_url or "").lower()
            if current.startswith("data:") or current.startswith("about:blank"):
                driver.execute_script("window.location.href = arguments[0];", GEMINI_URL)
                time.sleep(2.0)
            current = (driver.current_url or "").lower()
            if "gemini.google.com" in current:
                return
        except Exception as exc:
            last_exc = exc
        print(f"Navigation attempt {attempt}/{retries} failed. Current URL: {driver.current_url}")
        time.sleep(2.0)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Could not navigate to {GEMINI_URL}; final URL was {driver.current_url}")


def focus_or_open_gemini_tab(driver: webdriver.Chrome) -> None:
    try:
        handles = driver.window_handles
    except Exception:
        handles = []

    # Prefer an existing Gemini or Google login tab so we do not disrupt manual sign-in.
    for h in handles:
        try:
            driver.switch_to.window(h)
            current = (driver.current_url or "").lower()
            if "gemini.google.com" in current or "accounts.google.com" in current:
                return
        except Exception:
            continue

    # Otherwise navigate the current tab to Gemini first. Only create a new tab if that fails.
    try:
        open_gemini_with_retry(driver)
    except Exception:
        try:
            driver.switch_to.new_window("tab")
        except Exception:
            pass
        open_gemini_with_retry(driver)


def open_gemini_new_chat(driver: webdriver.Chrome) -> None:
    driver.execute_script("window.open('');")
    time.sleep(1.0)
    handles = driver.window_handles
    driver.switch_to.window(handles[-1])
    driver.get(GEMINI_URL)
    time.sleep(2.0)
    dismiss_open_overlays(driver)
    body = driver.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.CONTROL, Keys.SHIFT, "o")
    time.sleep(5)
    body.send_keys(Keys.CONTROL, Keys.SHIFT, "o")
    time.sleep(2.0)
    dismiss_open_overlays(driver)


def close_active_tab(driver: webdriver.Chrome) -> None:
    try:
        handles = driver.window_handles
    except Exception:
        handles = []

    if len(handles) <= 1:
        return

    try:
        driver.close()
    except Exception:
        return

    try:
        remaining = driver.window_handles
        if remaining:
            driver.switch_to.window(remaining[-1])
    except Exception:
        pass


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
        "div[contenteditable='true'][aria-label*='message']",
        "textarea[aria-label*='message']",
        "textarea[placeholder*='Message']",
        "button[aria-label*='New chat']",
        "button[aria-label*='New conversation']",
    ]
    for sel in selectors:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if any(e.is_displayed() for e in elems):
                return True
        except Exception:
            continue
    return False


def wait_for_manual_login(driver: webdriver.Chrome, timeout: int = 600, strict: bool = False) -> None:
    print("\nWaiting for Gemini login/readiness...")
    print("If login page is open, complete login in the browser. Script will auto-continue.")

    deadline = time.time() + timeout
    next_log = time.time() + 5
    while time.time() < deadline:
        try:
            if gemini_app_ready(driver):
                print(f"Gemini UI looks ready at {driver.current_url}. Continuing.")
                return
        except Exception:
            pass
        if time.time() >= next_log:
            try:
                current = driver.current_url
            except Exception:
                current = "<unavailable>"
            print(f"Still waiting for Gemini UI readiness... current URL: {current}")
            next_log = time.time() + 5
        time.sleep(2.0)
    msg = f"Timed out after {timeout}s waiting for Gemini readiness"
    if strict:
        raise TimeoutException(msg)
    print(f"{msg}; continuing in auto mode.")
    return


def click_new_chat_if_present(driver: webdriver.Chrome) -> None:
    selectors = [
        "button[aria-label*='New chat']",
        "button[aria-label*='New conversation']",
        "a[aria-label*='New chat']",
    ]
    for sel in selectors:
        buttons = driver.find_elements(By.CSS_SELECTOR, sel)
        if buttons:
            try:
                buttons[0].click()
                time.sleep(1.0)
            except Exception:
                pass
            return

    # Text fallback
    click_text_options(
        driver,
        ["New chat", "New conversation"],
        fail_silently=True,
    )


def ensure_sidebar_open(driver: webdriver.Chrome) -> None:
    # If sidebar's New chat is visible, nothing to do.
    visible_new = driver.execute_script(
        "const nodes=[...document.querySelectorAll('button,a,div,[role=button]')];"
        "return nodes.some(n=>{"
        " const t=(n.innerText||'').trim().toLowerCase();"
        " if(!t.includes('new chat')) return false;"
        " const r=n.getBoundingClientRect();"
        " const s=getComputedStyle(n);"
        " return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none' && r.left < 260;"
        "});"
    )
    if visible_new:
        return

    # Open sidebar/hamburger.
    click_first_visible_css(
        driver,
        [
            "button[aria-label*='menu']",
            "button[aria-label*='Menu']",
            "button[aria-label*='sidebar']",
            "button[aria-label*='navigation']",
        ],
        timeout=3,
    )
    time.sleep(0.6)


def click_sidebar_new_chat(driver: webdriver.Chrome) -> bool:
    # Click only the New chat entry in the left sidebar region.
    xpaths = [
        "//*[self::a or self::button or @role='button'][normalize-space()='New chat']",
        "//nav//*[self::a or self::button or @role='button'][normalize-space()='New chat']",
        "//*[contains(@class,'drawer') or contains(@class,'sidebar') or contains(@class,'nav')]//*[self::a or self::button or @role='button'][normalize-space()='New chat']",
    ]
    for xp in xpaths:
        for el in driver.find_elements(By.XPATH, xp):
            try:
                if not el.is_displayed() or not el.is_enabled():
                    continue
                rect = el.rect or {}
                if rect.get("x", 9999) > 330:
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

    script = """
        const nodes = [...document.querySelectorAll('button,a,div,[role="button"]')];
        const candidates = nodes.filter(n => {
          const txt = (n.innerText || '').trim().toLowerCase();
          if (txt !== 'new chat') return false;
          const r = n.getBoundingClientRect();
          const s = getComputedStyle(n);
          return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && r.left < 280;
        });
        if (!candidates.length) return false;
        candidates.sort((a,b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
        candidates[0].click();
        return true;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def old_chat_title_visible(driver: webdriver.Chrome) -> bool:
    script = """
        const els = [...document.querySelectorAll('main h1, main h2, header h1, header h2, [role="heading"]')];
        const texts = els
          .map(e => (e.innerText || '').trim())
          .filter(Boolean)
          .filter(t => t.toLowerCase() !== 'gemini')
          .filter(t => t.toLowerCase() !== 'pro')
          .filter(t => t.length > 8);
        return texts.length > 0;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def ensure_new_chat_strict(driver: webdriver.Chrome) -> None:
    # Open sidebar, click New chat once, then wait for the UI to settle.
    dismiss_open_overlays(driver)
    ensure_sidebar_open(driver)
    clicked = click_sidebar_new_chat(driver)
    if not clicked:
        click_new_chat_if_present(driver)

    # Let Gemini finish the route transition before touching anything else.
    time.sleep(2.5)
    dismiss_open_overlays(driver)

    # If we still landed on an old chat route, do one hard reset only.
    current = ""
    try:
        current = (driver.current_url or "").lower()
    except Exception:
        current = ""

    if "/app/a/" in current and old_chat_title_visible(driver):
        driver.get(GEMINI_URL)
        time.sleep(2.5)
        dismiss_open_overlays(driver)
        ensure_sidebar_open(driver)
        clicked = click_sidebar_new_chat(driver)
        if not clicked:
            click_new_chat_if_present(driver)
        time.sleep(2.5)
        dismiss_open_overlays(driver)


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


def get_image_sources(driver: webdriver.Chrome) -> List[str]:
    script = """
        const imgs = Array.from(document.querySelectorAll('main img, img'));
        const out = [];
        for (const img of imgs) {
          const src = img.currentSrc || img.src || '';
          if (!src) continue;
          if (src.includes('gstatic.com') || src.includes('googlelogo')) continue;
          if (src.startsWith('http') || src.startsWith('data:image/') || src.startsWith('blob:')) out.push(src);
        }
        return Array.from(new Set(out));
    """
    try:
        return driver.execute_script(script) or []
    except Exception:
        return []


def wait_for_new_generated_image(driver: webdriver.Chrome, before_sources: List[str], timeout: int) -> str:
    before = set(before_sources)
    start = time.time()
    while time.time() - start < timeout:
        current = get_image_sources(driver)
        fresh = [src for src in current if src not in before]
        if fresh:
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


def build_cookie_header(driver: webdriver.Chrome) -> str:
    cookies = driver.get_cookies()
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)


def download_generated_image(driver: webdriver.Chrome, src: str, out_path_no_ext: Path) -> Path:
    current_url = (driver.current_url or "").lower()
    if "/app/a/" in current_url:
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                url = (driver.current_url or "").lower()
                if "gemini" in url and "/app/a/" not in url:
                    break
            except Exception:
                continue

    if src.startswith("blob:"):
        data_url = driver.execute_async_script(
            "const url = arguments[0];"
            "const done = arguments[arguments.length - 1];"
            "fetch(url).then(r => r.blob()).then(blob => {"
            "  const reader = new FileReader();"
            "  reader.onloadend = () => done(reader.result);"
            "  reader.onerror = () => done(null);"
            "  reader.readAsDataURL(blob);"
            "}).catch(() => done(null));",
            src,
        )
        if isinstance(data_url, str) and data_url.startswith("data:image/"):
            header, b64data = data_url.split(",", 1)
            ext = infer_ext_from_src(header)
            out_path = out_path_no_ext.with_suffix(ext)
            out_path.write_bytes(base64.b64decode(b64data))
            return out_path

        original_tab = driver.current_window_handle
        initial_tabs = len(driver.window_handles)

        try:
            large_img = driver.execute_script("""
                var imgs = document.querySelectorAll('img');
                for (var img of imgs) {
                    var r = img.getBoundingClientRect();
                    if (r.width > 300 && img.src.startsWith('blob:')) {
                        return img;
                    }
                }
                return null;
            """)
            if large_img:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", large_img)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", large_img)
                time.sleep(2)

                current_tabs = len(driver.window_handles)
                if current_tabs > initial_tabs:
                    for handle in driver.window_handles:
                        if handle != original_tab:
                            try:
                                driver.switch_to.window(handle)
                                if "gemini" not in (driver.current_url or "").lower():
                                    driver.close()
                            except Exception:
                                pass
                    driver.switch_to.window(original_tab)
                    time.sleep(0.5)

                clicked = driver.execute_script("""
                    var dialog = document.querySelector('[role=dialog]');
                    if (!dialog) return false;
                    var buttons = dialog.querySelectorAll('button');
                    for (var b of buttons) {
                        var aria = b.getAttribute('aria-label') || '';
                        if (aria.includes('Download')) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                """)
                if clicked:
                    time.sleep(2)
                    current_tabs = len(driver.window_handles)
                    if current_tabs > initial_tabs:
                        for handle in driver.window_handles:
                            if handle != original_tab:
                                try:
                                    driver.switch_to.window(handle)
                                    if "gemini" not in (driver.current_url or "").lower():
                                        driver.close()
                                except Exception:
                                    pass
                        driver.switch_to.window(original_tab)
                    time.sleep(3)
                    # Check Downloads folder for most recent image
                    dl_dir = Path("/home/mylappy/Downloads")
                    if dl_dir.exists():
                        files = sorted(dl_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
                        # Also check for jpg/jpeg
                        if not files:
                            files = sorted(dl_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
                        if not files:
                            files = sorted(dl_dir.glob("*.jpeg"), key=lambda p: p.stat().st_mtime, reverse=True)
                        if files:
                            latest = files[0]
                            out_path = out_path_no_ext.with_suffix(latest.suffix)
                            shutil.copy(latest, out_path)
                            if out_path.exists() and out_path.stat().st_size > 100000:  # Full images are ~6MB
                                return out_path
        except Exception as e:
            pass

        # Last fallback: screenshot the exact rendered image element that uses this blob URL.
        elems = driver.find_elements(By.CSS_SELECTOR, "img")
        for el in elems:
            try:
                current_src = driver.execute_script("return arguments[0].currentSrc || arguments[0].src || '';", el)
                if current_src != src:
                    continue
                out_path = out_path_no_ext.with_suffix(".png")
                el.screenshot(str(out_path))
                if out_path.exists() and out_path.stat().st_size > 0:
                    return out_path
            except Exception:
                continue

        raise RuntimeError("Could not convert blob image to a downloadable data URL or screenshot the blob image element")

    if src.startswith("data:image/"):
        header, b64data = src.split(",", 1)
        ext = infer_ext_from_src(header)
        out_path = out_path_no_ext.with_suffix(ext)
        out_path.write_bytes(base64.b64decode(b64data))
        return out_path

    req = urllib.request.Request(
        src,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": GEMINI_URL,
            "Cookie": build_cookie_header(driver),
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
        ext = infer_ext_from_src(src, resp.headers.get("Content-Type", ""))
    out_path = out_path_no_ext.with_suffix(ext)
    out_path.write_bytes(data)
    return out_path


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
                            time.sleep(10)
                            dismiss_open_overlays(driver)
                            composer = find_composer(driver)
                            set_prompt_text(driver, composer, prompt_text)

                            # User-required order: switch Fast -> Pro before send.
                            force_fast_to_pro(driver)
                            select_pro_model_and_create_image_tool(driver)
                            if args.require_pro_model and not pro_model_selected(driver):
                                raise TimeoutException("Could not confirm Pro model selection in Gemini UI")

                            click_send(driver, composer)
                            time.sleep(5)
                            print("Waiting for image generation...")
                            time.sleep(100)

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
