"""Test: Intercept TikTok API response via Playwright to get video download URL"""
import json, re, time, urllib.request
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
    
    api_response_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Intercept XHR responses
        def on_response(response):
            if "/api/item/detail" in response.url and response.status == 200:
                try:
                    data = response.json()
                    api_response_data.append(data)
                except:
                    pass
        
        page.on("response", on_response)
        
        t0 = time.time()
        page.goto(url, wait_until="networkidle", timeout=30000)
        load_time = time.time() - t0
        
        print(f"  Load time: {load_time:.1f}s")
        print(f"  API responses captured: {len(api_response_data)}")
        
        if not api_response_data:
            print("  No API response captured!")
            browser.close()
            continue
        
        # Parse API response
        data = api_response_data[0]
        data_str = json.dumps(data, indent=2)
        
        # Find video download URL
        for term in ['downloadAddr', 'playAddr', 'bitRateInfo']:
            if term in data_str:
                idx = data_str.find(term)
                print(f"  '{term}' found: {data_str[idx:idx+150]}")
        
        # Navigate to video info
        item_info = data.get("itemInfo", {}).get("itemStruct", {})
        if not item_info:
            # Try different path
            for key in data.keys():
                print(f"  Top key: {key}")
                if isinstance(data[key], dict):
                    subkeys = list(data[key].keys())[:10]
                    print(f"    subkeys: {subkeys}")
        
        video = item_info.get("video", {})
        if video:
            print(f"\n  Video info:")
            print(f"    duration: {video.get('duration')}s")
            print(f"    width: {video.get('width')} x height: {video.get('height')}")
            print(f"    format: {video.get('format')}")
            
            download_addr = video.get("downloadAddr", "")
            play_addr = video.get("playAddr", "")
            
            # Use downloadAddr if available
            addr_to_use = download_addr or play_addr
            if addr_to_use:
                print(f"    Using: {'downloadAddr' if download_addr else 'playAddr'}")
                
                t1 = time.time()
                try:
                    req = urllib.request.Request(addr_to_use, headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Referer": "https://www.tiktok.com/",
                    })
                    resp = urllib.request.urlopen(req, timeout=60)
                    video_data = resp.read()
                    dl_time = time.time() - t1
                    
                    vid = item_info.get("id", "unknown")
                    filename = f"playwright_{vid}.mp4"
                    filepath = DOWNLOADS / filename
                    filepath.write_bytes(video_data)
                    
                    print(f"    Saved: {filepath} ({len(video_data):,} bytes, {dl_time:.1f}s)")
                    print(f"    Total: {load_time+dl_time:.1f}s")
                except Exception as e:
                    print(f"    Download error: {e}")
            
            # Check bitrate info for multiple quality options
            bitrate_info = video.get("bitRateInfo", [])
            if bitrate_info:
                print(f"    Bitrates available: {len(bitrate_info)}")
                for br in bitrate_info[:3]:
                    print(f"      {br.get('GearName', '?')}: {br.get('bit_rate', 0)} bps")
        else:
            print(f"  No video info in itemStruct")
            # Try to find video data anywhere in the response
            for k, v in data.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        if 'video' in str(sk).lower() or 'playAddr' in str(sv):
                            print(f"  Potential video data at: {k}.{sk}")
        
        browser.close()

print("\nDone!")
