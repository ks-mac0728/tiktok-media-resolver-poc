#!/usr/bin/env python3
"""results.json に残り4件の実測結果をマージし、最終 summary を再計算する。"""
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
RESULTS_JSON = PROJECT_DIR / "results.json"
REMAINING_JSON = PROJECT_DIR / "downloads" / "_remaining_matrix.json"


def rate(rows):
    ok = sum(1 for r in rows if r["success"])
    return {"success": ok, "total": len(rows), "rate": f"{ok}/{len(rows)}"}


def main():
    d = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    existing = d["matrix"]
    remaining = json.loads(REMAINING_JSON.read_text(encoding="utf-8"))

    existing_urls = {e["url"] for e in existing}
    merged = list(existing)
    for r in remaining:
        if r["url"] in existing_urls:
            merged = [e for e in merged if e["url"] != r["url"]]
        merged.append(r)

    by_set = {}
    for e in merged:
        by_set.setdefault(e["set"], []).append(e)
    by_platform = {}
    for e in merged:
        by_platform.setdefault(e["platform"], []).append(e)

    summary = {
        "sets": {k: rate(v) for k, v in by_set.items()},
        "platforms": {k: rate(v) for k, v in by_platform.items()},
    }

    final = {"matrix": merged, "summary": summary}
    RESULTS_JSON.write_text(
        json.dumps(final, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"FINAL results.json: {len(merged)} URLs")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
