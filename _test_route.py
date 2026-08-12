"""Test: Use page.route() to intercept TikTok API"""
import json, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

DOWNLOADS = Path("/Users/saitokosuke/Documents/projects/tiktok-media-resolver-poc/downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)

URL = "https://www.tiktok.com/@yuto1855/video/7669733182761192711"

api_data = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    
    # Intercept ALL /api/ requests
    def handle_route(route):
        url = route.request.url
        if "/api/item/detail" in url:
            print(f"INTERCEPTING: {url[:120]}...")
        route.continue_()
    
    page.route("**/api/item/detail**", handle_route)
    
    # Also capture all responses
    def log_response(response):
        url = response.url
        if "/api/" in url:
            print(f"RESPONSE [{response.status}]: {url[:120]}...")
            if "/api/item/detail" in url:
                try:
                    data = response.json()
                    api_data.append(data)
                    print(f"  -> Captured {len(json.dumps(data))} bytes of JSON")
                except Exception as e:
                    print(f"  -> JSON parse error: {e}")
    
    page.on("response", log_response)
    
    t0 = time.time()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    print(f"\nPage loaded in {time.time()-t0:.1f}s")
    
    # Also try waiting a bit more for lazy-loaded content
    page.wait_for_timeout(3000)
    
    print(f"\nTotal API responses captured: {len(api_data)}")
    
    if api_data:
        data = api_data[0]
        print(f"Top keys: {list(data.keys())}")
        # Try to find video
        item_info = data.get("itemInfo", {}).get("itemStruct", {})
        video = item_info.get("video", {})
        if video:
            print(f"Video: duration={video.get('duration')}, "
                  f"{video.get('width')}x{video.get('height')}")
            
            download_addr = video.get("downloadAddr", "")
            if download_addr:
                print(f"Download URL: {download_addr[:120]}...")
                
                req = urllib.request.Request(download_addr, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": "https://www.tiktok.com/",
                })
                resp = urllib.request.urlopen(req, timeout=60)
                video_data = resp.read()
                
                vid = item_info.get("id", "unknown")
                fp = DOWNLOADS / f"route_{vid}.mp4"
                fp.write_bytes(video_data)
                print(f"Saved: {fp} ({len(video_data):,} bytes)")
    
    browser.close()
