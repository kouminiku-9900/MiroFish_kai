"""
テキスト処理サービス
"""

from typing import List, Optional
from ..utils.file_parser import FileParser, split_text_into_chunks


class TextProcessor:
    """テキストプロセッサ"""

    @staticmethod
    def extract_from_files(file_paths: List[str]) -> str:
        """複数ファイルからテキストを抽出"""
        return FileParser.extract_from_multiple(file_paths)

    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        テキストを分割

        Args:
            text: 元のテキスト
            chunk_size: チャンクサイズ
            overlap: オーバーラップサイズ

        Returns:
            テキストチャンクのリスト
        """
        return split_text_into_chunks(text, chunk_size, overlap)

    @staticmethod
    def preprocess_text(text: str) -> str:
        """
        テキストの前処理
        - 余分な空白を除去
        - 改行を標準化

        Args:
            text: 元のテキスト

        Returns:
            処理後のテキスト
        """
        import re

        # 改行を標準化
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # 連続する空行を除去（最大2つの改行を保持）
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 行頭行末の空白を除去
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text.strip()

    @staticmethod
    def get_text_stats(text: str) -> dict:
        """テキストの統計情報を取得"""
        return {
            "total_chars": len(text),
            "total_lines": text.count('\n') + 1,
            "total_words": len(text.split()),
        }
