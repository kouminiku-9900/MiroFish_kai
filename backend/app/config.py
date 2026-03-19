"""
設定管理
プロジェクトルートディレクトリの.envファイルから設定を一括読み込み
"""

import os
import secrets
from dotenv import load_dotenv

# プロジェクトルートディレクトリの.envファイルを読み込み
# パス: MiroFish/.env (backend/app/config.pyからの相対パス)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # ルートディレクトリに.envがない場合、環境変数を読み込み（本番環境用）
    load_dotenv(override=True)


class Config:
    """Flask設定クラス"""

    # Flask設定
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    # JSON設定 - ASCIIエスケープを無効化し、日本語を直接表示（\\uXXXX形式ではなく）
    JSON_AS_ASCII = False

    # LLM設定（Gemini を既定とし、互換設定はレガシー用途として保持）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gemini-3.1-flash-lite-preview')
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'google')  # Gemini-only runtime

    # Google AI (Gemini) 設定
    GOOGLE_AI_API_KEY = os.environ.get('GOOGLE_AI_API_KEY')

    # Zep設定
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # ファイルアップロード設定
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # テキスト処理設定
    DEFAULT_CHUNK_SIZE = 500  # デフォルトチャンクサイズ
    DEFAULT_CHUNK_OVERLAP = 50  # デフォルトオーバーラップサイズ

    # OASISシミュレーション設定
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # OASISプラットフォーム利用可能アクション設定
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent設定
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def _is_placeholder(cls, value: str) -> bool:
        """値がプレースホルダーかどうかを確認"""
        if not value:
            return True
        return value.startswith('your_') or value.startswith('sk-placeholder')

    @classmethod
    def validate(cls):
        """必要な設定を検証し、(errors, warnings)を返す"""
        errors = []
        warnings = []

        if cls.LLM_PROVIDER != 'google':
            errors.append("LLM_PROVIDER は 'google' を設定してください（現在は Gemini 専用構成です）")

        if not cls.GOOGLE_AI_API_KEY or cls._is_placeholder(cls.GOOGLE_AI_API_KEY):
            errors.append("GOOGLE_AI_API_KEYが未設定です（.envに正しいAPI keyを設定してください）")

        if not cls.ZEP_API_KEY or cls._is_placeholder(cls.ZEP_API_KEY):
            warnings.append("ZEP_API_KEYが未設定です（グラフ構築機能は利用できません。.envに設定してください。https://app.getzep.com/ から無料で取得できます）")
        if cls._is_placeholder(os.environ.get('SECRET_KEY', '')):
            warnings.append("SECRET_KEY にプレースホルダー値が設定されています。.env で長いランダム文字列に置き換えてください")
        return errors, warnings
