# TikTok Media Resolver PoC — Results

Generated: 2026-08-12T00:42:46Z

---

## サマリー

| Provider | 成功/失敗 | 平均時間 | 1記事あたりコスト | 評価 |
|----------|----------|---------|-----------------|------|
| **playwright** | ✅ 3/3 | 17.5s | $0.00 | **RECOMMEND** |
| yt-dlp | ❌ 0/3 | 0.8s | $0.00 | **REJECT** |
| apify-tiktok-video-scraper | ⏸️ 未実測 | — | $0.01/video | **CONDITIONAL** |
| apify-tiktok-scraper | ⏸️ 未実測 | — | $0.017/video | **CONDITIONAL** |

> ⚠️ **Apify未実測**：APIFY_API_TOKEN未設定のため実測なし。token設定後 `python3 resolver_test.py --provider apify --use-sample-urls` で3URL検証可能。実測前のRECOMMEND評価は不可（PoCルール準拠）。

---

## Provider別詳細

### 1. Playwright（RECOMMEND）

**方式**: Playwright + Chromium headless → TikTok CDN動画リクエストを `route.fetch()` で捕捉 → MP4保存

**結果**: 3/3 成功（100%）

| URL | 時間 | サイズ | 長さ | 解像度 | コーデック |
|-----|------|--------|------|--------|-----------|
| @yuto1855/7669733182761192711 | 17.5s | 2.96 MB | 11.8s | 720×1280 | H.264 High |
| @minnakowaikarayada7/7671211573863517458 | 15.0s | 2.10 MB | 11.2s | 720×1280 | H.264 High |
| @zuttowakaku/7670096015315242247 | 19.9s | 9.43 MB | 66.4s | 720×1280 | H.264 High |

**技術的詳細**:
- TikTok Slardar WAF突破: 実際のChromiumブラウザがJavaScriptを実行するため、WAFチャレンジを自然に通過
- CDN URLパターン: `v16-webapp-prime.tiktok.com/video/tos/...`
- 音声: AAC HE-AACv2, 44100Hz stereo
- フレームレート: 30fps
- ウォーターマーク: TikTokロゴ埋め込みあり（CDNから直接取得のため除去不可）
- auth不要（公開動画のみ）
- rate-limit: 検出されず（短期3本のテストでは）

**Pros**:
- 無料・無制限
- WAFを確実に突破（実ブラウザ）
- 依存パッケージ最小（playwright + ffmpeg）
- コードベース簡潔（~40行のコアロジック）

**Cons**:
- 1動画あたり12-20秒（Chromium起動+ページロード）
- Chromiumリソース消費（~300MB RAM/インスタンス）
- バッチ処理には適さない（シーケンシャル実行推奨）
- TikTokのHTML構造変更に脆弱（CDN URLパターンが変わると追従が必要）

---

### 2. yt-dlp（REJECT）

**方式**: yt-dlp CLI → TikTok extractor → HTTP download

**結果**: 0/3 成功（0%）

| URL | エラー |
|-----|--------|
| @tiktok/7231339977841454382 | `Your IP address is blocked from accessing this post` |
| @charlidamelio/7151481841681878314 | `Unable to extract universal data for rehydration` |
| @khaby.lame/7008734934864276741 | `Unable to extract universal data for rehydration` |

**拒否理由**:
1. **TikTok Slardar WAFの完全ブロック**: yt-dlpのHTTP-onlyアプローチはTikTokのJavaScriptベースWAFを突破できない
2. **`SIGI_STATE` / `__UNIVERSAL_DATA__` 削除**: TikTokが2024-2025年にページ内の埋め込みデータ構造を変更し、yt-dlpのextractorが対応できていない
3. **impersonation target不在**: macOS環境ではyt-dlpのimpersonation機能が利用不可

---

### 3. Apify TikTok Video Scraper（CONDITIONAL）

