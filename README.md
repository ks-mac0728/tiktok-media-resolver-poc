# TikTok Media Resolver PoC

公開TikTok URLから動画Media（MP4）を取得可能かを検証する独立PoCプロジェクト。

## 目的

- TikTok URL → download URL → MP4取得 → local保存 → ffprobe検証 のパイプラインを検証
- **Playwright**（推奨）・**yt-dlp**・**Apify** の3方式を比較
- 各方式最低3本の公開TikTok URLで検証
- 最終的に RECOMMEND / CONDITIONAL / REJECT の3段階でProvider評価

## 結果サマリー

| Provider | 成功/失敗 | 評価 |
|----------|----------|------|
| **playwright** | ✅ 3/3 | **RECOMMEND** |
| yt-dlp | ❌ 0/3 | REJECT |
| apify | ⏸️ 未実測 | CONDITIONAL |

詳細は [RESULTS.md](./RESULTS.md) を参照。
