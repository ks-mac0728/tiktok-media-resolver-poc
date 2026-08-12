"""Test: Use Playwright to bypass TikTok WAF and extract video download URL"""
import sys, json, re, time
from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.tiktok.com/@tiktok/video/7231339977841454382"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    
    t0 = time.time()
    page.goto(url, wait_until="networkidle", timeout=30000)
    print(f"Page loaded in {time.time()-t0:.1f}s")
    
    html = page.content()
    print(f"HTML size: {len(html)} bytes")
    
    # Check for WAF
    if "wafchallengeid" in html or "slardar" in html:
        print("WAF DETECTED - taking screenshot for debug")
        page.screenshot(path="/tmp/tt_waf.png")
    else:
        print("NO WAF - page loaded successfully")
    
    # Check for common video data patterns
    for pattern_name, pattern in [
        ("SIGI_STATE", r'<script id="SIGI_STATE"[^>]*>(.*?)</script>'),
        ("UNIVERSAL_DATA", r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>'),
    ]:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            print(f"\n{pattern_name} FOUND! len={len(m.group(1))}")
            try:
                data = json.loads(m.group(1))
                top_keys = list(data.keys())[:10]
                print(f"  Top keys: {top_keys}")
                
                if 'ItemModule' in data:
                    for vid, item in data['ItemModule'].items():
                        print(f"  Video ID: {vid}")
                        v = item.get('video', {})
                        for k in ['downloadAddr', 'playAddr', 'bitRateInfo']:
                            if k in v:
                                val = v[k]
                                if isinstance(val, list):
                                    print(f"  {k}: {len(val)} items")
                                    for i, br in enumerate(val[:3]):
                                        print(f"    [{i}] {json.dumps(br)[:150]}")
                                elif isinstance(val, str):
                                    print(f"  {k}: {val[:120]}")
                        # Resolution
                        print(f"  width: {v.get('width')}, height: {v.get('height')}, duration: {v.get('duration')}")
            except Exception as e:
                print(f"  JSON parse error: {e}")
    
    # Also look for any mp4 URLs in HTML
    mp4_urls = re.findall(r'https?://[^"\'\s]+\.mp4[^"\'\s]*', html)
    print(f"\nMP4 URLs in HTML: {len(mp4_urls)}")
    for u in mp4_urls[:5]:
        print(f"  {u[:150]}")
    
    # Look for video-related JSON in page
    print("\n--- page title ---")
    print(page.title())
    
    browser.close()
