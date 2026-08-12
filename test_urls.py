"""
Instagram テストURLセット定義。

Phase 2 修正指示 #3 に従い、2種類に分離:

1. PUBLIC_ANONYMOUS_SET  — ログアウト状態でもInstagram上で閲覧できるReel
2. GENERAL_INPUT_SET     — ユーザーが通常URLとして投入しそうなReel
                          （認証要求・API制限・削除済み・画像投稿を含む）

成功率はセットごとに別々に集計する。
「取得可能なものだけを母数にして100%」は禁止。

=== 重要な発見 (2026-08-13) ===
Instagramは2023年以降、匿名アクセスを大幅に制限している。
- 真に公開されたReel（匿名で再生可能）は極めて稀少
- 短縮コードは11桁base64系で推測不能
- 匿名ではExplore/プロフィール一覧を閲覧できない
- yt-dlpのユーザー一覧取得もbroken扱い
このため PUBLIC_ANONYMOUS_SET の母数確保自体が困難であることが
PoCの重要な知見となる。
"""

# ---------------------------------------------------------------------------
# PUBLIC_ANONYMOUS_SET — 匿名で再生可能なReel（Playwrightでlogin wall無しを確認済み）
# ---------------------------------------------------------------------------

PUBLIC_ANONYMOUS_SET = [
    {
        "url": "https://www.instagram.com/reel/DLgMlwmhpah/",
        "shortcode": "DLgMlwmhpah",
        "note": "imaisakura_ の真に公開されたReel。Phase 1で yt-dlp 取得成功（720x1280, h264+aac）。",
    },
    # NOTE: 追加の真に公開されたReelの発見は、匿名での閲覧制限により極めて困難。
    # 下記は匿名アクセス不可（login wall / 削除済み）であり、母数に入れない。
]

# ---------------------------------------------------------------------------
# GENERAL_INPUT_SET — ユーザーが投入しそうなURLの現実的ミックス
# ---------------------------------------------------------------------------

GENERAL_INPUT_SET = [
    {
        "url": "https://www.instagram.com/reel/DLgMlwmhpah/",
        "shortcode": "DLgMlwmhpah",
        "note": "公開Reel（同一URL。general入力でも当然成功する）",
    },
    {
        "url": "https://www.instagram.com/reel/DDIR_4JvRRw/",
        "shortcode": "DDIR_4JvRRw",
        "note": "匿名では 'Post isn't available'（ログイン必須の実在Reel）",
    },
    {
        "url": "https://www.instagram.com/p/DCbkKZRPESX/",
        "shortcode": "DCbkKZRPESX",
        "note": "画像投稿（/p/ URL。動画でないため NOT_A_VIDEO 想定）",
    },
    {
        "url": "https://www.instagram.com/reel/CiZT7PkuOHL/",
        "shortcode": "CiZT7PkuOHL",
        "note": "Phase 1で匿名アクセス不可だった実在Reel",
    },
    {
        "url": "https://www.instagram.com/reel/DH1abc12345/",
        "shortcode": "DH1abc12345",
        "note": "存在しない短縮コード（404 / not found 想定）",
    },
    {
        "url": "https://www.instagram.com/reel/C0v_7_uvbBK/",
        "shortcode": "C0v_7_uvbBK",
        "note": "匿名で not available（ログイン必須 or 削除済み）",
    },
    {
        "url": "https://www.instagram.com/reel/DM7LmbEJG7S/",
        "shortcode": "DM7LmbEJG7S",
        "note": "Phase 1で匿名アクセス不可だった実在Reel",
    },
    {
        "url": "https://www.instagram.com/p/DLgMlwmhpah/",
        "shortcode": "DLgMlwmhpah",
        "note": "同一shortcodeの /p/ URL（正規化テスト: /p/→/reel/ 変換）",
    },
    {
        "url": "https://www.instagram.com/reel/DEWqXePuwYD/",
        "shortcode": "DEWqXePuwYD",
        "note": "匿名で not available",
    },
    {
        "url": "https://www.instagram.com/reel/DFDZe-YROdA/",
        "shortcode": "DFDZe-YROdA",
        "note": "匿名で not available",
    },
]


def get_public_set() -> list[str]:
    return [u["url"] for u in PUBLIC_ANONYMOUS_SET]


def get_general_set() -> list[str]:
    return [u["url"] for u in GENERAL_INPUT_SET]


def get_all_instagram_urls() -> list[str]:
    """重複除去した全Instagram URL"""
    seen = set()
    result = []
    for u in get_public_set() + get_general_set():
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


# ---------------------------------------------------------------------------
# TikTok サンプルURL（baseline / regression 用）
# ---------------------------------------------------------------------------

TIKTOK_SAMPLE_URLS = [
    "https://www.tiktok.com/@bymyside397/video/7668967279207615760",
    "https://www.tiktok.com/@pet22749v6x/video/7669757165208472852",
    "https://www.tiktok.com/@koreanmafin/video/7669550728171556103",
]


if __name__ == "__main__":
    print(f"PUBLIC_ANONYMOUS_SET: {len(get_public_set())} URLs")
    for u in get_public_set():
        print(f"  {u}")

    print(f"\nGENERAL_INPUT_SET: {len(get_general_set())} URLs")
    for u in get_general_set():
        print(f"  {u}")

    print(f"\nALL unique Instagram URLs: {len(get_all_instagram_urls())}")
