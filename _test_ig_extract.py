"""Extract video URL from Instagram dynamic page using Playwright"""
import json, re, time
from playwright.sync_api import sync_playwright

url = "https://www.instagram.com/reel/DLgMlwmhpah/"

t0 = time.monotonic()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
    )
    page = context.new_page()

    # Intercept XHR/GraphQL responses
    api_responses = []
    def handle_response(response):
        if "api" in response.url or "graphql" in response.url:
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    body = response.text()
                    if len(body) < 100000:
                        api_responses.append({
                            "url": response.url[:200],
                            "status": response.status,
                            "body_preview": body[:500],
                        })
            except:
                pass

    page.on("response", handle_response)

    resp = page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(8000)

    # Try to get the video URL from the page
    html = page.content()
    
    # Look for video_url patterns in the entire HTML
    for pattern in ['video_url', 'video_versions', 'videoUrl', 'video_src']:
        matches = re.findall(rf'"{pattern}"\s*:\s*"([^"]+)"', html)
        if matches:
            print(f"Found '{pattern}' in HTML: {matches[0][:200]}")

    # Try to get from JavaScript evaluation
    try:
        # Try to access the React state
        video_src = page.evaluate("""() => {
            const video = document.querySelector('video');
            if (video) {
                const sources = video.querySelectorAll('source');
                if (sources.length > 0) return sources[0].src;
                return video.src || video.getAttribute('src');
            }
            return null;
        }""")
        if video_src:
            print(f"video element src: {video_src[:200]}")
        else:
            print("No video element found")
    except Exception as e:
        print(f"JS eval error: {e}")

    # Check for og:video
    try:
        og_video = page.locator('meta[property="og:video"]').get_attribute("content", timeout=3000)
        if og_video:
            print(f"og:video: {og_video[:200]}")
    except:
        pass

    # Print collected API responses
    print(f"\nAPI responses: {len(api_responses)}")
    for ar in api_responses:
        print(f"  {ar['status']} {ar['url'][:120]}")
        # Check if body contains video URL
        for pattern in ['video_url', 'video_versions', 'playable_url']:
            if pattern in ar['body_preview']:
                match = re.search(rf'"{pattern}"\s*:\s*"([^"]+)"', ar['body_preview'])
                if match:
                    print(f"    -> {pattern}: {match.group(1)[:150]}")

    browser.close()

print(f"Time: {time.monotonic() - t0:.1f}s")
