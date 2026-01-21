"""
日志管理模块
"""
import os
import logging
from datetime import datetime
from typing import List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from peewee import SqliteDatabase, Model, CharField, TextField, DateTimeField

from .constants import DATABASE_FILE, LOG_FILE, LogLevel


# 数据库连接
db = SqliteDatabase(DATABASE_FILE)


class LogEntry(Model):
    """日志条目模型"""
    timestamp = DateTimeField(default=datetime.now)
    level = CharField(max_length=20)
    category = CharField(max_length=50, default="system")
    message = TextField()
    task_id = CharField(max_length=50, null=True)
    details = TextField(null=True)
    
    class Meta:
        database = db
        table_name = "logs"


class BackupHistory(Model):
    """备份历史记录模型"""
    timestamp = DateTimeField(default=datetime.now)
    task_id = CharField(max_length=50)
    task_name = CharField(max_length=200)
    action = CharField(max_length=50)  # created, modified, deleted, moved
    source_path = TextField()
    target_path = TextField(null=True)
    file_size = CharField(max_length=50, null=True)
    status = CharField(max_length=20)  # success, failed, skipped
    error_message = TextField(null=True)
    
    class Meta:
        database = db
        table_name = "backup_history"



import threading
import queue
import time
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any

class Logger:
    """日志管理器 (异步写入版)"""
    
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
        self._callbacks: List[Callable] = []
        
        # 异步队列
        self._log_queue = queue.Queue()
        self._is_running = True
        
        self._setup_database()
        self._setup_file_logger()
        
        # 启动后台写入线程
        self._worker_thread = threading.Thread(target=self._db_worker, daemon=True)
        self._worker_thread.start()
    
    def _setup_database(self):
        """初始化数据库"""
        try:
            db.connect(reuse_if_open=True)
            # 启用 WAL 模式提高并发性能
            db.execute_sql('PRAGMA journal_mode=WAL;')
            db.create_tables([LogEntry, BackupHistory], safe=True)
        except Exception as e:
            print(f"Database setup error: {e}")
    
    def _setup_file_logger(self):
        """设置文件日志"""
        self._file_logger = logging.getLogger("backup_system")
        self._file_logger.setLevel(logging.DEBUG)
        
        # 文件处理器
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # 格式化
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            self._file_logger.addHandler(file_handler)
        except Exception as e:
            print(f"File logger setup error: {e}")
            
    def _db_worker(self):
        """后台线程：从队列读取日志并写入数据库"""
        while self._is_running:
            try:
                # 获取任务
                item = self._log_queue.get()
                if item is None:  # 停止信号
                    break
                
                # 执行写入
                type_ = item.get("type")
                data = item.get("data")
                
                if type_ == "log":
                    try:
                        LogEntry.create(**data)
                    except Exception as e:
                        print(f"DB Write Log Error: {e}")
                        
                elif type_ == "backup":
                    try:
                        BackupHistory.create(**data)
                    except Exception as e:
                        print(f"DB Write History Error: {e}")
                
                self._log_queue.task_done()
                
            except Exception as e:
                print(f"Logger worker error: {e}")
                time.sleep(0.1)  # 防止死循环占用CPU

    def add_callback(self, callback: Callable):
        """添加日志回调 (用于UI更新)"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable):
        """移除日志回调"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, entry: dict):
        """通知所有回调"""
        for callback in self._callbacks:
            try:
                callback(entry)
            except Exception:
                pass
    
    def log(self, level: str, message: str, category: str = "system", 
            task_id: str = None, details: str = None):
        """
        记录日志 (异步)
        """
        try:
            # 1. 放入队列，异步写库
            log_data = {
                "level": level,
                "message": message,
                "category": category,
                "task_id": task_id,
                "details": details,
                "timestamp": datetime.now()
            }
            self._log_queue.put({"type": "log", "data": log_data})
            
            # 2. 立即写入文件 (文件系统通常比数据库快且并发更好)
            log_msg = f"[{category}] {message}"
            if task_id:
                log_msg = f"[Task:{task_id}] {log_msg}"
            
            if level == LogLevel.DEBUG.value:
                self._file_logger.debug(log_msg)
            elif level == LogLevel.INFO.value:
                self._file_logger.info(log_msg)
            elif level == LogLevel.WARNING.value:
                self._file_logger.warning(log_msg)
            elif level == LogLevel.ERROR.value:
                self._file_logger.error(log_msg)
            
            # 3. 立即通知回调 (确保UI更新及时)
            self._notify_callbacks({
                "timestamp": log_data["timestamp"],
                "level": level,
                "message": message,
                "category": category,
                "task_id": task_id
            })
            
        except Exception as e:
            print(f"Logging error: {e}")
    
    def debug(self, message: str, **kwargs):
        self.log(LogLevel.DEBUG.value, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self.log(LogLevel.INFO.value, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log(LogLevel.WARNING.value, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log(LogLevel.ERROR.value, message, **kwargs)
    
    def log_backup(self, task_id: str, task_name: str, action: str,
                    source_path: str, target_path: str = None,
                    file_size: str = None, status: str = "success",
                    error_message: str = None):
        """记录备份操作历史 (异步)"""
        try:
            # 放入队列
            history_data = {
                "task_id": task_id,
                "task_name": task_name,
                "action": action,
                "source_path": source_path,
                "target_path": target_path,
                "file_size": file_size,
                "status": status,
                "error_message": error_message,
                "timestamp": datetime.now()
            }
            self._log_queue.put({"type": "backup", "data": history_data})
            
        except Exception as e:
            print(f"Backup history logging error: {e}")
            
    def shutdown(self):
        """关闭日志管理器"""
        self._is_running = False
        self._log_queue.put(None)
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
    
    def get_logs(self, level: str = None, category: str = None,
                  task_id: str = None, start_time: datetime = None,
                  end_time: datetime = None, limit: int = 100) -> List[dict]:
        """查询日志 (直接读库，可能需要重试)"""
        try:
            query = LogEntry.select().order_by(LogEntry.timestamp.desc())
            
            if level:
                query = query.where(LogEntry.level == level)
            if category:
                query = query.where(LogEntry.category == category)
            if task_id:
                query = query.where(LogEntry.task_id == task_id)
            if start_time:
                query = query.where(LogEntry.timestamp >= start_time)
            if end_time:
                query = query.where(LogEntry.timestamp <= end_time)
            
            query = query.limit(limit)
            
            return [
                {
                    "id": entry.id,
                    "timestamp": entry.timestamp,
                    "level": entry.level,
                    "category": entry.category,
                    "message": entry.message,
                    "task_id": entry.task_id,
                    "details": entry.details
                }
                for entry in query
            ]
        except Exception:
            # 如果读库失败，返回空列表，避免UI卡死
            return []
    
    def get_backup_history(self, task_id: str = None, 
                           limit: int = 100) -> List[dict]:
        """获取备份历史"""
        try:
            query = BackupHistory.select().order_by(BackupHistory.timestamp.desc())
            
            if task_id:
                query = query.where(BackupHistory.task_id == task_id)
            
            query = query.limit(limit)
            
            return [
                {
                    "id": entry.id,
                    "timestamp": entry.timestamp,
                    "task_id": entry.task_id,
                    "task_name": entry.task_name,
                    "action": entry.action,
                    "source_path": entry.source_path,
                    "target_path": entry.target_path,
                    "file_size": entry.file_size,
                    "status": entry.status,
                    "error_message": entry.error_message
                }
                for entry in query
            ]
        except Exception:
            return []
    
    def clear_old_logs(self, days: int = 30):
        """清理旧日志"""
        try:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)
            LogEntry.delete().where(LogEntry.timestamp < cutoff).execute()
            BackupHistory.delete().where(BackupHistory.timestamp < cutoff).execute()
        except Exception as e:
            print(f"Clear old logs error: {e}")
    
    def get_statistics(self, task_id: str = None) -> dict:
        """获取统计信息"""
        try:
            # 简单的统计实现，避免复杂的聚合查询锁定数据库
            query = BackupHistory.select()
            if task_id:
                query = query.where(BackupHistory.task_id == task_id)
            
            total = query.count()
            success = query.where(BackupHistory.status == "success").count()
            failed = query.where(BackupHistory.status == "failed").count()
            
            return {
                "total_operations": total,
                "success_count": success,
                "failed_count": failed,
                "success_rate": round(success / total * 100, 2) if total > 0 else 0
            }
        except Exception:
            return {
                "total_operations": 0,
                "success_count": 0,
                "failed_count": 0,
                "success_rate": 0
            }


# 全局日志管理器实例
logger = Logger()
