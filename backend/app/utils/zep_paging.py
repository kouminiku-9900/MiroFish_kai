"""Zep Graphページネーション読み取りツール。

ZepのノードおよびエッジリストAPIはUUID cursorページネーションを使用。
本モジュールは自動ページ送りロジック（単一ページリトライ付き）をラップし、
呼び出し元に透過的に完全なリストを返す。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from zep_cloud import InternalServerError
from zep_cloud.client import Zep

from .logger import get_logger

logger = get_logger('mirofish.zep_paging')

_DEFAULT_PAGE_SIZE = 100
_MAX_NODES = 2000
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0  # seconds, doubles each retry


def _fetch_page_with_retry(
    api_call: Callable[..., list[Any]],
    *args: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
    page_description: str = "page",
    **kwargs: Any,
) -> list[Any]:
    """単一ページリクエスト、失敗時に指数バックオフでリトライ。ネットワーク/IO系の一時的エラーのみリトライ。"""
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    last_exception: Exception | None = None
    delay = retry_delay

    for attempt in range(max_retries):
        try:
            return api_call(*args, **kwargs)
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()
            
            is_rate_limit = '429' in error_str or 'rate limit' in error_str
            is_server_error = any(code in error_str for code in ['500', '502', '503', '504'])
            is_network_error = isinstance(e, (ConnectionError, TimeoutError, OSError, InternalServerError))
            
            if is_rate_limit or is_server_error or is_network_error:
                if attempt < max_retries - 1:
                    wait_time = delay
                    if is_rate_limit:
                        import re
                        match = re.search(r"'retry-after':\s*'(\d+)'", str(e), re.IGNORECASE)
                        wait_time = float(match.group(1)) + 2.0 if match else 62.0
                        
                    logger.warning(
                        f"Zep {page_description} attempt {attempt + 1} failed: {str(e)[:100]}, retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                    if not is_rate_limit:
                        delay *= 2
                else:
                    logger.error(f"Zep {page_description} failed after {max_retries} attempts: {str(e)}")
            else:
                raise

    assert last_exception is not None
    raise last_exception


def fetch_all_nodes(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int = _MAX_NODES,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    """グラフノードをページネーションで取得、最大max_items件（デフォルト2000）を返す。各ページリクエストにリトライ付き。"""
    all_nodes: list[Any] = []
    cursor: str | None = None
    page_num = 0

    while True:
        kwargs: dict[str, Any] = {"limit": page_size}
        if cursor is not None:
            kwargs["uuid_cursor"] = cursor

        page_num += 1
        batch = _fetch_page_with_retry(
            client.graph.node.get_by_graph_id,
            graph_id,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=f"fetch nodes page {page_num} (graph={graph_id})",
            **kwargs,
        )
        if not batch:
            break

        all_nodes.extend(batch)
        if len(all_nodes) >= max_items:
            all_nodes = all_nodes[:max_items]
            logger.warning(f"Node count reached limit ({max_items}), stopping pagination for graph {graph_id}")
            break
        if len(batch) < page_size:
            break

        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if cursor is None:
            logger.warning(f"Node missing uuid field, stopping pagination at {len(all_nodes)} nodes")
            break

    return all_nodes


def fetch_all_edges(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> list[Any]:
    """グラフの全エッジをページネーションで取得し、完全なリストを返す。各ページリクエストにリトライ付き。"""
    all_edges: list[Any] = []
    cursor: str | None = None
    page_num = 0

    while True:
        kwargs: dict[str, Any] = {"limit": page_size}
        if cursor is not None:
            kwargs["uuid_cursor"] = cursor

        page_num += 1
        batch = _fetch_page_with_retry(
            client.graph.edge.get_by_graph_id,
            graph_id,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=f"fetch edges page {page_num} (graph={graph_id})",
            **kwargs,
        )
        if not batch:
            break

        all_edges.extend(batch)
        if len(batch) < page_size:
            break

        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if cursor is None:
            logger.warning(f"Edge missing uuid field, stopping pagination at {len(all_edges)} edges")
            break

    return all_edges
