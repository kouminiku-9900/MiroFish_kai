"""
LLMクライアントラッパー
Google AI (Gemini) をサポート
レート制限・リトライ機能付き
"""

import json
import re
import time
import threading
from typing import Optional, Dict, Any, List
import google.generativeai as genai

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.llm_client')


class RateLimiter:
    """Google Gemini 無料枠レート制限用（デフォルト14 RPM）"""

    def __init__(self, requests_per_minute: int = 14):
        self.rpm = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self._lock = threading.Lock()
        self._last_call_time = 0.0

    def acquire(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self.min_interval:
                wait = self.min_interval - elapsed
                logger.debug(f"Rate limiter: {wait:.2f}秒待機中...")
                time.sleep(wait)
            self._last_call_time = time.time()


# グローバルレートリミッター（Gemini用・プロセス内共有）
_google_rate_limiter = RateLimiter(requests_per_minute=14)


def _extract_json_from_text(text: str) -> str:
    """Markdownコードブロックを除去し、JSON部分を抽出"""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def _try_repair_truncated_json(text: str):
    """トークン上限で途中切れしたJSONの修復を試みる。成功すればdictを返し、失敗すればNone"""
    text = text.strip()
    if not text:
        return None

    # 未閉じの文字列を閉じる
    if text and text[-1] not in '",}]':
        text += '"'

    # 未閉じの括弧を閉じる
    open_brackets = text.count('[') - text.count(']')
    open_braces = text.count('{') - text.count('}')
    text += ']' * max(open_brackets, 0)
    text += '}' * max(open_braces, 0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 制御文字を除去して再試行
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


class LLMClient:
    """LLMクライアント - Google Gemini 専用"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ):
        self.provider = provider or Config.LLM_PROVIDER
        self.model = model or Config.LLM_MODEL_NAME

        if self.provider != 'google':
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Gemini-only runtime requires 'google'.")

        self.api_key = api_key or Config.GOOGLE_AI_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_AI_API_KEYが未設定です")
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model)
        self._rate_limiter = _google_rate_limiter

    def _call_google_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
        max_retries: int = 5
    ) -> str:
        """Google Gemini API呼び出し（レート制限・リトライ付き）"""
        try:
            import google.api_core.exceptions as google_exceptions
            _quota_errors = (google_exceptions.ResourceExhausted, google_exceptions.ServiceUnavailable)
        except ImportError:
            _quota_errors = (Exception,)

        backoff = 15.0
        for attempt in range(max_retries):
            try:
                self._rate_limiter.acquire()

                history = []
                for msg in messages[:-1]:
                    role = 'user' if msg['role'] == 'user' else 'model'
                    history.append({"role": role, "parts": [msg['content']]})

                last_msg = messages[-1]['content']

                gen_cfg_kwargs = {
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
                if json_mode:
                    gen_cfg_kwargs["response_mime_type"] = "application/json"

                generation_config = genai.types.GenerationConfig(**gen_cfg_kwargs)

                chat_session = self.client.start_chat(history=history)
                response = chat_session.send_message(
                    last_msg, generation_config=generation_config
                )
                content = response.text
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                return content

            except _quota_errors as e:
                wait = backoff * (2 ** attempt)
                logger.warning(
                    f"Geminiレート制限/サービス不可 (attempt {attempt+1}/{max_retries}): "
                    f"{wait:.0f}秒待機します... ({e})"
                )
                time.sleep(wait)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 5 * (attempt + 1)
                    logger.warning(f"Gemini APIエラー (attempt {attempt+1}): {e} → {wait}秒後リトライ")
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError(f"Gemini APIの呼び出しが {max_retries} 回失敗しました")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """チャットリクエストを送信"""
        json_mode = bool(response_format and response_format.get("type") == "json_object")

        return self._call_google_with_retry(
            messages, temperature, max_tokens, json_mode=json_mode
        )

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """チャットリクエストを送信しJSONを返す"""
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        cleaned = _extract_json_from_text(response)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # トークン上限で途中切れしたJSONの修復を試みる
            repaired = _try_repair_truncated_json(cleaned)
            if repaired is not None:
                logger.warning("切り詰められたJSONを修復しました")
                return repaired
            raise ValueError(f"LLMが返したJSON形式が無効です: {cleaned[:300]}")

    def chat_completions_create(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        response_format: Optional[Dict] = None,
        **kwargs
    ) -> str:
        """
        レガシーコードとの互換性のためのOpenAI風インターフェース。
        文字列（content）を返す。
        """
        json_mode = bool(response_format and response_format.get("type") == "json_object")
        return self._call_google_with_retry(
            messages, temperature, 8192, json_mode=json_mode
        )
