"""
オントロジー生成サービス
インターフェース1：テキスト内容を分析し、社会シミュレーションに適したエンティティと関係タイプの定義を生成する
"""

import json
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# オントロジー生成用システムプロンプト
ONTOLOGY_SYSTEM_PROMPT = """あなたは専門的なナレッジグラフのオントロジー設計エキスパートです。あなたのタスクは、与えられたテキスト内容とシミュレーション要件を分析し、**ソーシャルメディア世論シミュレーション**に適したエンティティタイプと関係タイプを設計することです。

**重要：有効なJSON形式のデータを出力してください。それ以外の内容は出力しないでください。**

## コアタスクの背景

私たちは**ソーシャルメディア世論シミュレーションシステム**を構築しています。このシステムでは：
- 各エンティティは、ソーシャルメディア上で発信、交流、情報伝達が可能な「アカウント」または「主体」です
- エンティティ間で相互に影響し合い、リツイート、コメント、返信を行います
- 世論イベントにおける各方面の反応と情報伝達経路をシミュレーションする必要があります

したがって、**エンティティは現実に実在し、ソーシャルメディア上で発信・交流が可能な主体**でなければなりません：

**可能なもの**：
- 具体的な個人（公人、当事者、オピニオンリーダー、専門家、一般人）
- 企業・会社（公式アカウントを含む）
- 組織・機関（大学、協会、NGO、労働組合など）
- 政府機関、規制当局
- メディア機関（新聞、テレビ局、個人メディア、ウェブサイト）
- ソーシャルメディアプラットフォーム自体
- 特定のグループ代表（同窓会、ファンクラブ、権利擁護グループなど）

**不可のもの**：
- 抽象概念（「世論」「感情」「トレンド」など）
- テーマ/トピック（「学術的誠実性」「教育改革」など）
- 観点/態度（「支持派」「反対派」など）

## 出力フォーマット

JSON形式で以下の構造を出力してください：

```json
{
    "entity_types": [
        {
            "name": "エンティティタイプ名（英語、PascalCase）",
            "description": "簡潔な説明（英語、100文字以内）",
            "attributes": [
                {
                    "name": "属性名（英語、snake_case）",
                    "type": "text",
                    "description": "属性の説明"
                }
            ],
            "examples": ["サンプルエンティティ1", "サンプルエンティティ2"]
        }
    ],
    "edge_types": [
        {
            "name": "関係タイプ名（英語、UPPER_SNAKE_CASE）",
            "description": "簡潔な説明（英語、100文字以内）",
            "source_targets": [
                {"source": "ソースエンティティタイプ", "target": "ターゲットエンティティタイプ"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "テキスト内容の簡潔な分析説明（日本語）"
}
```

## 設計ガイドライン（非常に重要！）

### 1. エンティティタイプの設計 - 厳守事項

**数量要件：ちょうど10個のエンティティタイプが必要**

**階層構造要件（具体的なタイプとフォールバックタイプの両方を含める必要あり）**：

10個のエンティティタイプには以下の階層を含める必要があります：

A. **フォールバックタイプ（必須、リストの最後の2つに配置）**：
   - `Person`: あらゆる自然人個体のフォールバックタイプ。他のより具体的な人物タイプに属さない場合にこのカテゴリに分類。
   - `Organization`: あらゆる組織・機関のフォールバックタイプ。他のより具体的な組織タイプに属さない場合にこのカテゴリに分類。

B. **具体的なタイプ（8個、テキスト内容に基づいて設計）**：
   - テキストに登場する主要な役割に対して、より具体的なタイプを設計
   - 例：テキストが学術イベントに関する場合、`Student`, `Professor`, `University` など
   - 例：テキストがビジネスイベントに関する場合、`Company`, `CEO`, `Employee` など

**フォールバックタイプが必要な理由**：
- テキストには「小中学校の教師」「通りすがりの人」「あるネットユーザー」など様々な人物が登場します
- 専用のタイプがない場合、`Person` に分類されるべきです
- 同様に、小規模な組織や一時的なグループは `Organization` に分類されるべきです

**具体的なタイプの設計原則**：
- テキストから高頻度で登場するまたは重要な役割タイプを識別
- 各具体的なタイプには明確な境界を設け、重複を避ける
- description はフォールバックタイプとの違いを明確に説明する必要がある

### 2. 関係タイプの設計

- 数量：6-10個
- 関係はソーシャルメディアの交流における実際のつながりを反映すべき
- 関係の source_targets が定義したエンティティタイプをカバーしていることを確認

### 3. 属性の設計

- 各エンティティタイプに1-3個の主要属性
- **注意**：属性名に `name`、`uuid`、`group_id`、`created_at`、`summary` は使用不可（システム予約語）
- 推奨：`full_name`, `title`, `role`, `position`, `location`, `description` など

## エンティティタイプの参考

**個人タイプ（具体的）**：
- Student: 学生
- Professor: 教授・学者
- Journalist: 記者
- Celebrity: 著名人・インフルエンサー
- Executive: 経営幹部
- Official: 政府関係者
- Lawyer: 弁護士
- Doctor: 医師

**個人タイプ（フォールバック）**：
- Person: あらゆる自然人（上記の具体的なタイプに属さない場合に使用）

**組織タイプ（具体的）**：
- University: 大学
- Company: 企業
- GovernmentAgency: 政府機関
- MediaOutlet: メディア機関
- Hospital: 病院
- School: 小中高校
- NGO: 非政府組織

**組織タイプ（フォールバック）**：
- Organization: あらゆる組織・機関（上記の具体的なタイプに属さない場合に使用）

## 関係タイプの参考

- WORKS_FOR: 勤務先
- STUDIES_AT: 在籍先
- AFFILIATED_WITH: 所属先
- REPRESENTS: 代表
- REGULATES: 規制
- REPORTS_ON: 報道
- COMMENTS_ON: コメント
- RESPONDS_TO: 返信
- SUPPORTS: 支持
- OPPOSES: 反対
- COLLABORATES_WITH: 協力
- COMPETES_WITH: 競争
"""


