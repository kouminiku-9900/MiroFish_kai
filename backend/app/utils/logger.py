"""
ログ設定モジュール
統一的なログ管理を提供し、コンソールとファイルに同時出力
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler


def _ensure_utf8_stdout():
    """
    stdout/stderrがUTF-8エンコーディングを使用することを保証
    Windowsコンソールの文字化け問題を解決
    """
    if sys.platform == 'win32':
        # Windows環境で標準出力をUTF-8に再設定
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# ログディレクトリ
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logger(name: str = 'mirofish', level: int = logging.DEBUG) -> logging.Logger:
    """
    ロガーを設定

    Args:
        name: ロガー名
        level: ログレベル

    Returns:
        設定済みのロガー
    """
    # ログディレクトリの存在を確認
    os.makedirs(LOG_DIR, exist_ok=True)

    # ロガーを作成
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # ルートloggerへのログ伝播を阻止し、重複出力を回避
    logger.propagate = False

    # 既にハンドラーがある場合、重複追加しない
    if logger.handlers:
        return logger

    # ログフォーマット
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    # 1. ファイルハンドラー - 詳細ログ（日付名、ローテーション付き）
    log_filename = datetime.now().strftime('%Y-%m-%d') + '.log'
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_filename),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # 2. コンソールハンドラー - 簡潔ログ（INFO以上）
    # Windows環境でUTF-8エンコーディングを使用し、文字化けを回避
    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # ハンドラーを追加
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = 'mirofish') -> logging.Logger:
    """
    ロガーを取得（存在しない場合は作成）

    Args:
        name: ロガー名

    Returns:
        ロガーインスタンス
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# デフォルトロガーを作成
logger = setup_logger()


# 便利メソッド
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)
