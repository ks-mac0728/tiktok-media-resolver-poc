#!/usr/bin/env python3
"""
TikTok Media Resolver PoC
yt-dlp / Playwright / Apify の3方式で公開TikTok URLからMP4を取得し検証する。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = PROJECT_DIR / "downloads"
RESULTS_JSON = PROJECT_DIR / "results.json"
RESULTS_MD = PROJECT_DIR / "RESULTS.md"

# テスト用の公開TikTok URL（Playwrightで取得実証済みの動画）
SAMPLE_URLS = [
    "https://www.tiktok.com/@yuto1855/video/7669733182761192711",
    "https://www.tiktok.com/@minnakowaikarayada7/video/7671211573863517458",
    "https://www.tiktok.com/@zuttowakaku/video/7670096015315242247",
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class TestResult:
    provider: str  # "yt-dlp" | "apify-tiktok-video-scraper" | "apify-tiktok-scraper"
    url: str
    success: bool = False
    failure_reason: str = ""
    processing_seconds: float = 0.0
    downloaded_file_path: str = ""
    downloaded_file_size: int = 0
    duration: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""
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
# Helpers
# ---------------------------------------------------------------------------


def sanitize_filename(url: str, provider: str) -> str:
    """URLから安全なファイル名を生成"""
    # "https://www.tiktok.com/@user/video/12345" → "user_12345"
    m = re.search(r"@([^/]+)/video/(\d+)", url)
    if m:
        return f"{provider}_{m.group(1)}_{m.group(2)}.mp4"
    return f"{provider}_{hash(url) & 0xFFFFFFFF}.mp4"


def run_ffprobe(filepath: str) -> dict:
    """ffprobeで動画ファイルのメタデータを取得"""
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
        return {"error": str(e), "raw": getattr(result, "stdout", "")}


def parse_ffprobe(probe: dict) -> dict:
    """ffprobe結果から必要な情報を抽出"""
    info = {
        "duration": 0.0,
        "width": 0,
        "height": 0,
        "codec": "",
        "has_audio": False,
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


def detect_watermark(url: str, filepath: str, probe: dict) -> tuple:
    """
    TikTok watermarkの検出を試みる。
    ヒューリスティック:
    - yt-dlpがダウンロードしたファイルには通常watermarkあり
    - ファイル名やメタデータから判定
    Returns: (watermark_detected: bool, note: str)
    """
    # yt-dlpは通常watermark付きを取得
    # Apifyも通常watermark付き（ウォーターマーク除去は別途APIが必要）
    note = "TikTok動画には通常右下にTikTokロゴウォーターマークが埋め込まれている"

    # ファイル名に "watermark" が含まれているか
    if "watermark" in filepath.lower():
        return True, "ファイル名に watermark 含む"

    # ffprobeのフォーマットタグに手がかりがあるか
    fmt = probe.get("format", {})
    tags = fmt.get("tags", {})
    if "watermark" in str(tags).lower():
        return True, "メタデータタグに watermark 含む"

    return True, note  # デフォルト: ありと判定


def get_file_size(filepath: str) -> int:
    try:
        return os.path.getsize(filepath)
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Resolver: yt-dlp
# ---------------------------------------------------------------------------


class YtDlpResolver:
    """yt-dlpを使用してTikTok動画を取得"""

    PROVIDER = "yt-dlp"

    def resolve(self, url: str) -> TestResult:
        result = TestResult(provider=self.PROVIDER, url=url)
        result.tested_at = datetime.now(timezone.utc).isoformat()
        result.auth_required = False
        result.estimated_cost_article = "$0.00（無料・無制限）"

        filename = sanitize_filename(url, self.PROVIDER)
        output_path = DOWNLOADS_DIR / filename

        t_start = time.monotonic()

        try:
            # 出力テンプレート
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "--format", "mp4/best",
                "--output", str(output_path),
                "--print", "after_move:filepath",
                "--no-simulate",
                url,
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

                # rate-limit検出
                if "429" in stderr or "rate" in stderr.lower():
                    result.rate_limited = True
                    result.rate_limit_note = "HTTP 429 / rate-limit検出"

                return result

            # ダウンロード成功。実際の出力パスを確認
            actual_path = output_path
            if proc.stdout.strip():
                actual_path = Path(proc.stdout.strip())

            if not actual_path.exists():
                # output path with different extension
                candidates = list(DOWNLOADS_DIR.glob(f"{actual_path.stem}.*"))
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

            # watermark検出
            wm, wm_note = detect_watermark(url, str(actual_path), probe)
            result.watermark_detected = wm
            result.watermark_note = wm_note

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
# Resolver: Playwright
# ---------------------------------------------------------------------------


class PlaywrightResolver:
    """Playwright + ChromiumでTikTok WAFを突破し動画を取得

    TikTokのSlardar WAFはブラウザのJavaScript実行を必須とする。
    yt-dlp等のHTTP-onlyアプローチは全てブロックされる。
    Playwrightで実際のブラウザを起動し、CDNへの動画リクエストを
    route.fetch()で捕捉することでMP4を取得する。
    """

    PROVIDER = "playwright"

    def resolve(self, url: str) -> TestResult:
        result = TestResult(provider=self.PROVIDER, url=url)
        result.tested_at = datetime.now(timezone.utc).isoformat()
        result.auth_required = False
        result.estimated_cost_article = "$0.00（無料・無制限、ただしChromiumリソース消費あり）"

        filename = sanitize_filename(url, self.PROVIDER)
        output_path = DOWNLOADS_DIR / filename

        t_start = time.monotonic()

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            result.failure_reason = "playwright がインストールされていません（pip3 install playwright && playwright install chromium）"
            return result

        video_data = [b""]

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/131.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                def handle_route(route):
                    req_url = route.request.url
                    if "v16-webapp" in req_url and "/video/tos/" in req_url:
                        try:
                            resp = route.fetch()
                            body = resp.body()
                            if len(body) > len(video_data[0]):
                                video_data[0] = body
                            route.fulfill(response=resp)
                        except Exception:
                            route.continue_()
                    else:
                        route.continue_()

                page.route("**/*", handle_route)

                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(8000)

                browser.close()

        except Exception as e:
            result.processing_seconds = time.monotonic() - t_start
            result.failure_reason = f"Playwright error: {type(e).__name__}: {e}"
            err_str = str(e).lower()
            if "timeout" in err_str:
                result.failure_reason += "（ページロードタイムアウト）"
            return result

        result.processing_seconds = time.monotonic() - t_start

        if not video_data[0] or len(video_data[0]) < 50000:
            result.failure_reason = (
                f"CDN video URLが捕捉できませんでした "
                f"（captured={len(video_data[0])} bytes）。"
                f"動画が削除済み・非公開・地域制限の可能性があります。"
            )
            return result

        # ファイル保存
        output_path.write_bytes(video_data[0])
        result.downloaded_file_path = str(output_path)
        result.downloaded_file_size = len(video_data[0])
        result.success = True

        # ffprobe
        probe = run_ffprobe(str(output_path))
        parsed = parse_ffprobe(probe)
        result.ffprobe_raw = parsed["raw"]
        result.duration = parsed["duration"]
        result.width = parsed["width"]
        result.height = parsed["height"]
        result.codec = parsed["codec"]

        # watermark検出
        wm, wm_note = detect_watermark(url, str(output_path), probe)
        result.watermark_detected = wm
        result.watermark_note = wm_note

        return result


# ---------------------------------------------------------------------------
# Resolver: Apify
# ---------------------------------------------------------------------------


class ApifyResolver:
    """Apify ActorをAPI経由で呼び出しTikTok動画を取得

    対応Actor:
    - clockworks/tiktok-video-scraper (primary, $1.00/1k videos)
    - clockworks/tiktok-scraper (secondary, $1.70/1k results)
    """

    def __init__(self):
        # .env からトークンを読み込む
        try:
            from dotenv import load_dotenv
            load_dotenv(PROJECT_DIR / ".env")
        except ImportError:
            pass  # python-dotenvが未インストールの場合は環境変数を直接見る

        self.token = os.environ.get("APIFY_API_TOKEN", "")
        self.client = None
        self._init_client()

    def _init_client(self):
        if not self.token:
            return
        try:
            from apify_client import ApifyClient
            self.client = ApifyClient(self.token)
        except ImportError:
            pass

    @property
    def available(self) -> bool:
        return bool(self.token) and self.client is not None

    def resolve(self, url: str, actor: str = "tiktok-video-scraper") -> TestResult:
        provider = f"apify-{actor}"
        result = TestResult(provider=provider, url=url)
        result.tested_at = datetime.now(timezone.utc).isoformat()
        result.auth_required = True  # API token必須

        if actor == "tiktok-video-scraper":
            result.estimated_cost_article = "$0.01/video（$1.00/1k、Free枠月500本）"
        else:
            result.estimated_cost_article = "$0.017/video（$1.70/1k、Free枠月294本）"

        if not self.available:
            result.failure_reason = "APIFY_API_TOKEN が未設定、または apify-client が未インストール"
            result.extra["setup_required"] = [
                "pip3 install apify-client python-dotenv",
                ".env に APIFY_API_TOKEN=your_token を設定",
                "トークン取得: https://console.apify.com/account/integrations",
            ]
            return result

        t_start = time.monotonic()

        try:
            if actor == "tiktok-video-scraper":
                result = self._resolve_with_video_scraper(url, result, t_start)
            elif actor == "tiktok-scraper":
                result = self._resolve_with_tiktok_scraper(url, result, t_start)
            else:
                result.failure_reason = f"不明なActor: {actor}"

        except Exception as e:
            result.processing_seconds = time.monotonic() - t_start
            result.failure_reason = f"Apify API エラー: {type(e).__name__}: {e}"

            err_str = str(e).lower()
            if "403" in err_str or "unauthorized" in err_str:
                result.failure_reason += "（トークンが無効か権限不足）"
            elif "429" in err_str or "rate" in err_str:
                result.rate_limited = True
                result.rate_limit_note = "Apify API rate-limit"

        return result

    def _resolve_with_video_scraper(self, url: str, result: TestResult, t_start: float) -> TestResult:
        """clockworks/tiktok-video-scraper を使用"""
        run_input = {
            "postURLs": [url],
            "shouldDownloadCovers": False,
            "shouldDownloadSlideshowImages": False,
            "shouldDownloadSubtitles": False,
            "shouldDownloadVideos": True,
        }

        run = self.client.actor("clockworks/tiktok-video-scraper").call(run_input=run_input)
        result.processing_seconds = time.monotonic() - t_start

        # データセットから結果を取得
        items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())

        if not items:
            result.failure_reason = "Apify Actorが結果を返しませんでした（動画が削除済み/非公開の可能性）"
            return result

        first = items[0]

        # エラーチェック
        if "errorCode" in first:
            result.failure_reason = f"Apify error: {first.get('error', '')} (code={first['errorCode']})"
            return result

        # メタデータを記録
        result.extra["apify_metadata"] = {
            k: first.get(k)
            for k in ["webVideoUrl", "text", "createTimeISO", "authorMeta.name",
                       "diggCount", "playCount", "videoMeta.duration"]
            if k in first
        }

        # 動画をKey-Value Storeからダウンロード
        result = self._download_from_kvs(run, url, result)

        return result

    def _resolve_with_tiktok_scraper(self, url: str, result: TestResult, t_start: float) -> TestResult:
        """clockworks/tiktok-scraper を使用"""
        run_input = {
            "videoUrls": [url],
            "shouldDownloadVideos": True,
            "shouldDownloadCovers": False,
            "shouldDownloadSubtitles": False,
        }

        run = self.client.actor("clockworks/tiktok-scraper").call(run_input=run_input)
        result.processing_seconds = time.monotonic() - t_start

        items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())

        if not items:
            result.failure_reason = "Apify Actorが結果を返しませんでした"
            return result

        first = items[0]
        if "errorCode" in first:
            result.failure_reason = f"Apify error: {first.get('error', '')} (code={first['errorCode']})"
            return result

        result.extra["apify_metadata"] = {
            k: first.get(k)
            for k in ["webVideoUrl", "text", "createTimeISO", "authorMeta.name",
                       "diggCount", "playCount", "videoMeta.duration"]
            if k in first
        }

        result = self._download_from_kvs(run, url, result)
        return result

    def _download_from_kvs(self, run: dict, url: str, result: TestResult) -> TestResult:
        """Apify Key-Value Storeから動画ファイルをダウンロード"""
        try:
            kvs = self.client.key_value_store(run["defaultKeyValueStoreId"])

            # KVSのキー一覧を取得
            keys = list(kvs.list_keys())
            result.extra["kvs_keys"] = [k.get("key", "") for k in keys]

            # 動画ファイルらしきキーを探す
            video_keys = [k for k in result.extra["kvs_keys"] if k.endswith(".mp4")]

            if not video_keys:
                result.failure_reason = (
                    f"KVSにMP4ファイルが見つかりません。keys={result.extra['kvs_keys']}"
                    "（shouldDownloadVideos=True でも動画が取得できない場合があります）"
                )
                return result

            # 最初の動画をダウンロード
            video_key = video_keys[0]
            filename = sanitize_filename(url, result.provider)
            output_path = DOWNLOADS_DIR / filename

            # KVSからファイルを取得して保存
            record = kvs.get_record(video_key)
            value = record.get("value", b"")
            if isinstance(value, str):
                value = value.encode("utf-8")

            output_path.write_bytes(value)

            result.downloaded_file_path = str(output_path)
            result.downloaded_file_size = get_file_size(str(output_path))
            result.success = True

            # ffprobe
            probe = run_ffprobe(str(output_path))
            parsed = parse_ffprobe(probe)
            result.ffprobe_raw = parsed["raw"]
            result.duration = parsed["duration"]
            result.width = parsed["width"]
            result.height = parsed["height"]
            result.codec = parsed["codec"]

            wm, wm_note = detect_watermark(url, str(output_path), probe)
            result.watermark_detected = wm
            result.watermark_note = wm_note

        except Exception as e:
            result.failure_reason = f"KVS download error: {type(e).__name__}: {e}"

        return result


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_tests(urls: list[str], providers: list[str]) -> list[TestResult]:
    """全URL × 全Provider のテストを実行"""
    all_results: list[TestResult] = []

    for url in urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print(f"{'='*60}")

        for provider in providers:
            print(f"\n  [{provider}] ", end="", flush=True)

            if provider == "yt-dlp":
                resolver = YtDlpResolver()
                result = resolver.resolve(url)
            elif provider == "playwright":
                resolver = PlaywrightResolver()
                result = resolver.resolve(url)
            elif provider.startswith("apify-"):
                actor = provider.replace("apify-", "")
                resolver = ApifyResolver()
                if not resolver.available:
                    print("SKIPPED（APIFY_API_TOKEN未設定）")
                    result = TestResult(provider=provider, url=url)
                    result.failure_reason = "APIFY_API_TOKEN未設定のためスキップ"
                    result.tested_at = datetime.now(timezone.utc).isoformat()
                    result.extra["setup_required"] = [
                        "pip3 install apify-client python-dotenv",
                        ".env に APIFY_API_TOKEN=your_token を設定",
                    ]
                else:
                    result = resolver.resolve(url, actor=actor)
            else:
                print(f"SKIPPED（不明なprovider: {provider}）")
                continue

            if result.success:
                print(f"OK ({result.downloaded_file_size:,} bytes, "
                      f"{result.width}x{result.height}, "
                      f"{result.processing_seconds:.1f}s)")
            else:
                print(f"FAIL: {result.failure_reason[:100]}")

            all_results.append(result)

    return all_results


def save_results(results: list[TestResult]):
    """results.json に保存"""
    data = [asdict(r) for r in results]
    RESULTS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to {RESULTS_JSON}")


def generate_results_md(results: list[TestResult]):
    """RESULTS.md を生成"""
    lines = [
        "# TikTok Media Resolver PoC — Results",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "---",
        "",
    ]

    # Provider別にグルーピング
    by_provider: dict[str, list[TestResult]] = {}
    for r in results:
        by_provider.setdefault(r.provider, []).append(r)

    for provider, res_list in by_provider.items():
        success_count = sum(1 for r in res_list if r.success)
        total = len(res_list)
        lines.append(f"## {provider} （{success_count}/{total} 成功）")
        lines.append("")

        for r in res_list:
            lines.append(f"### {r.url}")
            lines.append("")
            lines.append(f"| 項目 | 値 |")
            lines.append(f"|------|-----|")
            lines.append(f"| success | {'✅' if r.success else '❌'} |")
            lines.append(f"| failure_reason | {r.failure_reason or 'N/A'} |")
            lines.append(f"| processing_seconds | {r.processing_seconds:.1f}s |")
            lines.append(f"| file_size | {r.downloaded_file_size:,} bytes |")
            lines.append(f"| duration | {r.duration:.1f}s |")
            lines.append(f"| resolution | {r.width}x{r.height} |")
            lines.append(f"| codec | {r.codec or 'N/A'} |")
            lines.append(f"| watermark | {'あり' if r.watermark_detected else 'なし'} |")
            lines.append(f"| auth_required | {'はい' if r.auth_required else 'いいえ'} |")
            lines.append(f"| rate_limited | {'はい' if r.rate_limited else 'いいえ'} |")
            lines.append(f"| estimated_cost | {r.estimated_cost_article or 'N/A'} |")
            lines.append("")

    # 最終評価
    lines.append("---")
    lines.append("")
    lines.append("## 最終評価")
    lines.append("")

    for provider, res_list in by_provider.items():
        success_count = sum(1 for r in res_list if r.success)
        total = len(res_list)

        if total == 0:
            lines.append(f"### {provider}: REJECT（テスト未実行）")
        elif success_count == total:
            lines.append(f"### {provider}: RECOMMEND")
        elif success_count > 0:
            lines.append(f"### {provider}: CONDITIONAL（{success_count}/{total}成功、条件付き）")
        else:
            lines.append(f"### {provider}: REJECT（{success_count}/{total}成功）")

        lines.append("")

    # Apify未実測の注記
    apify_results = [r for r in results if r.provider.startswith("apify-")]
    if apify_results and all(not r.success for r in apify_results):
        lines.append("> ⚠️ **Apify未実測**：APIFY_API_TOKEN未設定のため未検証。最終評価はyt-dlp実測値のみに基づく。")
        lines.append("> Apifyの評価をRECOMMENDにするには、tokenを設定して実測が必要。")
        lines.append("")

    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Results markdown saved to {RESULTS_MD}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="TikTok Media Resolver PoC - yt-dlp & Apify comparison"
    )
    parser.add_argument(
        "--provider",
        choices=["ytdlp", "playwright", "apify", "all"],
        default="playwright",
        help="検証対象のProvider（default: playwright）",
    )
    parser.add_argument(
        "--urls",
        nargs="*",
        default=[],
        help="検証するTikTok URL（スペース区切りで複数指定可）",
    )
    parser.add_argument(
        "--use-sample-urls",
        action="store_true",
        help="組み込みのサンプルURLを使用",
    )
    parser.add_argument(
        "--skip-ffprobe",
        action="store_true",
        help="ffprobe検証をスキップ（高速テスト用）",
    )

    args = parser.parse_args()

    # URLの準備
    urls = args.urls
    if args.use_sample_urls or not urls:
        urls = SAMPLE_URLS
        print(f"Using {len(urls)} sample URLs")

    # Providerの準備
    if args.provider == "ytdlp":
        providers = ["yt-dlp"]
    elif args.provider == "playwright":
        providers = ["playwright"]
    elif args.provider == "apify":
        providers = ["apify-tiktok-video-scraper", "apify-tiktok-scraper"]
    else:  # all
        providers = ["yt-dlp", "playwright", "apify-tiktok-video-scraper", "apify-tiktok-scraper"]

    # downloads/ ディレクトリ作成
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Providers: {providers}")
    print(f"URLs: {len(urls)}")
    print(f"Output dir: {DOWNLOADS_DIR}")
    print()

    # 実行
    results = run_tests(urls, providers)
    save_results(results)
    generate_results_md(results)

    # サマリー
    success_count = sum(1 for r in results if r.success)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {success_count}/{len(results)} succeeded")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
