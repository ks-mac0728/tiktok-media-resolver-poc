#!/usr/bin/env python3
"""
Method A (yt-dlp anonymous) runner — 再利用可能なテストランナー。

Public Anonymous Set / General Input Set の両方に対して
InstagramYtDlpAdapter を実行し、MediaResolveResult の一覧を
method_a_results.json に保存する。

Usage:
    python3 run_method_a.py
"""

import json
import sys
from pathlib import Path

from instagram_adapter import InstagramYtDlpAdapter
from test_urls import PUBLIC_ANONYMOUS_SET, GENERAL_INPUT_SET

PROJECT_DIR = Path(__file__).resolve().parent
OUT = PROJECT_DIR / "method_a_results.json"


def run_set(name: str, entries: list[dict]) -> list[dict]:
    adapter = InstagramYtDlpAdapter()
    out = []
    for e in entries:
        url = e["url"]
        print(f"[{name}] {url} ...", flush=True)
        try:
            result = adapter.resolve(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! adapter exception: {exc}", flush=True)
            out.append({
                "url": url,
                "success": False,
                "error_code": "RESOLVER_ERROR",
                "error_message": f"adapter exception: {type(exc).__name__}: {exc}",
            })
            continue
        out.append(result.to_dict())
        status = "OK" if result.success else "FAIL"
        print(f"  -> {status} [{result.error_code}] "
              f"{result.error_message[:80]}", flush=True)
    return out


def main() -> int:
    pub = run_set("public_anonymous_set", PUBLIC_ANONYMOUS_SET)
    gen = run_set("general_input_set", GENERAL_INPUT_SET)

    data = {
        "public_anonymous_set": pub,
        "general_input_set": gen,
    }
    OUT.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    pub_ok = sum(1 for r in pub if r["success"])
    gen_ok = sum(1 for r in gen if r["success"])
    print("\n===== Method A summary =====")
    print(f"public_anonymous_set: {pub_ok}/{len(pub)}")
    print(f"general_input_set:    {gen_ok}/{len(gen)}")
    print(f"Results -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
