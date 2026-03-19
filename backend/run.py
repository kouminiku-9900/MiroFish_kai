"""
MiroFish Backend起動エントリ
"""

import os
import sys

# Windowsコンソールの文字化け問題を解決：全てのインポート前にUTF-8エンコーディングを設定
if sys.platform == 'win32':
    # 環境変数を設定してPythonがUTF-8を使用するようにする
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    # 標準出力ストリームをUTF-8に再設定
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# プロジェクトルートディレクトリをパスに追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config


def main():
    """メイン関数"""
    # 設定を検証
    errors, warnings = Config.validate()
    if warnings:
        print("⚠️  設定の警告:")
        for warn in warnings:
            print(f"  - {warn}")
        print()
    if errors:
        print("❌ 設定エラー:")
        for err in errors:
            print(f"  - {err}")
        print("\n.envファイルの設定を確認してください")
        sys.exit(1)

    # アプリケーションを作成
    app = create_app()

    # 実行設定を取得
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5001))
    debug = Config.DEBUG

    # サービスを起動
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()
