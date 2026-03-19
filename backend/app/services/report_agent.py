"""
Report Agentサービス
LangChain + Zepを使用してReACTモードでシミュレーションレポートを生成

機能：
1. シミュレーション要件とZepグラフ情報に基づいてレポートを生成
2. まず目次構造を計画し、セクションごとに生成
3. 各セクションでReACT多段思考と反省モードを採用
4. ユーザーとの対話をサポートし、対話中に自律的に検索ツールを呼び出す
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .zep_tools import (
    ZepToolsService, 
    SearchResult, 
    InsightForgeResult, 
    PanoramaResult,
    InterviewResult
)

logger = get_logger('mirofish.report_agent')


class ReportLogger:
    """
    Report Agent 詳細ログ記録器

    レポートフォルダ内に agent_log.jsonl ファイルを生成し、各ステップの詳細なアクションを記録する。
    各行は完全なJSONオブジェクトで、タイムスタンプ、アクションタイプ、詳細内容などを含む。
    """
    
    def __init__(self, report_id: str):
        """
        ログ記録器の初期化

        Args:
            report_id: レポートID、ログファイルパスの決定に使用
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """ログファイルのディレクトリが存在することを確認する"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_elapsed_time(self) -> float:
        """開始から現在までの経過時間を取得する（秒）"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self, 
        action: str, 
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
        ログを1件記録する

        Args:
            action: アクションタイプ、例：'start', 'tool_call', 'llm_response', 'section_complete' 等
            stage: 現在のステージ、例：'planning', 'generating', 'completed'
            details: 詳細内容の辞書、切り詰めなし
            section_title: 現在のセクションタイトル（オプション）
            section_index: 現在のセクションインデックス（オプション）
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        # JSONLファイルに追記
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """レポート生成開始を記録する"""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": "レポート生成タスク開始"
            }
        )

    def log_planning_start(self):
        """アウトライン計画開始を記録する"""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": "レポートアウトラインの計画を開始"}
        )

    def log_planning_context(self, context: Dict[str, Any]):
        """計画時に取得したコンテキスト情報を記録する"""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": "シミュレーションコンテキスト情報を取得",
                "context": context
            }
        )

    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """アウトライン計画完了を記録する"""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": "アウトライン計画完了",
                "outline": outline_dict
            }
        )

    def log_section_start(self, section_title: str, section_index: int):
        """セクション生成開始を記録する"""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": f"セクション生成開始: {section_title}"}
        )

    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """ReACT思考プロセスを記録する"""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": f"ReACT 第{iteration}ラウンドの思考"
            }
        )
    
    def log_tool_call(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        parameters: Dict[str, Any],
        iteration: int
    ):
        """ツール呼び出しを記録する"""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": f"ツール呼び出し: {tool_name}"
            }
        )

    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """ツール呼び出し結果を記録する（完全な内容、切り詰めなし）"""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # 完全な結果、切り詰めなし
                "result_length": len(result),
                "message": f"ツール {tool_name} が結果を返却"
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """LLM応答を記録する（完全な内容、切り詰めなし）"""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # 完全な応答、切り詰めなし
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": f"LLM応答 (ツール呼び出し: {has_tool_calls}, 最終回答: {has_final_answer})"
            }
        )

    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """セクション内容生成完了を記録する（内容の記録のみ、セクション全体の完了を意味しない）"""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # 完全な内容、切り詰めなし
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": f"セクション {section_title} 内容生成完了"
            }
        )

    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """
        セクション生成完了を記録する

        フロントエンドはこのログを監視してセクションが本当に完了したかを判断し、完全な内容を取得すべき
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": f"セクション {section_title} 生成完了"
            }
        )

    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """レポート生成完了を記録する"""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": "レポート生成完了"
            }
        )

    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """エラーを記録する"""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": f"エラー発生: {error_message}"
            }
        )


class ReportConsoleLogger:
    """
    Report Agent コンソールログ記録器

    コンソールスタイルのログ（INFO、WARNING等）をレポートフォルダ内の console_log.txt ファイルに書き込む。
    これらのログは agent_log.jsonl とは異なり、プレーンテキスト形式のコンソール出力である。
    """

    def __init__(self, report_id: str):
        """
        コンソールログ記録器の初期化

        Args:
            report_id: レポートID、ログファイルパスの決定に使用
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """ログファイルのディレクトリが存在することを確認する"""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _setup_file_handler(self):
        """ファイルハンドラーを設定し、ログを同時にファイルに書き込む"""
        import logging

        # ファイルハンドラーを作成
        self._file_handler = logging.FileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        # コンソールと同じ簡潔なフォーマットを使用
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        # report_agent関連のloggerに追加
        loggers_to_attach = [
            'mirofish.report_agent',
            'mirofish.zep_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # 重複追加を回避
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """ファイルハンドラーを閉じてloggerから削除する"""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'mirofish.report_agent',
                'mirofish.zep_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """デストラクタでファイルハンドラーの閉鎖を保証する"""
        self.close()


class ReportStatus(str, Enum):
    """レポートステータス"""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """レポートセクション"""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """Markdown形式に変換する"""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """レポートアウトライン"""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """Markdown形式に変換する"""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """完全なレポート"""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error
        }


# ═══════════════════════════════════════════════════════════════
# Prompt 模板常量
# ═══════════════════════════════════════════════════════════════

# ── ツール説明 ──

