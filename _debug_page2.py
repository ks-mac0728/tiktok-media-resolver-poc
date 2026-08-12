"""Debug: Deep dive into TikTok's new page data structure"""
import re, json, base64
from playwright.sync_api import sync_playwright

url = "https://www.tiktok.com/@yuto1855/video/7669733182761192711"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    page.goto(url, wait_until="networkidle", timeout=30000)
    html = page.content()
    
    # 1. Check __UNIVERSAL_DATA__ deeply
    universal = page.evaluate("window.__UNIVERSAL_DATA__")
    print("=== __UNIVERSAL_DATA__ ===")
    universal_str = json.dumps(universal, indent=2)
    print(f"Size: {len(universal_str)} chars")
    
    # Search for video-related keys
    for term in ['playAddr', 'downloadAddr', 'video', 'bitRate', 'ItemModule']:
        if term in universal_str:
            idx = universal_str.find(term)
            print(f"\n'{term}' found at pos {idx}:")
            print(universal_str[max(0,idx-50):idx+200])
    
    # 2. Check the first big script (base64 encoded data)
    scripts = re.findall(r'<script[^>]*>(.{500,}?)</script>', html, re.DOTALL)
    if scripts:
        s0 = scripts[0]
        print(f"\n=== Script[0] ({len(s0)} chars) ===")
        print(f"First 200: {s0[:200]}")
        
        # Try to decode as JSON
        s0_stripped = s0.strip()
        if s0_stripped.startswith('{'):
            try:
                data = json.loads(s0_stripped)
                print(f"JSON keys: {list(data.keys())[:10]}")
                # Check for base64 encoded data
                for k, v in data.items():
                    if isinstance(v, str) and len(v) > 1000:
                        print(f"  {k}: str len={len(v)}, first 50: {v[:50]}")
                        # Try base64 decode
                        try:
                            decoded = base64.b64decode(v)
                            print(f"    Base64 decoded: {len(decoded)} bytes")
                            try:
                                text = decoded.decode('utf-8')
                                print(f"    As text first 100: {text[:100]}")
                            except:
                                print(f"    Binary (not text)")
                        except:
                            pass
            except json.JSONDecodeError as e:
                print(f"Not valid JSON: {e}")
    
    # 3. Try to find video URL via evaluating React fiber/state
    result = page.evaluate("""() => {
        // Try to find video element
        const video = document.querySelector('video');
        if (video) {
            return {
                src: video.src,
                currentSrc: video.currentSrc,
                width: video.videoWidth,
                height: video.videoHeight,
                duration: video.duration,
                poster: video.poster,
            };
        }
        return {error: 'no video element found'};
    }""")
    print(f"\n=== Video element ===")
    print(json.dumps(result, indent=2))
    
    # 4. Intercept network requests for video
    print("\n=== Capturing network (XHR/fetch) ===")
    requests = page.evaluate("""() => {
        const entries = performance.getEntriesByType('resource');
        const videoReqs = entries.filter(e => e.name.includes('video') || e.name.includes('.mp4') || e.name.includes('play'));
        return videoReqs.map(e => ({name: e.name, duration: e.duration, size: e.transferSize})).slice(0, 10);
    }""")
    print(json.dumps(requests, indent=2))
    
    browser.close()
