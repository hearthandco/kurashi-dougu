# 楽天LP自動作成キット — AIアシスタント向け説明書

このファイルは、Claude Code（CLAUDE.md）や ChatGPT の Codex（AGENTS.md）などのAIアシスタントが、
このフォルダで作業するときに最初に読む説明書です。利用者はプログラミング初心者です。
**専門用語を避け、やさしい日本語で、1ステップずつ**説明してください。

## このキットは何か
楽天ランキングから売れ筋商品を探し → 文章作成AI（Gemini / ChatGPT / Claude のどれか）で紹介ページ（LP）を作り →
品質チェックして → GitHub Pages（または Cloudflare）に公開する、Python製の自動化ツールです。
Windows と Mac の両方で動きます。標準ライブラリ＋`requests` だけで動きます。

## フォルダの地図
| 場所 | 役割 |
|---|---|
| `0_〜7_*.bat`（Windows） / `Mac用/*.command`（Mac） | 利用者がダブルクリックで使う起動ファイル |
| `tools/rakuten-lp/run_daily.py` | メイン処理（商品探し→AIで作成→チェック→公開） |
| `tools/rakuten-lp/config.json` | 設定（サイト名・作成本数・AIの種類・ジャンル等）。利用者が編集してよい |
| `tools/rakuten-lp/secrets.env` | **APIキー。絶対に表示・送信・コミットしない** |
| `tools/rakuten-lp/gemini.py` | 文章作成AIの呼び出し（gemini / openai / claude を切り替え） |
| `tools/rakuten-lp/writer.py` | AIへの指示文（分析・執筆・レビュー） |
| `tools/rakuten-lp/quality.py` | 捏造・誇張・薬機法/景表法表現・重複・HTMLのチェック |
| `tools/rakuten-lp/render.py` / `listing.py` | LP・一覧ページのHTML |
| `tools/rakuten-lp/data/` | 商品DBとLP原稿（消さない） |
| `tools/rakuten-lp/logs/` | 実行ログ（エラー調査はまずここの最新 `run_*.log` を読む） |
| `tools/kit/` | セットアップ・接続テスト・自動実行登録・デモ・取り下げ |
| `products/`, `index.html` など | 公開されるサイト本体（自動生成） |

## よく使うコマンド（キットのフォルダで実行）
- Windows は `python`（または `py -3`）、Mac は `python3` を使う。
- ネット不要の動作確認: `python tools/kit/demo.py`
- 接続テスト: `python tools/kit/check_setup.py`
- 1本だけ作る（公開しない）: `python tools/rakuten-lp/run_daily.py --limit 1 --no-push`
- APIを使わないテスト: `python tools/rakuten-lp/run_daily.py --mock --no-push --limit 3 --categories beauty,living`
- 本番（作成して公開）: `python tools/rakuten-lp/run_daily.py`
- 自動実行の確認: `python tools/kit/schedule_task.py --status`

## 必ず守るルール
1. **`secrets.env` の中身（APIキー・ID）を画面に出さない・チャットに書かない・Gitにコミットしない。** `.gitignore` を消さない。
2. プログラムを変更したら、公開する前に必ず `--mock --no-push` と `--limit 1 --no-push` で動作確認する。
3. `quality.py` の禁止表現チェック、PR表記、`rel="sponsored"`、楽天画像を加工しないルール、捏造防止のチェックを**弱めたり外したりしない**（楽天アフィリエイトの規約・ステマ規制・景品表示法・薬機法を守るため）。
4. `tools/rakuten-lp/data/` と `products/` のファイルを手で大量に消さない。ページの取り下げは `tools/kit/remove_page.py` を使う。
5. `git push --force`、履歴の書き換え、リポジトリの削除はしない。
6. 楽天APIのエラー `CLIENT_IP_NOT_ALLOWED` は、利用者のIPアドレスが変わったことが原因。楽天ウェブサービスの「許可されたIPアドレス」の更新を案内する（コードの問題ではない）。
7. 利用者にコマンドを実行してもらうときは、Windows と Mac の両方の書き方を示す。
8. 大きな変更をするときは、先に「何を・なぜ変えるか」を説明して了承を得る。
