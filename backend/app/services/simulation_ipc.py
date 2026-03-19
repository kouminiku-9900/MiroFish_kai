"""
シミュレーションIPC通信モジュール
Flaskバックエンドとシミュレーションスクリプトのプロセス間通信用

ファイルシステムを介したシンプルなコマンド/レスポンスパターンで実現：
1. Flaskがcommands/ディレクトリにコマンドを書き込む
2. シミュレーションスクリプトがコマンドディレクトリをポーリングし、コマンドを実行してresponses/ディレクトリにレスポンスを書き込む
3. Flaskがレスポンスディレクトリをポーリングして結果を取得
"""

import os
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger('mirofish.simulation_ipc')


class CommandType(str, Enum):
    """コマンドタイプ"""
    INTERVIEW = "interview"           # 単一Agentインタビュー
    BATCH_INTERVIEW = "batch_interview"  # バッチインタビュー
    CLOSE_ENV = "close_env"           # 環境を閉じる


class CommandStatus(str, Enum):
    """コマンドステータス"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IPCCommand:
    """IPCコマンド"""
    command_id: str
    command_type: CommandType
    args: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "args": self.args,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCCommand':
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            args=data.get("args", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class IPCResponse:
    """IPCレスポンス"""
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IPCResponse':
        return cls(
            command_id=data["command_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


class SimulationIPCClient:
    """
    シミュレーションIPCクライアント（Flask側で使用）

    シミュレーションプロセスにコマンドを送信し、レスポンスを待機
    """

    def __init__(self, simulation_dir: str):
        """
        IPCクライアントを初期化

        Args:
            simulation_dir: シミュレーションデータディレクトリ
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")

        # ディレクトリの存在を確認
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def send_command(
        self,
        command_type: CommandType,
        args: Dict[str, Any],
        timeout: float = 60.0,
        poll_interval: float = 0.5
    ) -> IPCResponse:
        """
        コマンドを送信しレスポンスを待機

        Args:
            command_type: コマンドタイプ
            args: コマンド引数
            timeout: タイムアウト時間（秒）
            poll_interval: ポーリング間隔（秒）

        Returns:
            IPCResponse

        Raises:
            TimeoutError: レスポンス待機タイムアウト
        """
        command_id = str(uuid.uuid4())
        command = IPCCommand(
            command_id=command_id,
            command_type=command_type,
            args=args
        )

        # コマンドファイルを書き込み
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        with open(command_file, 'w', encoding='utf-8') as f:
            json.dump(command.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"IPCコマンドを送信: {command_type.value}, command_id={command_id}")

        # レスポンスを待機
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        response_data = json.load(f)
                    response = IPCResponse.from_dict(response_data)

                    # コマンドとレスポンスファイルをクリーンアップ
                    try:
                        os.remove(command_file)
                        os.remove(response_file)
                    except OSError:
                        pass

                    logger.info(f"IPCレスポンスを受信: command_id={command_id}, status={response.status.value}")
                    return response
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"レスポンスの解析に失敗: {e}")

            time.sleep(poll_interval)

        # タイムアウト
        logger.error(f"IPCレスポンス待機タイムアウト: command_id={command_id}")

        # コマンドファイルをクリーンアップ
        try:
            os.remove(command_file)
        except OSError:
            pass

        raise TimeoutError(f"コマンドレスポンス待機タイムアウト ({timeout}秒)")

    def send_interview(
        self,
        agent_id: int,
        prompt: str,
        platform: str = None,
        timeout: float = 60.0
    ) -> IPCResponse:
        """
        単一Agentインタビューコマンドを送信

        Args:
            agent_id: Agent ID
            prompt: インタビュー質問
            platform: 指定プラットフォーム（任意）
                - "twitter": Twitterプラットフォームのみインタビュー
                - "reddit": Redditプラットフォームのみインタビュー
                - None: デュアルプラットフォームシミュレーション時は両方、シングルプラットフォーム時はそのプラットフォーム
            timeout: タイムアウト時間

        Returns:
            IPCResponse、resultフィールドにインタビュー結果を含む
        """
        args = {
            "agent_id": agent_id,
            "prompt": prompt
        }
        if platform:
            args["platform"] = platform

        return self.send_command(
            command_type=CommandType.INTERVIEW,
            args=args,
            timeout=timeout
        )

    def send_batch_interview(
        self,
        interviews: List[Dict[str, Any]],
        platform: str = None,
        timeout: float = 120.0
    ) -> IPCResponse:
        """
        バッチインタビューコマンドを送信

        Args:
            interviews: インタビューリスト、各要素は {"agent_id": int, "prompt": str, "platform": str(任意)}
            platform: デフォルトプラットフォーム（任意、各インタビュー項目のplatformで上書き可能）
                - "twitter": デフォルトでTwitterプラットフォームのみインタビュー
                - "reddit": デフォルトでRedditプラットフォームのみインタビュー
                - None: デュアルプラットフォームシミュレーション時は各Agentを両方でインタビュー
            timeout: タイムアウト時間

        Returns:
            IPCResponse、resultフィールドに全インタビュー結果を含む
        """
        args = {"interviews": interviews}
        if platform:
            args["platform"] = platform

        return self.send_command(
            command_type=CommandType.BATCH_INTERVIEW,
            args=args,
            timeout=timeout
        )

    def send_close_env(self, timeout: float = 30.0) -> IPCResponse:
        """
        環境閉鎖コマンドを送信

        Args:
            timeout: タイムアウト時間

        Returns:
            IPCResponse
        """
        return self.send_command(
            command_type=CommandType.CLOSE_ENV,
            args={},
            timeout=timeout
        )

    def check_env_alive(self) -> bool:
        """
        シミュレーション環境が生存しているか確認

        env_status.jsonファイルをチェックして判断
        """
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        if not os.path.exists(status_file):
            return False

        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                status = json.load(f)
            return status.get("status") == "alive"
        except (json.JSONDecodeError, OSError):
            return False


