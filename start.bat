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

:: .venv の存在確認
if not exist "%DIR%backend\.venv\Scripts\python.exe" (
    echo [Error] backend の仮想環境が見つかりません。
    echo         先に npm run setup:all を実行してください。
    exit /b 1
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
