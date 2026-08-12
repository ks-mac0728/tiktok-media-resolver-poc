"""Test: Wait for video element to load in Playwright"""
import json, time, urllib.request, re
from pathlib import Path
from playwright.sync_api import sync_playwright

DOWNLOADS = Path("/Users/saitokosuke/Documents/projects/tiktok-media-resolver-poc/downloads")
DOWNLOADS.mkdir(parents=True, exist_ok=True)

URL = "https://www.tiktok.com/@yuto1855/video/7669733182761192711"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    
    # Enable request/response logging for video URLs
    video_urls = []
    def on_request(request):
        url = request.url
        if '.mp4' in url or 'video' in url.lower():
            video_urls.append(('request', url[:150]))
    
    def on_response(response):
        url = response.url
        ct = response.headers.get('content-type', '')
        if '.mp4' in url or 'video/' in ct:
            video_urls.append(('response', f"[{response.status}] {url[:150]}"))
    
    page.on("request", on_request)
    page.on("response", on_response)
    
    t0 = time.time()
    page.goto(URL, wait_until="networkidle", timeout=30000)
    print(f"Page loaded: {time.time()-t0:.1f}s")
    
    # Wait for video element
    try:
        page.wait_for_selector("video", timeout=10000)
        print("Video element found!")
        
        video_info = page.evaluate("""() => {
            const v = document.querySelector('video');
            if (!v) return null;
            return {
                src: v.src,
                currentSrc: v.currentSrc,
                width: v.videoWidth,
                height: v.videoHeight,
                duration: v.duration,
                readyState: v.readyState,
                networkState: v.networkState,
                error: v.error ? v.error.message : null,
            };
        }""")
        print(f"Video info: {json.dumps(video_info, indent=2)}")
        
        # Try to get the actual video URL from src
        if video_info and video_info.get('src'):
            src = video_info['src']
            print(f"\nVideo src: {src[:200]}")
            
            if src.startswith('blob:'):
                print("  (blob URL - need to fetch via JS)")
                # For blob URLs, we need to fetch through the page context
                blob_data = page.evaluate("""async () => {
                    const v = document.querySelector('video');
                    if (!v || !v.src) return null;
                    const response = await fetch(v.src);
                    const blob = await response.blob();
                    const buffer = await blob.arrayBuffer();
                    return Array.from(new Uint8Array(buffer));
                }""")
                if blob_data:
                    video_bytes = bytes(blob_data)
                    fp = DOWNLOADS / f"blob_video.mp4"
                    fp.write_bytes(video_bytes)
                    print(f"  Saved blob: {fp} ({len(video_bytes):,} bytes)")
            
    except Exception as e:
        print(f"No video element after 10s: {e}")
    
    # Print video-related network requests
    print(f"\nVideo-related network requests: {len(video_urls)}")
    for typ, url in video_urls:
        print(f"  [{typ}] {url}")
    
    # Check full HTML for anything useful
    html = page.content()
    
    # Look for video JSON data embedded in page
    # Try to find any JSON containing the video ID
    vid_match = re.search(r'video/(\d+)', URL)
    vid = vid_match.group(1) if vid_match else ""
    if vid and vid in html:
        idx = html.find(vid)
        print(f"\nVideo ID '{vid}' found in HTML at pos {idx}:")
        print(f"  Context: {html[max(0,idx-100):idx+200]}")
    
    # Look for 'play_addr' or similar in HTML
    for term in ['play_addr', 'download_addr', 'video_url', 'url_list']:
        if term in html:
            idx = html.find(term)
            print(f"\n'{term}' in HTML at {idx}: {html[idx:idx+150]}")
    
    browser.close()
