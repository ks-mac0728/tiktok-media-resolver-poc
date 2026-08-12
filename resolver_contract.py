"""
Common Resolver Contract for SNS Media Resolver PoC.

全 Platform（TikTok / Instagram）・全方式（yt-dlp / Playwright / External API）で
統一された MediaResolveResult を返す。

Usage:
    result = resolve_media(url)  # -> MediaResolveResult
    print(result.summary())
"""

import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from error_codes import ErrorCode, ErrorCodes


# ---------------------------------------------------------------------------
# ResolveAttempt — 単一方式の試行結果
# ---------------------------------------------------------------------------

@dataclass
class ResolveAttempt:
    method: str                 # "tiktok-playwright" | "instagram-ytdlp-anonymous" など
    success: bool = False
    error_code: str = ""        # ErrorCode.code 文字列
    error_message: str = ""     # 生エラーメッセージ
    processing_seconds: float = 0.0
    downloaded_file_path: str = ""
    downloaded_file_size: int = 0
    auth_required: bool = False
    rate_limited: bool = False
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# MediaMetadata — ffprobe 抽出情報
# ---------------------------------------------------------------------------

@dataclass
class MediaMetadata:
    duration: float = 0.0
    width: int = 0
    height: int = 0
    codec: str = ""
    has_audio: bool = False
    file_size: int = 0
    ffprobe_raw: str = ""


# ---------------------------------------------------------------------------
# MediaResolveResult — 最終結果（全attemptを含む）
# ---------------------------------------------------------------------------

@dataclass
class MediaResolveResult:
    url: str
    canonical_url: str = ""
    platform: str = ""           # "tiktok" | "instagram"
    shortcode: str = ""          # Instagram shortcode / TikTok video ID

    # 最終結果
    success: bool = False
    final_method: str = ""       # 成功した方式名
    downloaded_file_path: str = ""
    metadata: Optional[MediaMetadata] = None

    # Attempt history
    attempts: list = field(default_factory=list)

    # 評価
    error_code: str = ""          # 最終エラーコード（全attempt失敗時）
    error_message: str = ""       # 人間向け最終メッセージ
    tested_at: str = ""
    total_seconds: float = 0.0

    # Cost
    estimated_cost_article: str = ""

    def add_attempt(self, attempt: ResolveAttempt):
        self.attempts.append(attempt)

    def finalize(self):
        """全attempt終了後に呼び、最終状態を計算"""
        self.total_seconds = sum(a.processing_seconds for a in self.attempts)
        self.tested_at = datetime.now(timezone.utc).isoformat()

        for attempt in self.attempts:
            if attempt.success:
                self.success = True
                self.final_method = attempt.method
                self.downloaded_file_path = attempt.downloaded_file_path
                if self.metadata is None:
                    self.metadata = MediaMetadata(
                        file_size=attempt.downloaded_file_size,
                    )
                self.error_code = ""
                self.error_message = ""
                return

        # 全失敗
        self.success = False
        self.final_method = ""

        # 最初のFATALエラーを優先、なければ最後のエラー
        for attempt in self.attempts:
            ec = ErrorCodes.by_code(attempt.error_code)
            if ec.severity.value == "fatal":
                self.error_code = attempt.error_code
                self.error_message = attempt.error_message
                return

        if self.attempts:
            last = self.attempts[-1]
            self.error_code = last.error_code
            self.error_message = last.error_message

    def summary(self) -> str:
        """人間向け1行サマリー"""
        if self.success:
            meta = self.metadata
            if meta:
                return (
                    f"✅ {self.final_method} | "
                    f"{meta.file_size:,} bytes | "
                    f"{meta.width}x{meta.height} | "
                    f"{meta.codec} | "
                    f"{meta.duration:.1f}s | "
                    f"{self.total_seconds:.1f}s"
                )
            return f"✅ {self.final_method} | {self.downloaded_file_path}"

        codes = " → ".join(
            a.error_code for a in self.attempts if a.error_code
        ) or "UNKNOWN"
        return f"❌ [{codes}] {self.error_message[:100]}"

    def attempt_summary(self) -> str:
        """全attemptの経過を文字列で返す"""
        lines = []
        for i, a in enumerate(self.attempts):
            status = "✅" if a.success else "❌"
            lines.append(
                f"  {i+1}. {status} {a.method} "
                f"({a.processing_seconds:.1f}s) "
                f"[{a.error_code or 'OK'}]"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# ResolverInterface — 全Resolverが実装すべき基底
# ---------------------------------------------------------------------------

class ResolverInterface:
    """全Media Resolverの共通インターフェース"""

    METHOD: str = ""  # 方式識別子（"tiktok-playwright" など）

    def resolve(self, url: str) -> ResolveAttempt:
        """単一URLを解決し ResolveAttempt を返す"""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

import re

RE_TIKTOK = re.compile(r"tiktok\.com/@[\w.-]+/video/(\d+)")
RE_INSTAGRAM_REEL = re.compile(r"instagram\.com/reel/([A-Za-z0-9_-]+)")
RE_INSTAGRAM_POST = re.compile(r"instagram\.com/p/([A-Za-z0-9_-]+)")


def detect_platform(url: str) -> str:
    """URLからプラットフォームを判定"""
    if RE_TIKTOK.search(url):
        return "tiktok"
    if RE_INSTAGRAM_REEL.search(url) or RE_INSTAGRAM_POST.search(url):
        return "instagram"
    return "unknown"


def extract_shortcode(url: str) -> str:
    """URLからshortcode / video IDを抽出"""
    m = RE_TIKTOK.search(url)
    if m:
        return m.group(1)
    m = RE_INSTAGRAM_REEL.search(url) or RE_INSTAGRAM_POST.search(url)
    if m:
        return m.group(1)
    return ""


def normalize_url(url: str) -> str:
    """URLを正規化（クエリパラメータ除去など）"""
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    clean = urlunparse(parsed._replace(query="", fragment=""))

    # Instagram: /p/ → /reel/
    m = RE_INSTAGRAM_POST.search(clean)
    if m:
        return f"https://www.instagram.com/reel/{m.group(1)}/"
    return clean.rstrip("/") + "/"
