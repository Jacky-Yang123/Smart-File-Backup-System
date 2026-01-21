"""
任务管理器模块
"""
import os
import uuid
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from utils.constants import SyncMode, ConflictStrategy, TaskStatus
from utils.config_manager import config_manager
from utils.logger import logger
from .file_monitor import FileMonitor, FileEvent
from .sync_processor import SyncProcessor


@dataclass
class BackupTask:
    """备份任务配置"""
    id: str = ""
    name: str = ""
    source_path: str = ""
    target_paths: List[str] = field(default_factory=list)
    sync_mode: str = SyncMode.ONE_WAY.value
    conflict_strategy: str = ConflictStrategy.NEWEST_WINS.value
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    enabled: bool = True
    auto_start: bool = False
    delete_orphans: bool = False
    reverse_delete: bool = False  # 单向备份：目标删除时是否同步删除源文件
    created_at: str = ""
    updated_at: str = ""
    last_run_time: str = ""
    compare_method: str = "mtime"  # 比较方式: mtime, hash
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BackupTask':
        return cls(**data)


class TaskRunner:
    """
    任务运行器
    管理单个任务的监控和同步
    """
    
    def __init__(self, task: BackupTask):
        self.task = task
        self._status = TaskStatus.STOPPED
        self._is_syncing = False
        self._monitor: Optional[FileMonitor] = None
        self._target_monitors: List[FileMonitor] = []  # 目标文件夹监控器（双向同步用）
        self._processor: Optional[SyncProcessor] = None
        self._lock = threading.Lock()
        self._operation_lock = threading.Lock()  # 操作锁，防止全量同步与实时同步冲突
        self._event_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None
    
    def set_event_callback(self, callback: Callable[[str, FileEvent, dict], None]):
        """设置事件回调 (task_id, event, result)"""
        self._event_callback = callback
    
    def set_status_callback(self, callback: Callable[[str, TaskStatus], None]):
        """设置状态变更回调"""
        self._status_callback = callback
    
    def _on_file_event(self, event: FileEvent):
        """处理源文件夹的文件事件（使用线程异步处理避免阻塞）"""
        if self._status != TaskStatus.RUNNING:
            return
        
        # 使用线程异步处理，避免阻塞文件监控
        import threading
        thread = threading.Thread(
            target=self._process_file_event_async,
            args=(event, False, None),
            daemon=True
        )
        thread.start()
    
    def _on_target_file_event(self, target_path: str, event: FileEvent):
        """处理目标文件夹的文件事件（双向同步，异步处理）"""
        if self._status != TaskStatus.RUNNING:
            return
        
        # 使用线程异步处理
        import threading
        thread = threading.Thread(
            target=self._process_file_event_async,
            args=(event, True, target_path),
            daemon=True
        )
        thread.start()
    
    def _process_file_event_async(self, event: FileEvent, is_reverse: bool, target_base: str = None):
        """异步处理文件事件"""
        # 获取操作锁，确保不与全量同步冲突
        if not self._operation_lock.acquire(timeout=60):  # 尝试获取锁，超时60秒
            logger.warning(f"获取操作锁超时，跳过事件: {event.src_path}", task_id=self.task.id, category="task")
            return

        try:
            self._is_syncing = True
            # 执行同步
            if is_reverse:
                results = self._processor.process_reverse_event(event, target_base)
            else:
                results = self._processor.process_event(event)
            
            # 更新最后运行时间
            if results:
                self.task.last_run_time = datetime.now().isoformat()
                # 可以在这里保存任务状态，但为了性能可能不需要每次都保存硬盘

            
            # 统计成功和失败
            success_count = sum(1 for r in results if r.success and r.action != "skip")
            failed_count = sum(1 for r in results if not r.success)
            total_count = len(results)
            
            # 文件夹操作：只发送一条聚合通知
            if event.is_directory and total_count > 0:
                # 在后台线程安全地计算文件数量
                file_count = total_count
                try:
                    src_dir = event.dst_path if event.dst_path else event.src_path
                    if src_dir and os.path.isdir(src_dir):
                        file_count = sum(1 for _, _, files in os.walk(src_dir) for _ in files)
                except:
                    pass
                
                # 只记录一条聚合日志
                logger.log_backup(
                    task_id=self.task.id,
                    task_name=self.task.name,
                    action=event.event_type.value,
                    source_path=event.src_path,
                    target_path=event.dst_path if event.dst_path else "",
                    file_size=None,
                    status="success" if failed_count == 0 else "partial",
                    error_message=f"处理 {total_count} 个文件, {failed_count} 个失败" if failed_count > 0 else None
                )
                
                # 只发送一条聚合回调
                if self._event_callback:
                    self._event_callback(self.task.id, event, {
                        "success": failed_count == 0,
                        "action": event.event_type.value,
                        "message": f"文件夹包含 {file_count} 个文件",
                        "target_path": event.dst_path if event.dst_path else "",
                        "file_count": file_count,
                        "is_folder_batch": True
                    })
            else:
                # 普通文件：逐个通知
                for result in results:
                    if result.action == "skip":
                        continue  # 跳过的不记录
                    
                    logger.log_backup(
                        task_id=self.task.id,
                        task_name=self.task.name,
                        action=event.event_type.value,
                        source_path=result.source_path,
                        target_path=result.target_path,
                        file_size=str(result.file_size) if result.file_size else None,
                        status="success" if result.success else "failed",
                        error_message=result.message if not result.success else None
                    )
                
                # 通知回调（普通文件只通知非跳过的）
                if self._event_callback:
                    for result in results:
                        if result.action == "skip":
                            continue
                        self._event_callback(self.task.id, event, {
                            "success": result.success,
                            "action": result.action,
                            "message": result.message,
                            "target_path": result.target_path
                        })
                        
        except Exception as e:
            logger.error(f"处理文件事件失败: {e}", task_id=self.task.id, category="task")
        finally:
            self._is_syncing = False
            self._operation_lock.release()
    
    def _set_status(self, status: TaskStatus):
        """设置状态"""
        self._status = status
        if self._status_callback:
            self._status_callback(self.task.id, status)
    
    def start(self) -> bool:
        """启动任务"""
        with self._lock:
            if self._status == TaskStatus.RUNNING:
                return True
            
            try:
                # 创建同步处理器
                self._processor = SyncProcessor(
                    source_path=self.task.source_path,
                    target_paths=self.task.target_paths,
                    sync_mode=SyncMode(self.task.sync_mode),
                    conflict_strategy=ConflictStrategy(self.task.conflict_strategy),
                    include_patterns=self.task.include_patterns,
                    exclude_patterns=self.task.exclude_patterns,
                    task_id=self.task.id,
                    compare_method=self.task.compare_method
                )
                
                # 创建源文件夹监控器
                self._monitor = FileMonitor(
                    path=self.task.source_path,
                    callback=self._on_file_event,
                    recursive=True,
                    include_patterns=self.task.include_patterns,
                    exclude_patterns=self.task.exclude_patterns
                )
                
                if not self._monitor.start():
                    return False
                
                # 双向同步时，也监控目标文件夹
                if self.task.sync_mode == SyncMode.TWO_WAY.value:
                    for target_path in self.task.target_paths:
                        # 为每个目标创建独立的监控器
                        target_monitor = FileMonitor(
                            path=target_path,
                            callback=lambda evt, tp=target_path: self._on_target_file_event(tp, evt),
                            recursive=True,
                            include_patterns=self.task.include_patterns,
                            exclude_patterns=self.task.exclude_patterns
                        )
                        if target_monitor.start():
                            self._target_monitors.append(target_monitor)
                            logger.info(f"双向同步：开始监控目标 {target_path}", task_id=self.task.id, category="task")
                
                self._set_status(TaskStatus.RUNNING)
                logger.info(f"任务已启动: {self.task.name}", task_id=self.task.id, category="task")
                
                # 启动后立即执行一次全量同步检测
                import threading
                def auto_sync():
                    # 稍微延迟一下，让UI先响应启动状态
                    import time
                    time.sleep(0.5)
                    self.run_full_sync()
                    
                threading.Thread(target=auto_sync, daemon=True).start()
                logger.info(f"触发启动时全量同步: {self.task.name}", task_id=self.task.id, category="task")
                
                return True
                
            except Exception as e:
                logger.error(f"启动任务失败: {e}", task_id=self.task.id, category="task")
                self._set_status(TaskStatus.ERROR)
                return False
    
    def stop(self):
        """停止任务"""
        with self._lock:
            if self._status == TaskStatus.STOPPED:
                return
            
            try:
                # 停止源监控器
                if self._monitor:
                    self._monitor.stop()
                    self._monitor = None
                
                # 停止所有目标监控器
                for target_monitor in self._target_monitors:
                    target_monitor.stop()
                self._target_monitors.clear()
                
                if self._processor:
                    self._processor.stop()
                
                self._set_status(TaskStatus.STOPPED)
                logger.info(f"任务已停止: {self.task.name}", task_id=self.task.id, category="task")
            except Exception as e:
                logger.error(f"停止任务失败: {e}", task_id=self.task.id, category="task")
    
    def pause(self):
        """暂停任务"""
        with self._lock:
            if self._status == TaskStatus.RUNNING:
                self._set_status(TaskStatus.PAUSED)
                logger.info(f"任务已暂停: {self.task.name}", task_id=self.task.id, category="task")
    
    def resume(self):
        """恢复任务"""
        with self._lock:
            if self._status == TaskStatus.PAUSED:
                self._set_status(TaskStatus.RUNNING)
                logger.info(f"任务已恢复: {self.task.name}", task_id=self.task.id, category="task")
    
    def run_full_sync(self) -> bool:
        """执行全量同步"""
        # 获取操作锁，防止与实时同步冲突
        with self._operation_lock:
            try:
                if self._processor is None:
                    self._processor = SyncProcessor(
                        source_path=self.task.source_path,
                        target_paths=self.task.target_paths,
                        sync_mode=SyncMode(self.task.sync_mode),
                        conflict_strategy=ConflictStrategy(self.task.conflict_strategy),
                        include_patterns=self.task.include_patterns,
                        exclude_patterns=self.task.exclude_patterns,
                        task_id=self.task.id,
                        compare_method=self.task.compare_method
                    )
                
                logger.info(f"开始全量同步: {self.task.name}", task_id=self.task.id, category="task")
                self._is_syncing = True
                results = self._processor.full_sync(delete_orphans=self.task.delete_orphans)
                self.task.last_run_time = datetime.now().isoformat()
                task_manager.save_tasks()  # 保存最后运行时间

                
                # 记录结果
                for result in results:
                    if result.action in ("copy", "delete"):
                        logger.log_backup(
                            task_id=self.task.id,
                            task_name=self.task.name,
                            action=result.action,
                            source_path=result.source_path,
                            target_path=result.target_path,
                            file_size=str(result.file_size) if result.file_size else None,
                            status="success" if result.success else "failed"
                        )
                
                return True
            except Exception as e:
                logger.error(f"全量同步失败: {e}", task_id=self.task.id, category="task")
                return False
            finally:
                self._is_syncing = False
    
    @property
    def status(self) -> TaskStatus:
        return self._status
    
    @property
    def stats(self) -> dict:
        if self._processor:
            return self._processor.get_stats_dict()
        return {}
    
    @property
    def is_syncing(self) -> bool:
        return self._is_syncing or (self._processor and self._processor.is_running)


