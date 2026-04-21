#!/usr/bin/env python3
"""
Export a "do-not-repeat" banlist from AD_GENERATION_REGISTRY.JSON for LLM copy generation.

This is intentionally simple:
  - Exact-string banning only (matches playbook rule).
  - Use `--last` to limit size so prompts stay manageable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "AD_GENERATION_REGISTRY.JSON"


DEFAULT_BUCKETS = [
    "headline_en",
    "headline_hi",
    "support_line_en",
    "support_line_hi",
    "cta_en",
    "cta_hi",
    "bullets_en",
    "bullets_hi",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export registry used_text banlist for LLM prompting")
    p.add_argument("--bucket", action="append", help="used_text bucket name (repeatable). Default: core buckets.")
    p.add_argument("--last", type=int, default=200, help="Take only last N strings per bucket (default: 200)")
    p.add_argument("--out", help="Write JSON to file instead of stdout")
    return p.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    registry = load_json(REGISTRY_PATH)
    used_text = (registry.get("indexes", {}) or {}).get("used_text", {}) or {}

    buckets = args.bucket or DEFAULT_BUCKETS
    out: dict[str, list[str]] = {}
    for b in buckets:
        arr = used_text.get(b) or []
        if not isinstance(arr, list):
            continue
        strings = [s for s in arr if isinstance(s, str) and s.strip()]
        out[b] = strings[-args.last :] if args.last > 0 else strings

    payload = {"source": str(REGISTRY_PATH), "last": args.last, "buckets": out}
    raw = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if args.out:
        Path(args.out).write_text(raw, encoding="utf-8")
    else:
        print(raw, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

