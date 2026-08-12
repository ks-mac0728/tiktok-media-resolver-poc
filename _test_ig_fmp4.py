#!/usr/bin/env python3
"""
Step 8 focused investigation: 捕捉した Instagram メディア断片の構造を精査し、
fMP4 再構築（init segment + fragment 結合）が可能かを判定する。

方針（time-boxed）:
  1. 全 video/mp4 レスポンス（init segment + 各断片）を保存
  2. 各断片の box 構造（ftyp/moov/moof/mdat）を検査
  3. init segment が捕捉できるか、順序が復元できるかを判定
  4. ffmpeg concat で remux を1回だけ試行

結論が出たら REJECT（クリーンな再構築経路なし）or CONDITIONAL を返す。
"""

import json
import subprocess
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
TMP = PROJECT_DIR / "downloads" / "_fmp4_investigation"
TMP.mkdir(parents=True, exist_ok=True)

URL = "https://www.instagram.com/reel/DLgMlwmhpah/"
CDN_PATTERNS = ["fbcdn.net", "scontent.", "cdninstagram.com"]


def box_scan(data: bytes) -> str:
    """先頭付近の box 種別を列挙して返す"""
    found = []
    i = 0
    while i + 8 <= len(data) and len(found) < 8:
        size = int.from_bytes(data[i:i + 4], "big")
        typ = data[i + 4:i + 8].decode("latin1", "replace")
        if typ in ("ftyp", "moov", "moof", "mdat", "styp", "sidx"):
            found.append(f"{typ}({size})")
        else:
            found.append(typ)
        i += size
        if size == 0:
            break
    return " ".join(found)


def main():
    from playwright.sync_api import sync_playwright

    segments = []  # list of {url, size, boxes, path}
    t0 = time.monotonic()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        def handle_route(route):
            req_url = route.request.url
            is_cdn = any(p in req_url for p in CDN_PATTERNS)
            is_mp4 = ".mp4" in req_url or "video" in req_url.lower()
            if is_cdn or is_mp4:
                try:
                    resp = route.fetch()
                    ct = resp.headers.get("content-type", "").lower()
                    if "video" in ct or ".mp4" in req_url:
                        body = resp.body()
                        path = TMP / f"seg_{len(segments):03d}.bin"
                        path.write_bytes(body)
                        segments.append({
                            "url": req_url,
                            "size": len(body),
                            "boxes": box_scan(body),
                            "path": str(path),
                            "t": round(time.monotonic() - t0, 2),
                        })
                        print(f"[{len(segments):03d}] {len(body):>9,}B "
                              f"{box_scan(body)[:60]}  {req_url[:110]}",
                              flush=True)
                    route.fulfill(response=resp)
                    return
                except Exception as e:
                    route.continue_()
            else:
                route.continue_()

        page.route("**/*", handle_route)
        try:
            page.goto(URL, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print("goto warn:", e)
        page.wait_for_timeout(12000)
        browser.close()

    print(f"\n===== captured {len(segments)} segments =====")
    has_init = any("ftyp" in s["boxes"] or "moov" in s["boxes"]
                   for s in segments)
    has_frag = any("moof" in s["boxes"] for s in segments)
    print(f"has_init(ftyp/moov): {has_init}")
    print(f"has_fragment(moof):  {has_frag}")

    # 簡易 concat 試行: init + 全断片（順序維持）
    if has_init and has_frag:
        init_seg = next(s for s in segments
                        if "ftyp" in s["boxes"] or "moov" in s["boxes"])
        frags = [s for s in segments if "moof" in s["boxes"]]
        concat = TMP / "concat.mp4"
        with concat.open("wb") as out:
            out.write(Path(init_seg["path"]).read_bytes())
            for f in frags:
                out.write(Path(f["path"]).read_bytes())
        print(f"\nconcat -> {concat} ({concat.stat().st_size:,} bytes)")
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams",
             str(concat)],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            print("ffprobe: OK (remux可能)")
        else:
            print("ffprobe: FAIL")
            print((r.stderr or "")[:800])
    else:
        print("\n=> init segment が捕捉できないため、単純concatは不可")

    result = {
        "url": URL,
        "segments": segments,
        "has_init": has_init,
        "has_fragment": has_frag,
        "conclusion": "",
    }
    (TMP / "investigation.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\ninvestigation.json -> {TMP}/investigation.json")


if __name__ == "__main__":
    main()
