# TikTok / Instagram Media Resolver PoC

公開 SNS URL から動画 Media（MP4）を取得できるか、どの方式が最適かを検証する独立 PoC。

> **本 PoC は完全に独立**。LA2 repo（`la2-manual-social-asset-builder` / `-v2`）および
> 本番インフラ（Production Sheets / R2 / Livedoor / AtomPub / GAS / Manual Builder）へは
> **一切接続しない**。成果物は「取得できるか」の実証と、統合可能な Contract の提示まで。

---

## 結論（要約）

| Platform | 判定 | 実測 | 根拠 |
|----------|------|------|------|
| **TikTok** | **READY_FOR_INTEGRATION_CANDIDATE** | 3/3 成功 | Playwright+Chromium の CDN intercept で安定取得。h264 720×1280 |
| **Instagram** | **CONDITIONAL** | public 1/1, general 1/9 | 真に公開された Reel のみ取得可。login-required は認証必須 |

### 核心的な知見

1. **TikTok は HTTP-only では取得不能**（Slardar WAF が JS 実行を必須とする）。
   yt-dlp 等は全滅。**Playwright + Chromium で CDN リクエストを `route.fetch()` 捕捉**する方式のみ成功。
2. **Instagram は 2023 年以降、匿名アクセスを大幅制限**。ログイン不要で再生できる
   「真に公開された Reel」は極めて稀少。**login-required Reel を取得するには
   どの方式でも認証情報（ログイン済み Cookie / credentials）が必須**であり、
   これは外部 API（Apify/RapidAPI）でも同じ制約。
3. 詳細は [RESULTS.md](RESULTS.md) 参照。

---

## アーキテクチャ

```
tiktok-media-resolver-poc/
├── README.md                     # 本ファイル
├── RESULTS.md                    # 実測結果 + per-platform 最終評価
├── results.json                  # 実測マトリクス（13 URL、成功/失敗/attempts/ffprobe）
│
├── resolver_contract.py          # ★ Common Contract（MediaResolveResult / ResolveAttempt / MediaMetadata）
├── error_codes.py                # ★ エラー分類（LOGIN_REQUIRED / EMPTY_MEDIA_RESPONSE / CDN_NOT_CAPTURED …）
├── resolve_media.py              # ★ 統合エントリポイント resolve_media(url) → MediaResolveResult（fallback chain）
│
├── resolver_test.py              # TikTok 基盤（PlaywrightResolver / ffprobe / Apify 未実測枠）
├── tiktok_adapter.py             # Adapter: TikTok → MediaResolveResult（内部ロジックは不変更）
├── instagram_resolver.py         # Instagram 基盤（yt-dlp / Playwright 診断）
├── instagram_adapter.py          # Adapter: Instagram yt-dlp / browser → MediaResolveResult
├── instagram_fmp4_remux.py       # Instagram fMP4 断片再構築（Method B、VP9 出力）
│
├── test_urls.py                  # テストURLセット（Public Anonymous / General / TikTok）
├── run_matrix.py                 # 実測マトリクスランナー（results.json 生成）
├── run_method_a.py               # Method A（yt-dlp 匿名）単体ランナー
├── external_api_research.md      # Apify/RapidAPI 調査結果（RESEARCH_ONLY）
│
├── app.py                        # Streamlit UI（:8503、attempt history / エラーコード表示）
│
├── .env                          # （gitignore）Apify token 等
├── data/                         # （gitignore）PoC専用ブラウザプロファイル
├── downloads/                    # （gitignore）取得 MP4 保存先
└── _test_*.py / _debug_*.py      # 調査用スクリプト（fMP4再構築の実証 等）
```

### Common Contract（resolver_contract.py）

全 Platform / 全方式が統一の `MediaResolveResult` を返す。

```python
@dataclass
class MediaResolveResult:
    url, canonical_url, platform, shortcode   # 入力情報
    success, final_method                      # 最終結果
    downloaded_file_path                       # ローカル保存 MP4 パス
    metadata: MediaMetadata                    # ffprobe（duration/width/height/codec/has_audio）
    attempts: list[ResolveAttempt]             # ★ 全方式の試行履歴（#8）
    error_code, error_message                  # 最終エラー + 日本語メッセージ
    total_seconds, estimated_cost_article      # 所要時間 / 記事あたりコスト
```

`ResolveAttempt` は 1 方式の試行を記録する（`method / success / error_code /
processing_seconds / downloaded_file_size / auth_required / rate_limited`）。

### Fallback chain（resolve_media.py）

