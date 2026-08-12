"""Debug: Inspect TikTok page structure with Playwright"""
import re, json
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
    
    print(f"HTML size: {len(html)}")
    print(f"Title: {page.title()}")
    print(f"URL: {page.url}")
    print(f"WAF: {'wafchallengeid' in html}")
    
    # Find all scripts >200 chars
    scripts = re.findall(r'<script[^>]*>(.{200,}?)</script>', html, re.DOTALL)
    print(f"\nScripts >200 chars: {len(scripts)}")
    for i, s in enumerate(scripts):
        start = s.strip()[:150]
        print(f"  [{i}] len={len(s)}, starts: {start[:100]}")
        
        for term in ['playAddr', 'downloadAddr', 'ItemModule', 'video:', 'bitRateInfo', 'videoInfo']:
            if term in s:
                idx = s.find(term)
                print(f"       CONTAINS '{term}': ...{s[max(0,idx-30):idx+80]}...")
    
    # Check window variables
    page_vars = page.evaluate("""() => {
        const vars = [];
        for (let k of Object.keys(window)) {
            if (k.startsWith('__') || k.startsWith('SIGI') || k.includes('STATE') || k.includes('DATA')) {
                vars.push(k);
            }
        }
        return vars;
    }""")
    print(f"\nSpecial window vars: {page_vars}")
    
    for var in page_vars:
        try:
            val = page.evaluate(f"window.{var}")
            if isinstance(val, dict):
                keys = list(val.keys())[:15]
                print(f"  window.{var}: dict, keys={keys}")
                # Check for video data deep inside
                val_str = json.dumps(val)
                for term in ['playAddr', 'downloadAddr', 'ItemModule']:
                    if term in val_str:
                        idx = val_str.find(term)
                        print(f"    CONTAINS '{term}': {val_str[idx:idx+200]}")
        except Exception as e:
            print(f"  window.{var}: error {e}")
    
    # Check page response for video API calls
    print("\n--- Network requests with 'video' or 'item' ---")
    
    browser.close()
