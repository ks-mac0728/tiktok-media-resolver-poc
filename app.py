"""
Media Resolver — Manual Test UI (Streamlit)

Common Contract (MediaResolveResult) を使用し、fallback chain の
全 attempt 履歴・エラーコード・日本語メッセージを表示する。

  TikTok:    tiktok-playwright（単一方式）
  Instagram: instagram-ytdlp-anonymous → instagram-browser-fmp4-remux
"""
import streamlit as st

from resolver_contract import detect_platform, extract_shortcode
from error_codes import ErrorCodes
from resolve_media import resolve_media

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Media Resolver PoC",
    page_icon="🎬",
    layout="centered",
)

st.title("🎬 Media Resolver — Manual Test")
st.caption(
    "Common Contract / fallback chain / attempt history | "
    "TikTok: playwright | Instagram: yt-dlp → fMP4 remux"
)

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

placeholder = (
    "https://www.tiktok.com/@user/video/1234567890123456789 "
    "または https://www.instagram.com/reel/DLgMlwmhpah/"
)
url = st.text_input("URL", placeholder=placeholder)

detected = ""
if url.strip():
    detected = detect_platform(url.strip())
    if detected in ("tiktok", "instagram"):
        st.info(f"🔍 プラットフォーム検出: {detected.upper()}")

fetch_clicked = st.button(
    "📥 動画を取得",
    type="primary",
    disabled=(not url.strip()),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------

if "result" not in st.session_state:
    st.session_state.result = None

if fetch_clicked and url.strip():
    with st.spinner("Resolver fallback chain で動画を取得中…（10〜40秒）"):
        st.session_state.result = resolve_media(url.strip())

result = st.session_state.result


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _display_result(result):
    if result.success:
        st.success(f"✅ 動画を取得しました（{result.final_method}）")
        _display_video(result)
        _display_metadata(result)
    else:
        _display_error(result)

    _display_attempts(result)


def _display_video(result):
    st.subheader("🎥 Preview")
    path = result.downloaded_file_path
    if path:
        try:
            with open(path, "rb") as f:
                st.video(f.read())
        except OSError as e:
            st.caption(f"プレビュー読み込み失敗: {e}")


def _display_metadata(result):
    st.subheader("📋 Media Metadata")
    meta = result.metadata
    rows = {}
    if result.canonical_url:
        rows["canonical_url"] = result.canonical_url
    if result.shortcode:
        rows["shortcode"] = result.shortcode
    rows["final_method"] = result.final_method
    rows["total_seconds"] = f"{result.total_seconds:.1f}s"
    rows["local_file"] = result.downloaded_file_path
    if meta:
        rows["file_size"] = f"{meta.file_size:,} bytes ({meta.file_size / 1024 / 1024:.1f} MB)"
        rows["duration"] = f"{meta.duration:.1f}s"
        rows["resolution"] = f"{meta.width}x{meta.height}"
        rows["codec"] = meta.codec or "N/A"
        rows["audio"] = "あり" if meta.has_audio else "なし"
    if result.estimated_cost_article:
        rows["estimated_cost"] = result.estimated_cost_article

    for label, value in rows.items():
        st.text(f"{label}:  {value}")


def _display_error(result):
    ec = ErrorCodes.by_code(result.error_code) if result.error_code else None
    if ec:
        st.error(f"❌ {ec.message_ja}  [{ec.code} / {ec.severity.value}]")
    else:
        st.error("❌ 動画を取得できませんでした")
    if result.error_message:
        st.caption(f"詳細: {result.error_message}")


def _display_attempts(result):
    st.subheader("🧭 Attempt History（fallback chain）")
    if not result.attempts:
        st.caption("attempt なし")
        return

    for i, a in enumerate(result.attempts):
        icon = "✅" if a.success else "❌"
        line = f"{icon} **{i + 1}. {a.method}** — {a.processing_seconds:.1f}s"
        if a.success:
            line += f" | {a.downloaded_file_size:,} bytes"
        else:
            line += f" | `{a.error_code or 'UNKNOWN'}`"
            jp = ErrorCodes.by_code(a.error_code).message_ja if a.error_code else ""
            if jp:
                line += f" — {jp}"
        st.markdown(line)

        if a.error_message and not a.success:
            with st.expander(f"詳細（{a.method}）"):
                st.caption(a.error_message)
                if a.extra:
                    st.json(a.extra)


# ---------------------------------------------------------------------------
# Result display（helpers 定義後に実行）
# ---------------------------------------------------------------------------

if result is not None:
    st.divider()
    _display_result(result)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "🔧 Common Contract（resolver_contract.py） | "
    "fallback chain（resolve_media.py） | PoC専用 | LA2非接続"
)
