"""
TikTok Resolver Adapter — 既存 resolver_test.PlaywrightResolver を
Common Contract (resolver_contract.MediaResolveResult) に適合させる。

既存の PlaywrightResolver.resolve() 内部ロジックには一切触れず、
戻り値を MediaResolveResult に変換する薄いラッパー。
"""

import time
from pathlib import Path

from resolver_contract import (
    MediaResolveResult,
    ResolveAttempt,
    MediaMetadata,
    detect_platform,
    extract_shortcode,
    normalize_url,
)
from error_codes import ErrorCodes
from resolver_test import PlaywrightResolver as _PlaywrightResolver, run_ffprobe, parse_ffprobe


class TikTokResolver:
    """TikTok専用Resolver。内部は既存 PlaywrightResolver + リトライ。"""

    METHOD = "tiktok-playwright"

    def resolve(self, url: str) -> MediaResolveResult:
        result = MediaResolveResult(
            url=url,
            canonical_url=normalize_url(url),
            platform=detect_platform(url),
            shortcode=extract_shortcode(url),
        )

        # 既存 PlaywrightResolver を呼び出し
        resolver = _PlaywrightResolver()
        legacy_result = resolver.resolve(url)

        # ResolveAttempt に変換
        attempt = ResolveAttempt(
            method=self.METHOD,
            success=legacy_result.success,
            error_code="",
            error_message=legacy_result.failure_reason,
            processing_seconds=legacy_result.processing_seconds,
            downloaded_file_path=legacy_result.downloaded_file_path,
            downloaded_file_size=legacy_result.downloaded_file_size,
            auth_required=legacy_result.auth_required,
            rate_limited=legacy_result.rate_limited,
            extra={
                "watermark_detected": legacy_result.watermark_detected,
                "watermark_note": legacy_result.watermark_note,
                "attempts": legacy_result.extra.get("attempts", 1),
            },
        )

        # エラーコード分類
        if not attempt.success:
            attempt.error_code = ErrorCodes.classify_error(
                attempt.error_message, "tiktok-playwright"
            ).code
        else:
            attempt.error_code = ""

        result.add_attempt(attempt)

        # ffprobe metadata
        if legacy_result.success and legacy_result.downloaded_file_path:
            probe = run_ffprobe(legacy_result.downloaded_file_path)
            parsed = parse_ffprobe(probe)
            result.metadata = MediaMetadata(
                duration=parsed["duration"],
                width=parsed["width"],
                height=parsed["height"],
                codec=parsed["codec"],
                has_audio=parsed["has_audio"],
                file_size=legacy_result.downloaded_file_size,
                ffprobe_raw=parsed["raw"],
            )

        result.estimated_cost_article = legacy_result.estimated_cost_article
        result.finalize()
        return result
