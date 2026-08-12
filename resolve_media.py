"""
Unified Media Resolver — fallback chain（成功方式のみ採用）

Phase 2 修正指示 #1 / #7 / #8 に従い、以下を実現する:

1. プラットフォーム自動判定（TikTok / Instagram）
2. 成功が実証された方式のみをチェーンに採用（失敗方式は REJECT、チェーンに入れない）
3. 全 attempt の履歴を MediaResolveResult.attempts に記録（#8）
4. 最終状態を finalize() で集約

Chain 構成（2026-08-13 時点）:

  TikTok:
    tiktok-playwright             （3/3 成功実証、単一方式で足りる）

  Instagram:
    instagram-ytdlp-anonymous     （primary: h264 完全MP4、公開Reelで成功実証）
    instagram-browser-fmp4-remux  （secondary: fMP4再構築、VP9。公開Reelで成功実証）
    ※ 外部API（Apify/RapidAPI）は RESEARCH_ONLY のため実行チェーンに含めない。
      token取得・契約なしで RECOMMEND しない（修正指示 #6）。

Usage:
    from resolve_media import resolve_media
    result = resolve_media(url)
    print(result.summary())
    print(result.attempt_summary())
"""

from resolver_contract import (
    MediaResolveResult,
    ResolveAttempt,
    detect_platform,
    extract_shortcode,
    normalize_url,
)
from error_codes import ErrorCodes
from tiktok_adapter import TikTokResolver
from instagram_adapter import InstagramYtDlpAdapter
from instagram_fmp4_remux import InstagramFmp4RemuxResolver

# 外部APIの研究結果ポインタ（実行チェーンには含めない）
EXTERNAL_API_RESEARCH = "external_api_research.md"


def _merge_attempts(acc: MediaResolveResult, sub: MediaResolveResult):
    """sub の全 attempt を acc に統合。成功時の file/metadata も引き継ぐ。"""
    for attempt in sub.attempts:
        acc.add_attempt(attempt)
    if sub.success:
        acc.success = True
        acc.final_method = sub.final_method
        acc.downloaded_file_path = sub.downloaded_file_path
        acc.metadata = sub.metadata
        acc.error_code = ""
        acc.error_message = ""
    else:
        # 失敗時は最後のエラーを引き継ぐ（finalize で FATAL 優先解決される）
        if sub.error_code:
            acc.error_code = sub.error_code
            acc.error_message = sub.error_message
    if sub.estimated_cost_article:
        acc.estimated_cost_article = sub.estimated_cost_article
    return acc


def resolve_tiktok(url: str) -> MediaResolveResult:
    """TikTok: tiktok-playwright（単一方式）"""
    return TikTokResolver().resolve(url)


def resolve_instagram(url: str) -> MediaResolveResult:
    """Instagram: yt-dlp anonymous → fMP4 remux（成功方式のみ）"""
    canonical, shortcode, url_type = _ig_normalize(url)

    acc = MediaResolveResult(
        url=url,
        canonical_url=canonical,
        platform="instagram",
        shortcode=shortcode,
    )

    # 1) primary: yt-dlp anonymous
    yt = InstagramYtDlpAdapter().resolve(url)
    _merge_attempts(acc, yt)

    if acc.success:
        acc.finalize()
        return acc

    # 2) secondary: fMP4 remux（yt-dlp 失敗時のみ）
    remux = InstagramFmp4RemuxResolver().resolve(url)
    _merge_attempts(acc, remux)

    acc.finalize()
    return acc


def _ig_normalize(url: str) -> tuple:
    from instagram_resolver import normalize_instagram_url
    return normalize_instagram_url(url)


def resolve_media(url: str) -> MediaResolveResult:
    """プラットフォームを判定して fallback chain を実行"""
    platform = detect_platform(url)
    if platform == "tiktok":
        return resolve_tiktok(url)
    if platform == "instagram":
        return resolve_instagram(url)

    # 不明なプラットフォーム
    result = MediaResolveResult(
        url=url,
        canonical_url=normalize_url(url),
        platform=platform,
    )
    attempt = ResolveAttempt(
        method="unknown-platform",
        error_code=ErrorCodes.MEDIA_NOT_FOUND.code,
        error_message=(
            f"対応していないURLです（platform={platform}）。"
            "TikTok または Instagram のURLを指定してください。"
        ),
    )
    result.add_attempt(attempt)
    result.finalize()
    return result


if __name__ == "__main__":
    import sys

    for u in sys.argv[1:] or [
        "https://www.tiktok.com/@bymyside397/video/7668967279207615760",
        "https://www.instagram.com/reel/DLgMlwmhpah/",
    ]:
        r = resolve_media(u)
        print(f"\nURL: {u}")
        print(r.summary())
        print(r.attempt_summary())
