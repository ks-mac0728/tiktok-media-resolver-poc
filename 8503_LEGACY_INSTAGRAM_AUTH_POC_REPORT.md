# 8503 LEGACY INSTAGRAM AUTH POC REPORT

> Legacy Authenticated Resolver 移植前 PoC（旧Instagram RPA方式の8503再現検証）
> 検証日: 2026-08-13
> 検証端末: 開発Mac（8503 = `tiktok-media-resolver-poc`）
> 正本参照（READ ONLY）: RPA-Mac `~/livedoorblog-automation-Y/collectors/instagram/upload_videos.py:download_video()`
> 共有資料: `~/Documents/projects/INSTAGRAM_LEGACY_RPA_TECHNICAL_HANDOFF.md`

---

## A. Environment

| 項目 | 値 |
| :--- | :--- |
| 8503 repo | `/Users/saitokosuke/Documents/projects/tiktok-media-resolver-poc` |
| branch | `main` |
| HEAD | `b59097b43b7d7c6542c338f3476ab640806e6172` |
| Python (system) | 3.9.6 |
| Python (yt-dlp bundled) | 3.14.6（`/opt/homebrew/Cellar/yt-dlp/2026.7.4/libexec/bin/python`） |
| yt-dlp version (8503) | **2026.07.04**（`/opt/homebrew/bin/yt-dlp`） |
| RPA-Mac yt-dlp version | **2026.07.04**（`/opt/homebrew/bin/yt-dlp`、PATH未登録） |
| RPA-Mac Python | 3.9.6 |
| ffprobe | 8.1.2（Homebrew） |

**version差なし**。yt-dlp は両端末とも 2026.07.04 で同一。勝手な upgrade/downgrade は実施していない。

---

## B. Browser Session

| 項目 | 値 |
| :--- | :--- |
| Safari login session | **不明**（cookie DB に TCC ブロックがかかり中身を検証不能。`Cookies.binarycookies` は 5441 bytes で存在） |
| Chrome login session | **Default profile = ログイン済み**（`sessionid` あり、有効期限 2027-08-12、加えて `ds_user_id`/`csrftoken`/`datr`/`rur`/`mid`/`ig_did`/`ig_nrcb`/`ps_l`/`ps_n`/`wd` = 計 11 cookies） |
| Chrome Profile 1 | **未ログイン**（`sessionid` なし・`ds_user_id` なし = 5 cookies） |
| Profile | Default（ログイン済み）を今回使用 |
| Cookie access | Chrome = OK（`--cookies-from-browser chrome` が Keychain 復号で取得成功、4310 cookies 抽出）。Safari = **NG（`[Errno 1] Operation not permitted`）** |
| Credential exposed | **NO**（cookie値・sessionid・token は一切ログ/report/git に出していない） |

**Safari cookie DB アクセス不可の原因**（推測でなく実測）:
- 実行ユーザー `saitokosuke` はファイル所有者（`-rw-r--r--`）であり filesystem permission の問題ではない。
- `yt-dlp --cookies-from-browser safari` → `[Errno 1] Operation not permitted: .../Safari/.../Cookies.binarycookies`。
- macOS TCC（プライバシー保護）により、Safari の cookie DB は **Full Disk Access を付与していないプロセスからは読めない**。これが RPA-Mac と 8503 開発Mac の決定的な差（RPA-Mac は Safari ログイン済みで yt-dlp が読めていたが、8503 開発Mac は TCC ブロック）。

---

## C. Control URL

| 項目 | 値 |
| :--- | :--- |
| URL | `https://www.instagram.com/reel/DLgMlwmhpah/` |
| Anonymous | **SUCCESS**（`instagram_results.json`: 4358401 bytes, 10.7s, 720x1280, h264+aac, `auth_required=false`） |
| Legacy Safari cookie | **BLOCKED**（TCC `Operation not permitted`） |
| Legacy Chrome cookie | **SUCCESS**（2.66s、4358401 bytes、complete MP4） |
| MP4 | `/tmp/auth_poc_test/DLgMlwmhpah.mp4` |
| ffprobe | **PASS**（h264 / 720x1280 + aac audio、duration 10.702993s、size 4358401） |

**確認**: 旧 yt-dlp command（`-f "mp4/best[ext=mp4]/best"` + cookie + 単一URL）が 8503 でも正常動作し、音声内包の complete MP4 を1ファイルで取得できる。ただし Control は anonymous でも成功するため、authenticated 方式の有効性は証明しない。

---

## D. Login-wall URL

| 項目 | 値 |
| :--- | :--- |
| URL | `https://www.instagram.com/reel/DDIR_4JvRRw/` |
| Anonymous result (A) | **EMPTY_MEDIA_RESPONSE**（`Instagram API is not granting access` → `empty media response`） |
| Existing 8503 cookie result (B) | `CDN_NOT_CAPTURED`（Phase 1 の Playwright intercept では fMP4 も取得できず） |
| Legacy-equivalent result (C) | **HTTP 400**（`Video info extraction failed: HTTP Error 400: Bad Request`） |

**決定的追加検証（ログイン済みブラウザ実レンダリング）**:
Chrome Default の cookies（sessionid 有効）を Playwright に注入してページを実ロードした結果:

