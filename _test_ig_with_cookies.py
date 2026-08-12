"""Try Instagram with Chrome cookies (persistent context)"""
import json, os, time, sqlite3
from playwright.sync_api import sync_playwright

# Extract Instagram cookies from Chrome
cookie_path = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Cookies")
conn = sqlite3.connect(cookie_path)
rows = conn.execute(
    "SELECT host_key, name, encrypted_value, path, expires_utc, is_secure, is_httponly, samesite "
    "FROM cookies WHERE host_key LIKE '%instagram%' AND name='sessionid'"
).fetchall()
conn.close()
print(f"Found {len(rows)} Instagram sessionid cookies")

# Try Playwright with storage state
# First, let's use a simpler approach: launch with Chrome channel and see if cookies are inherited
url = "https://www.instagram.com/reel/DDIR_4JvRRw/"

t0 = time.monotonic()
with sync_playwright() as p:
    # Try using chrome channel which might inherit cookies
    try:
        browser = p.chromium.launch(
            headless=True,
            channel="chrome",
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Set Instagram cookies manually
        cookies = [
            {
                "name": "sessionid",
                "value": "PLACEHOLDER",  # We'll read actual value
                "domain": ".instagram.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }
        ]
        # Can't read encrypted cookies easily, so skip manual cookie injection
        
        resp = page.goto(url, wait_until="networkidle", timeout=30000)
        title = page.title()
        print(f"Status: {resp.status if resp else '?'} | Title: {title[:100]}")
        
        # Try video detection
        try:
            og_video = page.locator('meta[property="og:video"]').get_attribute("content", timeout=3000)
            print(f"og:video: {og_video[:200] if og_video else 'NONE'}")
        except:
            print("og:video: NONE")
        
        page.wait_for_timeout(5000)
        
        # Check for login wall
        has_login = page.locator('input[name="username"]').count()
        print(f"Login form: {'YES' if has_login else 'NO'}")
        
        # Check for video element
        video_count = page.locator("video").count()
        print(f"<video> elements: {video_count}")
        
        # Check page content
        html_snippet = page.content()[:500]
        if "login" in html_snippet.lower() and "instagram" in html_snippet.lower():
            print("Page contains login references")
        if "unavailable" in html_snippet.lower() or "isn't available" in html_snippet.lower():
            print("Page contains 'not available' message")
        
        browser.close()
    except Exception as e:
        print(f"Error: {e}")

print(f"Time: {time.monotonic() - t0:.1f}s")