class SimulationIPCServer:
    """
    シミュレーションIPCサーバー（シミュレーションスクリプト側で使用）

    コマンドディレクトリをポーリングし、コマンドを実行してレスポンスを返す
    """

    def __init__(self, simulation_dir: str):
        """
        IPCサーバーを初期化

        Args:
            simulation_dir: シミュレーションデータディレクトリ
        """
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")

        # ディレクトリの存在を確認
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

        # 環境ステータス
        self._running = False

    def start(self):
        """サーバーを実行状態にマーク"""
        self._running = True
        self._update_env_status("alive")

    def stop(self):
        """サーバーを停止状態にマーク"""
        self._running = False
        self._update_env_status("stopped")

    def _update_env_status(self, status: str):
        """環境ステータスファイルを更新"""
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump({
                "status": status,
                "timestamp": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

    def poll_commands(self) -> Optional[IPCCommand]:
        """
        コマンドディレクトリをポーリングし、最初の未処理コマンドを返す

        Returns:
            IPCCommand または None
        """
        if not os.path.exists(self.commands_dir):
            return None

        # 時間順にコマンドファイルを取得
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                command_files.append((filepath, os.path.getmtime(filepath)))

        command_files.sort(key=lambda x: x[1])

        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return IPCCommand.from_dict(data)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"コマンドファイルの読み取りに失敗: {filepath}, {e}")
                continue

        return None

    def send_response(self, response: IPCResponse):
        """
        レスポンスを送信

        Args:
            response: IPCレスポンス
        """
        response_file = os.path.join(self.responses_dir, f"{response.command_id}.json")
        with open(response_file, 'w', encoding='utf-8') as f:
            json.dump(response.to_dict(), f, ensure_ascii=False, indent=2)

        # コマンドファイルを削除
        command_file = os.path.join(self.commands_dir, f"{response.command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass

    def send_success(self, command_id: str, result: Dict[str, Any]):
        """成功レスポンスを送信"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.COMPLETED,
            result=result
        ))

    def send_error(self, command_id: str, error: str):
        """エラーレスポンスを送信"""
        self.send_response(IPCResponse(
            command_id=command_id,
            status=CommandStatus.FAILED,
            error=error
        ))
