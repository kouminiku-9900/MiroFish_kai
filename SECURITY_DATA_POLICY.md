# Security Data Policy

このリポジトリで扱うデータを、`公開してよいもの` と `公開してはいけないもの` に分けるための実務用メモです。

## 公開してはいけないもの

- 実キー / 実トークン
  - `GOOGLE_AI_API_KEY`
  - `ZEP_API_KEY`
  - `LLM_BOOST_API_KEY`
  - `LLM_API_KEY`（互換用でも実値なら非公開）
  - `SECRET_KEY`
- ルートの [`.env`](/Users/udzur/Documents/Mirofish_kai/.env)
- ローカル生成ログ
  - [`log/`](/Users/udzur/Documents/Mirofish_kai/log)
  - [`backend/logs/`](/Users/udzur/Documents/Mirofish_kai/backend/logs)
- アップロード元データとその派生物
  - [`backend/uploads/`](/Users/udzur/Documents/Mirofish_kai/backend/uploads)
  - ユーザーが投入した PDF / MD / TXT
  - そこから生成されたシミュレーション設定、プロフィール、レポート、会話ログ
- セッション系 / 一時ファイル
  - `.backend.pid`
  - `.frontend.pid`
  - `*.pid`
- 証明書 / 秘密鍵 / ローカルDB
  - `*.pem`
  - `*.key`
  - `*.crt`
  - `*.p12`
  - `*.sqlite`, `*.sqlite3`, `*.db`
- テストデータ一式
  - [`test_data/`](/Users/udzur/Documents/Mirofish_kai/test_data)

## 条件付きで公開してよいもの

- [`.env.example`](/Users/udzur/Documents/Mirofish_kai/.env.example)
  - プレースホルダのみなら公開可
  - 実キーを絶対に入れない
- [`README.md`](/Users/udzur/Documents/Mirofish_kai/README.md), [`README-EN.md`](/Users/udzur/Documents/Mirofish_kai/README-EN.md)
  - 例示値のみなら公開可
  - 実運用 URL、内部ホスト名、個人環境パスは載せない
- ビルド成果物 / スクリーンショット / レポート例
  - ダミーデータであれば公開可
  - 実ユーザーデータ由来なら非公開

## 公開してよいもの

- ソースコード
  - `frontend/src/`
  - `backend/app/`
  - `backend/scripts/`
- 設定テンプレート
  - [`.env.example`](/Users/udzur/Documents/Mirofish_kai/.env.example)
  - [`docker-compose.yml`](/Users/udzur/Documents/Mirofish_kai/docker-compose.yml)
  - [`start.sh`](/Users/udzur/Documents/Mirofish_kai/start.sh)
- ドキュメント
  - README
  - 設計メモ
  - 公開前提の図や説明資料
  - ただし、個人連絡先、コミュニティ QR、顔写真入りサムネイルは含めない

## この repo で今すぐ注意すべき点

- ルートに [`.env`](/Users/udzur/Documents/Mirofish_kai/.env) がある。Git ignore 対象だが、共有・添付・画面共有では露出に注意。
- [`backend/app/config.py`](/Users/udzur/Documents/Mirofish_kai/backend/app/config.py) は `SECRET_KEY` 未設定時にランダム値を生成する。
  - ローカル開発では動くが、再起動でセッションが無効化されるため、継続利用時は `.env` で明示設定する。
- `start.sh` は `.backend.pid` と `.frontend.pid` を生成する。
  - これは公開価値がなく、ignore 対象にする。
- ログには API 応答、入力文、生成結果の一部が残りうる。
  - 鍵そのものだけでなく、業務データ流出にも注意する。
- 以下の公開不要アセットは repo に含めない。
  - コミュニティ参加用の QR 画像
  - 顔写真や個人を特定しうる要素を含む動画サムネイル
  - 公開必須ではないデモ用キービジュアル

## 運用ルール

1. 実キーは `.env` にのみ置く。
2. キーを README や issue、PR、チャットに貼らない。
3. 検証ファイルは `test_data/` か `backend/uploads/` に置き、Git に乗せない。
4. ログを共有する前に、キー・URL・入力文・生成文を確認する。
5. 公開前チェックでは `git status` と `git diff --cached` を必ず見る。

## 現在コード上で使っている主要な秘密情報

- `GOOGLE_AI_API_KEY`
- `ZEP_API_KEY`
- `LLM_BOOST_API_KEY`
- `LLM_API_KEY`
- `SECRET_KEY`