成功が実証された方式**のみ**をチェーンに採用（失敗方式は REJECT、チェーンに入れない）。

```
TikTok:
  tiktok-playwright           （3/3 成功実証、単一方式で足りる）

Instagram:
  instagram-ytdlp-anonymous   （primary: h264 完全MP4、公開Reelで成功実証）
  instagram-browser-fmp4-remux（secondary: fMP4再構築、VP9。公開Reelで成功実証）
  ※ 外部API（Apify/RapidAPI）は RESEARCH_ONLY のため実行チェーンに含めない
```

---

## 使い方

```bash
# 事前準備
pip3 install playwright streamlit python-dotenv
playwright install chromium
brew install ffmpeg yt-dlp

# 1. 実測マトリクス（13 URL）を実行 → results.json 生成
python3 run_matrix.py

# 2. 単一 URL を resolve_media で解決
python3 -c "from resolve_media import resolve_media; print(resolve_media('URL').summary())"

# 3. Streamlit UI（手動テスト・attempt history 表示）
python3 -m streamlit run app.py --server.port 8503

# 4. Method A（yt-dlp 匿名）単体
python3 run_method_a.py
```

### 記録項目

`results.json` の各エントリに記録: `success / error_code / error_message /
wall_seconds（処理秒）/ metadata.file_size / metadata.duration / width / height /
codec / has_audio / attempts（方式ごとの成功・エラー・所要時間）/ set（URLセット）`。
watermark・auth・rate-limit は attempt 単位で記録される。

---

## 方式別評価

### TikTok

| 方式 | 結果 | 判定 |
|------|------|------|
| `tiktok-playwright`（Chromium CDN intercept） | 3/3 成功、h264 720×1280 | **採用（RECOMMEND）** |
| `yt-dlp`（HTTP-only） | Slardar WAF で全滅 | REJECT |
| `apify-*` | 未実測（token なし） | RESEARCH_ONLY |

- 無料・無制限・auth 不要。1 動画 10〜30 秒（Chromium 起動が支配的）。
- **watermark あり**（TikTok ロゴが焼き込まれる。除去は別途 API が必要）。
- **断続的な CAPTCHA が発生**（実測で数回に 1 回）。`MAX_RETRIES=2` + 例外リトライで吸収。
  完全な 100% 安定ではなく、**リトライ前提の運用**が必要。

### Instagram

| 方式 | 結果 | 判定 |
|------|------|------|
| `instagram-ytdlp-anonymous` | 公開Reel 1/1 成功、h264 | **採用（primary）** |
| `instagram-browser-fmp4-remux` | 公開Reel で成功実証、VP9。fragile | 採用（secondary、time-box 内で実証） |
| `instagram-browser`（login なし） | 匿名と同一制限 | 診断用 |
| 外部 API（Apify/RapidAPI） | logged-out version = 匿名と同一制限 | RESEARCH_ONLY |

- **真に公開された Reel のみ取得可**。login-required Reel（general の大半）は
  `EMPTY_MEDIA_RESPONSE`（yt-dlp）/ `CDN_NOT_CAPTURED`（browser）。
- 取得には **credentials（ログイン済み Cookie）が必須**。これは PoC スコープ外。
- fMP4 再構築は「Instagram 配信は fragmented MP4 で、init+moof 断片を
  ストリームID（/f2/m367/ 映像, /f2/m86/ 音声）で分離結合 → ffmpeg で mux」する方式。
  公開Reel では VP9 出力で成功するが、ヒューリスティック依存で fragile。

---

## 統合準備（8502-integratable contract）

本 PoC の成果は `resolve_media(url) -> MediaResolveResult` という単一関数に集約される。
これは他サービス（例: 8502 で稼働する Builder 等）が import 可能な形に設計してある。

- `resolver_contract.py` / `error_codes.py` / `resolve_media.py` の 3 ファイルが公開インターフェース。
- `attempts` 履歴・`error_code`（日本語メッセージ付き）・ffprobe metadata を返す。
- **本フェーズでは LA2 / 8502 への接続は一切行っていない**（契約の提示までで停止）。

---

## 禁止事項（本 PoC の絶対ルール）

- ❌ LA2 repo（`la2-manual-social-asset-builder` / `-v2`）の変更
- ❌ Production Sheets / R2 / Livedoor / AtomPub / GAS の使用
- ❌ Manual Builder 接続
- ❌ Scene 抽出 / 記事生成
- ❌ 認証情報・Cookie の git/results/logs への漏出（`data/`・`.env` は gitignore 済み）
