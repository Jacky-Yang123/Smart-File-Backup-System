"""
配置管理模块
"""
import json
import os
from typing import Any, Dict, Optional
from copy import deepcopy
from .constants import CONFIG_FILE, TASKS_FILE, DEFAULT_CONFIG


class ConfigManager:
    """配置管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config: Dict = {}
        self._tasks: Dict = {}
        self.load_config()
        self.load_tasks()
    
    def load_config(self) -> None:
        """加载配置文件"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            else:
                self._config = deepcopy(DEFAULT_CONFIG)
                self.save_config()
        except Exception:
            self._config = deepcopy(DEFAULT_CONFIG)
    
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键 (支持点号分隔, 如 "general.auto_start")
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def get_all(self) -> Dict:
        """获取所有配置"""
        return deepcopy(self._config)
    
    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self._config = deepcopy(DEFAULT_CONFIG)
        self.save_config()
    
    # 任务配置管理
    def _get_storage_path(self) -> str:
        """获取存储路径"""
        from .constants import DATA_DIR
        return self.get("general.storage_path", DATA_DIR)

    def load_tasks(self) -> None:
        """加载任务配置"""
        try:
            storage_path = self._get_storage_path()
            tasks_file = os.path.join(storage_path, "tasks.json")
            
            if os.path.exists(tasks_file):
                with open(tasks_file, 'r', encoding='utf-8') as f:
                    self._tasks = json.load(f)
            else:
                self._tasks = {"tasks": []}
                # 如果新路径下没有任务文件，但在默认路径下有，是否应该尝试迁移？
                # 用户的需求是 "自动导入"，通常指读取。如果文件不存在，新建即可。
                # 为了防止覆盖，我们只在保存时写入。
        except Exception:
            self._tasks = {"tasks": []}
    
    def save_tasks(self) -> bool:
        """保存任务配置"""
        try:
            storage_path = self._get_storage_path()
            if not os.path.exists(storage_path):
                os.makedirs(storage_path, exist_ok=True)
                
            tasks_file = os.path.join(storage_path, "tasks.json")
            
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self._tasks, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def get_tasks(self) -> list:
        """获取所有任务"""
        return self._tasks.get("tasks", [])
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取指定任务"""
        for task in self._tasks.get("tasks", []):
            if task.get("id") == task_id:
                return task
        return None
    
    def add_task(self, task: Dict) -> bool:
        """添加任务"""
        try:
            self._tasks["tasks"].append(task)
            return self.save_tasks()
        except Exception:
            return False
    
    def update_task(self, task_id: str, task_data: Dict) -> bool:
        """更新任务"""
        try:
            for i, task in enumerate(self._tasks.get("tasks", [])):
                if task.get("id") == task_id:
                    self._tasks["tasks"][i] = task_data
                    return self.save_tasks()
            return False
        except Exception:
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        try:
            self._tasks["tasks"] = [
                t for t in self._tasks.get("tasks", []) 
                if t.get("id") != task_id
            ]
            return self.save_tasks()
        except Exception:
            return False
    
    def export_config(self, filepath: str) -> bool:
        """导出配置"""
        try:
            export_data = {
                "config": self._config,
                "tasks": self._tasks
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def import_config(self, filepath: str) -> bool:
        """导入配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if "config" in data:
                self._config = data["config"]
                self.save_config()
            if "tasks" in data:
                self._tasks = data["tasks"]
                self.save_tasks()
            return True
        except Exception:
            return False


# 全局配置管理器实例
config_manager = ConfigManager()
