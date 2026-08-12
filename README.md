# TikTok Media Resolver PoC

公開TikTok URLから動画Media（MP4）を取得可能かを検証する独立PoCプロジェクト。

## 目的

- TikTok URL → download URL → MP4取得 → local保存 → ffprobe検証 のパイプラインを検証
- **Playwright**（推奨）・**yt-dlp**・**Apify** の3方式を比較
- 各方式最低3本の公開TikTok URLで検証
- 最終的に RECOMMEND / CONDITIONAL / REJECT の3段階でProvider評価

## ディレクトリ構成

```
tiktok-media-resolver-poc/
├── README.md           # 本ファイル
├── resolver_test.py    # 検証スクリプト
├── results.json        # 構造化結果（テスト実行後に生成）
├── RESULTS.md          # 人間向け要約＋最終評価（テスト実行後に生成）
├── .env                # Apify API Token（gitignore対象）
├── .gitignore
└── downloads/          # 取得MP4保存先（gitignore対象）
```

## 事前準備

```bash
# Playwright（推奨）+ ffprobe が必要
pip3 install playwright
playwright install chromium
brew install ffmpeg

# yt-dlp も使う場合
brew install yt-dlp

# Apifyを使う場合（要API Token）
pip3 install apify-client python-dotenv
# .env に APIFY_API_TOKEN=your_token を記入
```

## 使い方

```bash
# 1. Playwright でテスト（推奨・3/3成功実証済み）
python3 resolver_test.py --provider playwright --use-sample-urls

# 2. 個別URLでテスト
python3 resolver_test.py --provider playwright --urls "URL1" "URL2" "URL3"

# 3. yt-dlp のみ（全滅することを確認用）
python3 resolver_test.py --provider ytdlp --use-sample-urls

# 4. Apify（.envにtokenが必要）
python3 resolver_test.py --provider apify --use-sample-urls

# 5. 全Providerテスト
python3 resolver_test.py --provider all --use-sample-urls
```

### 出力

- `results.json` - 全テスト結果（成功/失敗、所要時間、ファイルサイズ、ffprobe結果など）
- `RESULTS.md` - 人間向け要約＋ RECOMMEND / CONDITIONAL / REJECT 評価
- `downloads/` - 取得したMP4ファイル
```

## 検証対象Provider

### 1. Playwright（⭐ RECOMMEND）
- Playwright + Chromium headlessでTikTok WAFを突破
- CDN動画リクエストを `route.fetch()` で捕捉しMP4保存
- 無料・無制限・auth不要
- 1動画12-20秒（Chromium起動+ページロード）
- 実測: **3/3成功**（720×1280, H.264 High, 30fps）

### 2. yt-dlp（❌ REJECT）
- オープンソースの動画ダウンローダー
- TikTok extractor内蔵
- 無料・無制限
- auth不要（公開動画のみ）
- リスク: TikTokのanti-bot対策によるブロック

### 3. Apify TikTok Video Scraper（⏸️ CONDITIONAL）
- Actor名: `clockworks/tiktok-video-scraper`
- URL: https://apify.com/clockworks/tiktok-video-scraper
- 入力: `postURLs`（TikTok動画URLの配列）
- 動画ダウンロード: `shouldDownloadVideos: true` でKey-Value Storeに保存
- 料金: $1.00 / 1,000 videos（Freeプランで月$5クレジット = 500 videos無料）
- 認証: API Token（Apify Console → Settings → Integrations）
- API: `apify-client` Pythonパッケージ経由でREST API呼び出し
- レスポンス: Datasetにメタデータ（JSON）、Key-Value Storeに動画ファイル

### 4. Apify TikTok Scraper（⏸️ CONDITIONAL）
- Actor名: `clockworks/tiktok-scraper`
- URL: https://apify.com/clockworks/tiktok-scraper
- 入力: `videoUrls` または `profiles`/`hashtags`/`search`
- 動画ダウンロード: `shouldDownloadVideos: true`
- 料金: $1.70 / 1,000 results
- こちらも実装済み（resolver_test.py で両方対応）

## 記録項目

| 項目 | 説明 |
|------|------|
| success | 取得成否 |
| failure_reason | 失敗理由 |
| processing_seconds | 処理時間（秒） |
| downloaded_file_size | ファイルサイズ（bytes） |
| duration | 動画長（秒） |
| width/height | 解像度 |
| codec | コーデック |
| watermark | watermark有無 |
| auth_required | 認証/cookie要否 |
| rate_limited | rate-limit/block有無 |
| estimated_cost_article | 記事1本あたり推定コスト |

## 禁止事項

- LA2 repo変更禁止
- Production Sheets / R2 / Livedoor 不使用
- Manual Builder接続禁止
- Scene抽出 / 記事生成禁止