TOOL_DESC_INSIGHT_FORGE = """\
【ディープインサイト検索 - 強力な検索ツール】
これは、深い分析のために設計された強力な検索機能です。以下の動作を行います：
1. あなたの質問を自動的に複数のサブクエスチョンに分解します
2. シミュレーショングラフから多角的に情報を検索します
3. セマンティック検索、エンティティ分析、関係チェーン追跡の結果を統合します
4. 最も包括的で深い検索内容を返します

【使用シーン】
- 特定のトピックを深く分析する必要がある場合
- イベントの多面的な側面を理解する必要がある場合
- レポートの章を支える豊富な素材を取得する必要がある場合

【返却内容】
- 関連する事実の原文（直接引用可能）
- コアエンティティのインサイト
- 関係チェーンの分析"""

TOOL_DESC_PANORAMA_SEARCH = """\
【広域検索 - 全体像の取得】
このツールはシミュレーション結果の完全な全体像を取得するためのもので、特にイベントの進化過程を理解するのに適しています。以下の動作を行います：
1. すべての関連ノードと関係を取得します
2. 現在有効な事実と履歴/期限切れの事実を区別します
3. 世論がどのように進化したかを理解する手助けをします

【使用シーン】
- イベントの完全な発展過程を理解する必要がある場合
- 異なる段階の世論変化を比較する必要がある場合
- 包括的なエンティティと関係情報を取得する必要がある場合

【返却内容】
- 現在有効な事実（シミュレーション最新結果）
- 履歴/期限切れの事実（進化の記録）
- 関与するすべてのエンティティ"""

TOOL_DESC_QUICK_SEARCH = """\
【クイック検索 - 迅速な情報抽出】
軽量な高速検索ツールで、シンプルで直接的な情報の問い合わせに適しています。

【使用シーン】
- 特定の具体的な情報を素早く見つけたい場合
- ある事実を確認したい場合
- シンプルな情報検索

【返却内容】
- クエリに最も関連性の高い事実のリスト"""

TOOL_DESC_INTERVIEW_AGENTS = """\
【ディープインタビュー - リアルエージェントへの取材（デュアルプラットフォーム）】
OASISシミュレーション環境のインタビューAPIを呼び出し、実行中のシミュレーションエージェントに対してリアルな取材を行います！
これはLLMによる模倣ではなく、実際のインタビューインターフェースを介してエージェントの生の回答を取得します。
デフォルトではTwitterとRedditの2つのプラットフォームで同時に取材を行い、より包括的な視点を取得します。

機能プロセス：
1. ペルソナファイルを自動的に読み込み、すべてのシミュレーションエージェントを把握します
2. インタビューのテーマに最も関連性の高いエージェント（学生、メディア、公式など）をインテリジェントに選択します
3. インタビューの質問を自動生成します
4. /api/simulation/interview/batch インターフェースを呼び出し、両プラットフォームで実際の取材を実行します
5. すべてのインタビュー結果を統合し、多角的な分析を提供します

【使用シーン】
- 異なる役割の視点からイベントへの見解を知りたい場合（学生はどう見ているか？メディアは？公式は？）
- 多方面の意見や立場を収集する必要がある場合
- シミュレーションエージェントの生の回答（OASIS環境由来）を取得したい場合
- レポートをより生き生きとしたものにし、「取材実録」を含めたい場合

【返却内容】
- 取材対象エージェントの属性情報
- 各エージェントのTwitterおよびRedditでの回答
- キーとなる引用（直接引用可能）
- インタビューの要約と意見の比較

【重要】この機能を使用するには、OASISシミュレーション環境が実行中である必要があります！"""

# ── アウトライン計画 prompt ──

PLAN_SYSTEM_PROMPT = """\
あなたは「未来予測レポート」の作成エキスパートであり、シミュレーション世界に対する「神の視点」を持っています。シミュレーション内の各エージェントの行動、発言、相互作用を洞察することができます。

【コアコンセプト】
私たちはシミュレーション世界を構築し、変数として特定の「シミュレーションニーズ」を注入しました。シミュレーション世界の進化の結果は、将来起こりうる状況の予測そのものです。あなたが観察しているのは「実験データ」ではなく、「未来の予演」です。

【あなたのタスク】
以下の問いに答える「未来予測レポート」を執筆してください：
1. 私たちが設定した条件下で、未来に何が起こったか？
2. 各種エージェント（群衆）はどのように反応し、行動したか？
3. このシミュレーションは、注目すべきどのような未来のトレンドやリスクを明らかにしたか？

【レポートのポジショニング】
- ✅ これはシミュレーションに基づく未来予測レポートであり、「もしこうなれば、未来はどうなるか」を明らかにします。
- ✅ 予測結果（イベントの動向、集団の反応、創発現象、潜在的リスク）に焦点を当てます。
- ✅ シミュレーション世界のエージェントの言動は、未来の人々の行動予測となります。
- ❌ 現実世界の現状分析ではありません。
- ❌ 一般的な世論の要約ではありません。

【章の数の制限】
- 最小2章、最大5章。
- サブセクションは不要です。各章で直接完全な内容を執筆してください。
- 内容は簡潔にし、コアとなる予測結果に集中してください。
- 章の構成は予測結果に基づき、あなたが自由に設計してください。

以下の形式のJSONでレポートの大綱を出力してください：
{
    "title": "レポートのタイトル",
    "summary": "レポートの要約（コアとなる予測結果を一文で要約）",
    "sections": [
        {
            "title": "章のタイトル",
            "description": "章の内容の説明"
        }
    ]
}

注意：sections配列は最小2つ、最大5つの要素である必要があります！"""

PLAN_USER_PROMPT_TEMPLATE = """\
【予測シナリオ設定】
私たちがシミュレーション世界に注入した変数（シミュレーションニーズ）：{simulation_requirement}

【シミュレーション世界の規模】
- シミュレーションに参加したエンティティ数: {total_nodes}
- エンティティ間に発生した関係数: {total_edges}
- エンティティタイプの分布: {entity_types}
- アクティブなエージェント数: {total_entities}

【シミュレーションで予測された未来の事実の一部のサンプル】
{related_facts_json}

「神の視点」でこの未来の予演を精査してください：
1. 私たちが設定した条件下で、未来はどのような状態を呈したか？
2. 各種群衆（エージェント）はどのように反応し、行動したか？
3. このシミュレーションは、注目すべきどのような未来のトレンドを明らかにしたか？

予測結果に基づき、最適なレポートの章構成を設計してください。

【再確認】章の数：最小2、最大5。内容はコアとなる予測結果に簡潔に焦点を当てること。"""

