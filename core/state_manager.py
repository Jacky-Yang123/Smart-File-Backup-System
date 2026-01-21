"""
状态管理模块
用于记录文件同步状态（哈希值等），支持断点续传和双向冲突检测
"""
import os
import json
import threading
from typing import Dict, Optional
from dataclasses import dataclass, asdict

from utils.constants import DATA_DIR
from utils.logger import logger

STATE_FILE = os.path.join(DATA_DIR, "sync_state.json")

@dataclass
class FileState:
    """文件状态"""
    hash: str = ""
    mtime: float = 0.0
    size: int = 0
    last_sync_time: str = ""

class StateManager:
    """状态管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._state: Dict[str, Dict[str, Dict]] = {}  # task_id -> { rel_path -> FileState dict }
        self._file_lock = threading.Lock()
        self.load_state()
        
    def load_state(self):
        """加载状态"""
        with self._file_lock:
            try:
                if os.path.exists(STATE_FILE):
                    with open(STATE_FILE, 'r', encoding='utf-8') as f:
                        self._state = json.load(f)
            except Exception as e:
                logger.error(f"加载同步状态失败: {e}", category="system")
                self._state = {}

    def save_state(self):
        """保存状态"""
        with self._file_lock:
            try:
                # 确保目录存在
                os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
                with open(STATE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(self._state, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"保存同步状态失败: {e}", category="system")

    def get_file_state(self, task_id: str, rel_path: str) -> Optional[FileState]:
        """获取文件上次同步的状态"""
        task_state = self._state.get(task_id, {})
        file_data = task_state.get(rel_path)
        if file_data:
            return FileState(**file_data)
        return None

    def update_file_state(self, task_id: str, rel_path: str, state: FileState):
        """更新文件状态"""
        if task_id not in self._state:
            self._state[task_id] = {}
        self._state[task_id][rel_path] = asdict(state)
        # 注意：频繁调用 update 可能导致 IO 瓶颈，
        # 在实际 sync process 中应该批量保存，或者由定时器保存
        # 这里为了简单起见，暂时依赖调用者手动 save 或 periodic save
        # 但为了数据安全，我们在重要节点保存
        
    def remove_file_state(self, task_id: str, rel_path: str):
        """移除文件记录"""
        if task_id in self._state and rel_path in self._state[task_id]:
            del self._state[task_id][rel_path]

    def clear_task_state(self, task_id: str):
        """清除任务的所有状态"""
        if task_id in self._state:
            del self._state[task_id]
            self.save_state()

# 全局实例
state_manager = StateManager()
