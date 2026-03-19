"""
MiroFish Backend - Flaskアプリケーションファクトリ
"""

import os
import warnings

# multiprocessing resource_trackerの警告を抑制（transformers等のサードパーティライブラリ由来）
# 他のインポートの前に設定する必要あり
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flaskアプリケーションファクトリ関数"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # JSONエンコーディング設定：日本語を直接表示（\\uXXXX形式ではなく）
    # Flask >= 2.3はapp.json.ensure_asciiを使用、旧バージョンはJSON_AS_ASCII設定を使用
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False

    # ログ設定
    logger = setup_logger('mirofish')

    # reloaderの子プロセスでのみ起動情報を表示（debugモードでの二重表示を回避）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 起動中...")
        logger.info("=" * 50)

    # CORSを有効化
    # CORS設定: 環境変数で許可オリジンを制御（デフォルトはローカル開発用）
    allowed_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    # シミュレーションプロセスクリーンアップ関数を登録（サーバー終了時に全シミュレーションプロセスを終了）
    from .services.simulation_runner import SimulationRunner
    SimulationRunner.register_cleanup()
    if should_log_startup:
        logger.info("シミュレーションプロセスクリーンアップ関数を登録しました")

    # リクエストログミドルウェア
    @app.before_request
    def log_request():
        logger = get_logger('mirofish.request')
        logger.debug(f"リクエスト: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"リクエストボディ: {request.get_json(silent=True)}")

    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"レスポンス: {response.status_code}")
        return response

    # Blueprintを登録
    from .api import graph_bp, simulation_bp, report_bp
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
    app.register_blueprint(report_bp, url_prefix='/api/report')

    # ヘルスチェック
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}

    if should_log_startup:
        logger.info("MiroFish Backend 起動完了")

    return app