| shortcode | 判定 | ページ本文（抜粋） |
| :--- | :--- | :--- |
| `DLgMlwmhpah`（Control） | **ACCESSIBLE** | 投稿本文・キャプション完全表示（`imaisakura_` /「【全力坂】…」） → 注入成功・ログイン有効の証明 |
| `DDIR_4JvRRw` | **DELETED** | `Sorry, this page isn't available. The link you followed may be broken, or the page may have been removed.` |
| `CiZT7PkuOHL` | **DELETED** | 同上 |
| `DM7LmbEJG7S` | **DELETED** | 同上 |

**ログイン済みモバイルAPI直接照会**（`/api/v1/media/{id}/info/` + 有効 sessionid）:

| shortcode | 結果 |
| :--- | :--- |
| `DLgMlwmhpah` | HTTP 200, `items=1` |
| `DDIR_4JvRRw` | HTTP 400, `{"message":"Media not found or unavailable","status":"fail"}` |
| `CiZT7PkuOHL` | HTTP 400, 同上 |
| `DM7LmbEJG7S` | HTTP 400, 同上 |

**結論**: 8503 の「login-wall」候補 URL は、実は **削除済み/存在しない media**（「ページが削除された可能性があります」）であり、**真の login-required（非公開アカウント等）ではない**。有効なログインセッションでも API が 400「Media not found or unavailable」を返し、ブラウザ実ロードでも「Sorry, this page isn't available」を表示する。

---

## E. Comparison

| 観点 | 比較結果 |
| :--- | :--- |
| Safari vs Chrome | 旧方式は Safari（yt-dlp 用）+ Chrome（API列挙用）。8503 開発Mac では Safari cookie が **TCC ブロック**（Operation not permitted）で読めない。Chrome は Keychain 復号で読める（ログイン済み Default profile）。 |
| 8503 vs RPA | yt-dlp version 同一（2026.07.04）。RPA-Mac は Safari ログイン済み + Chrome Profile 1 ログイン済み。8503 は Chrome Default ログイン済み（sessionid 有効・新鮮）+ Safari アクセス不可。 |
| yt-dlp versions | **同一**（2026.07.04 / 2026.07.04）。version差は原因ではない。 |
| command differences | 旧: `--cookies-from-browser safari` + ランダムUA + `--sleep-requests 1 --sleep-interval 1 --max-sleep-interval 3`（大量実行のアンチ検知用）。今回: `--cookies-from-browser chrome` + UA/sleep なし（1 URL のみなので不要）。 |
| cookie source differences | 旧 = Safari。今回 = Chrome（Safari が TCC ブロックのため）。いずれも「ログイン済み IG セッション」を供給する点で等価。 |
| 真の原因 | login-wall ではなかった。テスト URL が **削除済み media** だった。cookie/session/auth の問題ではない。 |

---

## F. Result

**INCONCLUSIVE**

理由（推測でなく実測）:
1. **login-wall 突破は未実証**: 8503 の「login-wall」候補 URL はすべて削除済み/存在しない media であり、有効ログインでも API 400「Media not found or unavailable」・ブラウザ実ロードでも「page isn't available」。**検証すべき「真の login-required URL」がテストセットに存在しない**ため、本命の検証が成立していない。
2. **旧方式そのものの再現は一部確認**: yt-dlp + cookies 方式は 8503 で公開コンテンツ（Control）に対し complete MP4 取得成功（音声内包・ffprobe PASS）。ただし Control は anonymous でも成功するため、authenticated の有効性証明にはならない。
3. **Safari（旧と同一条件）は TCC ブロック**: `--cookies-from-browser safari` は `Operation not permitted`。Chrome は同等に機能するが、旧方式と完全同一条件での再現は Safari 権限の都合で不可。

（`LEGACY_AUTH_RESOLVER_REPRODUCED` でも `NOT_REPRODUCED` でもなく、判定不能。）

---

## G. Integration Recommendation

**NEEDS_MORE_POC**

理由:
1. authenticated resolver（yt-dlp + cookies）が 8503 で**公開コンテンツを取得できることは実証済み**（complete MP4 取得成功）。
2. ただし **login-wall 突破は未実証**。次フェーズで以下が必要:
   - **真の login-required Reel URL を1本用意**（例: ログイン中セッションがフォローしている非公開アカウントの Reel、またはログイン必須ゲートがかかった実在 Reel）。
   - **Safari TCC の解決**（Full Disk Access 付与）または **Chrome cookie 方式への標準化**を決める。
3. 現時点で 8503 本体（`resolve_media.py` / fallback chain / `app.py`）への統合は行わない。

---

## H. Safety

| 項目 | 値 |
| :--- | :--- |
| LA2 changes | 0 |
| 8502 changes | 0 |
| Production writes | 0 |
| R2 writes | 0 |
| Livedoor writes | 0 |
| Credentials committed | 0 |
| 旧RPA repo changes | 0（READ ONLY） |

---

## 補足: 次フェーズへの引き継ぎ（本 PoC では実施しない）

1. 真の login-required URL（非公開アカウントの Reel 等）を1本用意し、`--cookies-from-browser chrome`（Default profile）で complete MP4 取得 → ffprobe まで確認。
2. Safari TCC を解決（Full Disk Access 付与）して旧方式と完全同一条件（`--cookies-from-browser safari`）でも再検証。
3. 成功すれば 8503 の Instagram Resolver は「yt-dlp + cookies-from-browser」を primary 方式として採用、`instagram_fmp4_remux.py` をフォールバック降格候補とする（今回 fMP4 は触っていない・削除しない）。
