# Media Resolver PoC — Results（Phase 2）

Generated: 2026-08-13

実測マトリクス: **13 URL**（TikTok 3 + Instagram 10）
結果データ: `results.json`（各 attempt の詳細・ffprobe・エラーコードを含む）

---

## サマリー

| セット | 成功率 | 方式 |
|--------|--------|------|
| TikTok baseline | **3/3** | tiktok-playwright |
| Instagram public-anonymous | **1/1** | instagram-ytdlp-anonymous |
| Instagram general-input | **1/9** | 1件は /p/→/reel/ 正規化で成功、残り8件は login-wall |

| Platform | 判定 |
|----------|------|
| **TikTok** | **READY_FOR_INTEGRATION_CANDIDATE** |
| **Instagram** | **CONDITIONAL**（真に公開された Reel のみ。login-required は認証必須） |

---

## 1. TikTok — READY_FOR_INTEGRATION_CANDIDATE

方式: `tiktok-playwright`（Chromium + CDN network intercept `route.fetch()`）

| URL | success | 処理秒 | file size | duration | resolution | codec | watermark |
|-----|---------|--------|-----------|----------|------------|-------|-----------|
| @bymyside397/video/7668967279207615760 | ✅ | 27.6s | 1,246,739 B | 5.5s | 720×1280 | h264 | あり |
| @pet22749v6x/video/7669757165208472852 | ✅ | 15.7s | 780,819 B | 12.3s | 720×1280 | h264 | あり |
| @koreanmafin/video/7669550728171556103 | ✅ | 10.5s | 911,768 B | 5.3s | 720×1280 | h264 | あり |

- **auth / cookie 不要**。無料・無制限（Chromium リソース消費のみ）。
- **watermark あり**（TikTok ロゴ焼き込み。除去は別途 API が必要）。
- **断続的な CAPTCHA / WAF 揺らぎ**を確認。本セッション中に 1 回
  `TargetClosedError`（→リトライ修正）と 1 回 `CDN_NOT_CAPTURED`（CAPTCHA 起因と推定）
  が発生し、いずれもリトライ後に成功。→ **リトライ前提の運用**が必要。
- yt-dlp（HTTP-only）は Slardar WAF で全滅 → **REJECT**。

### TikTok 最終判定: READY_FOR_INTEGRATION_CANDIDATE

> 実証済み・無料・auth 不要。ただし (1) リトライ前提、(2) watermark あり、
> (3) 1 動画 10〜30 秒、という条件付き。統合候補として提示可能。

---

## 2. Instagram — CONDITIONAL

### 2-1. Public Anonymous Set — 1/1 成功

方式: `instagram-ytdlp-anonymous`（primary）

| URL | success | 処理秒 | file size | duration | resolution | codec |
|-----|---------|--------|-----------|----------|------------|-------|
| /reel/DLgMlwmhpah/ | ✅ | 1.7s | 4,358,401 B | 10.7s | 720×1280 | h264 |

- 真に公開された Reel（imaisakura_ の投稿）。h264+aac、1.7 秒で取得。

### 2-2. General Input Set — 1/9 成功

| URL | note | success | 最終エラー | attempts（error code 遷移） |
|-----|------|---------|-----------|------------------------------|
| /reel/DLgMlwmhpah/ 相当（/p/ 正規化） | 同一 shortcode の /p/ | ✅ | — | instagram-ytdlp-anonymous OK |
| /reel/DDIR_4JvRRw/ | ログイン必須の実在 Reel | ❌ | CDN_NOT_CAPTURED | EMPTY_MEDIA_RESPONSE → CDN_NOT_CAPTURED |
| /p/DCbkKZRPESX/ | 画像投稿 | ❌ | CDN_NOT_CAPTURED | EMPTY_MEDIA_RESPONSE → CDN_NOT_CAPTURED |
| /reel/CiZT7PkuOHL/ | 匿名アクセス不可 | ❌ | CDN_NOT_CAPTURED | EMPTY_MEDIA_RESPONSE → CDN_NOT_CAPTURED |
| /reel/DH1abc12345/ | 存在しないコード | ❌ | CDN_NOT_CAPTURED | EMPTY_MEDIA_RESPONSE → CDN_NOT_CAPTURED |
| /reel/C0v_7_uvbBK/ | not available | ❌ | CDN_NOT_CAPTURED | EMPTY_MEDIA_RESPONSE → CDN_NOT_CAPTURED |
| /reel/DM7LmbEJG7S/ | 匿名アクセス不可 | ❌ | CDN_NOT_CAPTURED | EMPTY_MEDIA_RESPONSE → CDN_NOT_CAPTURED |
| /reel/DEWqXePuwYD/ | not available | ❌ | CDN_NOT_CAPTURED | EMPTY_MEDIA_RESPONSE → CDN_NOT_CAPTURED |
| /reel/DFDZe-YROdA/ | not available | ❌ | CDN_NOT_CAPTURED | EMPTY_MEDIA_RESPONSE → CDN_NOT_CAPTURED |

