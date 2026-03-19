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

## インストール方法

### 前提ツールのインストール

以下のツールが必要です。確認コマンドを打ってバージョンが表示されれば、そのツールはすでに入っています。入っていないものだけインストールしてください。

| ツール | 何に使うか | 確認コマンド |
| --- | --- | --- |
| Git | ソースコードの取得 | `git --version` |
| Node.js（18 以上） | フロントエンド（画面側） | `node -v` |
| Python（3.11 or 3.12） | バックエンド（サーバー側） | `python3 --version` |
| uv | Python パッケージの管理（pip の高速版） | `uv --version` |

<details>
<summary><strong>macOS の場合</strong></summary>

Homebrew（macOS 用のパッケージマネージャ）が入っていない場合は、まず https://brew.sh/ を開いて、表示されるコマンドをターミナルに貼り付けて実行してください。

```bash
# Git（macOS は xcode-select でも入る）
xcode-select --install

# Node.js
brew install node

# Python
brew install python@3.12

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

</details>

<details>
<summary><strong>Linux（Ubuntu / Debian）の場合</strong></summary>

```bash
# Git
sudo apt update && sudo apt install -y git

# Node.js（22.x 系をインストールする例）
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Python
sudo apt install -y python3.12 python3.12-venv

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

</details>

<details>
<summary><strong>Windows の場合</strong></summary>

Windows でもネイティブに動きます。WSL は不要です。

1. **Git**: https://gitforwindows.org/ からインストーラをダウンロードして実行
2. **Node.js**: https://nodejs.org/ から LTS 版のインストーラをダウンロードして実行（npm も一緒に入ります）
3. **Python**: https://www.python.org/downloads/ からインストーラをダウンロードして実行
   - インストール時に **「Add python.exe to PATH」にチェックを入れる**（重要）
4. **uv**: PowerShell またはコマンドプロンプトで以下を実行
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

インストール後、**コマンドプロンプトか PowerShell を開き直して**から確認コマンドを試してください。

