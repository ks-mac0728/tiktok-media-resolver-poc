#!/usr/bin/env python3
"""
Instagram Media Resolver PoC

Resolver:
  PRIMARY:  yt-dlp（完全MP4取得、安定）
  FALLBACK: Playwright network intercept（fMP4断片取得、診断用）

TikTok Resolver と同じ TestResult contract を使用して相互運用可能に。

=== 実証結果 ===
yt-dlp:
  DLgMlwmhpah → 720x1280 h264+aac, 10.7s, 4.3MB ✅

Playwright network intercept:
  CDNから video/mp4 断片を捕捉するが、fragmented MP4 (moof/mfhd) 形式のため
  単独では再生不可。init segment + 全断片の再構築が必要。
  TikTok方式（完全MP4が1リクエストで返る）とは異なる。
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = PROJECT_DIR / "downloads"

# Instagram URL patterns
RE_REEL_URL = re.compile(r"instagram\.com/reel/([A-Za-z0-9_-]+)")
RE_POST_URL = re.compile(r"instagram\.com/p/([A-Za-z0-9_-]+)")

# Instagram CDN patterns for Playwright fallback diagnostics
INSTAGRAM_CDN_PATTERNS = [
    "fbcdn.net",
    "scontent.",
    "cdninstagram.com",
]


# ---------------------------------------------------------------------------
# Data model (TestResult - same contract as resolver_test.py)
# ---------------------------------------------------------------------------


@dataclass
class TestResult:
    provider: str  # "instagram-ytdlp" | "instagram-playwright"
    url: str
    canonical_url: str = ""
    shortcode: str = ""
    url_type: str = ""  # "reel" or "post"
    success: bool = False
    failure_reason: str = ""
    processing_seconds: float = 0.0
    downloaded_file_path: str = ""
    downloaded_file_size: int = 0
    duration: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""
    has_audio: bool = False
    watermark_detected: bool = False
    watermark_note: str = ""
    auth_required: bool = False
    rate_limited: bool = False
    rate_limit_note: str = ""
    estimated_cost_article: str = ""
    ffprobe_raw: str = ""
    extra: dict = field(default_factory=dict)
    tested_at: str = ""


# ---------------------------------------------------------------------------
# URL Helpers
# ---------------------------------------------------------------------------


def normalize_instagram_url(url: str) -> tuple:
    """
    Instagram URL を canonical 形式に正規化。
    Returns: (canonical_url: str, shortcode: str, url_type: str)
    url_type: "reel" | "post" | "unknown"
    """
    parsed = urlparse(url)
    clean_url = urlunparse(parsed._replace(query="", fragment=""))

    m = RE_REEL_URL.search(clean_url)
    if m:
        shortcode = m.group(1)
        canonical = f"https://www.instagram.com/reel/{shortcode}/"
        return canonical, shortcode, "reel"

    m = RE_POST_URL.search(clean_url)
    if m:
        shortcode = m.group(1)
        canonical = f"https://www.instagram.com/p/{shortcode}/"
        return canonical, shortcode, "post"

    return clean_url, "", "unknown"


# ---------------------------------------------------------------------------
# ffprobe helpers
# ---------------------------------------------------------------------------


def run_ffprobe(filepath: str) -> dict:
    """ffprobe で動画ファイルのメタデータを取得"""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"error": str(e)}


def parse_ffprobe(probe: dict) -> dict:
    """ffprobe 結果から必要な情報を抽出"""
    info = {
        "duration": 0.0, "width": 0, "height": 0,
        "codec": "", "has_audio": False,
        "raw": json.dumps(probe, indent=2),
    }
    if "error" in probe:
        return info

    fmt = probe.get("format", {})
    info["duration"] = float(fmt.get("duration", 0))

    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = stream.get("width", 0)
            info["height"] = stream.get("height", 0)
            info["codec"] = stream.get("codec_name", "")
        elif stream.get("codec_type") == "audio":
            info["has_audio"] = True

    return info


def get_file_size(filepath: str) -> int:
    try:
        return os.path.getsize(filepath)
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# PRIMARY Resolver: yt-dlp
# ---------------------------------------------------------------------------


class InstagramYtDlpResolver:
    """yt-dlp を使用して Instagram Reel/Post から MP4 を取得

    TikTok と異なり Instagram では yt-dlp が安定して動作する。
    Instagram の WAF は TikTok ほど厳しくなく、yt-dlp の HTTP リクエストで
    完全な MP4 を取得可能。
    """

    PROVIDER = "instagram-ytdlp"

    def resolve(self, url: str) -> TestResult:
        result = TestResult(provider=self.PROVIDER, url=url)
        result.tested_at = datetime.now(timezone.utc).isoformat()
        result.estimated_cost_article = "$0.00（無料・無制限）"

        canonical_url, shortcode, url_type = normalize_instagram_url(url)
        result.canonical_url = canonical_url
        result.shortcode = shortcode
        result.url_type = url_type

        if not shortcode:
            result.failure_reason = f"URLからshortcodeを抽出できませんでした: {url}"
            return result

        output_path = DOWNLOADS_DIR / f"{self.PROVIDER}_{shortcode}.mp4"
        t_start = time.monotonic()

        try:
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "--format", "mp4/best",
                "--output", str(output_path),
                "--print", "after_move:filepath",
                "--no-simulate",
                canonical_url,
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(PROJECT_DIR),
            )

            result.processing_seconds = time.monotonic() - t_start

            if proc.returncode != 0:
                stderr = proc.stderr.strip()
                result.failure_reason = f"yt-dlp exit={proc.returncode}: {stderr[:500]}"

                if "429" in stderr or "rate" in stderr.lower():
                    result.rate_limited = True
                    result.rate_limit_note = "HTTP 429 / rate-limit検出"
                if "login" in stderr.lower():
                    result.auth_required = True
                    result.failure_reason += "（ログイン必須の可能性）"
                if "private" in stderr.lower():
                    result.failure_reason += "（非公開アカウントの可能性）"

                return result

            # 実際の出力パスを確認
            actual_path = output_path
            if proc.stdout.strip():
                actual_path = Path(proc.stdout.strip())

            if not actual_path.exists():
                candidates = list(DOWNLOADS_DIR.glob(f"{output_path.stem}.*"))
                if candidates:
                    actual_path = candidates[0]
                else:
                    result.failure_reason = f"出力ファイルが見つかりません: {actual_path}"
                    return result

            result.downloaded_file_path = str(actual_path)
            result.downloaded_file_size = get_file_size(str(actual_path))
            result.success = True

            # ffprobe
            probe = run_ffprobe(str(actual_path))
            parsed = parse_ffprobe(probe)
            result.ffprobe_raw = parsed["raw"]
            result.duration = parsed["duration"]
            result.width = parsed["width"]
            result.height = parsed["height"]
            result.codec = parsed["codec"]
            result.has_audio = parsed["has_audio"]

        except subprocess.TimeoutExpired:
            result.processing_seconds = time.monotonic() - t_start
            result.failure_reason = "yt-dlp タイムアウト（120秒）"
        except FileNotFoundError:
            result.failure_reason = "yt-dlp がインストールされていません"
        except Exception as e:
            result.processing_seconds = time.monotonic() - t_start
            result.failure_reason = f"予期せぬエラー: {type(e).__name__}: {e}"

        return result


# ---------------------------------------------------------------------------
# FALLBACK / Diagnostic Resolver: Playwright
# ---------------------------------------------------------------------------


class InstagramPlaywrightResolver:
    """Playwright + Chromium で Instagram 動画取得を試行（診断用）

    PRIMARY は yt-dlp。こちらは以下を目的とする:
    1. yt-dlp 失敗時の原因診断（login wall, challenge, redirect）
    2. ネットワーク断片の捕捉（fMP4 断片）
    3. HTML メタデータ抽出

    注意: Instagram は fragmented MP4 (fMP4) を CDN 配信するため、
    Playwright で捕捉できるのは moof/mfhd 断片であり、
    単独では再生不可。完全な MP4 には init segment の結合が必要。
    """

    PROVIDER = "instagram-playwright"

    def resolve(self, url: str) -> TestResult:
        result = TestResult(provider=self.PROVIDER, url=url)
        result.tested_at = datetime.now(timezone.utc).isoformat()
        result.estimated_cost_article = "$0.00（無料・無制限、Chromiumリソース消費あり）"

        canonical_url, shortcode, url_type = normalize_instagram_url(url)
        result.canonical_url = canonical_url
        result.shortcode = shortcode
        result.url_type = url_type

        if not shortcode:
            result.failure_reason = f"URLからshortcodeを抽出できませんでした: {url}"
            return result

        t_start = time.monotonic()

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            result.failure_reason = "playwright がインストールされていません"
            return result

        # 収集データ
        video_segments = []  # (url, size, content_type, body) のリスト
        http_status = [0]
        redirect_url = [""]
        page_title = [""]
        html_meta = {}
        login_wall = [False]
        challenge = [False]
        largest_body = b""
        largest_url = ""

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

                # メイン response 記録
                def handle_response(response):
                    if shortcode in response.url:
                        http_status[0] = response.status
                        if response.status in (301, 302):
                            redirect_url[0] = (
                                response.headers.get("location", "")
                            )

                page.on("response", handle_response)

                # ネットワークルート: CDN video リクエストを捕捉
                def handle_route(route):
                    req_url = route.request.url
                    resp_headers = route.request.headers
                    ct = resp_headers.get("content-type", "")

                    is_ig_cdn = any(p in req_url for p in INSTAGRAM_CDN_PATTERNS)
                    is_video_req = ".mp4" in req_url or "video" in ct.lower()

                    if is_ig_cdn or is_video_req:
                        try:
                            resp = route.fetch()
                            resp_ct = resp.headers.get("content-type", "").lower()
                            resp_cl = resp.headers.get("content-length", "")
                            body = resp.body()

                            if "video" in resp_ct or ".mp4" in req_url:
                                video_segments.append({
                                    "url": req_url[:250],
                                    "content_type": resp_ct,
                                    "content_length": resp_cl,
                                    "status": resp.status,
                                    "body_size": len(body),
                                    "timestamp": round(time.monotonic() - t_start, 3),
                                })
                                if len(body) > len(largest_body):
                                    largest_body = body
                                    largest_url = req_url

                            route.fulfill(response=resp)
                            return
                        except Exception:
                            route.continue_()
                    else:
                        route.continue_()

                page.route("**/*", handle_route)

                # ページアクセス
                resp = page.goto(canonical_url, wait_until="networkidle", timeout=30000)
                if resp:
                    http_status[0] = resp.status

                page.wait_for_timeout(8000)
                page_title[0] = page.title()

                # ページ内容から login wall / challenge 検出
                pc = page.content().lower()
                if '"native_client_side_navigation":false' not in pc:
                    if "log in" in pc and "instagram" in pc:
                        # 単なるリンクではなく、ログインフォームがあるか
                        if page.locator('input[name="username"]').count() > 0:
                            login_wall[0] = True
                if "challenge" in pc or "suspicious" in pc:
                    challenge[0] = True

                # HTML metadata
                for meta_name in ["og:video", "og:video:url", "og:video:secure_url",
                                  "og:video:type", "og:video:width", "og:video:height"]:
                    try:
                        val = page.locator(
                            f'meta[property="{meta_name}"]'
                        ).get_attribute("content", timeout=1000)
                        if val:
                            html_meta[meta_name] = val
                    except Exception:
                        pass

                # video element
                for attr in ["src", "poster"]:
                    try:
                        val = page.locator(f"video[{attr}]").get_attribute(
                            attr, timeout=1000
                        )
                        if val:
                            html_meta[f"video_{attr}"] = val[:300]
                    except Exception:
                        pass

                # script video_url
                try:
                    scripts = page.locator("script")
                    for i in range(min(scripts.count(), 30)):
                        try:
                            text = scripts.nth(i).inner_text(timeout=500)
                            m = re.search(r'"video_url"\s*:\s*"([^"]+)"', text)
                            if m and len(m.group(1)) > 20:
                                html_meta["script_video_url"] = m.group(1)[:300]
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

                browser.close()

        except Exception as e:
            result.processing_seconds = time.monotonic() - t_start
            result.failure_reason = f"Playwright error: {type(e).__name__}: {e}"
            return result

        result.processing_seconds = time.monotonic() - t_start
        result.extra["http_status"] = http_status[0]
        result.extra["page_title"] = page_title[0][:200]
        result.extra["login_wall_detected"] = login_wall[0]
        result.extra["challenge_detected"] = challenge[0]
        result.extra["video_segments_count"] = len(video_segments)
        result.extra["video_segments"] = [
            {"body_size": s["body_size"], "content_type": s["content_type"]}
            for s in video_segments
        ]
        result.extra["html_meta"] = html_meta

        if login_wall[0]:
            result.auth_required = True
        if challenge[0]:
            result.extra["note"] = "Challenge検出。Cookie認証が必要な可能性あり。"

        # 最大断片を保存（診断用、再生不可）
        if largest_body and len(largest_body) >= 10000:
            pw_path = DOWNLOADS_DIR / f"{self.PROVIDER}_{shortcode}.mp4"
            pw_path.write_bytes(largest_body)
            result.downloaded_file_path = str(pw_path)
            result.downloaded_file_size = len(largest_body)

            # ヘッダーチェック
            header = largest_body[:4]
            if header == b"\x00\x00\x00":
                # fMP4 断片（moof または ftyp のサイズフィールド）
                ftyp = b"ftyp" in largest_body[:100]
                moof = b"moof" in largest_body[:100]
                if moof and not ftyp:
                    result.failure_reason = (
                        "fragmented MP4 (moof) 断片のみ取得。"
                        "完全なMP4にするにはinit segment (ftyp+moov) との結合が必要。"
                        "yt-dlpによる完全MP4取得を推奨。"
                    )
                else:
                    result.failure_reason = (
                        f"MP4断片を取得（{len(largest_body):,} bytes）するも"
                        "ffprobeで解析不可。yt-dlpを推奨。"
                    )
            else:
                result.failure_reason = (
                    f"不明なフォーマット（header={header.hex()}）。"
                    "yt-dlpを推奨。"
                )
        else:
            reasons = []
            if login_wall[0]:
                reasons.append("Login wall")
            if challenge[0]:
                reasons.append("Challenge")
            if http_status[0] >= 400:
                reasons.append(f"HTTP {http_status[0]}")
            if not video_segments:
                reasons.append("CDN video segment 0件")
            result.failure_reason = " | ".join(reasons) or "動画を検出できず"

        return result


# ---------------------------------------------------------------------------
# Unified Resolver (yt-dlp primary, Playwright fallback diagnostic)
# ---------------------------------------------------------------------------


class InstagramResolver:
    """統合 Instagram Resolver: yt-dlp を PRIMARY として使用"""

    def resolve(self, url: str, method: str = "ytdlp") -> TestResult:
        if method == "playwright":
            resolver = InstagramPlaywrightResolver()
        else:
            resolver = InstagramYtDlpResolver()
        return resolver.resolve(url)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Instagram Media Resolver PoC"
    )
    parser.add_argument("url", nargs="?", help="Instagram URL")
    parser.add_argument(
        "--shortcode", default="DLgMlwmhpah",
        help="Shortcode (default: DLgMlwmhpah)"
    )
    parser.add_argument(
        "--both", action="store_true",
        help="Test both /reel/ and /p/ URLs"
    )
    parser.add_argument(
        "--method", choices=["ytdlp", "playwright", "both"],
        default="ytdlp",
        help="Resolver method (default: ytdlp)"
    )
    args = parser.parse_args()

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    if args.url:
        urls = [args.url]
    elif args.both:
        urls = [
            f"https://www.instagram.com/reel/{args.shortcode}/",
            f"https://www.instagram.com/p/{args.shortcode}/",
        ]
    else:
        urls = [f"https://www.instagram.com/reel/{args.shortcode}/"]

    all_results = []

    for url in urls:
        canonical, shortcode, url_type = normalize_instagram_url(url)
        print(f"\n{'='*60}")
        print(f"URL:      {url}")
        print(f"Canonical: {canonical}")
        print(f"Shortcode: {shortcode}  Type: {url_type}")
        print(f"{'='*60}")

        methods = (
            ["ytdlp", "playwright"] if args.method == "both" else [args.method]
        )

        for method in methods:
            resolver = InstagramResolver()
            print(f"\n  [{method}] ", end="", flush=True)
            result = resolver.resolve(url, method=method)

            if result.success:
                print(f"✅ SUCCESS ({result.downloaded_file_size:,} bytes, "
                      f"{result.width}x{result.height}, "
                      f"{result.duration:.1f}s, "
                      f"{result.processing_seconds:.1f}s)")
            else:
                print(f"❌ FAIL: {result.failure_reason[:150]}")

            all_results.append(result)

    # Save results
    results_json = PROJECT_DIR / "instagram_results.json"
    results_json.write_text(
        json.dumps(
            [asdict(r) for r in all_results],
            indent=2, ensure_ascii=False, default=str
        ),
        encoding="utf-8",
    )
    print(f"\nResults → {results_json}")


if __name__ == "__main__":
    main()
