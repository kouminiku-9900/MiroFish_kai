"""
グラフ関連APIルーティング
プロジェクトコンテキスト機構を採用、サーバー側で状態を永続化
"""

import os
import traceback
import threading
from flask import request, jsonify

from . import graph_bp
from ..config import Config
from ..services.ontology_generator import OntologyGenerator
from ..services.graph_builder import GraphBuilderService
from ..services.text_processor import TextProcessor
from ..utils.file_parser import FileParser
from ..utils.logger import get_logger
from ..models.task import TaskManager, TaskStatus
from ..models.project import ProjectManager, ProjectStatus

# ロガーを取得
logger = get_logger('mirofish.api')


def allowed_file(filename: str) -> bool:
    """ファイル拡張子が許可されているか確認"""
    if not filename or '.' not in filename:
        return False
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    return ext in Config.ALLOWED_EXTENSIONS


# ============== プロジェクト管理インターフェース ==============

@graph_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id: str):
    """
    プロジェクト詳細を取得
    """
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": f"プロジェクトが存在しません: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": project.to_dict()
    })


@graph_bp.route('/project/list', methods=['GET'])
def list_projects():
    """
    全プロジェクトを一覧表示
    """
    limit = request.args.get('limit', 50, type=int)
    projects = ProjectManager.list_projects(limit=limit)

    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in projects],
        "count": len(projects)
    })


