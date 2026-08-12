"""TikTok Media Resolver — Manual Test UI (Streamlit)"""
import streamlit as st
from resolver_test import PlaywrightResolver, TestResult

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="TikTok Media Resolver",
    page_icon="🎬",
    layout="centered",
)

st.title("🎬 TikTok Media Resolver — Manual Test")
st.caption("公開TikTok URL → Playwright → MP4取得 → その場で再生")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "result" not in st.session_state:
    st.session_state.result = None

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

url = st.text_input(
    "TikTok URL",
    placeholder="https://www.tiktok.com/@user/video/1234567890123456789",
    label_visibility="collapsed",
)

col1, col2 = st.columns([1, 3])
with col1:
    fetch_clicked = st.button(
        "📥 動画を取得",
        type="primary",
        disabled=(not url.strip()),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------

if fetch_clicked and url.strip():
    st.session_state.result = None  # reset

    with st.spinner("Playwright + Chromium で動画を取得中…（10〜25秒かかります）"):
        resolver = PlaywrightResolver()
        result = resolver.resolve(url.strip())
        st.session_state.result = result

# ---------------------------------------------------------------------------
# Display result
# ---------------------------------------------------------------------------

result = st.session_state.result

if result is not None:
    st.divider()

    if result.success:
        st.success("✅ 動画を取得しました")

        # --- Video preview ---
        st.subheader("🎥 Preview")
        video_path = result.downloaded_file_path
        if video_path:
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            st.video(video_bytes)

        # --- Metadata ---
        st.subheader("📋 Media Metadata")

        meta = {
            "source_url": result.url,
            "resolver": result.provider,
            "processing_seconds": f"{result.processing_seconds:.1f}s",
            "local_file": result.downloaded_file_path,
            "file_size": f"{result.downloaded_file_size:,} bytes ({result.downloaded_file_size / 1024 / 1024:.1f} MB)",
            "duration": f"{result.duration:.1f}s",
            "width": str(result.width),
            "height": str(result.height),
            "codec": result.codec,
        }

        for label, value in meta.items():
            st.text(f"{label}:  {value}")

    else:
        st.error("❌ 動画を取得できませんでした")
        st.caption(f"理由: {result.failure_reason}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption("🔧 Resolver: Playwright + Chromium (CDN intercept) | PoC専用")
