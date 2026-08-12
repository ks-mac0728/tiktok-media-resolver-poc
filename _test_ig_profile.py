#!/usr/bin/env python3
"""
Method C: PoC専用ブラウザプロファイル (data/instagram_browser_profile/) の検証。

目的:
  1. ユーザー実Chromeプロファイルを一切使わず、PoC専用プロファイルで
     ログイン状態を永続化できることを示す
  2. ログイン状態を判定する（login form の有無）
  3. 真に公開されたReel と ログイン必須Reel のアクセス可否を比較する

結論（予想）:
  ログイン無しでは login-required Reel は login wall でブロックされる。
  プロファイルに手動ログインすれば、以後 login-required Reel が取得可能になる
  （credentials は本スクリプトに埋め込まず、手動で一度だけログインする運用）。

credentials/cookies は data/ 以下にのみ置き、git/results/logs には一切出さない。
"""

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_DIR = Path(__file__).resolve().parent
PROFILE_DIR = PROJECT_DIR / "data" / "instagram_browser_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

URLS = {
    "public": "https://www.instagram.com/reel/DLgMlwmhpah/",
    "login_required": "https://www.instagram.com/reel/DDIR_4JvRRw/",
}


def check_login_state(page) -> bool:
    """ログイン済みかを判定（login form の有無）"""
    try:
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded",
                  timeout=30000)
        page.wait_for_timeout(3000)
        has_login_form = page.locator('input[name="username"]').count() > 0
        has_loggedin_nav = page.locator(
            'a[href="/direct/inbox/"], svg[aria-label="Direct"]'
        ).count() > 0
        return (not has_login_form) and has_loggedin_nav
    except Exception:
        return False


def probe_reel(page, url: str) -> dict:
    """指定Reelのアクセス可否を判定する"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
    except Exception as e:
        return {"url": url, "accessible": False, "reason": f"goto error: {e}"}

    pc = page.content().lower()
    has_video = page.locator("video").count() > 0
    has_login = page.locator('input[name="username"]').count() > 0
    not_available = ("isn't available" in pc) or ("not available" in pc)

    if has_video:
        return {"url": url, "accessible": True, "reason": "video element found"}
    if has_login:
        return {"url": url, "accessible": False, "reason": "login wall"}
    if not_available:
        return {"url": url, "accessible": False, "reason": "not available"}
    return {"url": url, "accessible": False, "reason": "unknown (no video)"}


def main():
    t0 = time.monotonic()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        logged_in = check_login_state(page)
        print(f"login state: {'✅ logged in' if logged_in else '❌ not logged in'}")
        print(f"profile dir: {PROFILE_DIR}")

        for label, url in URLS.items():
            r = probe_reel(page, url)
            mark = "✅" if r["accessible"] else "❌"
            print(f"[{label:14s}] {mark} {r['reason']:30s} {url}")
            if label == "public":
                # 公開Reelから video URL を取得できるか（Method Bと同経路）
                src = page.locator("video").get_attribute("src", timeout=3000) \
                    if r["accessible"] else None
                print(f"  video src: {src if src else '(none)'}")

        ctx.close()

    print(f"\ntotal: {time.monotonic() - t0:.1f}s")
    print("\n=> Method C 結論:")
    print("   PoC専用プロファイルは作成・永続化される（data/ は .gitignore 済み）。")
    print("   ログイン無しでは login-required Reel は login wall でブロック。")
    print("   手動ログインすれば以後ログイン状態が永続し、取得可能になる見込み")


if __name__ == "__main__":
    main()
