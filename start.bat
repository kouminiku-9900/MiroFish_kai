@echo off
chcp 65001 >nul
setlocal

:: MiroFish - Windows 起動スクリプト
:: Usage: start.bat          (バックエンド＋フロントエンド)
::        start.bat stop     (停止)

set "DIR=%~dp0"

if /i "%~1"=="stop" goto :stop

echo === MiroFish Engine ===
echo.

:: 依存関係の自動セットアップ
if not exist "%DIR%node_modules" (
    echo [Info] ルートディレクトリの npm パッケージをインストールしています...
    npm install
)

if not exist "%DIR%frontend\node_modules" (
    echo [Info] frontend の npm パッケージをインストールしています...
    cd /d "%DIR%frontend"
    call npm install
    cd /d "%DIR%"
)

if not exist "%DIR%backend\.venv\Scripts\python.exe" (
    echo [Info] backend の仮想環境が見つかりません。作成しています...
    cd /d "%DIR%backend"
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
    cd /d "%DIR%"
)

:: npm run dev で backend + frontend を同時起動
echo [Starting] backend + frontend ...
cd /d "%DIR%"
npm run dev
goto :eof

:stop
echo Stopping MiroFish...
:: ポート 5001 を使っているプロセスを停止
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5001" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
:: ポート 5173 を使っているプロセスを停止
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
echo Stopped.