@graph_bp.route('/project/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    プロジェクトを削除
    """
    success = ProjectManager.delete_project(project_id)

    if not success:
        return jsonify({
            "success": False,
            "error": f"プロジェクトが存在しないか削除に失敗しました: {project_id}"
        }), 404

    return jsonify({
        "success": True,
        "message": f"プロジェクトを削除しました: {project_id}"
    })


@graph_bp.route('/project/<project_id>/reset', methods=['POST'])
def reset_project(project_id: str):
    """
    プロジェクト状態をリセット（グラフの再構築用）
    """
    project = ProjectManager.get_project(project_id)

    if not project:
        return jsonify({
            "success": False,
            "error": f"プロジェクトが存在しません: {project_id}"
        }), 404

    # オントロジー生成済み状態にリセット
    if project.ontology:
        project.status = ProjectStatus.ONTOLOGY_GENERATED
    else:
        project.status = ProjectStatus.CREATED

    project.graph_id = None
    project.graph_build_task_id = None
    project.error = None
    ProjectManager.save_project(project)

    return jsonify({
        "success": True,
        "message": f"プロジェクトをリセットしました: {project_id}",
        "data": project.to_dict()
    })


# ============== インターフェース1：ファイルアップロードとオントロジー生成 ==============

@graph_bp.route('/ontology/generate', methods=['POST'])
def generate_ontology():
    """
    インターフェース1：ファイルをアップロードし、分析してオントロジー定義を生成

    リクエスト方式：multipart/form-data

    パラメータ：
        files: アップロードファイル（PDF/MD/TXT）、複数可
        simulation_requirement: シミュレーション要件の説明（必須）
        project_name: プロジェクト名（任意）
        additional_context: 追加説明（任意）

    レスポンス：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "ontology": {
                    "entity_types": [...],
                    "edge_types": [...],
                    "analysis_summary": "..."
                },
                "files": [...],
                "total_text_length": 12345
            }
        }
    """
    try:
        logger.info("=== オントロジー定義の生成を開始 ===")

        simulation_requirement = request.form.get('simulation_requirement', '')
        project_name = request.form.get('project_name', 'Unnamed Project')
        additional_context = request.form.get('additional_context', '')

        logger.debug(f"プロジェクト名: {project_name}")
        logger.debug(f"シミュレーション要件: {simulation_requirement[:100]}...")

        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "シミュレーション要件の説明を入力してください (simulation_requirement)"
            }), 400

        uploaded_files = request.files.getlist('files')
        if not uploaded_files or all(not f.filename for f in uploaded_files):
            return jsonify({
                "success": False,
                "error": "少なくとも1つのドキュメントファイルをアップロードしてください"
            }), 400

        project = ProjectManager.create_project(name=project_name)
        project.simulation_requirement = simulation_requirement
        logger.info(f"プロジェクトを作成: {project.project_id}")

        saved_files = []
        for file in uploaded_files:
            if file and file.filename and allowed_file(file.filename):
                file_info = ProjectManager.save_file_to_project(
                    project.project_id,
                    file,
                    file.filename
                )
                project.files.append({
                    "filename": file_info["original_filename"],
                    "saved_filename": file_info["saved_filename"],
                    "path": file_info["path"],
                    "size": file_info["size"]
                })
                saved_files.append(file_info)

        if not saved_files:
            ProjectManager.delete_project(project.project_id)
            return jsonify({
                "success": False,
                "error": "ドキュメントの処理に成功しませんでした。ファイル形式を確認してください"
            }), 400

        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="ontology_generate",
            metadata={
                "project_id": project.project_id,
                "file_count": len(saved_files)
            }
        )

        project.status = ProjectStatus.ONTOLOGY_GENERATING
        project.ontology_task_id = task_id
        project.error = None
        ProjectManager.save_project(project)

        def run_ontology_task():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=5,
                    message="アップロード済みファイルを確認中...",
                    progress_detail={"stage": "upload_saved", "stage_progress": 100}
                )

                document_texts = []
                all_text = ""
                total_files = len(saved_files)

                for idx, file_info in enumerate(saved_files, start=1):
                    task_manager.update_task(
                        task_id,
                        progress=10 + int((idx / total_files) * 30),
                        message=f"テキスト抽出中: {file_info['original_filename']} ({idx}/{total_files})",
                        progress_detail={
                            "stage": "text_extraction",
                            "stage_progress": int(idx / total_files * 100),
                            "current": idx,
                            "total": total_files,
                            "item_name": file_info["original_filename"]
                        }
                    )

                    text = FileParser.extract_text(file_info["path"])
                    text = TextProcessor.preprocess_text(text)
                    document_texts.append(text)
                    all_text += f"\n\n=== {file_info['original_filename']} ===\n{text}"

                if not document_texts:
                    raise ValueError("抽出可能なドキュメント内容が見つかりませんでした")

                project.total_text_length = len(all_text)
                ProjectManager.save_extracted_text(project.project_id, all_text)
                task_manager.update_task(
                    task_id,
                    progress=45,
                    message=f"テキスト抽出完了、合計 {len(all_text)} 文字",
                    progress_detail={"stage": "text_preprocessing", "stage_progress": 100}
                )

                task_manager.update_task(
                    task_id,
                    progress=60,
                    message="オントロジーを生成中...",
                    progress_detail={"stage": "ontology_generation", "stage_progress": 0}
                )
                logger.info("LLMを呼び出してオントロジー定義を生成中...")
                generator = OntologyGenerator()
                ontology = generator.generate(
                    document_texts=document_texts,
                    simulation_requirement=simulation_requirement,
                    additional_context=additional_context if additional_context else None
                )

                entity_count = len(ontology.get("entity_types", []))
                edge_count = len(ontology.get("edge_types", []))
                logger.info(f"オントロジー生成完了: {entity_count} エンティティタイプ, {edge_count} 関係タイプ")

                project.ontology = {
                    "entity_types": ontology.get("entity_types", []),
                    "edge_types": ontology.get("edge_types", [])
                }
                project.analysis_summary = ontology.get("analysis_summary", "")
                project.status = ProjectStatus.ONTOLOGY_GENERATED
                project.error = None
                ProjectManager.save_project(project)

                task_manager.complete_task(
                    task_id,
                    result={
                        "project_id": project.project_id,
                        "status": project.status.value,
                        "entity_count": entity_count,
                        "edge_count": edge_count
                    }
                )
                task_manager.update_task(
                    task_id,
                    message="オントロジー生成完了",
                    progress_detail={"stage": "ontology_persisted", "stage_progress": 100}
                )
                logger.info(f"=== オントロジー生成完了 === プロジェクトID: {project.project_id}")
            except Exception as e:
                logger.error(f"オントロジー生成に失敗: {str(e)}")
                logger.debug(traceback.format_exc())
                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)
                task_manager.fail_task(task_id, str(e))

        thread = threading.Thread(target=run_ontology_task, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "project_name": project.name,
                "task_id": task_id,
                "status": project.status.value,
                "files": project.files,
                "total_text_length": project.total_text_length
            }
        })

    except Exception as e:
        logger.error(f"オントロジー生成に失敗: {str(e)}")
        logger.debug(traceback.format_exc())
        response_data = {"success": False, "error": str(e)}
        if Config.DEBUG:
            response_data["traceback"] = traceback.format_exc()
        return jsonify(response_data), 500


# ============== オントロジータスク照会インターフェース ==============

@graph_bp.route('/ontology/status', methods=['POST'])
def get_ontology_status():
    """オントロジー生成タスク状態を照会"""
    data = request.get_json() or {}
    task_id = data.get('task_id')
    project_id = data.get('project_id')

    project = ProjectManager.get_project(project_id) if project_id else None
    if not task_id and project:
        task_id = project.ontology_task_id

    if project and project.status == ProjectStatus.ONTOLOGY_GENERATED:
        return jsonify({
            "success": True,
            "data": {
                "project_id": project.project_id,
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "message": "オントロジー生成完了",
                "result": {
                    "project_id": project.project_id,
                    "status": project.status.value
                }
            }
        })

    if not task_id:
        return jsonify({
            "success": False,
            "error": "task_id または project_id を指定してください"
        }), 400

    task = TaskManager().get_task(task_id)
    if not task:
        return jsonify({
            "success": False,
            "error": f"タスクが存在しません: {task_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


# ============== インターフェース2：グラフ構築 ==============

@graph_bp.route('/build', methods=['POST'])
def build_graph():
    """
    インターフェース2：project_idに基づいてグラフを構築

    リクエスト（JSON）：
        {
            "project_id": "proj_xxxx",  // 必須、インターフェース1から取得
            "graph_name": "グラフ名",    // 任意
            "chunk_size": 500,          // 任意、デフォルト500
            "chunk_overlap": 50         // 任意、デフォルト50
        }

    レスポンス：
        {
            "success": true,
            "data": {
                "project_id": "proj_xxxx",
                "task_id": "task_xxxx",
                "message": "グラフ構築タスクを開始しました"
            }
        }
    """
    try:
        logger.info("=== グラフ構築を開始 ===")

        # 設定を確認
        errors = []
        if not Config.ZEP_API_KEY:
            errors.append("ZEP_API_KEYが未設定です")
        if errors:
            logger.error(f"設定エラー: {errors}")
            return jsonify({
                "success": False,
                "error": "設定エラー: " + "; ".join(errors)
            }), 500

        # リクエストを解析
        data = request.get_json() or {}
        project_id = data.get('project_id')
        logger.debug(f"リクエストパラメータ: project_id={project_id}")

        if not project_id:
            return jsonify({
                "success": False,
                "error": "project_idを入力してください"
            }), 400

        # プロジェクトを取得
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"プロジェクトが存在しません: {project_id}"
            }), 404

        # プロジェクト状態を確認
        force = data.get('force', False)  # 強制再構築

        if project.status in [ProjectStatus.CREATED, ProjectStatus.ONTOLOGY_GENERATING]:
            return jsonify({
                "success": False,
                "error": "プロジェクトのオントロジーが未生成です。先に /ontology/generate を呼び出してください"
            }), 400

        if project.status == ProjectStatus.GRAPH_BUILDING and not force:
            return jsonify({
                "success": False,
                "error": "グラフは構築中です。重複送信しないでください。強制再構築するには force: true を追加してください",
                "task_id": project.graph_build_task_id
            }), 400

        # 強制再構築の場合、状態をリセット
        if force and project.status in [ProjectStatus.GRAPH_BUILDING, ProjectStatus.FAILED, ProjectStatus.GRAPH_COMPLETED]:
            project.status = ProjectStatus.ONTOLOGY_GENERATED
            project.graph_id = None
            project.graph_build_task_id = None
            project.error = None

        # 設定を取得
        graph_name = data.get('graph_name', project.name or 'MiroFish Graph')
        chunk_size = data.get('chunk_size', project.chunk_size or Config.DEFAULT_CHUNK_SIZE)
        chunk_overlap = data.get('chunk_overlap', project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP)

        # プロジェクト設定を更新
        project.chunk_size = chunk_size
        project.chunk_overlap = chunk_overlap

        # 抽出されたテキストを取得
        text = ProjectManager.get_extracted_text(project_id)
        if not text:
            return jsonify({
                "success": False,
                "error": "抽出されたテキスト内容が見つかりません"
            }), 400

        # オントロジーを取得
        ontology = project.ontology
        if not ontology:
            return jsonify({
                "success": False,
                "error": "オントロジー定義が見つかりません"
            }), 400

        # 非同期タスクを作成
        task_manager = TaskManager()
        task_id = task_manager.create_task(f"グラフ構築: {graph_name}")
        logger.info(f"グラフ構築タスクを作成: task_id={task_id}, project_id={project_id}")

        # プロジェクト状態を更新
        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)

        # バックグラウンドタスクを開始
        def build_task():
            build_logger = get_logger('mirofish.build')
            try:
                build_logger.info(f"[{task_id}] グラフ構築を開始...")
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    message="グラフ構築サービスを初期化中..."
                )

                # グラフ構築サービスを作成
                builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)

                # チャンク分割
                task_manager.update_task(
                    task_id,
                    message="テキストをチャンク分割中...",
                    progress=5
                )
                chunks = TextProcessor.split_text(
                    text,
                    chunk_size=chunk_size,
                    overlap=chunk_overlap
                )
                total_chunks = len(chunks)

                # グラフを作成
                task_manager.update_task(
                    task_id,
                    message="Zepグラフを作成中...",
                    progress=10
                )
                graph_id = builder.create_graph(name=graph_name)

                # プロジェクトのgraph_idを更新
                project.graph_id = graph_id
                ProjectManager.save_project(project)

                # オントロジーを設定
                task_manager.update_task(
                    task_id,
                    message="オントロジー定義を設定中...",
                    progress=15
                )
                builder.set_ontology(graph_id, ontology)

                # テキストを追加（progress_callbackのシグネチャは (msg, progress_ratio)）
                def add_progress_callback(msg, progress_ratio):
                    progress = 15 + int(progress_ratio * 40)  # 15% - 55%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )

                task_manager.update_task(
                    task_id,
                    message=f"{total_chunks} 個のテキストチャンクの追加を開始...",
                    progress=15
                )

                episode_uuids = builder.add_text_batches(
                    graph_id,
                    chunks,
                    batch_size=3,
                    progress_callback=add_progress_callback
                )

                # Zepの処理完了を待機（各episodeのprocessed状態を確認）
                task_manager.update_task(
                    task_id,
                    message="Zepのデータ処理を待機中...",
                    progress=55
                )

                def wait_progress_callback(msg, progress_ratio):
                    progress = 55 + int(progress_ratio * 35)  # 55% - 90%
                    task_manager.update_task(
                        task_id,
                        message=msg,
                        progress=progress
                    )

                builder._wait_for_episodes(episode_uuids, wait_progress_callback)

                # グラフデータを取得
                task_manager.update_task(
                    task_id,
                    message="グラフデータを取得中...",
                    progress=95
                )
                graph_data = builder.get_graph_data(graph_id)

                # プロジェクト状態を更新
                project.status = ProjectStatus.GRAPH_COMPLETED
                ProjectManager.save_project(project)

                node_count = graph_data.get("node_count", 0)
                edge_count = graph_data.get("edge_count", 0)
                build_logger.info(f"[{task_id}] グラフ構築完了: graph_id={graph_id}, ノード={node_count}, エッジ={edge_count}")

                # 完了
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.COMPLETED,
                    message="グラフ構築完了",
                    progress=100,
                    result={
                        "project_id": project_id,
                        "graph_id": graph_id,
                        "node_count": node_count,
                        "edge_count": edge_count,
                        "chunk_count": total_chunks
                    }
                )

            except Exception as e:
                # プロジェクト状態を失敗に更新
                build_logger.error(f"[{task_id}] グラフ構築に失敗: {str(e)}")
                build_logger.debug(traceback.format_exc())

                project.status = ProjectStatus.FAILED
                project.error = str(e)
                ProjectManager.save_project(project)

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.FAILED,
                    message=f"構築に失敗: {str(e)}",
                    error=traceback.format_exc()
                )

        # バックグラウンドスレッドを開始
        thread = threading.Thread(target=build_task, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "project_id": project_id,
                "task_id": task_id,
                "message": "グラフ構築タスクを開始しました。/task/{task_id} で進捗を確認してください"
            }
        })

    except Exception as e:
        logger.error(f"グラフ構築の開始に失敗: {str(e)}")
        logger.debug(traceback.format_exc())
        response_data = {"success": False, "error": str(e)}
        if Config.DEBUG:
            response_data["traceback"] = traceback.format_exc()
        return jsonify(response_data), 500


# ============== タスク照会インターフェース ==============

@graph_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """
    タスク状態を照会
    """
    task = TaskManager().get_task(task_id)

    if not task:
        return jsonify({
            "success": False,
            "error": f"タスクが存在しません: {task_id}"
        }), 404

    return jsonify({
        "success": True,
        "data": task.to_dict()
    })


@graph_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """
    全タスクを一覧表示
    """
    tasks = TaskManager().list_tasks()

    return jsonify({
        "success": True,
        "data": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


# ============== グラフデータインターフェース ==============

@graph_bp.route('/data/<graph_id>', methods=['GET'])
def get_graph_data(graph_id: str):
    """
    グラフデータを取得（ノードとエッジ）
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEYが未設定です"
            }), 500

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        graph_data = builder.get_graph_data(graph_id)

        return jsonify({
            "success": True,
            "data": graph_data
        })

    except Exception as e:
        logger.error(f"グラフデータの取得に失敗: {str(e)}")
        logger.debug(traceback.format_exc())
        response_data = {"success": False, "error": str(e)}
        if Config.DEBUG:
            response_data["traceback"] = traceback.format_exc()
        return jsonify(response_data), 500


@graph_bp.route('/delete/<graph_id>', methods=['DELETE'])
def delete_graph(graph_id: str):
    """
    Zepグラフを削除
    """
    try:
        if not Config.ZEP_API_KEY:
            return jsonify({
                "success": False,
                "error": "ZEP_API_KEYが未設定です"
            }), 500

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)
        builder.delete_graph(graph_id)

        return jsonify({
            "success": True,
            "message": f"グラフを削除しました: {graph_id}"
        })

    except Exception as e:
        logger.error(f"グラフの削除に失敗: {str(e)}")
        logger.debug(traceback.format_exc())
        response_data = {"success": False, "error": str(e)}
        if Config.DEBUG:
            response_data["traceback"] = traceback.format_exc()
        return jsonify(response_data), 500
