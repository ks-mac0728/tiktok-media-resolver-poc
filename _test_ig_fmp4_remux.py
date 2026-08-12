#!/usr/bin/env python3
"""
Step 8 remux attempt: fMP4 断片からトラックごとに init+fragments を結合し、
ffmpeg で映像+音声を mux して再生可能な MP4 を作れるか検証する。

方針:
  1. URL の /f2/mXXX/ からストリームIDを判別（m367=映像, m86=音声）
  2. ストリームごとに init(ftyp+moov) + 各断片(moof+mdat) を capture順で結合
  3. ffmpeg -c copy で映像+音声を mux
  4. ffprobe で検証（codec / width-height / duration / has_audio）
"""

import re
import subprocess
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
TMP = PROJECT_DIR / "downloads" / "_fmp4_investigation"
OUT = PROJECT_DIR / "downloads" / "instagram-playwright_remux.mp4"

URL = "https://www.instagram.com/reel/DLgMlwmhpah/"
CDN_PATTERNS = ["fbcdn.net", "scontent.", "cdninstagram.com"]
STREAM_RE = re.compile(r"/f2/(m\d+)/")


def box_scan(data: bytes) -> str:
    found = []
    i = 0
    while i + 8 <= len(data) and len(found) < 8:
        size = int.from_bytes(data[i:i + 4], "big")
        typ = data[i + 4:i + 8].decode("latin1", "replace")
        found.append(typ)
        i += size
        if size == 0:
            break
    return " ".join(found)


def main():
    from playwright.sync_api import sync_playwright

    TMP.mkdir(parents=True, exist_ok=True)
    segments = []  # {url, body, stream, is_init}

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
            if is_cdn or ".mp4" in req_url or "video" in req_url.lower():
                try:
                    resp = route.fetch()
                    ct = resp.headers.get("content-type", "").lower()
                    if "video" in ct or "audio" in ct or ".mp4" in req_url:
                        body = resp.body()
                        m = STREAM_RE.search(req_url)
                        stream = m.group(1) if m else "unknown"
                        boxes = box_scan(body)
                        is_init = "ftyp" in boxes and "moov" in boxes
                        if stream != "unknown" or is_init:
                            segments.append({
                                "url": req_url, "body": body,
                                "stream": stream, "is_init": is_init,
                                "boxes": boxes,
                            })
                    route.fulfill(response=resp)
                    return
                except Exception:
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

    # ストリームごとにグルーピング
    streams = {}
    for s in segments:
        streams.setdefault(s["stream"], []).append(s)

    print(f"streams detected: {list(streams.keys())}")
    for sid, segs in streams.items():
        inits = [s for s in segs if s["is_init"]]
        frags = [s for s in segs if not s["is_init"]]
        total_frag = sum(len(s["body"]) for s in frags)
        print(f"  {sid}: init={len(inits)} frag={len(frags)} "
              f"frag_bytes={total_frag:,}")

    # トラックごとに concat（init + fragments in capture order）
    track_files = {}
    for sid, segs in streams.items():
        inits = [s for s in segs if s["is_init"]]
        frags = [s for s in segs if not s["is_init"]]
        if not inits or not frags:
            continue
        path = TMP / f"track_{sid}.mp4"
        with path.open("wb") as out:
            out.write(inits[0]["body"])  # 最初のinitを使用
            for f in frags:
                out.write(f["body"])
        track_files[sid] = path
        print(f"  -> {sid}: {path.stat().st_size:,} bytes")

    if len(track_files) < 2:
        print("=> 映像+音声の2トラックが揃わないため mux 不可")
        return

    # 映像トラックを m367、音声を m86 と仮定（サイズで判定）
    # 実際はサイズ大 = 映像
    sorted_tracks = sorted(
        track_files.items(), key=lambda kv: kv[1].stat().st_size, reverse=True
    )
    video_path = sorted_tracks[0][1]
    audio_path = sorted_tracks[1][1]
    print(f"\nvideo track: {sorted_tracks[0][0]} -> {video_path}")
    print(f"audio track: {sorted_tracks[1][0]} -> {audio_path}")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        str(OUT),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(f"\nffmpeg exit={r.returncode}")
    if r.returncode != 0:
        print((r.stderr or "")[-1200:])
        return

    print(f"\nremux -> {OUT} ({OUT.stat().st_size:,} bytes)")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height",
         "-show_entries", "format=duration,size",
         "-of", "json", str(OUT)],
        capture_output=True, text=True, timeout=30,
    )
    print(f"ffprobe exit={probe.returncode}")
    print(probe.stdout)


if __name__ == "__main__":
    main()
