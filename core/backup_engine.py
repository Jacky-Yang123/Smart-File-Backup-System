"""
备份引擎模块 - 协调所有核心组件
"""
import threading
from typing import Callable, Optional

from utils.logger import logger
from utils.config_manager import config_manager
from .task_manager import task_manager
from .scheduler import scheduler


class BackupEngine:
    """
    备份引擎
    统一管理和协调所有备份相关组件
    """
    
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
        
        self._running = False
        self._event_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None
    
    def set_event_callback(self, callback: Callable):
        """设置事件回调"""
        self._event_callback = callback
        task_manager.set_event_callback(callback)
    
    def set_status_callback(self, callback: Callable):
        """设置状态变更回调"""
        self._status_callback = callback
        task_manager.set_status_callback(callback)
    
    def start(self):
        """启动备份引擎"""
        if self._running:
            return
        
        try:
            # 启动调度器
            scheduler.start()
            
            # 启动自动启动的任务
            task_manager.start_all()
            
            self._running = True
            logger.info("备份引擎已启动", category="engine")
        except Exception as e:
            logger.error(f"启动备份引擎失败: {e}", category="engine")
    
    def stop(self):
        """停止备份引擎"""
        if not self._running:
            return
        
        try:
            # 停止所有任务
            task_manager.stop_all()
            
            # 停止调度器
            scheduler.stop()
            
            self._running = False
            logger.info("备份引擎已停止", category="engine")
        except Exception as e:
            logger.error(f"停止备份引擎失败: {e}", category="engine")
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def tasks(self):
        return task_manager
    
    @property
    def schedule(self):
        return scheduler
    
    def get_status(self) -> dict:
        """获取引擎状态"""
        task_stats = task_manager.get_overall_stats()
        return {
            "engine_running": self._running,
            "scheduler_running": scheduler.is_running,
            **task_stats
        }


# 全局备份引擎实例
backup_engine = BackupEngine()