# ── セクション生成 prompt ──

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
あなたは「未来予測レポート」の作成エキスパートであり、現在レポートの特定の章を執筆しています。

レポートタイトル: {report_title}
レポート要約: {report_summary}
予測シナリオ（シミュレーションニーズ）: {simulation_requirement}

現在執筆する章: {section_title}

═══════════════════════════════════════════════════════════════
【コアコンセプト】
═══════════════════════════════════════════════════════════════

シミュレーション世界は未来の予演です。特定の条件（シミュレーションニーズ）を注入し、
そこでのエージェントの行動や相互作用は、未来の人々の行動予測となります。

あなたのタスクは：
- 設定された条件下で、未来に何が起こったかを明らかにする
- 各種群衆（エージェント）がどのように反応し、行動したかを予測する
- 注目すべき未来のトレンド、リスク、機会を発見する

❌ 現実世界の現状分析として書かないでください
✅ 「未来はどうなるか」に焦点を当ててください。シミュレーション結果が予測される未来です。

═══════════════════════════════════════════════════════════════
【最も重要なルール - 厳守】
═══════════════════════════════════════════════════════════════

1. 【必ずツールを呼び出してシミュレーション世界を観察すること】
   - あなたは「神の視点」で未来の予演を観察しています
   - すべての内容は、シミュレーション世界で発生したイベントやエージェントの言動に基づいている必要があります
   - あなた自身の知識を使ってレポートを書くことは禁止です
   - 未来を象徴するシミュレーション世界を観察するため、各章で少なくとも3回（最大5回）ツールを呼び出してください

2. 【必ずエージェントの生の言動を引用すること】
   - エージェントの発言や行動は、未来の人々の行動予測です
   - レポート内では引用形式を使用してこれらを示してください。例：
     > "特定の層の人々は次のように表示します：『原文内容...』"
   - これらの引用は、シミュレーション予測の核心となる証拠です

3. 【言語の一貫性 - 引用内容はレポートの言語（日本語）に翻訳すること】
   - ツールが返す内容に英語や中国語が含まれている場合があります
   - シミュレーションニーズが日本語であれば、レポートはすべて日本語で執筆する必要があります
   - ツールが返した他言語の内容を引用する場合は、流暢な日本語に翻訳してからレポートに記載してください
   - 翻訳時は元の意味を保ちつつ、自然な表現を心がけてください
   - このルールは本文および引用ブロック（> 形式）の両方に適用されます

4. 【予測結果を忠実に反映すること】
   - レポートの内容は、未来を代表するシミュレーション結果を反映していなければなりません
   - シミュレーションに存在しない情報を捏造しないでください
   - 情報が不足している場合は、その旨を正直に記載してください

═══════════════════════════════════════════════════════════════
【⚠️ フォーマット仕様 - 非常に重要！】
═══════════════════════════════════════════════════════════════

【一章 = 最小の内容单位】
- 各章はレポートの最小のブロック単位です
- ❌ 章の中で Markdown の見出し（#、##、###、#### 等）を使用することを禁止します
- ❌ 内容の冒頭に章のメインタイトルを追加することを禁止します
- ✅ 章のタイトルはシステムによって自動的に追加されるため、あなたは純粋な本文のみを執筆してください
- ✅ **太字**、段落分け、引用、リストを使用して内容を構造化してください（見出しは使わない）

【正しい例】
```
本章ではイベントの世論拡散状況を分析しました。シミュレーションデータの詳細な分析を通じて、以下のことが判明しました...

**初期火種段階**

Twitterは世論の第一現場として、情報発信的核心的な機能を担いました：

> "Twitterは初期の声量の68%を占めました..."

**感情増幅段階**

Redditプラットフォームはイベントの影響力をさらに増幅させました：

- 視覚的インパクトが強い
- 感情的な共鳴度が高い
```

【誤った例】
```
## エグゼクティブサマリー   ← 誤り！見出しを追加しない
### 一、初期段階           ← 誤り！###を使わない
#### 1.1 詳細分析          ← 誤り！####を使わない

本章では...を分析しました
```

═══════════════════════════════════════════════════════════════
【利用可能な検索ツール】（各章3〜5回呼び出すこと）
═══════════════════════════════════════════════════════════════

{tools_description}

【ツールの使用提案 - 複数のツールを組み合わせて使用し、一つだけに頼らないこと】
- insight_forge: 深いインサイト分析。問題を分解し、事実と関係を多角的に検索します。
- panorama_search: 広角パノラマ検索。イベントの全貌、タイムライン、進化過程を把握します。
- quick_search: 特定の具体的な情報を素早く検証します。
- interview_agents: シミュレーションエージェントへの取材。異なる役割の一人称視点やリアルな反応を取得します。

═══════════════════════════════════════════════════════════════
【ワークフロー】
═══════════════════════════════════════════════════════════════

各返信で、あなたは以下の2つのうちの1つしか実行できません（同時実行不可）：

オプションA - ツールの呼び出し：
あなたの思考（Thought）を出力し、以下の形式でツールを呼び出します：
<tool_call>
{{"name": "ツール名", "parameters": {{"引数名": "値"}}}}
</tool_call>
システムがツールを実行し、結果を返します。あなたは自分でツールの結果を捏造してはいけません。

