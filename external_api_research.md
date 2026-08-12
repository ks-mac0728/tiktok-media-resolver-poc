# External API Research (Step 10)

Apify / RapidAPI の TikTok・Instagram 動画取得系サービスを調査した結果。
**全て RESEARCH_ONLY / IMPLEMENTED_NOT_TESTED**（token未取得・契約なしのため
RECOMMEND にはしない）。

調査日: 2026-08-13

---

## 1. Apify Actors

### TikTok Scraper (`clockworks/tiktok-scraper`)
- 価格: **$1.70 / 1,000 results**（pay-per-event）
- 入力に `videoUrls` を渡すと特定動画を取得可能
- `shouldDownloadVideos: true` で**動画本体を key-value store にダウンロード**可能
- Apify の proxy rotation により、ローカルの WAF/CAPTCHA を回避できる点が価値
- 出力例: `webVideoUrl`, `musicMeta.playUrl`（署名付きCDN URL）
- エラーコード: `POST_NOT_FOUND_OR_PRIVATE`, `POST_SENSITIVE`, `PROFILE_PRIVATE` 等

### Instagram Scraper (`apify/instagram-scraper`)
- 価格: **$1.50〜$2.70 / 1,000 results**
- メタデータ + メディアURL（`displayUrl`, video URL）を返す
- **重要**: FAQ に「The Actor sees the **logged-out version** of the page」と明記。
  つまり**匿名アクセス制限は我々のローカル実装と同一**。
- 「Can I scrape private Instagram profiles? → In general, **no**」

### Instagram Reel Scraper (`apify/instagram-reel-scraper`)
- 131K users（評価 3.8）
- 「Scrape or **download Instagram reels** … and **downloaded video**」
- Reel の動画ダウンロードオプションあり（要 token）

## 2. RapidAPI

- `Lundehund/tiktok-api23` — TikTok API（30+ endpoints、Post/Search/User/Ads/Trending）
- `irrors-apis/instagram-looter2` — 「99.99% Success Guarantee」を謳う Instagram 取得
- 多数の Instagram scraper（安定版・高速・最安を謳うもの多数）
- いずれも pay-per-call / subscription（token必須）

## 3. 結論

| 項目 | 判定 | 理由 |
|------|------|------|
| TikTok（外部API） | CONDITIONAL | proxy rotation でWAF回避は価値あり。ただしローカルPlaywrightで既に3/3成功。コスト$1.70/1K |
| Instagram（外部API） | RESEARCH_ONLY | 匿名アクセス制限はローカルと同一（logged-out version）。login-required Reel は外部APIでも取得不可。credentials提供が必須 |
| 採用判断 | 今回は採用しない | token未取得・契約なし。不正な契約/課金は行わない |

## 4. 重要な帰結

Instagram の **login-required Reel（＝GENERAL_INPUT_SET の大半）を取得するには、
どの方式でも「認証情報（ログイン済みCookie / credentials）」が必須**であり、
これは外部APIでも同じ制約。つまり:
- 外部APIは「公開Reelのみ」なら追加価値が薄い（ローカルyt-dlpで足りる）
- ログイン必須Reelの取得には、いずれにせよユーザーのInstagram認証が必要