> うまくいかない場合は WSL（Windows 上で Linux を動かす仕組み）を使う手もあります。
> 詳しくは [Microsoft 公式ガイド（日本語）](https://learn.microsoft.com/ja-jp/windows/wsl/install) を参照してください。

</details>

---

### セットアップ手順

#### 1. clone

ターミナル（Windows ならコマンドプロンプトか PowerShell）を開いて:

```bash
git clone https://github.com/kouminiku-9900/MiroFish_kai.git
cd MiroFish_kai
```

#### 2. `.env` を作る

```bash
cp .env.example .env
```

Windows のコマンドプロンプトでは `cp` が使えないので、代わりに:

```
copy .env.example .env
```

次に `.env` をテキストエディタで開いて、自分の値を入れてください。

最低限、意識するのはこの 3 つです。

- `GOOGLE_AI_API_KEY` — LLM を動かすための API キー（必須）
- `ZEP_API_KEY` — グラフ構築・エージェントの記憶に使う（必須）
- `SECRET_KEY` — セッション管理用の秘密鍵

`SECRET_KEY` は自分で長いランダム文字列を入れてください。例えば:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

その出力を `.env` の `SECRET_KEY=` に入れれば十分です。

#### API キーの取得方法

**Google AI API Key（必須）**

Google Gemini（LLM）を動かすために必要です。無料枠でも動きます。

1. https://aistudio.google.com/apikey にアクセス
2. Google アカウントでログイン
3. 「API キーを作成」をクリック
4. 表示されたキーをコピーして `.env` の `GOOGLE_AI_API_KEY=` に貼り付ける

**Zep Cloud API Key（グラフ構築に必要）**

Zep Cloud は、エージェントの記憶やナレッジグラフを管理するサービスです。無料プランがあります。

1. https://app.getzep.com/ にアクセス
2. アカウントを作成（無料プランあり）
3. ダッシュボードから API Key をコピー
4. `.env` の `ZEP_API_KEY=` に貼り付ける

#### 3. `.env` の記入例

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

#### 4. 依存を入れる

```bash
npm run setup:all
```

これで次が入ります。

- ルートの Node 依存
- `frontend` の Node 依存
- `backend` の Python 依存
- `backend/.venv`（Python の仮想環境）

#### 5. 起動する

**macOS / Linux:**

```bash
./start.sh
```

**Windows:**

```
start.bat
```

または、どの OS でも使えるコマンド:

```bash
npm run dev
```

起動に成功すると、だいたい次のようになります。

- backend: `http://localhost:5001`
- frontend: `http://localhost:5173` 前後

frontend のポートは Vite 側で決まるので、ターミナルに表示された URL を見てください。

#### 6. 動作確認

最低限、ここを見れば大丈夫です。

1. `http://localhost:5001/health` を開く → JSON が返ってくれば backend は OK
2. frontend の URL を開く
3. ホーム画面が出る
4. ファイル投入と要件入力ができる

#### 7. 停止する

`npm run dev` や `start.bat` で起動した場合は、ターミナルで `Ctrl + C` を押せば止まります。

`./start.sh` で起動した場合:

```bash
./start.sh stop
```

---

## Docker で起動する（もうひとつの方法）

Docker がすでに入っている場合は、Node.js や Python のインストールなしで動かせます。

```bash
# 1. .env を用意する（API キーの記入は必要）
cp .env.example .env
# .env を編集して API キーを入れる

# 2. 起動
docker compose up -d
```

- frontend: `http://localhost:3000`
- backend: `http://localhost:5001`

停止は `docker compose down` です。

---

## AI コーディングツールと一緒に進めるなら

この repo は、Codex や Claude Code などの AI ツールに作業を頼みながら進める使い方と相性が良いです。
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

---

## つまずきやすいポイント

### `uv: command not found`

`uv` が入っていません。[前提ツールのインストール](#uv)を参照してインストールしてから `npm run setup:all` をやり直してください。

### `./start.sh` で backend が上がらない

先に `npm run setup:all` をやってください。
この fork の `start.sh` は `backend/.venv/bin/python` がない場合、その場で止まるようにしてあります。

### frontend が `3000` では開かない

今の frontend は Vite なので、固定で `3000` とは限りません。
`./start.sh` が出した URL をそのまま開いてください。

### `GOOGLE_AI_API_KEY` を入れたのに動かない

次を確認してください。

- `.env` を repo ルート（`MiroFish_kai/` の直下）に置いているか
- キー名を間違えていないか
- key の前後に余計な空白が入っていないか
- backend を再起動したか

### `ZEP_API_KEY` を入れていない

一部機能は動いても、graph 構築や記憶系の処理が使えません。
「まず全部動かしたい」なら `ZEP_API_KEY` も入れてください。

---

## ディレクトリの見方

- [`frontend/`](./frontend)
  - Vue フロントエンド（画面側）
- [`backend/`](./backend)
  - Flask API とシミュレーション実装（サーバー側）
- [`.env.example`](./.env.example)
  - 環境変数の公開用テンプレート
- [`start.sh`](./start.sh)
  - 起動スクリプト

## システム画面

<div align="center">
<table>
<tr>
<td><img src="./static/image/Screenshot/运行截图1.png" alt="グラフ構築画面" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图2.png" alt="エージェント設定画面" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图3.png" alt="シミュレーション設定画面" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图4.png" alt="シミュレーション実行画面" width="100%"/></td>
</tr>
<tr>
<td><img src="./static/image/Screenshot/运行截图5.png" alt="レポート画面" width="100%"/></td>
<td><img src="./static/image/Screenshot/运行截图6.png" alt="対話画面" width="100%"/></td>
</tr>
</table>
</div>

## クレジット

- ベース実装: [666ghj/MiroFish](https://github.com/666ghj/MiroFish)
- シミュレーション基盤: [camel-ai/oasis](https://github.com/camel-ai/oasis)
- ライセンス: AGPL-3.0

本家の設計・発想・主要機能の由来は upstream にあります。
この fork は、その上に公開整理と日本語運用向けの調整を重ねたものです。