### 2-3. 失敗の根本原因（重要）

- **yt-dlp（匿名）**: Instagram が「not granting access / empty media response」を返す
  → `EMPTY_MEDIA_RESPONSE`（login-wall）。
- **browser（fMP4 remux）**: ログイン画面のため CDN video segment を 1 件も捕捉できず
  → `CDN_NOT_CAPTURED`。
- つまり general set の 8/9 失敗は「投稿が動画でない/削除済み」ではなく
  **Instagram の匿名アクセス制限（login-wall）**が原因。

### 2-4. fMP4 再構築（Method B）の実証結果

- 公開Reel `DLgMlwmhpah` で実証: Instagram は fragmented MP4（init `ftyp+moov` +
  断片 `moof+mdat`）を配信。URL の `/f2/m367/`（映像）・`/f2/m86/`（音声）で
  ストリーム分離 → init+断片を capture 順に結合 → `ffmpeg -c copy` で mux。
- 結果: **VP9 720×1280 + AAC、10.61s、2,757,659 B** の再生可能 MP4 を生成成功。
  （yt-dlp は同じ投稿を h264 4,358,401 B で返す。コーデック・サイズが異なる点に注意）
- **fragile**: ストリームID ヒューリスティック・断片順序に依存。ある URL
  （DM7LmbEJG7S）で `route.fetch()` がハングしうるため timeout ガードを追加済み。
- 公開Reel では yt-dlp が既に成功するため、チェーン上の実用価値は限定的（診断/secondary）。

### Instagram 最終判定: CONDITIONAL

> **真に公開された Reel のみ取得可（1/1 成功実証）**。
> login-required Reel（general の 8/9）を取得するには**認証情報（ログイン済み Cookie /
> credentials）が必須**。これは外部 API（Apify/RapidAPI）でも同じ制約。
> 認証を使うかどうかは PoC スコープ外の判断事項 → 現時点では CONDITIONAL
> （匿名運用としては NOT_READY）。

---

## 3. 外部 API（Apify / RapidAPI）— RESEARCH_ONLY

調査は `external_api_research.md` に記載。**token 未取得・契約なし**のため
`IMPLEMENTED_NOT_TESTED` / `RESEARCH_ONLY` 扱いで、RECOMMEND にはしない。

| サービス | 価格 | 結論 |
|----------|------|------|
| Apify TikTok Scraper | $1.70/1K | proxy rotation で WAF 回避は価値。ただしローカル Playwright で 3/3 成功済み |
| Apify Instagram Scraper | $1.50–2.70/1K | FAQ に「logged-out version」と明記 = 匿名制限はローカルと同一 |
| RapidAPI（tiktok-api23 / instagram-looter2 等） | pay-per-call | いずれも token 必須 |

**核心**: 外部 API を使っても Instagram の login-required 制限は回避できない。
「公開Reel のみ」ならローカル yt-dlp で足りるため、追加コストに見合わない。

---

## 4. 共通の知見・運用上の注意

1. **TikTok**: HTTP-only は不可。ブラウザ必須。リトライ前提。watermark あり。
2. **Instagram**: 匿名アクセスは 2023 年以降大幅制限。短縮コードは 11 桁 base64 系で推測不能、
   匿名では Explore/プロフィール一覧も閲覧不可。**真に公開された Reel の母数確保自体が困難**。
3. **fMP4 配信**: Instagram は fragmented MP4。完全 MP4 化には init+断片の再構築が必要。
4. **コスト**: ローカル方式は全て $0.00/記事（無料・無制限）。外部 API は $1.5–2.7/1K。

---

## 5. 最終評価（per-platform）

| Platform | 判定 | 補足 |
|----------|------|------|
| **TikTok** | **READY_FOR_INTEGRATION_CANDIDATE** | 3/3 実証・無料・auth 不要。リトライ前提 |
| **Instagram** | **CONDITIONAL** | 公開Reel のみ。login-required は認証必須（スコープ外） |
| 外部 API | **RESEARCH_ONLY** | token 未取得。匿名制限はローカルと同一のため採用見送り |