class TaskManager:
    """
    任务管理器
    管理所有备份任务
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
        
        self._tasks: Dict[str, BackupTask] = {}
        self._runners: Dict[str, TaskRunner] = {}
        self._lock = threading.Lock()
        self._event_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None
        
        # 加载保存的任务
        self._load_tasks()
    
    def _load_tasks(self):
        """从配置加载任务"""
        try:
            tasks_data = config_manager.get_tasks()
            for task_data in tasks_data:
                task = BackupTask.from_dict(task_data)
                self._tasks[task.id] = task
                self._runners[task.id] = TaskRunner(task)
            logger.info(f"加载了 {len(self._tasks)} 个备份任务", category="task")
        except Exception as e:
            logger.error(f"加载任务失败: {e}", category="task")
    
    def _save_tasks(self):
        """保存任务到配置"""
        try:
            tasks_data = [task.to_dict() for task in self._tasks.values()]
            config_manager._tasks = {"tasks": tasks_data}
            config_manager.save_tasks()
        except Exception as e:
            logger.error(f"保存任务失败: {e}", category="task")

    def save_tasks(self):
        """公开的保存任务方法"""
        self._save_tasks()
    
    def set_event_callback(self, callback: Callable):
        """设置全局事件回调"""
        self._event_callback = callback
        for runner in self._runners.values():
            runner.set_event_callback(callback)
    
    def set_status_callback(self, callback: Callable):
        """设置状态变更回调"""
        self._status_callback = callback
        for runner in self._runners.values():
            runner.set_status_callback(callback)
    
    def create_task(self, name: str, source_path: str, target_paths: List[str],
                    sync_mode: SyncMode = SyncMode.ONE_WAY,
                    conflict_strategy: ConflictStrategy = ConflictStrategy.NEWEST_WINS,
                    **kwargs) -> Optional[BackupTask]:
        """创建新任务"""
        with self._lock:
            try:
                task = BackupTask(
                    name=name,
                    source_path=source_path,
                    target_paths=target_paths,
                    sync_mode=sync_mode.value,
                    conflict_strategy=conflict_strategy.value,
                    **kwargs
                )
                
                self._tasks[task.id] = task
                runner = TaskRunner(task)
                if self._event_callback:
                    runner.set_event_callback(self._event_callback)
                if self._status_callback:
                    runner.set_status_callback(self._status_callback)
                self._runners[task.id] = runner
                
                self._save_tasks()
                logger.info(f"创建任务: {task.name} (ID: {task.id})", category="task")
                return task
            except Exception as e:
                logger.error(f"创建任务失败: {e}", category="task")
                return None
    
    def update_task(self, task_id: str, **kwargs) -> bool:
        """更新任务配置"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            try:
                task = self._tasks[task_id]
                
                # 如果任务正在运行,先停止
                was_running = self._runners[task_id].status == TaskStatus.RUNNING
                if was_running:
                    self._runners[task_id].stop()
                
                # 更新任务属性
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                task.updated_at = datetime.now().isoformat()
                
                # 重新创建runner
                runner = TaskRunner(task)
                if self._event_callback:
                    runner.set_event_callback(self._event_callback)
                if self._status_callback:
                    runner.set_status_callback(self._status_callback)
                self._runners[task_id] = runner
                
                # 如果之前在运行,重新启动
                if was_running:
                    runner.start()
                
                self._save_tasks()
                logger.info(f"更新任务: {task.name}", task_id=task_id, category="task")
                return True
            except Exception as e:
                logger.error(f"更新任务失败: {e}", task_id=task_id, category="task")
                return False
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        with self._lock:
            if task_id not in self._tasks:
                return False
            
            try:
                # 停止任务
                if task_id in self._runners:
                    self._runners[task_id].stop()
                    del self._runners[task_id]
                
                task_name = self._tasks[task_id].name
                del self._tasks[task_id]
                
                self._save_tasks()
                logger.info(f"删除任务: {task_name}", category="task")
                return True
            except Exception as e:
                logger.error(f"删除任务失败: {e}", category="task")
                return False
    
    def get_task(self, task_id: str) -> Optional[BackupTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[BackupTask]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def start_task(self, task_id: str) -> bool:
        """启动任务"""
        if task_id in self._runners:
            return self._runners[task_id].start()
        return False
    
    def stop_task(self, task_id: str):
        """停止任务"""
        if task_id in self._runners:
            self._runners[task_id].stop()
    
    def pause_task(self, task_id: str):
        """暂停任务"""
        if task_id in self._runners:
            self._runners[task_id].pause()
    
    def resume_task(self, task_id: str):
        """恢复任务"""
        if task_id in self._runners:
            self._runners[task_id].resume()
    
    def run_full_sync(self, task_id: str) -> bool:
        """执行全量同步"""
        if task_id in self._runners:
            return self._runners[task_id].run_full_sync()
        return False
    
    def start_all(self):
        """启动所有启用的任务"""
        for task_id, task in self._tasks.items():
            if task.enabled and task.auto_start:
                self.start_task(task_id)
    
    def stop_all(self):
        """停止所有任务"""
        for task_id in self._runners:
            self.stop_task(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        if task_id in self._runners:
            return self._runners[task_id].status
        return None
    
    def get_task_stats(self, task_id: str) -> dict:
        """获取任务统计"""
        if task_id in self._runners:
            return self._runners[task_id].stats
        return {}
    
    def get_running_count(self) -> int:
        """获取运行中的任务数量"""
        return sum(1 for r in self._runners.values() if r.status == TaskStatus.RUNNING)
    
    def get_overall_stats(self) -> dict:
        """获取总体统计"""
        total_tasks = len(self._tasks)
        running = 0
        paused = 0
        stopped = 0
        
        for runner in self._runners.values():
            if runner.status == TaskStatus.RUNNING:
                running += 1
            elif runner.status == TaskStatus.PAUSED:
                paused += 1
            else:
                stopped += 1
        
        return {
            "total_tasks": total_tasks,
            "running": running,
            "paused": paused,
            "stopped": stopped,
            "is_syncing": any(r.is_syncing for r in self._runners.values()),
            "last_run_time": max((t.last_run_time for t in self._tasks.values() if t.last_run_time), default="")
        }


# 全局任务管理器实例
task_manager = TaskManager()