**Actor**: `clockworks/tiktok-video-scraper`
**URL**: https://apify.com/clockworks/tiktok-video-scraper
**料金**: $1.00/1,000 videos（Free枠 $5/月 = 500 videos無料）
**1記事あたり**: $0.01（動画1本）
**認証**: API Token（Apify Console → Settings → Integrations）

**入力**:
```json
{
  "postURLs": ["https://www.tiktok.com/@user/video/12345"],
  "shouldDownloadVideos": true,
  "shouldDownloadCovers": false
}
```

**出力**（Dataset）:
```json
{
  "webVideoUrl": "https://www.tiktok.com/@user/video/12345",
  "text": "キャプション",
  "authorMeta": {"name": "user"},
  "videoMeta": {"duration": 11.8},
  "diggCount": 1234
}
```

**動画取得**: Key-Value Store → `{video_id}.mp4` として保存

**実装状態**: `resolver_test.py` 内の `ApifyResolver` クラスで完全実装済み。以下のコマンドで即時実行可能:

```bash
# 1. 環境準備
pip3 install apify-client python-dotenv
# 2. .env にトークン設定
echo "APIFY_API_TOKEN=apify_api_..." > .env
# 3. 実行
python3 resolver_test.py --provider apify --use-sample-urls
```

---

### 4. Apify TikTok Scraper（CONDITIONAL）

**Actor**: `clockworks/tiktok-scraper`
**URL**: https://apify.com/clockworks/tiktok-scraper
**料金**: $1.70/1,000 results（Free枠 $5/月 = 294 results無料）
**1記事あたり**: $0.017（動画1本）
**認証**: 同上（API Token）

**入力**:
```json
{
  "videoUrls": ["https://www.tiktok.com/@user/video/12345"],
  "shouldDownloadVideos": true
}
```

**特徴**: tiktok-video-scraperより高機能（プロフィール全体・ハッシュタグ・検索対応）だが単一動画取得にはオーバースペック。1本あたりコストが70%高い。

---

## アーキテクチャ比較

| 観点 | Playwright | Apify | yt-dlp |
|------|-----------|-------|--------|
| WAF突破 | ✅ 実ブラウザ | ✅ 専用IPローテーション | ❌ HTTP only |
| コスト | 無料 | $0.01-0.017/video | 無料 |
| 速度 | 12-20s | 10-30s（推定） | 1-2s（成功時） |
| 信頼性 | ⚠️ HTML構造依存 | ✅ SaaS運用 | ❌ 構造変化で即死 |
| 依存 | playwright + chromium | apify-client + token | yt-dlp |
| スケーラビリティ | 低（1プロセス） | 高（並列run可能） | 中 |
| 運用負荷 | 中（ブラウザ更新） | 低（SaaS） | 低 |

---

## 最終評価

### RECOMMEND: Playwright + CDN Intercept

PoCの目的「公開TikTok URLから動画Mediaを**取得できるか**」に対して、唯一3/3成功。

**推奨シナリオ**: 1日数十本程度の低頻度取得、コストゼロ運用が求められるケース。

### CONDITIONAL: Apify TikTok Video Scraper

実測待ち。理論上はPlaywrightより安定（SaaSのIPローテーション + 専用メンテナンス）。月500本まで無料。

**条件**: 実測で3/3成功し、かつ速度・信頼性がPlaywrightを上回る場合、自動化パイプライン向けに有望。実測が取れ次第RECOMMENDに格上げ可能。

### REJECT: yt-dlp

TikTok Slardar WAFにより完全ブロック。`SIGI_STATE`削除後のHTML構造変更にもextractorが追従できていない。現状のTikTokに対しては実用不可。

---

## ファイル構成

```
tiktok-media-resolver-poc/
├── README.md           # プロジェクト説明・使い方
├── resolver_test.py    # 検証スクリプト（3Provider実装）
├── results.json        # 構造化テスト結果（本ファイルの元データ）
├── RESULTS.md          # 本ファイル
├── .env                # Apify API Token（gitignore）
├── .gitignore
├── downloads/          # 取得MP4（gitignore）
└── _test_*.py          # 研究用診断スクリプト（参考）
```
