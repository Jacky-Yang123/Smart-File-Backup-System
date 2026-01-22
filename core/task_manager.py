"""
任务管理器模块
"""
import os
import uuid
import threading
from typing import Dict, List, Optional, Callable, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

from utils.constants import SyncMode, ConflictStrategy, TaskStatus
from utils.config_manager import config_manager
from utils.logger import logger
from .file_monitor import FileMonitor, FileEvent, PollingMonitor
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
    initial_sync_delete: bool = False # 启动时全量同步是否删除目标多余文件
    reverse_delete: bool = False  # 单向备份：目标删除时是否同步删除源文件
    disable_delete: bool = False  # 禁止删除操作：防止任何文件被删除
    file_count_diff_threshold: int = 20  # 双向同步：文件数量差异警告阈值
    monitor_mode: str = "realtime"  # 监控模式: realtime(实时) 或 polling(轮询)
    poll_interval: int = 5  # 轮询间隔(秒)
    safety_threshold: int = 50  # 安全阈值：一次同步最大允许变更文件数 (超过则警告)
    batch_delay: float = 1.0  # 批量操作防抖延迟(秒)
    created_at: str = ""
    updated_at: str = ""
    last_run_time: str = ""
    
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
        
        # 批量处理相关属性
        self._batch_lock = threading.Lock()
        self._file_event_batch: List[Tuple[FileEvent, bool, object]] = []
        self._batch_timer: Optional[threading.Timer] = None
        # self._SAFETY_DELAY = 1.0  # 使用 self.task.batch_delay 代替
        
        # 安全暂停状态
        self._is_safety_paused = False
        self._paused_batch: List[Tuple[FileEvent, bool, object]] = []
    
    def set_event_callback(self, callback: Callable[[str, FileEvent, dict], None]):
        """设置事件回调 (task_id, event, result)"""
        self._event_callback = callback
    
    def set_status_callback(self, callback: Callable[[str, TaskStatus], None]):
        """设置状态变更回调"""
        self._status_callback = callback
    
    def _on_file_event(self, event: FileEvent):
        """文件变更事件回调 - 改为批量缓冲"""
        if self.status != TaskStatus.RUNNING:
            return
            
        self._add_to_batch(event, False)

    def _on_target_file_event(self, event: FileEvent, target_base: str):
        """目标文件变更回调 - 改为批量缓冲"""
        if self.status != TaskStatus.RUNNING:
            return
            
        self._add_to_batch(event, True, target_base)
        
    def _add_to_batch(self, event: FileEvent, is_reverse: bool, target_base: str = None):
        """添加到批量缓冲区并重置定时器"""
        with self._batch_lock:
            # 取消现有定时器
            if self._batch_timer:
                self._batch_timer.cancel()
            
            # 添加到缓冲区
            self._file_event_batch.append((event, is_reverse, target_base))
            
            # 设置新定时器 (Debounce)
            self._batch_timer = threading.Timer(self.task.batch_delay, self._process_batch_events)
            self._batch_timer.start()
            
    def _process_batch_events(self):
        """处理批量收集的事件"""
        with self._batch_lock:
            if not self._file_event_batch:
                return
            
            # 复制并清空缓冲区 (Snapshot)
            batch = list(self._file_event_batch)
            self._file_event_batch.clear()
            self._batch_timer = None
        
        # 如果处于安全暂停状态，直接累积到暂停的批次中
        if self._is_safety_paused:
             self._paused_batch.extend(batch)
             self._trigger_safety_alert_update() # 更新提醒
             return
            
        # Issue 7 Fix: 检查是否超过安全阈值时，对于文件夹事件要计算内部文件数量
        total_changes = 0
        for evt, _, _ in batch:
            if evt.is_directory and os.path.isdir(evt.src_path):
                # 文件夹：计算内部文件数量
                try:
                    file_count = sum(1 for _, _, files in os.walk(evt.src_path) for _ in files)
                    total_changes += max(file_count, 1)  # 至少算1个
                except Exception:
                    total_changes += 1
            else:
                total_changes += 1
        
        # 如果超过阈值，触发警告
        if total_changes >= self.task.safety_threshold:
             self._is_safety_paused = True
             self._paused_batch.extend(batch)
             self._trigger_safety_alert_update()
        else:
             # 正常执行 - 使用 execute_batch 通过队列执行
             self.execute_batch(batch)

    def _get_effective_excludes(self) -> List[str]:
        """获取有效的排除列表 (自动添加嵌套的目标目录)"""
        effective_excludes = list(self.task.exclude_patterns)
        for target_path in self.task.target_paths:
            try:
                rel = os.path.relpath(target_path, self.task.source_path)
                if not rel.startswith('..') and not os.path.isabs(rel):
                    # 目标在源目录内，必须排除
                    effective_excludes.append(target_path)
                    # 同时也尝试排除目录名，以防万一
                    target_name = os.path.basename(target_path)
                    if target_name not in effective_excludes:
                         effective_excludes.append(target_name)
            except ValueError:
                pass
        return effective_excludes

    def confirm_safety_alert(self):
        """确认并执行安全暂停期间累积的所有变更"""
        if not self._is_safety_paused:
            logger.warning("confirm_safety_alert 调用时未处于安全暂停状态", task_id=self.task.id, category="safety")
            return
        
        batch_to_run = list(self._paused_batch)
        count = len(batch_to_run)
        logger.info(f"确认安全警告: 准备执行 {count} 项操作", task_id=self.task.id, category="safety")
        
        self._paused_batch.clear()
        self._is_safety_paused = False
        
        if batch_to_run:
            self.execute_batch(batch_to_run)
        else:
            logger.warning("确认安全警告: 批次为空，无操作执行", task_id=self.task.id, category="safety")
        
    def execute_batch(self, batch):
        """执行批量任务 (通过操作队列)"""
        if not batch:
            logger.warning("执行批量任务: 批次为空", task_id=self.task.id, category="task")
            return
            
        from .operation_queue import operation_queue, OperationType
        from utils.constants import FileEventType, FileEvent
        from utils.file_utils import get_relative_path
        
        ops = []
        task_id = self.task.id
        task_name = self.task.name
        
        logger.info(f"开始执行批量任务(Queue): {len(batch)} 项", task_id=task_id, category="task")

        for item in batch:
            # 格式: (event, is_reverse, target_base)
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                event, is_reverse, target_base = item[:3]
                if not isinstance(event, FileEvent):
                    continue
                    
                op_type = OperationType.COPY_FILE
                source = ""
                target = ""
                
                try:
                    # 确定操作类型
                    if event.event_type == FileEventType.DELETED:
                        op_type = OperationType.DELETE_FILE
                    
                    src_path = event.src_path
                    
                    if is_reverse:
                        # 反向模式
                        if op_type == OperationType.DELETE_FILE:
                            # 目标删了 -> 删源
                            rel = get_relative_path(src_path, target_base)
                            source = os.path.join(self.task.source_path, rel)
                        else:
                             # 目标新增/修改 -> 复制到源
                            rel = get_relative_path(src_path, target_base)
                            source = src_path
                            target = os.path.join(self.task.source_path, rel)
                    else:
                        # 正向模式
                        if op_type == OperationType.DELETE_FILE:
                            # 源删了 -> 删目标
                            rel = get_relative_path(src_path, self.task.source_path)
                            for t_path in self.task.target_paths:
                                target_file_to_del = os.path.join(t_path, rel)
                                ops.append({
                                    "op_type": op_type,
                                    "source": target_file_to_del,
                                    "target": "",
                                    "task_id": task_id,
                                    "task_name": task_name
                                })
                            continue # 已添加所有目标，跳过通用逻辑
                        else:
                            # 源新增/修改 -> 复制到目标
                            rel = get_relative_path(src_path, self.task.source_path)
                            for t_path in self.task.target_paths:
                                dst = os.path.join(t_path, rel)
                                ops.append({
                                    "op_type": op_type,
                                    "source": src_path,
                                    "target": dst,
                                    "task_id": task_id,
                                    "task_name": task_name
                                })
                            continue

                    # 处理单目标情况 (反向或者其他逻辑)
                    if source or (op_type == OperationType.COPY_FILE and source and target):
                         ops.append({
                            "op_type": op_type,
                            "source": source,
                            "target": target,
                            "task_id": task_id,
                            "task_name": task_name
                        })
                        
                except Exception as e:
                    logger.error(f"解析批量项失败: {e}", task_id=task_id)

        if ops:
            operation_queue.add_batch_operations(ops)


    def _execute_batch(self, batch):
        """执行批量任务 (内部实现) - 带进度追踪"""
        if not self._processor:
            return
        
        total = len(batch)
        if total == 0:
            return
            
        try:
            processed = 0
            
            for event, is_reverse, target_base in batch:
                if self.status != TaskStatus.RUNNING:
                    logger.info(f"批量任务中断: 已处理 {processed}/{total}", task_id=self.task.id, category="task")
                    break
                
                # 调用处理逻辑
                self._process_file_event_async(event, is_reverse, target_base)
                processed += 1
                
                # 每处理10个或每5%发送一次进度更新
                if processed % max(1, total // 20) == 0 or processed == total:
                    remaining = total - processed
                    if self._event_callback:
                        self._event_callback(self.task.id, event, {
                            "success": True,
                            "action": "progress",
                            "message": f"进度: {processed}/{total}, 剩余: {remaining}",
                            "progress_current": processed,
                            "progress_total": total,
                            "progress_remaining": remaining
                        })
            
            logger.info(f"批量任务完成: {processed}/{total}", task_id=self.task.id, category="task")
            
        except Exception as e:
            logger.error(f"批量执行失败: {e}", task_id=self.task.id, category="task")
    
    def get_pending_batch_count(self) -> int:
        """获取待处理批次数量"""
        return len(self._paused_batch)

    def _trigger_safety_alert_update(self):
        """触发或更新安全警告"""
        count = len(self._paused_batch)
        batch = self._paused_batch
        
        logger.warning(f"安全暂停中: 累积变更 {count} (阈值 {self.task.safety_threshold})", 
                      task_id=self.task.id, category="safety")
        
        # 构造警告信息
        msg = f"检测到 {count} 个文件发生变更，超过了安全阈值 ({self.task.safety_threshold})。\n"
        msg += "在此期间的所有后续变更都将暂缓执行，直到您确认。\n\n"
        
        preview_files = [os.path.basename(e[0].src_path) for e in batch[:5]]
        msg += "变更预览:\n" + "\n".join(preview_files)
        if count > 5:
            msg += f"\n... 等 {count} 个文件"
            
        if self._event_callback:
            dummy_event = batch[0][0] 
            # Issue 1 Fix: 限制传递给UI的预览数据为前100项，防止大量数据导致UI卡死
            # 完整数据保留在 self._paused_batch 中用于执行
            preview_batch = batch[:100] if len(batch) > 100 else batch
            self._event_callback(self.task.id, dummy_event, {
                "success": False,
                "action": "safety_alert",
                "message": msg,
                "batch_data": preview_batch,  # 只传递预览数据
                "batch_total_count": count,   # 传递总数供UI显示
                "alert_type": "massive_change",
                "accumulated_count": count
            })

    def reset_safety_pause(self):
        """重置安全暂停状态（不执行已累积的操作）"""
        self._is_safety_paused = False
        self._paused_batch.clear()
        
    def _process_file_event_async(self, event: FileEvent, is_reverse: bool, target_base: str = None):
        """异步处理文件事件"""
        # 获取操作锁，确保不与全量同步冲突
        if not self._processor or not self._operation_lock.acquire(timeout=60):  # 尝试获取锁，超时60秒
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
            if self._operation_lock.locked():
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
                # 获取有效的排除列表（包含自动排除的嵌套目标）
                effective_excludes = self._get_effective_excludes()

                # 创建同步处理器
                self._processor = SyncProcessor(
                    source_path=self.task.source_path,
                    target_paths=self.task.target_paths,
                    sync_mode=SyncMode(self.task.sync_mode),
                    conflict_strategy=ConflictStrategy(self.task.conflict_strategy),
                    include_patterns=self.task.include_patterns,
                    exclude_patterns=effective_excludes,
                    disable_delete=self.task.disable_delete
                )

                # 创建源文件夹监控器（根据模式选择实时或轮询）
                if self.task.monitor_mode == "polling":
                    self._monitor = PollingMonitor(
                        path=self.task.source_path,
                        callback=self._on_file_event,
                        interval=self.task.poll_interval,
                        recursive=True,
                        include_patterns=self.task.include_patterns,
                        exclude_patterns=effective_excludes
                    )
                else:
                    self._monitor = FileMonitor(
                        path=self.task.source_path,
                        callback=self._on_file_event,
                        recursive=True,
                        include_patterns=self.task.include_patterns,
                        exclude_patterns=effective_excludes
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
                    
                    # Issue 4 Fix: 初始同步前先进行安全检查
                    try:
                        safety = self.check_sync_safety()
                        if not safety.get("safe", True):
                            # 触发安全警告，而不是直接执行
                            logger.warning(f"启动时全量同步需要确认: {safety.get('message', '')}", 
                                          task_id=self.task.id, category="safety")
                            
                            if self._event_callback:
                                from .file_monitor import FileEvent
                                from utils.constants import FileEventType
                                dummy_event = FileEvent(
                                    event_type=FileEventType.CREATED,
                                    src_path=self.task.source_path,
                                    is_directory=True
                                )
                                self._event_callback(self.task.id, dummy_event, {
                                    "success": False,
                                    "action": "safety_alert",
                                    "message": f"启动时全量同步:\n{safety.get('message', '')}",
                                    "batch_data": [],
                                    "batch_total_count": safety.get("changes_count", 0),
                                    "alert_type": safety.get("warning_type", "massive_change"),
                                    "accumulated_count": safety.get("changes_count", 0),
                                    "is_initial_sync": True  # 标记为初始同步，需要执行 run_full_sync
                                })
                            return  # 不执行同步，等待用户确认
                    except Exception as e:
                        logger.warning(f"安全检查失败，继续执行同步: {e}", task_id=self.task.id, category="safety")
                    
                    # 初始同步删除规则
                    delete_rule = getattr(self.task, 'initial_sync_delete', False)
                    self.run_full_sync(delete_orphans_override=delete_rule)
                    
                threading.Thread(target=auto_sync, daemon=True).start()
                logger.info(f"触发启动时全量同步(删除策略={getattr(self.task, 'initial_sync_delete', False)}): {self.task.name}", 
                           task_id=self.task.id, category="task")
                
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
    
    def run_full_sync(self, skip_safety_check: bool = False, delete_orphans_override: Optional[bool] = None) -> bool:
        """执行全量同步 (通过操作队列)"""
        if self._is_syncing:
            return False
            
        # 启动后台线程进行扫描和计划
        import threading
        from .operation_queue import operation_queue, OperationType
        
        def plan_and_queue():
             try:
                with self._operation_lock:
                    if self._processor is None:
                        self._processor = SyncProcessor(
                            source_path=self.task.source_path,
                            target_paths=self.task.target_paths,
                            sync_mode=SyncMode(self.task.sync_mode),
                            conflict_strategy=ConflictStrategy(self.task.conflict_strategy),
                            include_patterns=self.task.include_patterns,
                            exclude_patterns=self.task.exclude_patterns,
                            disable_delete=self.task.disable_delete
                        )
                    
                    delete_orphans = delete_orphans_override if delete_orphans_override is not None else self.task.delete_orphans
                    logger.info(f"开始全量同步扫描(清理={delete_orphans}): {self.task.name}", task_id=self.task.id, category="task")
                    
                    self._is_syncing = True
                    # 1. 扫描并生成计划 (可能耗时，但不会卡死UI)
                    plans = self._processor.scan_and_plan(delete_orphans=delete_orphans)
                    
                    if not plans:
                         logger.info(f"全量同步扫描完成: 无需变更", task_id=self.task.id, category="task")
                         self.task.last_run_time = datetime.now().isoformat()
                         task_manager.save_tasks()
                         self._is_syncing = False
                         return

                    # 2. 添加到队列
                    ops = []
                    for p in plans:
                        ops.append({
                            "op_type": p["op_type"],
                            "source": p["source"],
                            "target": p["target"],
                            "task_id": self.task.id,
                            "task_name": self.task.name
                        })
                    
                operation_queue.add_batch_operations(ops)
                    
                logger.info(f"已将 {len(ops)} 个全量同步操作加入队列", task_id=self.task.id, category="task")
                self.task.last_run_time = datetime.now().isoformat()
                task_manager.save_tasks()
                    
             except Exception as e:
                logger.error(f"全量同步计划失败: {e}", task_id=self.task.id, category="task")
                import traceback
                logger.error(f"Error Traceback: {traceback.format_exc()}", task_id=self.task.id, category="task")
             finally:
                self._is_syncing = False

        try:
            threading.Thread(target=plan_and_queue, daemon=True).start()
            return True
        except Exception as e:
            logger.error(f"启动全量同步线程失败: {e}", task_id=self.task.id, category="task")
            self._is_syncing = False
            return False
    
    
    def check_sync_safety(self) -> dict:
        """
        检查同步前的安全状态 (使用模拟运行)
        
        Returns:
            dict: {
                "safe": bool,  # 是否安全
                "warning_type": str,  # "empty_source" | "massive_change" | None
                "message": str,  # 警告消息
                "changes_count": int
            }
        """
        try:
            # 临时创建处理器如果不存在
            processor = self._processor
            if processor is None:
                processor = SyncProcessor(
                    source_path=self.task.source_path,
                    target_paths=self.task.target_paths,
                    sync_mode=SyncMode(self.task.sync_mode),
                    conflict_strategy=ConflictStrategy(self.task.conflict_strategy),
                    include_patterns=self.task.include_patterns,
                    exclude_patterns=self._get_effective_excludes(),
                    disable_delete=self.task.disable_delete
                )
            
            # 执行模拟运行
            logger.info(f"正在进行安全检查(Dry Run): {self.task.name}", task_id=self.task.id, category="safety")
            results = processor.full_sync(delete_orphans=self.task.delete_orphans, dry_run=True)
            
            # 分析结果
            total_changes = 0
            delete_count = 0
            changes_details = []
            
            for res in results:
                if res.action in ("copy", "delete", "move"):
                    total_changes += 1
                    if len(changes_details) < 5:  # 只记录前5个变更用于显示
                        changes_details.append(f"{res.action}: {os.path.basename(res.source_path or res.target_path)}")
                
                if res.action == "delete":
                    delete_count += 1
            
            logger.info(f"安全检查结果: 变更={total_changes}, 删除={delete_count}", task_id=self.task.id, category="safety")
            
            # 1. 检查空源保护 (仅在单向同步且开启清理时)
            if self.task.sync_mode == SyncMode.ONE_WAY.value and self.task.delete_orphans:
                 from utils.file_utils import scan_directory
                 source_files = scan_directory(self.task.source_path)
                 if len(source_files) == 0 and delete_count > 0:
                     return {
                        "safe": False,
                        "warning_type": "empty_source",
                        "message": f"警告：源文件夹为空！\n本次同步将删除目标文件夹中的 {delete_count} 个文件。\n\n如果您不确定，请点击【取消】。",
                        "changes_count": total_changes
                    }

            # 2. 检查大量变更
            if total_changes >= self.task.safety_threshold:
                 detail_str = "\n".join(changes_details)
                 if total_changes > 5:
                     detail_str += f"\n... 等 {total_changes} 个文件"
                     
                 return {
                    "safe": False,
                    "warning_type": "massive_change",
                    "message": f"警告：本次同步涉及大量变更 ({total_changes} 个文件)！\n超过了设定的安全阈值 ({self.task.safety_threshold})。\n\n变更预览:\n{detail_str}",
                    "changes_count": total_changes
                }
            
            return {"safe": True, "warning_type": None, "message": "", "changes_count": total_changes}
            
        except Exception as e:
            logger.error(f"安全检查失败: {e}", task_id=self.task.id, category="safety")
            # 如果检查失败，默认放行，但记录错误
            return {"safe": True, "warning_type": None, "message": "", "changes_count": 0}
    
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
        
        # 设置操作队列执行器
        from .operation_queue import operation_queue
        operation_queue.set_executor(self._execute_queue_operation)

    def _execute_queue_operation(self, op) -> Tuple[bool, str]:
        """执行队列操作 (作为 OperationQueue 的执行器)"""
        task_id = op.task_id
        if not task_id or task_id not in self._runners:
            return False, f"Task not found: {task_id}"
            
        runner = self._runners[task_id]
        if not runner._processor:
            # 尝试初始化处理器 (可能需要从 task 创建)
            task = self._tasks.get(task_id)
            if not task:
                return False, "Task object missing"
                
            from .sync_processor import SyncProcessor
            runner._processor = SyncProcessor(
                source_path=task.source_path,
                target_paths=task.target_paths,
                sync_mode=SyncMode(task.sync_mode),
                conflict_strategy=ConflictStrategy(task.conflict_strategy),
                include_patterns=task.include_patterns,
                exclude_patterns=task.exclude_patterns,
                disable_delete=task.disable_delete
            )
        
        # 将 Enum 转换为字符串
        op_type_str = op.op_type.value if hasattr(op.op_type, 'value') else str(op.op_type)
        return runner._processor.execute_op(op_type_str, op.source_path, op.target_path)
    
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
    
    def run_full_sync(self, task_id: str, delete_orphans_override: bool = None) -> bool:
        """执行全量同步"""
        if task_id in self._runners:
            return self._runners[task_id].run_full_sync(delete_orphans_override=delete_orphans_override)
        return False
    
    def start_all(self, force: bool = False):
        """
        启动所有启用的任务
        :param force: 是否强制启动（忽略 auto_start 设置），用于手动点击"全部启动"
        """
        for task_id, task in self._tasks.items():
            if task.enabled and (task.auto_start or force):
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
        
    def execute_batch(self, task_id: str, batch: list):
        """执行批量任务"""
        if task_id in self._runners:
            self._runners[task_id].execute_batch(batch)
    
    def confirm_safety_alert(self, task_id: str):
        """确认处理安全警告累积的所有操作"""
        if task_id in self._runners:
            self._runners[task_id].confirm_safety_alert()

    def reset_safety_pause(self, task_id: str):
        """重置安全暂停状态（丢弃累积的操作）"""
        if task_id in self._runners:
            self._runners[task_id].reset_safety_pause()

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
