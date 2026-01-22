"""
独立操作队列模块 - 所有文件操作在单独线程中执行
"""
import os
import queue
import threading
import shutil
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, List, Dict, Any, Tuple
from PyQt5.QtCore import QObject, pyqtSignal


class OperationType(Enum):
    """操作类型"""
    COPY_FILE = "copy"
    DELETE_FILE = "delete"
    FULL_SYNC = "full_sync"


class OperationStatus(Enum):
    """操作状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FileOperation:
    """文件操作数据"""
    id: str
    op_type: OperationType
    source_path: str
    target_path: str = ""
    task_id: str = ""
    task_name: str = ""
    status: OperationStatus = OperationStatus.PENDING
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class OperationQueueSignals(QObject):
    """操作队列信号"""
    progress_updated = pyqtSignal(int, int, str)  # current, total, current_file
    operation_completed = pyqtSignal(str, bool, str)  # op_id, success, message
    queue_status_changed = pyqtSignal(dict)  # status dict


class OperationQueue:
    """独立操作队列 - 单例模式"""
    
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
        
        self._queue: queue.Queue = queue.Queue()
        self._pending_ops: List[FileOperation] = []
        self._current_op: Optional[FileOperation] = None
        self._completed_count = 0
        self._failed_count = 0
        self._is_running = True
        self._is_paused = False
        self._lock = threading.Lock()
        
        # Qt信号
        self.signals = OperationQueueSignals()
        
        # 启动工作线程
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
    
    def add_operation(self, op_type: OperationType, source: str, target: str = "",
                      task_id: str = "", task_name: str = "") -> str:
        """添加操作到队列"""
        import uuid
        op_id = str(uuid.uuid4())[:8]
        
        op = FileOperation(
            id=op_id,
            op_type=op_type,
            source_path=source,
            target_path=target,
            task_id=task_id,
            task_name=task_name
        )
        
        with self._lock:
            self._pending_ops.append(op)
            self._queue.put(op)
        
        self._emit_status()
        return op_id
    
    def add_batch_operations(self, operations: List[dict]) -> List[str]:
        """批量添加操作"""
        op_ids = []
        for op_data in operations:
            op_id = self.add_operation(
                op_type=op_data.get("op_type", OperationType.COPY_FILE),
                source=op_data.get("source", ""),
                target=op_data.get("target", ""),
                task_id=op_data.get("task_id", ""),
                task_name=op_data.get("task_name", "")
            )
            op_ids.append(op_id)
        return op_ids
    
    def pause(self):
        """暂停队列"""
        self._is_paused = True
        self._emit_status()
    
    def resume(self):
        """恢复队列"""
        self._is_paused = False
        self._emit_status()
    
    def clear(self):
        """清空待处理队列"""
        with self._lock:
            # 清空队列
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            
            # 标记所有待处理为取消
            for op in self._pending_ops:
                if op.status == OperationStatus.PENDING:
                    op.status = OperationStatus.CANCELLED
            self._pending_ops.clear()
        
        self._emit_status()
    
    def get_status(self) -> dict:
        """获取队列状态"""
        with self._lock:
            pending = len([op for op in self._pending_ops if op.status == OperationStatus.PENDING])
            current_file = ""
            if self._current_op:
                current_file = os.path.basename(self._current_op.source_path)
            
            return {
                "pending": pending,
                "completed": self._completed_count,
                "failed": self._failed_count,
                "is_paused": self._is_paused,
                "current_file": current_file,
                "current_op": self._current_op
            }
    
    def get_next_operations(self, count: int = 5) -> List[dict]:
        """获取接下来的操作预览"""
        with self._lock:
            pending = [op for op in self._pending_ops if op.status == OperationStatus.PENDING]
            return [{
                "id": op.id,
                "type": op.op_type.value,
                "file": os.path.basename(op.source_path),
                "task": op.task_name
            } for op in pending[:count]]
    
    def _worker(self):
        """工作线程"""
        while self._is_running:
            try:
                # 检查暂停状态
                if self._is_paused:
                    import time
                    time.sleep(0.1)
                    continue
                
                # 获取下一个操作
                try:
                    op = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                if op is None:
                    break
                
                # 执行操作
                self._current_op = op
                op.status = OperationStatus.RUNNING
                self._emit_status()
                
                # logger.debug(f"Executing queue op: {op.op_type} {op.source_path}")
                
                success, message = self._execute_operation(op)
                
                op.completed_at = datetime.now()
                if success:
                    op.status = OperationStatus.COMPLETED
                    with self._lock:
                        self._completed_count += 1
                else:
                    from utils.logger import logger
                    logger.error(f"Queue op failed: {op.source_path} - {message}", category="queue")
                    op.status = OperationStatus.FAILED
                    op.error_message = message
                    with self._lock:
                        self._failed_count += 1
                
                # 从待处理列表移除
                with self._lock:
                    if op in self._pending_ops:
                        self._pending_ops.remove(op)
                
                self._current_op = None
                
                # 发送完成信号
                self.signals.operation_completed.emit(op.id, success, message)
                self._emit_status()
                
            except Exception as e:
                from utils.logger import logger
                logger.error(f"Queue worker error: {e}", category="queue")
    
    def set_executor(self, executor: Callable[[FileOperation], Tuple[bool, str]]):
        """设置外部执行器"""
        self._executor = executor
    
    def _execute_operation(self, op: FileOperation) -> tuple:
        """执行单个操作"""
        try:
            # 优先使用外部执行器 (通常是 TaskManager)
            if hasattr(self, '_executor') and self._executor:
                return self._executor(op)
            
            # 回退到内部简单实现
            if op.op_type == OperationType.COPY_FILE:
                return self._do_copy(op.source_path, op.target_path)
            elif op.op_type == OperationType.DELETE_FILE:
                return self._do_delete(op.source_path)
            else:
                return False, f"Unknown operation type: {op.op_type}"
        except Exception as e:
            return False, str(e)
    
    def _do_copy(self, source: str, target: str) -> tuple:
        """执行复制"""
        try:
            if not os.path.exists(source):
                return False, f"源文件不存在: {source}"
            
            target_dir = os.path.dirname(target)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            
            if os.path.isdir(source):
                if os.path.exists(target):
                    shutil.rmtree(target)
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
            
            return True, ""
        except Exception as e:
            return False, str(e)
    
    def _do_delete(self, path: str) -> tuple:
        """执行删除"""
        try:
            if not os.path.exists(path):
                return True, "文件已不存在"
            
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            
            return True, ""
        except Exception as e:
            return False, str(e)
    
    def _emit_status(self):
        """发送状态更新信号"""
        try:
            status = self.get_status()
            self.signals.queue_status_changed.emit(status)
            
            pending = status["pending"]
            completed = status["completed"]
            total = pending + completed
            self.signals.progress_updated.emit(completed, total, status["current_file"])
        except Exception:
            pass
    
    def shutdown(self):
        """关闭队列"""
        self._is_running = False
        self._queue.put(None)
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)


# 全局实例
operation_queue = OperationQueue()
