"""
ファイル解析ツール
PDF、Markdown、TXTファイルからのテキスト抽出をサポート
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    テキストファイルを読み込み、UTF-8で失敗した場合は自動的にエンコーディングを検出。

    多段階フォールバック戦略を採用：
    1. まずUTF-8デコードを試行
    2. charset_normalizerでエンコーディングを検出
    3. chardetでエンコーディングを検出にフォールバック
    4. 最終的にUTF-8 + errors='replace'で対応

    Args:
        file_path: ファイルパス

    Returns:
        デコード済みのテキスト内容
    """
    data = Path(file_path).read_bytes()

    # まずUTF-8を試行
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass

    # charset_normalizerでエンコーディング検出を試行
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass

    # chardetにフォールバック
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass

    # 最終フォールバック：UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'

    return data.decode(encoding, errors='replace')


class FileParser:
    """ファイルパーサー"""

    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        ファイルからテキストを抽出

        Args:
            file_path: ファイルパス

        Returns:
            抽出されたテキスト内容
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"ファイルが存在しません: {file_path}")

        suffix = path.suffix.lower()

        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"サポートされていないファイル形式: {suffix}")

        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)

        raise ValueError(f"処理できないファイル形式: {suffix}")

    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """PDFからテキストを抽出"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDFのインストールが必要です: pip install PyMuPDF")

        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)

        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Markdownからテキストを抽出、自動エンコーディング検出対応"""
        return _read_text_with_fallback(file_path)

    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """TXTからテキストを抽出、自動エンコーディング検出対応"""
        return _read_text_with_fallback(file_path)

    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        複数ファイルからテキストを抽出して結合

        Args:
            file_paths: ファイルパスリスト

        Returns:
            結合されたテキスト
        """
        all_texts = []

        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== ドキュメント {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== ドキュメント {i}: {file_path} (抽出失敗: {str(e)}) ===")

        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    テキストを小さなチャンクに分割

    Args:
        text: 元のテキスト
        chunk_size: 各チャンクの文字数
        overlap: オーバーラップ文字数

    Returns:
        テキストチャンクのリスト
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # 文の境界で分割を試行
        if end < len(text):
            # 最も近い文末記号を検索
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # 次のチャンクはオーバーラップ位置から開始
        start = end - overlap if end < len(text) else len(text)

    return chunks
