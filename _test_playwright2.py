"""Test: Playwright-based TikTok video extraction with working URLs"""
import sys, json, re, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

TEST_URLS = [
    "https://www.tiktok.com/@yuto1855/video/7669733182761192711",
    "https://www.tiktok.com/@minnakowaikarayada7/video/7671211573863517458",
    "https://www.tiktok.com/@zuttowakaku/video/7670096015315242247",
]

DOWNLOADS = Path("/Users/saitokosuke/Documents/projects/tiktok-media-resolver-poc/downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)

for url in TEST_URLS:
    print(f"\n{'='*60}")
    print(f"URL: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        t0 = time.time()
        page.goto(url, wait_until="networkidle", timeout=30000)
        load_time = time.time() - t0
        html = page.content()
        
        # Extract SIGI_STATE
        m = re.search(r'<script id="SIGI_STATE"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            print("  SIGI_STATE NOT FOUND")
            browser.close()
            continue
        
        data = json.loads(m.group(1))
        
        # Check ItemModule
        item_module = data.get("ItemModule", {})
        if not item_module:
            # Try alternative locations
            print(f"  ItemModule not found. Keys: {list(data.keys())[:10]}")
            browser.close()
            continue
        
        for vid, item in item_module.items():
            desc = item.get("desc", "")[:80]
            author = item.get("author", "")
            video = item.get("video", {})
            
            print(f"  Video: {vid}")
            print(f"  Desc: {desc}")
            print(f"  Author: {author}")
            print(f"  Duration: {video.get('duration')}s")
            print(f"  Resolution: {video.get('width')}x{video.get('height')}")
            print(f"  Format: {video.get('format')}")
            
            # Get download URL
            download_addr = video.get("downloadAddr", "")
            if download_addr:
                print(f"  downloadAddr: {download_addr[:120]}...")
            
            # Try bitrate info for best quality
            bitrate_info = video.get("bitRateInfo", [])
            if bitrate_info:
                print(f"  Bitrates: {len(bitrate_info)} available")
                for br in bitrate_info:
                    print(f"    {br.get('GearName', '')}: {br.get('bit_rate', 0)} bps, "
                          f"{br.get('PlayAddr', {}).get('UrlList', [''])[0][:80]}")
                
                # Pick highest bitrate
                best = max(bitrate_info, key=lambda x: x.get("bit_rate", 0))
                play_addr = best.get("PlayAddr", {}).get("UrlList", [""])[0]
                if play_addr:
                    print(f"\n  Downloading highest quality: {best.get('GearName', '')}")
                    t1 = time.time()
                    try:
                        req = urllib.request.Request(play_addr, headers={
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                            "Referer": "https://www.tiktok.com/",
                        })
                        resp = urllib.request.urlopen(req, timeout=60)
                        video_data = resp.read()
                        dl_time = time.time() - t1
                        
                        # Save
                        filename = f"playwright_{vid}.mp4"
                        filepath = DOWNLOADS / filename
                        filepath.write_bytes(video_data)
                        
                        print(f"  Saved: {filepath} ({len(video_data):,} bytes, {dl_time:.1f}s)")
                        print(f"  Total time: {load_time+dl_time:.1f}s")
                    except Exception as e:
                        print(f"  Download error: {e}")
            
            elif download_addr:
                print(f"\n  Downloading from downloadAddr...")
                t1 = time.time()
                try:
                    req = urllib.request.Request(download_addr, headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "Referer": "https://www.tiktok.com/",
                    })
                    resp = urllib.request.urlopen(req, timeout=60)
                    video_data = resp.read()
                    dl_time = time.time() - t1
                    
                    filename = f"playwright_{vid}.mp4"
                    filepath = DOWNLOADS / filename
                    filepath.write_bytes(video_data)
                    
                    print(f"  Saved: {filepath} ({len(video_data):,} bytes, {dl_time:.1f}s)")
                    print(f"  Total time: {load_time+dl_time:.1f}s")
                except Exception as e:
                    print(f"  Download error: {e}")
        
        browser.close()

print("\nDone!")
