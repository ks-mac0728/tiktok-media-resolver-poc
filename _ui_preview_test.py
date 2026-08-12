"""8503 UI 実再生検証ハーネス: app.py を AppTest で headless 実行し、
Instagram Reel URL → resolve → st.video() preview まで通ることを検証する。

Usage:
    python3 _ui_preview_test.py "https://www.instagram.com/reel/XXXX/"
"""
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

from streamlit.testing.v1 import AppTest

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.instagram.com/reel/Db8wcqjvmGS/"

at = AppTest.from_file("app.py", default_timeout=180)
at.run()

at.text_input[0].set_value(URL)
at.run()

at.button[0].click()
at.run()

print("=== exception ===")
print(at.exception)

print("=== success messages ===")
for s in at.success:
    print("SUCCESS:", s.value)

print("=== error messages ===")
for e in at.error:
    print("ERROR:", e.value)

print("=== metadata (st.text) ===")
for t in at.text:
    print("TEXT:", t.value)

print("=== video elements (st.video) ===")
print("video elements:", len(at.get("video")))
