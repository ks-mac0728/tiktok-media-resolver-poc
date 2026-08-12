"""Quick Playwright test for Instagram with Chrome cookies"""
import json, os, time
from playwright.sync_api import sync_playwright

url = "https://www.instagram.com/reel/DDIR_4JvRRw/"

t0 = time.monotonic()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        storage_state=None,
    )
    page = context.new_page()

    video_urls = []

    def handle_response(response):
        ct = response.headers.get("content-type", "").lower()
        if "video" in ct and "mp4" in ct:
            video_urls.append({
                "url": response.url[:200],
                "status": response.status,
                "content_length": response.headers.get("content-length", "?"),
            })

    page.on("response", handle_response)

    resp = page.goto(url, wait_until="networkidle", timeout=30000)
    print(f"HTTP Status: {resp.status if resp else 'N/A'}")
    page.wait_for_timeout(8000)

    title = page.title()
    print(f"Title: {title[:100]}")

    has_login = page.locator('input[name="username"]').count()
    print(f"Login form present: {has_login > 0}")

    try:
        og_video = page.locator('meta[property="og:video"]').get_attribute("content", timeout=2000)
        print(f"og:video: {og_video[:200] if og_video else 'NOT FOUND'}")
    except:
        print("og:video: ERROR getting")

    try:
        video_src = page.locator("video[src]").get_attribute("src", timeout=2000)
        print(f"video[src]: {video_src[:200] if video_src else 'NOT FOUND'}")
    except:
        print("video[src]: ERROR getting")

    print(f"\nVideo responses captured: {len(video_urls)}")
    for v in video_urls:
        print(f"  {v['status']} {v['content_length']:>8s} {v['url'][:120]}")

    browser.close()

print(f"\nTime: {time.monotonic() - t0:.1f}s")