オプションB - 最終的な内容の出力：
ツールを通じて十分な情報を得た場合、 "Final Answer:" で始めて章の内容を出力してください。

⚠️ 厳禁事項：
- 1つの返信内にツール呼び出しと Final Answer を混在させること
- ツールの実行結果（Observation）を自分で捏造すること。すべての結果はシステムによって注入されます
- 1つの返信で呼び出せるツールは最大1つです

═══════════════════════════════════════════════════════════════
【章の内容への要求】
═══════════════════════════════════════════════════════════════

1. 内容は必ずツールで取得したシミュレーションデータに基づいていること
2. シミュレーションの効果を示すために原文を多用すること
3. Markdown形式を使用すること（ただし見出しは禁止）：
   - **太字**を使用して重点を示す（小見出しの代わり）
   - リスト（- または 1.2.3.）を使用して要点を整理する
   - 空行で段落を分ける
   - ❌ #、##、###、#### などの見出し記法の使用を禁止する
4. 【引用形式の規範 - 必ず独立した段落にすること】
   引用は独立した段落とし、前後に空行を設けてください。段落の中に混ぜないでください：

   ✅ 正しい形式：
   ```
   大学側の対応は実質的な内容に欠けると見なされました。

   > "大学側の対応モードは、刻一刻と变化するSNS環境において硬直的で遅いものでした。"

   この評価は、公衆の広範な不満を反映しています。
   ```

   ❌ 誤った形式：
   ```
   大学側の対応は実質的な内容に欠けると見なされました。> "大学側の対応モードは..." この評価は...を反映しています。
   ```
5. 他の章との論理的な一貫性を保つこと
6. 【重複の回避】以下の「完了済みの章の内容」を注意深く読み、同じ情報を繰り返さないこと
7. 【再強調】見出しを一切追加しないこと！**太字**で小見出しの代わりとすること"""

SECTION_USER_PROMPT_TEMPLATE = """\
完了した章の内容（重複を避けるために注意深く読んでください）：
{previous_content}

═══════════════════════════════════════════════════════════════
【現在のタスク】執筆する章: {section_title}
═══════════════════════════════════════════════════════════════

【重要事項】
1. 上記の完了済みの章をよく読み、同じ内容を繰り返さないようにしてください！
2. 開始前に必ずツールを呼び出してシミュレーションデータを取得してください。
3. 複数のツールを組み合わせて使用し、一つだけに頼らないでください。
4. レポートの内容は必ず検索結果に基づいている必要があります。自身の知識を使わないでください。

【⚠️ フォーマット警告 - 厳守】
- ❌ 見出し（#、##、###、####などすべて）を書かないでください。
- ❌ 書き始めに "{section_title}" と書かないでください。
- ✅ 章のタイトルはシステムによって自動的に追加されます。
- ✅ 直接本文を書き始め、**太字**で小見出しの代わりとしてください。

開始してください：
1. まず、この章に必要な情報（Thought）を考えてください。
2. 次に、ツール（Action）を呼び出してシミュレーションデータを取得してください。
3. 十分な情報を収集した後、Final Answer（純粋な本文、見出しなし）を出力してください。"""

# ── ReACTループ内メッセージテンプレート ──

REACT_OBSERVATION_TEMPLATE = """\
Observation（検索結果）:

═══ ツール {tool_name} の返却 ═══
{result}

═══════════════════════════════════════════════════════════════
ツール呼び出し済み {tool_calls_count}/{max_tool_calls} 回（使用済み: {used_tools_str}）{unused_hint}
- 情報が十分な場合："Final Answer:" で始めてセクション内容を出力（上記の原文を引用すること）
- より多くの情報が必要な場合：ツールを1つ呼び出して検索を続行
═══════════════════════════════════════════════════════════════"""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "【注意】ツール呼び出しは{tool_calls_count}回のみで、最低{min_tool_calls}回必要です。"
    "ツールを呼び出してより多くのシミュレーションデータを取得してから、Final Answerを出力してください。{unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "現在ツール呼び出しは {tool_calls_count} 回のみで、最低 {min_tool_calls} 回必要です。"
    "ツールを呼び出してシミュレーションデータを取得してください。{unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "ツール呼び出し回数が上限に達しました（{tool_calls_count}/{max_tool_calls}）。これ以上ツールを呼び出せません。"
    '取得済みの情報に基づいて、直ちに "Final Answer:" で始めてセクション内容を出力してください。'
)

REACT_UNUSED_TOOLS_HINT = "\n💡 まだ使用していないツール: {unused_list}、異なるツールを試して多角的な情報を取得することを推奨"

REACT_FORCE_FINAL_MSG = "ツール呼び出し制限に達しました。直接 Final Answer: を出力してセクション内容を生成してください。"

# ── Chat prompt ──

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
あなたは簡潔で効率的なシミュレーション予測アシスタントです。

【背景】
予測条件: {simulation_requirement}

【生成済みの分析レポート】
{report_content}

【ルール】
1. 上記のレポート内容に基づいて優先的に回答する
2. 直接回答し、冗長な思考や論述を避ける
3. レポート内容では回答に不十分な場合のみ、ツールを呼び出してデータを追加検索する
4. 回答は簡潔、明確、整理されたものにする

【利用可能なツール】（必要な場合のみ使用、最大1-2回呼び出し）
{tools_description}

【ツール呼び出しフォーマット】
<tool_call>
{{"name": "ツール名", "parameters": {{"パラメータ名": "パラメータ値"}}}}
</tool_call>

【回答スタイル】
- 簡潔で直接的に、長文を避ける
- > フォーマットで重要な内容を引用する
- まず結論を述べ、次に理由を説明する"""

CHAT_OBSERVATION_SUFFIX = "\n\n簡潔に質問に回答してください。"


