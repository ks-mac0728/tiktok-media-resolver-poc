"""Debug: Extract TikTok page structure"""
import urllib.request, re, json, sys

url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.tiktok.com/@tiktok/video/7231339977841454382'
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8')

# Look for video-related terms
for term in ['playAddr', 'downloadAddr', 'play_url', 'video_url', 'bit_rate']:
    if term in html:
        idx = html.find(term)
        print(f"'{term}' FOUND at pos {idx}: ...{html[max(0,idx-50):idx+100]}...")
    else:
        print(f"'{term}': NOT FOUND")

# Look for JSON data in script tags (any id)
scripts = re.findall(r'<script[^>]*id="([^"]*)"[^>]*>(.*?)</script>', html, re.DOTALL)
for sid, content in scripts:
    print(f"\nScript id='{sid}', len={len(content)}")
    if len(content) < 500:
        print(f"  Content: {content[:300]}")

# Look for __NUXT__ or similar SSR data patterns
for pattern_name, pattern in [
    ("__UNIVERSAL_DATA", r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>'),
    ("SIGI_STATE", r'<script id="SIGI_STATE"[^>]*>(.*?)</script>'),
    ("__NEXT_DATA__", r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'),
]:
    m = re.search(pattern, html, re.DOTALL)
    print(f"\n{pattern_name}: {'FOUND' if m else 'NOT FOUND'}")

# Look for any large embedded JSON
large_scripts = re.findall(r'<script[^>]*>(.{500,}?)</script>', html, re.DOTALL)
print(f"\nLarge scripts (>500 chars): {len(large_scripts)}")
for i, s in enumerate(large_scripts):
    print(f"  [{i}] len={len(s)}, starts with: {s[:100]}...")
    # Try to find JSON-like patterns
    if s.strip().startswith('{') or s.strip().startswith('window.'):
        print(f"  -> Looks like JSON/JS data")
        # Try to find video URLs inside
        urls = re.findall(r'https?://[^"\'\s]+\.mp4[^"\'\s]*', s)
        if urls:
            print(f"  -> MP4 URLs: {urls[:3]}")

# Print first 1500 chars
print("\n=== HTML head (first 1500 chars) ===")
print(html[:1500])