class OntologyGenerator:
    """
    オントロジー生成器
    テキスト内容を分析し、エンティティと関係タイプの定義を生成する
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        オントロジー定義を生成する

        Args:
            document_texts: ドキュメントテキストのリスト
            simulation_requirement: シミュレーション要件の説明
            additional_context: 追加コンテキスト

        Returns:
            オントロジー定義（entity_types, edge_typesなど）
        """
        # ユーザーメッセージを構築
        user_message = self._build_user_message(
            document_texts,
            simulation_requirement,
            additional_context
        )

        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        # LLMを呼び出す（オントロジー定義JSONは大きいため、十分なトークンが必要）
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=16384
        )

        # 検証と後処理
        result = self._validate_and_process(result)

        return result

    # LLMに渡すテキストの最大長（5万字）
    MAX_TEXT_LENGTH_FOR_LLM = 50000

    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """ユーザーメッセージを構築する"""

        # テキストを結合
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        # テキストが5万字を超える場合、切り詰める（LLMに渡す内容のみ影響、グラフ構築には影響しない）
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(原文は全{original_length}文字、先頭{self.MAX_TEXT_LENGTH_FOR_LLM}文字をオントロジー分析に使用)..."

        message = f"""## シミュレーション要件

{simulation_requirement}

## ドキュメント内容

{combined_text}
"""

        if additional_context:
            message += f"""
## 追加説明

{additional_context}
"""

        message += """
上記の内容に基づいて、社会世論シミュレーションに適したエンティティタイプと関係タイプを設計してください。

**厳守ルール**：
1. ちょうど10個のエンティティタイプを出力すること
2. 最後の2つはフォールバックタイプ：Person（個人フォールバック）と Organization（組織フォールバック）
3. 最初の8個はテキスト内容に基づいて設計された具体的なタイプ
4. すべてのエンティティタイプは現実に発信可能な主体であること、抽象概念は不可
5. 属性名に name、uuid、group_id などの予約語は使用不可、full_name、org_name などを代用
"""

        return message

    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """結果を検証し後処理する"""

        # 必須フィールドの存在を確認
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""

        # エンティティタイプの検証
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # descriptionが100文字を超えないようにする
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."

        # 関係タイプの検証
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."

        # Zep API制限：カスタムエンティティタイプは最大10個、カスタムエッジタイプは最大10個
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # フォールバックタイプの定義
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }

        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }

        # フォールバックタイプが既に存在するか確認
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names

        # 追加が必要なフォールバックタイプ
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)

        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)

            # 追加後に10個を超える場合、既存のタイプを一部削除
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # 削除が必要な数を計算
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # 末尾から削除（前方のより重要な具体的タイプを保持）
                result["entity_types"] = result["entity_types"][:-to_remove]

            # フォールバックタイプを追加
            result["entity_types"].extend(fallbacks_to_add)

        # 最終的に制限を超えないことを確認（防御的プログラミング）
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]

        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]

        return result

    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        オントロジー定義をPythonコードに変換する（ontology.pyと同様）

        Args:
            ontology: オントロジー定義

        Returns:
            Pythonコード文字列
        """
        code_lines = [
            '"""',
            'カスタムエンティティタイプ定義',
            'MiroFishにより自動生成、社会世論シミュレーション用',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== エンティティタイプ定義 ==============',
            '',
        ]

        # エンティティタイプを生成
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")

            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')

            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')

            code_lines.append('')
            code_lines.append('')

        code_lines.append('# ============== 関係タイプ定義 ==============')
        code_lines.append('')

        # 関係タイプを生成
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # PascalCaseクラス名に変換
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")

            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')

            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')

            code_lines.append('')
            code_lines.append('')

        # タイプ辞書を生成
        code_lines.append('# ============== タイプ設定 ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')

        # エッジのsource_targetsマッピングを生成
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')

        return '\n'.join(code_lines)
