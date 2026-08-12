#!/usr/bin/env python3
"""
Real URL Test Matrix — fallback chain を通して実測し results.json を生成する。

  TikTok    3 URL（baseline/regression）
  Instagram 1 public + 10 general（重複除去）

成功率はセットごとに別々に集計する（修正指示 #3）。
各URL終了ごとに results.json を増分保存（タイムアウト時の部分成果を保全）。

Usage:
    python3 run_matrix.py
"""

import json
import time
from pathlib import Path

from resolve_media import resolve_media
from resolver_contract import detect_platform
from test_urls import (
    TIKTOK_SAMPLE_URLS,
    PUBLIC_ANONYMOUS_SET,
    GENERAL_INPUT_SET,
)

PROJECT_DIR = Path(__file__).resolve().parent
RESULTS_JSON = PROJECT_DIR / "results.json"


def build_matrix() -> list[dict]:
    matrix = []
    seen = set()

    for u in TIKTOK_SAMPLE_URLS:
        matrix.append({"url": u, "platform": "tiktok", "set": "tiktok-baseline"})

    for e in PUBLIC_ANONYMOUS_SET:
        if e["url"] not in seen:
            seen.add(e["url"])
            matrix.append({
                "url": e["url"], "platform": "instagram",
                "set": "instagram-public-anonymous", "note": e.get("note", ""),
            })

    for e in GENERAL_INPUT_SET:
        if e["url"] not in seen:
            seen.add(e["url"])
            matrix.append({
                "url": e["url"], "platform": "instagram",
                "set": "instagram-general-input", "note": e.get("note", ""),
            })

    return matrix


def run_matrix() -> dict:
    matrix = build_matrix()
    entries = []

    print(f"Matrix size: {len(matrix)} URLs", flush=True)

    for i, item in enumerate(matrix):
        url = item["url"]
        print(f"\n[{i + 1}/{len(matrix)}] {item['set']} :: {url}", flush=True)
        t0 = time.monotonic()
        try:
            result = resolve_media(url)
            d = result.to_dict()
        except Exception as exc:  # noqa: BLE001
            d = {
                "url": url, "platform": item["platform"],
                "success": False, "error_code": "RESOLVER_ERROR",
                "error_message": f"resolve_media exception: {type(exc).__name__}: {exc}",
                "attempts": [],
            }
        d["set"] = item["set"]
        d["note"] = item.get("note", "")
        d["wall_seconds"] = round(time.monotonic() - t0, 1)
        entries.append(d)

        status = "OK" if d["success"] else "FAIL"
        print(f"  -> {status} [{d.get('final_method') or d.get('error_code')}] "
              f"{d.get('error_message', '')[:70]}", flush=True)

        # 増分保存
        _save({"matrix": entries}, RESULTS_JSON)

    summary = _summarize(entries)
    _save({"matrix": entries, "summary": summary}, RESULTS_JSON)

    print("\n===== SUMMARY =====")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return {"matrix": entries, "summary": summary}


def _summarize(entries: list[dict]) -> dict:
    def rate(rows):
        ok = sum(1 for r in rows if r["success"])
        return {"success": ok, "total": len(rows), "rate": f"{ok}/{len(rows)}"}

    by_set = {}
    for e in entries:
        by_set.setdefault(e["set"], []).append(e)

    by_platform = {}
    for e in entries:
        by_platform.setdefault(e["platform"], []).append(e)

    return {
        "sets": {k: rate(v) for k, v in by_set.items()},
        "platforms": {k: rate(v) for k, v in by_platform.items()},
    }


def _save(data: dict, path: Path):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


if __name__ == "__main__":
    run_matrix()