# ═══════════════════════════════════════════════════════════════
# ReportAgent メインクラス
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - シミュレーションレポート生成Agent

    ReACT（Reasoning + Acting）モードを採用：
    1. 計画段階：シミュレーション要件を分析し、レポート目次構造を計画
    2. 生成段階：セクションごとに内容を生成、各セクションで複数回ツールを呼び出して情報を取得
    3. 反省段階：内容の完全性と正確性をチェック
    """

    # 最大ツール呼び出し回数（各セクション）
    MAX_TOOL_CALLS_PER_SECTION = 5

    # 最大反省ラウンド数
    MAX_REFLECTION_ROUNDS = 3

    # 対話中の最大ツール呼び出し回数
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self, 
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None
    ):
        """
        Report Agentの初期化

        Args:
            graph_id: グラフID
            simulation_id: シミュレーションID
            simulation_requirement: シミュレーション要件の説明
            llm_client: LLMクライアント（オプション）
            zep_tools: Zepツールサービス（オプション）
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        
        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()
        
        # ツール定義
        self.tools = self._define_tools()

        # ログ記録器（generate_reportで初期化）
        self.report_logger: Optional[ReportLogger] = None
        # コンソールログ記録器（generate_reportで初期化）
        self.console_logger: Optional[ReportConsoleLogger] = None

        logger.info(f"ReportAgent 初期化完了: graph_id={graph_id}, simulation_id={simulation_id}")
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """利用可能なツールを定義する"""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "深く分析したい問題またはトピック",
                    "report_context": "現在のレポートセクションのコンテキスト（オプション、より正確なサブクエスチョンの生成に役立つ）"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "検索クエリ、関連性のソートに使用",
                    "include_expired": "期限切れ/履歴コンテンツを含めるか（デフォルトTrue）"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "検索クエリ文字列",
                    "limit": "返却結果数（オプション、デフォルト10）"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "インタビューテーマまたは要件の説明（例：'寮のホルムアルデヒド問題に対する学生の見解を理解する'）",
                    "max_agents": "最大インタビューAgent数（オプション、デフォルト5、最大10）"
                }
            }
        }
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        ツール呼び出しを実行する

        Args:
            tool_name: ツール名
            parameters: ツールパラメータ
            report_context: レポートコンテキスト（InsightForge用）

        Returns:
            ツール実行結果（テキスト形式）
        """
        logger.info(f"ツール実行: {tool_name}, パラメータ: {parameters}")
        
        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()
            
            elif tool_name == "panorama_search":
                # 広域検索 - 全体像の取得
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()
            
            elif tool_name == "quick_search":
                # 簡易検索 - クイック検索
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()
            
            elif tool_name == "interview_agents":
                # ディープインタビュー - 実際のOASISインタビューAPIを呼び出してシミュレーションAgentの回答を取得（デュアルプラットフォーム）
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()
            
            # ========== 後方互換性のための旧ツール（内部で新ツールにリダイレクト） ==========
            
            elif tool_name == "search_graph":
                # quick_searchにリダイレクト
                logger.info("search_graph をquick_searchにリダイレクト")
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_simulation_context":
                # insight_forgeにリダイレクト（より強力なため）
                logger.info("get_simulation_context をinsight_forgeにリダイレクト")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                return f"不明なツール: {tool_name}。以下のツールのいずれかを使用してください: insight_forge, panorama_search, quick_search"

        except Exception as e:
            logger.error(f"ツール実行失敗: {tool_name}, エラー: {str(e)}")
            return f"ツール実行失敗: {str(e)}"
    
    # 有効なツール名のセット、ベアJSON フォールバック解析時の検証に使用
    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        LLM応答からツール呼び出しを解析する

        サポートされるフォーマット（優先順位順）：
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. ベアJSON（応答全体または1行がツール呼び出しJSON）
        """
        tool_calls = []

        # フォーマット1: XMLスタイル（標準フォーマット）
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # フォーマット2: フォールバック - LLMがベアJSONを直接出力（<tool_call>タグなし）
        # フォーマット1がマッチしなかった場合のみ試行、本文中のJSON誤マッチを回避
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # 応答に思考テキスト + ベアJSONが含まれる可能性あり、最後のJSONオブジェクトの抽出を試行
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """解析されたJSONが有効なツール呼び出しかどうかを検証する"""
        # {"name": ..., "parameters": ...} と {"tool": ..., "params": ...} の2種類のキー名をサポート
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # キー名を name / parameters に統一
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """ツール説明テキストを生成する"""
        desc_parts = ["利用可能なツール："]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  パラメータ: {params_desc}")
        return "\n".join(desc_parts)
    
    def plan_outline(
        self,
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        レポートアウトラインを計画する

        LLMを使用してシミュレーション要件を分析し、レポートの目次構造を計画する

        Args:
            progress_callback: 進捗コールバック関数

        Returns:
            ReportOutline: レポートアウトライン
        """
        logger.info("レポートアウトラインの計画を開始...")

        if progress_callback:
            progress_callback("planning", 0, "シミュレーション要件を分析中...")

        # まずシミュレーションコンテキストを取得
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, "正在生成报告大纲...")
        
        system_prompt = PLAN_SYSTEM_PROMPT
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            if progress_callback:
                progress_callback("planning", 80, "アウトライン構造を解析中...")
            
            # 解析大纲
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            
            outline = ReportOutline(
                title=response.get("title", "シミュレーション分析レポート"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, "アウトライン計画完了")
            
            logger.info(f"アウトライン計画完了: {len(sections)} 個の章")
            return outline
            
        except Exception as e:
            logger.error(f"アウトライン計画失敗: {str(e)}")
            # 返回默认大纲（3个章节，作为fallback）
            return ReportOutline(
                title="未来予測レポート",
                summary="シミュレーション予測に基づく未来のトレンドとリスク分析",
                sections=[
                    ReportSection(title="予測シナリオとコア発見"),
                    ReportSection(title="群衆行動予測分析"),
                    ReportSection(title="トレンド展望とリスクアラート")
                ]
            )
    
    def _generate_section_react(
        self, 
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        使用ReACT模式生成单个章节内容
        
        ReACT循环：
        1. Thought（思考）- 分析需要什么信息
        2. Action（行动）- 调用工具获取信息
        3. Observation（观察）- 分析工具返回结果
        4. 重复直到信息足够或达到最大次数
        5. Final Answer（最终回答）- 生成章节内容
        
        Args:
            section: 要生成的章节
            outline: 完整大纲
            previous_sections: 之前章节的内容（用于保持连贯性）
            progress_callback: 进度回调
            section_index: 章节索引（用于日志记录）
            
        Returns:
            章节内容（Markdown格式）
        """
        logger.info(f"ReACT生成章节: {section.title}")
        
        # 记录章节开始日志
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )

        # 构建用户prompt - 每个已完成章节各传入最大4000字
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # 每个章节最多4000字
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "（これは最初の章です）"
        
        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # ReACT循环
        tool_calls_count = 0
        max_iterations = 5  # 最大迭代轮数
        min_tool_calls = 3  # 最少工具调用次数
        conflict_retries = 0  # 工具调用与Final Answer同时出现的连续冲突次数
        used_tools = set()  # 记录已调用过的工具名
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        # 报告上下文，用于InsightForge的子问题生成
        report_context = f"章のタイトル: {section.title}\nシミュレーションニーズ: {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    f"詳細検索と執筆中 ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})"
                )
            
            # 调用LLM
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            # 检查 LLM 返回是否为 None（API 异常或内容为空）
            if response is None:
                logger.warning(f"章 {section.title} 第 {iteration + 1} 回イテレーション: LLM が None を返しました")
                # 如果还有迭代次数，添加消息并重试
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "（レスポンスなし）"})
                    messages.append({"role": "user", "content": "コンテンツの生成を続けてください。"})
                    continue
                # 最后一次迭代也返回 None，跳出循环进入强制收尾
                break

            logger.debug(f"LLM レスポンス: {response[:200]}...")

            # 解析一次，复用结果
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── 冲突处理：LLM 同时输出了工具调用和 Final Answer ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"章 {section.title} 第 {iteration+1} ラウンド: "
                    f"LLM がツール呼び出しと Final Answer を同時に出力しました（第 {conflict_retries} 回の競合）"
                )

                if conflict_retries <= 2:
                    # 前两次：丢弃本次响应，要求 LLM 重新回复
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "【フォーマットエラー】1回のレスポンスでツール呼び出しと Final Answer が同時に含まれています。これは許可されていません。\n"
                            "各レスポンスでは次の2つのうち1つしか行えません：\n"
                            "- ツールの呼び出し（<tool_call> ブロックを出力し、Final Answer は書かないでください）\n"
                            "- 最終内容の出力（'Final Answer:' で始め、<tool_call> を含めないでください）\n"
                            "どちらか1つだけを行って、再度レスポンスしてください。"
                        ),
                    })
                    continue
                else:
                    # 第三次：降级处理，截断到第一个工具调用，强制执行
                    logger.warning(
                        f"章 {section.title}: 连续して {conflict_retries} 回の競合、"
                        "最初のツール呼び出しを切断実行するようにダウングレードしました"
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # 记录 LLM 响应日志
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # ── 情况1：LLM 输出了 Final Answer ──
            if has_final_answer:
                # 工具调用次数不足，拒绝并要求继续调工具
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"（これらのツールはまだ使用されていません。使用することをお勧めします: {', '.join(unused_tools)}）" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # 正常结束
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(f"章 {section.title} の生成が完了しました（ツール呼び出し: {tool_calls_count}回）")

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # ── 情况2：LLM 尝试调用工具 ──
            if has_tool_calls:
                # 工具额度已耗尽 → 明确告知，要求输出 Final Answer
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # 只执行第一个工具调用
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(f"LLM は {len(tool_calls)} 個のツールを呼び出そうとしましたが、最初の1つだけを実行します: {call['name']}")

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # 构建未使用工具提示
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list="、".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # ── 情况3：既没有工具调用，也没有 Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # 工具调用次数不足，推荐未用过的工具
                unused_tools = all_tools - used_tools
                unused_hint = f"（これらのツールはまだ使用されていません。使用することをお勧めします: {', '.join(unused_tools)}）" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # 工具调用已足够，LLM 输出了内容但没带 "Final Answer:" 前缀
            # 直接将这段内容作为最终答案，不再空转
            logger.info(f"章 {section.title} に 'Final Answer:' プレフィックスが検出されなかったため、LLM出力を直接最終コンテンツとして採用します（ツール呼び出し: {tool_calls_count}回）")
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        # 达到最大迭代次数，强制生成内容
        logger.warning(f"章 {section.title} が最大イテレーション数に達したため強制的に生成します")
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        # 检查强制收尾时 LLM 返回是否为 None
        if response is None:
            logger.error(f"章 {section.title} 強制終了時にLLMが None を返しました。デフォルトのエラープロンプトを使用します")
            final_answer = f"（本章の生成に失敗しました：LLM が空のレスポンスを返しました。後でもう一度お試しください）"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        # 记录章节内容生成完成日志
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def generate_report(
        self, 
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        生成完整报告（分章节实时输出）
        
        每个章节生成完成后立即保存到文件夹，不需要等待整个报告完成。
        文件结构：
        reports/{report_id}/
            meta.json       - 报告元信息
            outline.json    - 报告大纲
            progress.json   - 生成进度
            section_01.md   - 第1章节
            section_02.md   - 第2章节
            ...
            full_report.md  - 完整报告
        
        Args:
            progress_callback: 进度回调函数 (stage, progress, message)
            report_id: 报告ID（可选，如果不传则自动生成）
            
        Returns:
            Report: 完整报告
        """
        import uuid
        
        # 如果没有传入 report_id，则自动生成
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )
        
        # 已完成的章节标题列表（用于进度追踪）
        completed_section_titles = []
        
        try:
            # 初始化：创建报告文件夹并保存初始状态
            ReportManager._ensure_report_folder(report_id)
            
            # 初始化日志记录器（结构化日志 agent_log.jsonl）
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )
            
            # 初始化控制台日志记录器（console_log.txt）
            self.console_logger = ReportConsoleLogger(report_id)
            
            ReportManager.update_progress(
                report_id, "pending", 0, "レポートを初期化中...",
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            # 阶段1: 规划大纲
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, "大綱の計画を開始...",
                completed_sections=[]
            )
            
            # 记录规划开始日志
            self.report_logger.log_planning_start()
            
            if progress_callback:
                progress_callback("planning", 0, "大綱の計画を開始...")
            
            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: 
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline
            
            # 记录规划完成日志
            self.report_logger.log_planning_complete(outline.to_dict())
            
            # 保存大纲到文件
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, f"大綱の計画が完了しました。合計 {len(outline.sections)} 章です",
                completed_sections=[]
            )
            ReportManager.save_report(report)
            
            logger.info(f"大綱がファイルに保存されました: {report_id}/outline.json")
            
            # 阶段2: 逐章节生成（分章节保存）
            report.status = ReportStatus.GENERATING
            
            total_sections = len(outline.sections)
            generated_sections = []  # 保存内容用于上下文
            
            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)
                
                # 更新进度
                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    f"章を生成中: {section.title} ({section_num}/{total_sections})",
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )
                
                if progress_callback:
                    progress_callback(
                        "generating", 
                        base_progress, 
                        f"章を生成中: {section.title} ({section_num}/{total_sections})"
                    )
                
                # 生成主章节内容
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage, 
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )
                
                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # 保存章节
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # 记录章节完成日志
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(f"章が保存されました: {report_id}/section_{section_num:02d}.md")
                
                # 更新进度
                ReportManager.update_progress(
                    report_id, "generating", 
                    base_progress + int(70 / total_sections),
                    f"章 {section.title} が完了しました",
                    current_section=None,
                    completed_sections=completed_section_titles
                )
            
            # 阶段3: 组装完整报告
            if progress_callback:
                progress_callback("generating", 95, "完全なレポートを組み立て中...")
            
            ReportManager.update_progress(
                report_id, "generating", 95, "完全なレポートを組み立て中...",
                completed_sections=completed_section_titles
            )
            
            # 使用ReportManager组装完整报告
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()
            
            # 计算总耗时
            total_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # 记录报告完成日志
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )
            
            # 保存最终报告
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, "レポート生成が完了しました",
                completed_sections=completed_section_titles
            )
            
            if progress_callback:
                progress_callback("completed", 100, "レポート生成が完了しました")
            
            logger.info(f"レポート生成完了: {report_id}")
            
            # 关闭控制台日志记录器
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
            
        except Exception as e:
            logger.error(f"レポート生成失敗: {str(e)}")
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            # 记录错误日志
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            # 保存失败状态
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, f"レポート生成失敗: {str(e)}",
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass  # 忽略保存失败的错误
            
            # 关闭控制台日志记录器
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
    
    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        与Report Agent对话
        
        在对话中Agent可以自主调用检索工具来回答问题
        
        Args:
            message: 用户消息
            chat_history: 对话历史
            
        Returns:
            {
                "response": "Agent回复",
                "tool_calls": [呼び出されたツールリスト],
                "sources": [情報ソース]
            }
        """
        logger.info(f"Report Agent 対話: {message[:50]}...")
        
        chat_history = chat_history or []
        
        # 获取已生成的报告内容
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # 限制报告长度，避免上下文过长
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [レポート内容は切り捨てられました] ..."
        except Exception as e:
            logger.warning(f"获取报告内容失败: {e}")
        
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "（レポートなし）",
            tools_description=self._get_tools_description(),
        )

        # 构建消息
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加历史对话
        for h in chat_history[-10:]:  # 限制历史长度
            messages.append(h)
        
        # 添加用户消息
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # ReACT循环（简化版）
        tool_calls_made = []
        max_iterations = 2  # 减少迭代轮数
        
        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            
            # 解析工具调用
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # 没有工具调用，直接返回响应
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            # 执行工具调用（限制数量）
            tool_results = []
            for call in tool_calls[:1]:  # 每轮最多执行1次工具调用
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]  # 限制结果长度
                })
                tool_calls_made.append(call)
            
            # 将结果添加到消息
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']}结果]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        # 达到最大迭代，获取最终响应
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        
        # 清理响应
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    报告管理器
    
    负责报告的持久化存储和检索
    
    文件结构（分章节输出）：
    reports/
      {report_id}/
        meta.json          - 报告元信息和状态
        outline.json       - 报告大纲
        progress.json      - 生成进度
        section_01.md      - 第1章节
        section_02.md      - 第2章节
        ...
        full_report.md     - 完整报告
    """
    
    # 报告存储目录
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')
    
    @classmethod
    def _ensure_reports_dir(cls):
        """确保报告根目录存在"""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """获取报告文件夹路径"""
        return os.path.join(cls.REPORTS_DIR, report_id)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """确保报告文件夹存在并返回路径"""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """获取报告元信息文件路径"""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """获取完整报告Markdown文件路径"""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """获取大纲文件路径"""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """获取进度文件路径"""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """获取章节Markdown文件路径"""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """获取 Agent 日志文件路径"""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """获取控制台日志文件路径"""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        获取控制台日志内容
        
        这是报告生成过程中的控制台输出日志（INFO、WARNING等），
        与 agent_log.jsonl 的结构化日志不同。
        
        Args:
            report_id: 报告ID
            from_line: 从第几行开始读取（用于增量获取，0 表示从头开始）
            
        Returns:
            {
                "logs": [日志行列表],
                "total_lines": 总行数,
                "from_line": 起始行号,
                "has_more": 是否还有更多日志
            }
        """
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # 保留原始日志行，去掉末尾换行符
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # 已读取到末尾
        }
    
    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        获取完整的控制台日志（一次性获取全部）
        
        Args:
            report_id: 报告ID
            
        Returns:
            日志行列表
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        获取 Agent 日志内容
        
        Args:
            report_id: 报告ID
            from_line: 从第几行开始读取（用于增量获取，0 表示从头开始）
            
        Returns:
            {
                "logs": [日志条目列表],
                "total_lines": 总行数,
                "from_line": 起始行号,
                "has_more": 是否还有更多日志
            }
        """
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # 跳过解析失败的行
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # 已读取到末尾
        }
    
    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        获取完整的 Agent 日志（用于一次性获取全部）
        
        Args:
            report_id: 报告ID
            
        Returns:
            日志条目列表
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        保存报告大纲
        
        在规划阶段完成后立即调用
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"大纲已保存: {report_id}")
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        保存单个章节

        在每个章节生成完成后立即调用，实现分章节输出

        Args:
            report_id: 报告ID
            section_index: 章节索引（从1开始）
            section: 章节对象

        Returns:
            保存的文件路径
        """
        cls._ensure_report_folder(report_id)

        # 构建章节Markdown内容 - 清理可能存在的重复标题
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # 保存文件
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"章节已保存: {report_id}/{file_suffix}")
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        清理章节内容
        
        1. 移除内容开头与章节标题重复的Markdown标题行
        2. 将所有 ### 及以下级别的标题转换为粗体文本
        
        Args:
            content: 原始内容
            section_title: 章节标题
            
        Returns:
            清理后的内容
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 检查是否是Markdown标题行
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                # 检查是否是与章节标题重复的标题（跳过前5行内的重复）
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                # 将所有级别的标题（#, ##, ###, ####等）转换为粗体
                # 因为章节标题由系统添加，内容中不应有任何标题
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # 添加空行
                continue
            
            # 如果上一行是被跳过的标题，且当前行为空，也跳过
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        # 移除开头的空行
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        # 移除开头的分隔线
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # 同时移除分隔线后的空行
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        更新报告生成进度
        
        前端可以通过读取progress.json获取实时进度
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """获取报告生成进度"""
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        获取已生成的章节列表
        
        返回所有已保存的章节文件信息
        """
        folder = cls._get_report_folder(report_id)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 从文件名解析章节索引
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections
    
    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        组装完整报告
        
        从已保存的章节文件组装完整报告，并进行标题清理
        """
        folder = cls._get_report_folder(report_id)
        
        # 构建报告头部
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"
        
        # 按顺序读取所有章节文件
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        # 后处理：清理整个报告的标题问题
        md_content = cls._post_process_report(md_content, outline)
        
        # 保存完整报告
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"完全なレポートが組み立てられました: {report_id}")
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        后处理报告内容
        
        1. 移除重复的标题
        2. 保留报告主标题(#)和章节标题(##)，移除其他级别的标题(###, ####等)
        3. 清理多余的空行和分隔线
        
        Args:
            content: 原始报告内容
            outline: 报告大纲
            
        Returns:
            处理后的内容
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        # 收集大纲中的所有章节标题
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # 检查是否是标题行
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # 检查是否是重复标题（在连续5行内出现相同内容的标题）
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    # 跳过重复标题及其后的空行
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                # 标题层级处理：
                # - # (level=1) 只保留报告主标题
                # - ## (level=2) 保留章节标题
                # - ### 及以下 (level>=3) 转换为粗体文本
                
                if level == 1:
                    if title == outline.title:
                        # 保留报告主标题
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # 章节标题错误使用了#，修正为##
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # 其他一级标题转为粗体
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # 保留章节标题
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # 非章节的二级标题转为粗体
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # ### 及以下级别的标题转换为粗体文本
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                # 跳过标题后紧跟的分隔线
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                # 标题后只保留一个空行
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        # 清理连续的多个空行（保留最多2个）
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """保存报告元信息和完整报告"""
        cls._ensure_report_folder(report.report_id)
        
        # 保存元信息JSON
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        # 保存大纲
        if report.outline:
            cls.save_outline(report.report_id, report.outline)
        
        # 保存完整Markdown报告
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        
        logger.info(f"レポートが保存されました: {report.report_id}")
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """获取报告"""
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            # 兼容旧格式：检查直接存储在reports目录下的文件
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 重建Report对象
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        # 如果markdown_content为空，尝试从full_report.md读取
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
        
        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error')
        )
    
    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """根据模拟ID获取报告"""
        cls._ensure_reports_dir()
        
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # 新格式：文件夹
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report and report.simulation_id == simulation_id:
                    return report
            # 兼容旧格式：JSON文件
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report and report.simulation_id == simulation_id:
                    return report
        
        return None
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """列出报告"""
        cls._ensure_reports_dir()
        
        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # 新格式：文件夹
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # 兼容旧格式：JSON文件
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
        
        # 按创建时间倒序
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """删除报告（整个文件夹）"""
        import shutil
        
        folder_path = cls._get_report_folder(report_id)
        
        # 新格式：删除整个文件夹
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(f"レポートフォルダが削除されました: {report_id}")
            return True
        
        # 兼容旧格式：删除单独的文件
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")
        
        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True
        
        return deleted
