"""Test v2: Capture TikTok VIDEO CDN URL specifically"""
import json, time, urllib.request, re
from pathlib import Path
from playwright.sync_api import sync_playwright

DOWNLOADS = Path("/Users/saitokosuke/Documents/projects/tiktok-media-resolver-poc/downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)

URLS = [
    "https://www.tiktok.com/@yuto1855/video/7669733182761192711",
    "https://www.tiktok.com/@minnakowaikarayada7/video/7671211573863517458",
    "https://www.tiktok.com/@zuttowakaku/video/7670096015315242247",
]

for url in URLS:
    print(f"\n{'='*60}")
    print(f"URL: {url}")
    
    cdn_video_urls = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Capture requests - focus on v16-webapp which serves actual video
        def capture_request(request):
            u = request.url
            # v16-webapp*.tiktok.com/video/tos/ is the actual video CDN
            if 'v16-webapp' in u and '/video/tos/' in u:
                cdn_video_urls.append(u)
                print(f"  [CDN] {u[:150]}")
        
        page.on("request", capture_request)
        
        t0 = time.time()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(5000)  # Wait for lazy video load
        load_time = time.time() - t0
        
        print(f"  Load time: {load_time:.1f}s")
        print(f"  Video CDN URLs: {len(cdn_video_urls)}")
        
        if cdn_video_urls:
            cdn_url = cdn_video_urls[0]
            
            t1 = time.time()
            try:
                req = urllib.request.Request(cdn_url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Referer": "https://www.tiktok.com/",
                })
                resp = urllib.request.urlopen(req, timeout=60)
                video_data = resp.read()
                dl_time = time.time() - t1
                
                vid = re.search(r'video/(\d+)', url).group(1)
                fp = DOWNLOADS / f"cdn_{vid}.mp4"
                fp.write_bytes(video_data)
                
                print(f"  Saved: {fp} ({len(video_data):,} bytes, {dl_time:.1f}s)")
                print(f"  Total: {load_time+dl_time:.1f}s")
            except Exception as e:
                print(f"  Download error: {e}")
        
        browser.close()

print("\nDone!")
