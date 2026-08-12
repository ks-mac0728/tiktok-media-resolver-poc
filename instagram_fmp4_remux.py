"""
Instagram fMP4 Remux Resolver — Method B（fMP4断片 → トラック結合 → ffmpeg mux）

_step test_ig_fmp4_remux.py で実証済みの「fMP4断片再構築」ロジックを
Common Contract (MediaResolveResult) に適合させた Resolver。

方式:
  1. Playwright で CDN への video/audio リクエストを捕捉
  2. URL の /f2/mXXX/ からストリームIDを判別（m367=映像, m86=音声）
  3. ストリームごとに init(ftyp+moov) + 各断片(moof+mdat) を capture順で結合
  4. ffmpeg -c copy で映像+音声を mux し、再生可能な MP4 を生成
  5. ffprobe で検証

制約（REPORT に記載すべき点）:
  - Instagram は匿名アクセスを制限しており、login-required Reel には通用しない
  - ストリームID / 断片順序のヒューリスティックに依存（fragile）
  - 出力は VP9（Instagram 側配信コーデック）になる。yt-dlp は h264 を返す
  - 真に公開された Reel（例: DLgMlwmhpah）でのみ成功実績あり

Method identifier: instagram-browser-fmp4-remux
"""

import json
import re
import subprocess
import time

from resolver_contract import (
    MediaResolveResult,
    ResolveAttempt,
    MediaMetadata,
    detect_platform,
    extract_shortcode,
    normalize_url,
)
from error_codes import ErrorCodes
from instagram_resolver import normalize_instagram_url

PROJECT_DIR = __import__("pathlib").Path(__file__).resolve().parent
DOWNLOADS_DIR = PROJECT_DIR / "downloads"

CDN_PATTERNS = ["fbcdn.net", "scontent.", "cdninstagram.com"]
STREAM_RE = re.compile(r"/f2/(m\d+)/")


def _box_scan(data: bytes) -> str:
    """MP4 box のタイプ列を軽くスキャン（init segment 判定用）"""
    found = []
    i = 0
    while i + 8 <= len(data) and len(found) < 8:
        size = int.from_bytes(data[i:i + 4], "big")
        typ = data[i + 4:i + 8].decode("latin1", "replace")
        found.append(typ)
        if size <= 0:
            break
        i += size
    return " ".join(found)


