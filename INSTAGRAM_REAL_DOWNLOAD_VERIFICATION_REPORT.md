# INSTAGRAM REAL DOWNLOAD VERIFICATION REPORT

> 目的: 「現在ブラウザ上で実際に再生できる Instagram Reel を、8503 環境から
> complete MP4 として本当にダウンロードできるか」の実証（それだけ）。
> LA2 / 8502 には一切触れない。認証情報はログに出さない。

---

## A. Test URL

- **URL:** `https://www.instagram.com/reel/Db8wcqjvmGS/`
- **種別:** 動画投稿（NASA 公式アカウント / 皆既日食 Reel）
- **Browser playable:** YES（Playwright + ログイン済み Chrome cookie で実ロードし、`video` 要素（blob: ソース）を確認。caption「total solar eclipse」）
- **Login state:** Chrome「Default」profile が Instagram にログイン済み（`--cookies-from-browser chrome` で sessionid を取得可能なことを確認）

> 削除済みと判明した `DDIR_4JvRRw` / `CiZT7PkuOHL` / `DM7LmbEJG7S` は不使用。
> `DLgMlwmhpah` は anonymous でも取得できる Control のため、認証検証の本命にはしない。

---

## B. Anonymous

- **Result:** SUCCESS（yt-dlp + cookies なし、exit code 0）
- **Error:** なし
- **File:** `/tmp/auth_poc_test/Db8wcqjvmGS_anon.mp4`
- **processing seconds:** ≈3.3s
- **md5:** `bf726e2494278ed6ceece2f1f43b88b3`

---

## C. Chrome Authenticated

- **Result:** SUCCESS（yt-dlp + `--cookies-from-browser chrome`、exit code 0）
- **Error:** なし
- **File:** `/tmp/auth_poc_test/Db8wcqjvmGS_auth.mp4`
- **processing seconds:** ≈2.1s
- **md5:** `bf726e2494278ed6ceece2f1f43b88b3`

> **重要:** anonymous と authenticated の出力 MP4 は **md5 が完全一致**（同一ファイル）。
> つまり、この公開 Reel については認証 cookie が取得結果に何も寄与していない。

---

## D. Media Validation

- **File size:** 1,399,789 bytes（約 1.3 MB）
- **Duration:** 30.505375s（> 0 ✅）
- **Resolution:** 720 × 1280（縦動画、width/height > 0 ✅）
- **Video codec:** h264（29.97 fps、`r_frame_rate=2997/100`）
- **Audio codec:** aac（音声あり投稿のため audio stream も存在 ✅）
- **ffprobe:** PASS
- **Standalone playback:** OK（progressive MP4、`format_name=mov,mp4,m4a,3gp,3g2,mj2`、単独再生可能）

> SUCCESS 条件（実ファイル存在 / size>0 / ffprobe PASS / duration>0 / video stream / width・height>0 / codec 取得 / complete MP4 単独再生 / 音声 stream）をすべて満たす。

---

## E. 8503 UI

- **URL input:** OK（`st.text_input` に Reel URL を入力 → プラットフォーム検出 `INSTAGRAM`）
- **Download:** OK（`resolve_media.py` の fallback chain により `instagram-ytdlp-anonymous` が成功）
- **Preview:** OK（`st.video()` が MP4 を描画。AppTest で `video` 要素 = 1 を確認）
- **Result:** `✅ 動画を取得しました（instagram-ytdlp-anonymous）`
- **Metadata 表示:** file_size `1,399,789 bytes (1.3 MB)` / duration `30.5s` / resolution `720x1280` / codec `h264` / audio `あり` / estimated_cost `$0.00`
- **UI 経由の出力:** `downloads/instagram-ytdlp_Db8wcqjvmGS.mp4` が手動取得 MP4 と md5 一致

> 注: 検証中に `app.py` の既存バグ（`_display_result()` が定義前に呼ばれる `NameError`）を
> 発見し、表示ヘルパー定義後に呼び出すよう順序を修正した（resolver 本体の変更ではない）。

---

## F. Verdict

**PUBLIC_DOWNLOAD_VERIFIED**

分類: **CASE A**（anonymous SUCCESS / authenticated SUCCESS）
→ 公開 Reel 取得は成功。Instagram download capability = **VERIFIED**。
→ ただし、認証突破能力は未証明（authenticated 出力が anonymous と md5 完全一致のため）。

---

## G. Integration Recommendation

**NEEDS_MORE_POC**

- 公開 Reel の取得は 8503 環境で end-to-end（URL 入力 → complete MP4 → st.video() Preview）まで実証できた。
- しかし本 PoC の最重要命題である「**login-required（非公開/ログイン必須）Reel** を既存 Chrome session の cookie 移譲で取得できるか」（CASE B）は、今回の URL が公開 Reel だったため**未証明**。
- 認証が本当に必要な URL（自身がログイン状態でしか再生できない Reel）で CASE B を実証するまでは、8503 への正式統合（Instagram resolver の認証済み経路）は保留とする。
- 現状の anonymous yt-dlp 経路は公開 Reel に対して有効であることは本レポートで確認済み。

---

## H. Safety

- LA2 repo changes: **0**
- 8502 changes: **0**
- Production Sheets writes: **0**
- R2 writes: **0**
- Livedoor writes: **0**
- AtomPub: **0**

作業対象は `tiktok-media-resolver-poc` のみ。
credential / cookie 値のログ出力なし。

---

## Evidence（credential 非含有）

| item | value |
|---|---|
| source URL | `https://www.instagram.com/reel/Db8wcqjvmGS/` |
| normalized URL | 同上 |
| method (anonymous) | `yt-dlp` + `-f "mp4/best[ext=mp4]/best"`（cookies なし） |
| method (authenticated) | `yt-dlp` + `--cookies-from-browser chrome` |
| anonymous result | SUCCESS（exit 0） |
| authenticated result | SUCCESS（exit 0） |
| output filename (anon) | `Db8wcqjvmGS_anon.mp4` |
| output filename (auth) | `Db8wcqjvmGS_auth.mp4` |
| file size | 1,399,789 bytes |
| duration | 30.505375 s |
| resolution | 720 × 1280 |
| video codec | h264 |
| audio codec | aac |
| ffprobe | PASS |
| 8503 preview | PASS（st.video 1 要素） |
| processing seconds (anon) | ≈3.3 s |
| processing seconds (auth) | ≈2.1 s |
| md5 (anon == auth) | `bf726e2494278ed6ceece2f1f43b88b3` |
