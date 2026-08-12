"""Quick test to find working TikTok URLs for the 3rd test slot"""
import time
from playwright.sync_api import sync_playwright

# Try some additional URLs to find one that works
URLS = [
    "https://www.tiktok.com/@zuttowakaku/video/7670096015315242247",  # original 3rd
    "https://www.tiktok.com/@nikkietutorials/video/7234532789012384567",
    "https://www.tiktok.com/@zachking/video/7234567890123456789",
    "https://www.tiktok.com/@tiktok/video/7231339977841454382",  # from sample URLs
]

for url in URLS:
    print(f"\n--- Testing: {url[:80]}...")
    captured = {"count": 0, "url": "", "bytes": 0}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        def handle_route(route):
            req_url = route.request.url
            if 'v16-webapp' in req_url and '/video/tos/' in req_url:
                captured["count"] += 1
                captured["url"] = req_url[:120]
                try:
                    resp = route.fetch()
                    body = resp.body()
                    if len(body) > captured["bytes"]:
                        captured["bytes"] = len(body)
                    route.fulfill(response=resp)
                except:
                    route.continue_()
            else:
                route.continue_()
        
        page.route("**/*", handle_route)
        
        t0 = time.time()
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(8000)
        except Exception as e:
            print(f"  Error: {e}")
        
        load_time = time.time() - t0
        print(f"  CDN requests: {captured['count']}, bytes: {captured['bytes']:,}, time: {load_time:.1f}s")
        
        browser.close()

print("\nDone!")