class InstagramFmp4RemuxResolver:
    """fMP4 断片を再構築して再生可能 MP4 を生成する Resolver"""

    METHOD = "instagram-browser-fmp4-remux"

    def resolve(self, url: str) -> MediaResolveResult:
        canonical, shortcode, url_type = normalize_instagram_url(url)

        result = MediaResolveResult(
            url=url,
            canonical_url=canonical,
            platform="instagram",
            shortcode=shortcode,
        )

        attempt = ResolveAttempt(method=self.METHOD)
        t_start = time.monotonic()

        if not shortcode:
            attempt.error_message = f"URLからshortcodeを抽出できませんでした: {url}"
            attempt.error_code = ErrorCodes.MEDIA_NOT_FOUND.code
            attempt.processing_seconds = time.monotonic() - t_start
            result.add_attempt(attempt)
            result.estimated_cost_article = "$0.00（無料・無制限、Chromium+ffmpegリソース消費あり）"
            result.finalize()
            return result

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            attempt.error_message = "playwright がインストールされていません"
            attempt.error_code = ErrorCodes.NOT_CONFIGURED.code
            attempt.processing_seconds = time.monotonic() - t_start
            result.add_attempt(attempt)
            result.finalize()
            return result

        segments = []  # {url, body, stream, is_init, boxes}

        try:
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
                            resp = route.fetch(timeout=30000)
                            ct = resp.headers.get("content-type", "").lower()
                            if "video" in ct or "audio" in ct or ".mp4" in req_url:
                                body = resp.body()
                                m = STREAM_RE.search(req_url)
                                stream = m.group(1) if m else "unknown"
                                boxes = _box_scan(body)
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
                    # networkidle は SPA で到達しないことがありハングしうるため
                    # domcontentloaded + 固定待機に変更（堅牢性）
                    page.goto(canonical, wait_until="domcontentloaded", timeout=25000)
                except Exception:
                    pass  # タイムアウトは許容
                page.wait_for_timeout(8000)
                browser.close()
        except Exception as e:
            attempt.processing_seconds = time.monotonic() - t_start
            attempt.error_message = f"Playwright error: {type(e).__name__}: {e}"
            attempt.error_code = ErrorCodes.classify_error(
                attempt.error_message, self.METHOD
            ).code
            result.add_attempt(attempt)
            result.finalize()
            return result

        attempt.processing_seconds = time.monotonic() - t_start

        # ストリームごとにグルーピング
        streams = {}
        for s in segments:
            streams.setdefault(s["stream"], []).append(s)

        if not streams:
            attempt.error_message = (
                "CDN video segment を捕捉できませんでした。"
                "この投稿はログイン必須・削除済み・非公開の可能性があります。"
            )
            attempt.error_code = ErrorCodes.CDN_NOT_CAPTURED.code
            result.add_attempt(attempt)
            result.finalize()
            return result

        # トラックごとに init + fragments を結合
        tmp = DOWNLOADS_DIR / "_fmp4_remux"
        tmp.mkdir(parents=True, exist_ok=True)
        track_files = {}
        for sid, segs in streams.items():
            inits = [s for s in segs if s["is_init"]]
            frags = [s for s in segs if not s["is_init"]]
            if not inits or not frags:
                continue
            path = tmp / f"track_{sid}.mp4"
            with path.open("wb") as out:
                out.write(inits[0]["body"])
                for f in frags:
                    out.write(f["body"])
            track_files[sid] = path

        if len(track_files) < 2:
            attempt.error_message = (
                f"映像+音声の2トラックが揃いませんでした（streams={list(streams.keys())}）。"
                "fMP4再構築はストリームIDヒューリスティックに依存します。"
            )
            attempt.error_code = ErrorCodes.FRAGMENTED_MP4.code
            result.add_attempt(attempt)
            result.finalize()
            return result

        # サイズ大 = 映像、小 = 音声
        sorted_tracks = sorted(
            track_files.items(), key=lambda kv: kv[1].stat().st_size, reverse=True
        )
        video_path = sorted_tracks[0][1]
        audio_path = sorted_tracks[1][1]

        out_path = DOWNLOADS_DIR / f"{self.METHOD}_{shortcode}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            str(out_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            attempt.error_message = (
                f"ffmpeg mux に失敗（exit={r.returncode}）: "
                f"{(r.stderr or '')[-300:]}"
            )
            attempt.error_code = ErrorCodes.FRAGMENTED_MP4.code
            result.add_attempt(attempt)
            result.finalize()
            return result

        # ffprobe 検証
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type,codec_name,width,height",
            "-show_entries", "format=duration,size",
            "-of", "json", str(out_path),
        ]
        probe_r = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        if probe_r.returncode != 0:
            attempt.error_message = f"ffprobe 検証失敗: {(probe_r.stderr or '')[-300:]}"
            attempt.error_code = ErrorCodes.FRAGMENTED_MP4.code
            result.add_attempt(attempt)
            result.finalize()
            return result

        try:
            probe_json = json.loads(probe_r.stdout)
        except json.JSONDecodeError:
            probe_json = {}

        meta = self._parse_probe(probe_json, out_path)
        attempt.success = True
        attempt.downloaded_file_path = str(out_path)
        attempt.downloaded_file_size = out_path.stat().st_size
        attempt.extra = {
            "streams_detected": list(streams.keys()),
            "note": "VP9コーデック（Instagram配信）。fMP4再構築経由。",
        }

        result.add_attempt(attempt)
        result.metadata = meta
        result.estimated_cost_article = "$0.00（無料・無制限、Chromium+ffmpegリソース消費あり）"
        result.finalize()
        return result

    @staticmethod
    def _parse_probe(probe_json: dict, path) -> MediaMetadata:
        meta = MediaMetadata(file_size=path.stat().st_size)
        fmt = probe_json.get("format", {})
        try:
            meta.duration = float(fmt.get("duration", 0))
        except (TypeError, ValueError):
            meta.duration = 0.0
        for stream in probe_json.get("streams", []):
            if stream.get("codec_type") == "video":
                meta.width = stream.get("width", 0)
                meta.height = stream.get("height", 0)
                meta.codec = stream.get("codec_name", "")
            elif stream.get("codec_type") == "audio":
                meta.has_audio = True
        meta.ffprobe_raw = json.dumps(probe_json, indent=2)
        return meta
