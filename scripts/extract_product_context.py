#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def compact_lines(text: str, max_lines: int) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:max_lines]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract compact product context for generation")
    parser.add_argument("--product", default="productinfomain.txt")
    parser.add_argument("--mechanism", default="PRODUCT_MECHANISM_V1.txt")
    parser.add_argument("--faq", default="faq.txt")
    parser.add_argument("--max-lines", type=int, default=60)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = {
        "product_info": compact_lines(Path(args.product).read_text(encoding="utf-8"), args.max_lines),
        "mechanism": compact_lines(Path(args.mechanism).read_text(encoding="utf-8"), args.max_lines),
        "faq": compact_lines(Path(args.faq).read_text(encoding="utf-8"), args.max_lines),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key, values in payload.items():
            print(f"[{key}]")
            for item in values:
                print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
