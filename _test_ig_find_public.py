"""Find publicly accessible Instagram reels"""
from playwright.sync_api import sync_playwright

# Try a few known accounts that frequently have public reels
URLS = [
    "https://www.instagram.com/reel/CiZT7PkuOHL/",
    "https://www.instagram.com/reel/DM7LmbEJG7S/",
    "https://www.instagram.com/reel/DCbkKZRPESX/",
    "https://www.instagram.com/p/DCbkKZRPESX/",
]

def check_url(page, url):
    print(f"\n--- {url}")
    try:
        resp = page.goto(url, wait_until="networkidle", timeout=20000)
    except:
        print("  Timeout")
        return
    
    title = page.title()
    print(f"  Status: {resp.status if resp else '?'} | Title: {title[:80]}")
    
    # Check for video
    try:
        og_video = page.locator('meta[property="og:video"]').get_attribute("content", timeout=2000)
        if og_video:
            print(f"  og:video: YES ({og_video[:100]}...)")
        else:
            print(f"  og:video: NONE")
    except:
        print(f"  og:video: NONE")
    
    try:
        video_els = page.locator("video").count()
        print(f"  <video> elements: {video_els}")
        if video_els > 0:
            src = page.locator("video").first.get_attribute("src", timeout=2000)
            poster = page.locator("video").first.get_attribute("poster", timeout=2000)
            print(f"  video src: {src[:200] if src else 'none'}")
    except:
        pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = context.new_page()
    
    for url in URLS:
        check_url(page, url)
    
    browser.close()
