"""
タスク状態管理
長時間実行タスク（グラフ構築など）の追跡に使用
"""

import uuid
import threading
import json
import os
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..config import Config


class TaskStatus(str, Enum):
    """タスク状態列挙"""
    PENDING = "pending"          # 待機中
    PROCESSING = "processing"    # 処理中
    COMPLETED = "completed"      # 完了
    FAILED = "failed"            # 失敗


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    progress: int = 0              # 合計進捗パーセント 0-100
    message: str = ""              # 状態メッセージ
    result: Optional[Dict] = None  # タスク結果
    error: Optional[str] = None    # エラー情報
    metadata: Dict = field(default_factory=dict)  # 追加メタデータ
    progress_detail: Dict = field(default_factory=dict)  # 詳細進捗情報
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "message": self.message,
            "progress_detail": self.progress_detail,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            task_id=data["task_id"],
            task_type=data.get("task_type", ""),
            status=TaskStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            progress=data.get("progress", 0),
            message=data.get("message", ""),
            result=data.get("result"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            progress_detail=data.get("progress_detail", {})
        )


class TaskManager:
    """
    タスクマネージャー
    スレッドセーフなタスク状態管理
    """
    
    _instance = None
    _lock = threading.Lock()
    TASKS_DIR = os.path.join(Config.UPLOAD_FOLDER, "tasks")
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._tasks: Dict[str, Task] = {}
                    cls._instance._task_lock = threading.Lock()
                    os.makedirs(cls.TASKS_DIR, exist_ok=True)
        return cls._instance

    def _get_task_path(self, task_id: str) -> str:
        return os.path.join(self.TASKS_DIR, f"{task_id}.json")

    def _persist_task(self, task: Task):
        with open(self._get_task_path(task.task_id), "w", encoding="utf-8") as f:
            json.dump(task.to_dict(), f, ensure_ascii=False, indent=2)
    
    def create_task(self, task_type: str, metadata: Optional[Dict] = None) -> str:
        """
        创建新任务
        
        Args:
            task_type: 任务类型
            metadata: 额外元数据
            
        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.now()
        
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )
        
        with self._task_lock:
            self._tasks[task_id] = task
            self._persist_task(task)
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                return task

        task_path = self._get_task_path(task_id)
        if not os.path.exists(task_path):
            return None

        with open(task_path, "r", encoding="utf-8") as f:
            task = Task.from_dict(json.load(f))

        with self._task_lock:
            self._tasks[task_id] = task
        return task
    
    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        progress_detail: Optional[Dict] = None
    ):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度
            message: 消息
            result: 结果
            error: 错误信息
            progress_detail: 详细进度信息
        """
        with self._task_lock:
            task = self._tasks.get(task_id)
            if task:
                task.updated_at = datetime.now()
                if status is not None:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if message is not None:
                    task.message = message
                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if progress_detail is not None:
                    task.progress_detail = progress_detail
                self._persist_task(task)
    
    def complete_task(self, task_id: str, result: Dict):
        """タスク完了をマーク"""
        self.update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress=100,
            message="タスク完了",
            result=result
        )
    
    def fail_task(self, task_id: str, error: str):
        """タスク失敗をマーク"""
        self.update_task(
            task_id,
            status=TaskStatus.FAILED,
            message="タスク失敗",
            error=error
        )
    
    def list_tasks(self, task_type: Optional[str] = None) -> list:
        """列出任务"""
        with self._task_lock:
            for filename in os.listdir(self.TASKS_DIR):
                if not filename.endswith(".json"):
                    continue
                task_id = filename[:-5]
                if task_id in self._tasks:
                    continue
                try:
                    with open(self._get_task_path(task_id), "r", encoding="utf-8") as f:
                        self._tasks[task_id] = Task.from_dict(json.load(f))
                except Exception:
                    continue
            tasks = list(self._tasks.values())
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            return sorted(tasks, key=lambda x: x.created_at, reverse=True)
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理旧任务"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._task_lock:
            old_ids = [
                tid for tid, task in self._tasks.items()
                if task.created_at < cutoff and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            ]
            for tid in old_ids:
                del self._tasks[tid]
                task_path = self._get_task_path(tid)
                if os.path.exists(task_path):
                    os.remove(task_path)
