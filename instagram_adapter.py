"""
Instagram Resolver Adapter — 既存 instagram_resolver.py の各 Resolver を
Common Contract (resolver_contract.MediaResolveResult) に適合させる。

既存の InstagramYtDlpResolver / InstagramPlaywrightResolver 内部ロジックには
触れず、戻り値を MediaResolveResult に変換する薄いラッパー。

Method identifier 規約:
  instagram-ytdlp-anonymous   — yt-dlp 認証なし
  instagram-browser           — Playwright browser (診断用、fMP4断片)
"""

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
from instagram_resolver import (
    InstagramYtDlpResolver as _YtDlpResolver,
    InstagramPlaywrightResolver as _PlaywrightResolver,
    normalize_instagram_url,
)


class InstagramYtDlpAdapter:
    """yt-dlp 認証なし (Method A) を Common Contract に適合"""

    METHOD = "instagram-ytdlp-anonymous"

    def resolve(self, url: str) -> MediaResolveResult:
        canonical, shortcode, url_type = normalize_instagram_url(url)

        result = MediaResolveResult(
            url=url,
            canonical_url=canonical,
            platform="instagram",
            shortcode=shortcode,
        )

        legacy = _YtDlpResolver().resolve(url)

        attempt = ResolveAttempt(
            method=self.METHOD,
            success=legacy.success,
            error_code="",
            error_message=legacy.failure_reason,
            processing_seconds=legacy.processing_seconds,
            downloaded_file_path=legacy.downloaded_file_path,
            downloaded_file_size=legacy.downloaded_file_size,
            auth_required=legacy.auth_required,
            rate_limited=legacy.rate_limited,
            extra={
                "url_type": legacy.url_type,
            },
        )

        if not attempt.success:
            attempt.error_code = ErrorCodes.classify_error(
                attempt.error_message, self.METHOD
            ).code
        else:
            attempt.error_code = ""

        result.add_attempt(attempt)

        if legacy.success:
            result.metadata = MediaMetadata(
                duration=legacy.duration,
                width=legacy.width,
                height=legacy.height,
                codec=legacy.codec,
                has_audio=legacy.has_audio,
                file_size=legacy.downloaded_file_size,
                ffprobe_raw=legacy.ffprobe_raw,
            )

        result.estimated_cost_article = legacy.estimated_cost_article
        result.finalize()
        return result


class InstagramBrowserAdapter:
    """Playwright browser (Method C, 診断用) を Common Contract に適合"""

    METHOD = "instagram-browser"

    def resolve(self, url: str) -> MediaResolveResult:
        canonical, shortcode, url_type = normalize_instagram_url(url)

        result = MediaResolveResult(
            url=url,
            canonical_url=canonical,
            platform="instagram",
            shortcode=shortcode,
        )

        legacy = _PlaywrightResolver().resolve(url)

        attempt = ResolveAttempt(
            method=self.METHOD,
            success=legacy.success,
            error_code="",
            error_message=legacy.failure_reason,
            processing_seconds=legacy.processing_seconds,
            downloaded_file_path=legacy.downloaded_file_path,
            downloaded_file_size=legacy.downloaded_file_size,
            auth_required=legacy.auth_required,
            rate_limited=legacy.rate_limited,
            extra=legacy.extra,
        )

        if not attempt.success:
            attempt.error_code = ErrorCodes.classify_error(
                attempt.error_message, self.METHOD
            ).code
        else:
            attempt.error_code = ""

        result.add_attempt(attempt)

        if legacy.success:
            result.metadata = MediaMetadata(
                duration=legacy.duration,
                width=legacy.width,
                height=legacy.height,
                codec=legacy.codec,
                has_audio=legacy.has_audio,
                file_size=legacy.downloaded_file_size,
                ffprobe_raw=legacy.ffprobe_raw,
            )

        result.estimated_cost_article = legacy.estimated_cost_article
        result.finalize()
        return result
