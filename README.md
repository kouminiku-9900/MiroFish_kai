<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="72%"/>

# MiroFish_kai

群衆シミュレーションとレポート生成をまとめて扱える、MiroFish 系の公開用 fork です。

[この fork](https://github.com/kouminiku-9900/MiroFish_kai) | [元リポジトリ](https://github.com/666ghj/MiroFish) | [English](./README-EN.md)

</div>

## このリポジトリについて

このリポジトリは、[666ghj/MiroFish](https://github.com/666ghj/MiroFish) をベースにした fork です。  
この fork では、主に次の整理を入れています。

- GUI の日本語寄せと閲覧性の調整
- 公開前サニタイズ
  - `.env`
  - `test_data/`
  - `backend/uploads/`
  - `log/`
  - `backend/logs/`
  - 公開不要の QR / サムネイル画像
- 初見でも動かしやすい README と起動導線の整備

公式の本家実装や由来を追いたい場合は、まず [元リポジトリ](https://github.com/666ghj/MiroFish) を見てください。  
この fork は「日本語で使いやすくする」「公開できる状態に整える」ことを主目的にしています。

## これは何ができるのか

MiroFish は、投入した資料や要件をもとに、以下の流れで仮想社会を組み立ててシミュレーションするアプリです。

1. グラフを構築する
2. エージェントの人設や環境設定を作る
3. シミュレーションを回す
4. レポートを生成する
5. シミュレーション世界やレポートと対話する

今回の fork では、現行導線の GUI を中心に日本語で扱いやすい形へ寄せています。

## まず結論

何もわからない状態から動かすなら、この順で進めれば足ります。

1. この fork を clone する
2. `.env.example` を `.env` にコピーする
3. 自分の API key を `.env` に入れる
4. `npm run setup:all` を実行する
5. `./start.sh` を実行する
6. ターミナルに出た URL をブラウザで開く

停止するときは `./start.sh stop` です。

## 前提環境

| ツール | 推奨バージョン | 確認コマンド |
| --- | --- | --- |
| Node.js | 18 以上 | `node -v` |
| npm | Node.js 同梱 | `npm -v` |
| Python | 3.11 または 3.12 | `python3 --version` |
| uv | 最新推奨 | `uv --version` |

macOS / Linux 前提で書いています。Windows の場合は WSL を使うのが無難です。

## いちばん安全な起動方法

この repo では、現状 `./start.sh` が一番無難です。

- backend を先に起動する
- `/health` を確認してから frontend を起動する
- PID 管理をする
- 停止を `./start.sh stop` に寄せられる

`npm run dev` でも起動できますが、初回は `./start.sh` を勧めます。

## 最短セットアップ

### 1. clone

```bash
git clone https://github.com/kouminiku-9900/MiroFish_kai.git
cd MiroFish_kai
```

### 2. `.env` を作る

```bash
cp .env.example .env
```

次に `.env` を開いて、自分の値を入れてください。

最低限、意識するのはこの 3 つです。

- `GOOGLE_AI_API_KEY`
- `ZEP_API_KEY`
- `SECRET_KEY`

`SECRET_KEY` は自分で長いランダム文字列を入れてください。例えば:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

その出力を `.env` の `SECRET_KEY=` に入れれば十分です。

### 3. `.env` の記入例

```env
# Gemini を使う
LLM_PROVIDER=google
LLM_MODEL_NAME=gemini-3.1-flash-lite-preview
GOOGLE_AI_API_KEY=your_google_ai_api_key_here

# Flask / session 用
SECRET_KEY=put_a_long_random_secret_here

# 互換用。今の実行系では空でよい
LLM_API_KEY=
LLM_BASE_URL=

# Zep Cloud
ZEP_API_KEY=your_zep_api_key_here

# 任意。並列シミュレーションで別 key を使いたいときだけ設定
LLM_BOOST_API_KEY=your_second_google_ai_api_key_here
LLM_BOOST_MODEL_NAME=gemini-3.1-flash-lite-preview
```

補足:

- `GOOGLE_AI_API_KEY` は実質必須です
- `ZEP_API_KEY` がないと graph 構築系が動きません
- `LLM_BOOST_API_KEY` は任意です
- `.env` は Git に commit しないでください

### 4. 依存を入れる

```bash
npm run setup:all
```

これで次が入ります。

- ルートの Node 依存
- `frontend` の Node 依存
- `backend` の Python 依存
- `backend/.venv`

### 5. 起動する

```bash
./start.sh
```

起動に成功すると、だいたい次のようになります。

- backend: `http://localhost:5001`
- frontend: `http://localhost:5173` 前後

frontend のポートは Vite 側で決まるので、実際には `./start.sh` が表示した URL を見てください。

### 6. 動作確認

最低限、ここを見れば大丈夫です。

1. `http://localhost:5001/health` を開く
2. frontend の URL を開く
3. ホーム画面が出る
4. ファイル投入と要件入力ができる

### 7. 停止する

```bash
./start.sh stop
```

## Codex と一緒に進めるなら

この repo は、Codex に作業させながら進める前提と相性が良いです。  
repo を開いた状態で、次のように頼めば進めやすいです。

```text
この repo をセットアップして。足りない依存があれば教えて。
```

```text
.env.example を見て、私が入れるべき値だけを日本語で整理して。
```

```text
./start.sh で起動して、動かなかったら原因を切り分けて。
```

```text
ホーム画面から最後まで一通り触って、まだ中国語が残っている UI を探して。
```

```text
公開してはいけないファイルが混ざっていないか、git diff と gitignore を確認して。
```

## つまずきやすいポイント

### `uv: command not found`

`uv` が入っていません。インストールしてから `npm run setup:all` をやり直してください。

### `./start.sh` で backend が上がらない

先に `npm run setup:all` をやってください。  
この fork の `start.sh` は `backend/.venv/bin/python` がない場合、その場で止まるようにしてあります。

### frontend が `3000` では開かない

今の frontend は Vite なので、固定で `3000` とは限りません。  
`./start.sh` が出した URL をそのまま開いてください。

### `GOOGLE_AI_API_KEY` を入れたのに動かない

次を確認してください。

- `.env` を repo ルートに置いているか
- キー名を間違えていないか
- key の前後に余計な空白が入っていないか
- backend を再起動したか

### `ZEP_API_KEY` を入れていない

一部機能は動いても、graph 構築や記憶系の処理が使えません。  
「まず全部動かしたい」なら `ZEP_API_KEY` も入れてください。

## ディレクトリの見方

- [`frontend/`](./frontend)
  - Vue フロントエンド
- [`backend/`](./backend)
  - Flask API とシミュレーション実装
- [`.env.example`](./.env.example)
  - 公開用テンプレート
- [`start.sh`](./start.sh)
  - いちばん無難な起動スクリプト
- [`SECURITY_DATA_POLICY.md`](./SECURITY_DATA_POLICY.md)
  - 公開してよいもの / だめなものの基準

## 公開とセキュリティ

この fork では、公開物に次を含めない方針です。

- `.env`
- `test_data/`
- `backend/uploads/`
- `log/`
- `backend/logs/`
- ローカル生成レポート
- ローカル会話ログ
- 公開不要な QR / 顔入りサムネイル

公開可否の基準は [`SECURITY_DATA_POLICY.md`](./SECURITY_DATA_POLICY.md) にまとめています。

## システム画面

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/运行截图1.png" alt="画面 1" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图2.png" alt="画面 2" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图3.png" alt="画面 3" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图4.png" alt="画面 4" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图5.png" alt="画面 5" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图6.png" alt="画面 6" width="100%"/></td>
</tr>
</table>
</div>

## クレジット

- ベース実装: [666ghj/MiroFish](https://github.com/666ghj/MiroFish)
- シミュレーション基盤: [camel-ai/oasis](https://github.com/camel-ai/oasis)
- ライセンス: AGPL-3.0

本家の設計・発想・主要機能の由来は upstream にあります。  
この fork は、その上に公開整理と日本語運用向けの調整を重ねたものです。
