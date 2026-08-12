"""Test v3: Capture TikTok video via Playwright route.fetch()"""
import json, time, re
from pathlib import Path
from playwright.sync_api import sync_playwright

DOWNLOADS = Path(__file__).resolve().parent / "downloads"
DOWNLOADS.mkdir(parents=True, exist_ok=True)

URLS = [
    "https://www.tiktok.com/@yuto1855/video/7669733182761192711",
    "https://www.tiktok.com/@minnakowaikarayada7/video/7671211573863517458",
    "https://www.tiktok.com/@zuttowakaku/video/7670096015315242247",
]

for url in URLS:
    print(f"\n{'='*60}")
    print(f"URL: {url}")

    video_data = {"bytes": b"", "url": ""}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def handle_route(route):
            req_url = route.request.url
            if 'v16-webapp' in req_url and '/video/tos/' in req_url:
                print(f"  [INTERCEPT] {req_url[:120]}")
                video_data["url"] = req_url
                # Fetch the response ourselves to capture body
                try:
                    resp = route.fetch()
                    body = resp.body()
                    if body and len(body) > len(video_data["bytes"]):
                        video_data["bytes"] = body
                    route.fulfill(response=resp)
                except Exception as e:
                    print(f"  [FETCH ERROR] {e}")
                    route.continue_()
            else:
                route.continue_()

        page.route("**/*", handle_route)

        t0 = time.time()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(8000)
        load_time = time.time() - t0

        print(f"  Load time: {load_time:.1f}s")
        print(f"  Data captured: {len(video_data['bytes']):,} bytes")

        if video_data["bytes"] and len(video_data["bytes"]) > 50000:
            vid = re.search(r'video/(\d+)', url).group(1)
            fp = DOWNLOADS / f"pwright_{vid}.mp4"
            fp.write_bytes(video_data["bytes"])
            print(f"  ✅ Saved: {fp} ({len(video_data['bytes']):,} bytes, {load_time:.1f}s total)")
        else:
            print(f"  ❌ No video data captured")

        browser.close()

print("\nDone!")
