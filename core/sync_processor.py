"""
同步处理器模块
"""
import os
import shutil
from typing import List, Tuple, Dict, Callable, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from datetime import datetime
from utils.constants import SyncMode, ConflictStrategy, FileEventType
from utils.file_utils import (
    safe_copy_file, safe_delete_file, safe_move_file,
    get_relative_path, scan_directory, compare_files,
    format_file_size, get_file_size, match_file_patterns,
    get_file_hash
)
from utils.logger import logger
from .conflict_handler import ConflictHandler
from .file_monitor import FileEvent
from .state_manager import state_manager, FileState


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    action: str  # copy, delete, skip, error
    source_path: str
    target_path: str = None
    message: str = ""
    file_size: int = 0


@dataclass
class SyncStats:
    """同步统计"""
    total_files: int = 0
    copied_files: int = 0
    deleted_files: int = 0
    skipped_files: int = 0
    failed_files: int = 0
    total_size: int = 0
    
    def reset(self):
        self.total_files = 0
        self.copied_files = 0
        self.deleted_files = 0
        self.skipped_files = 0
        self.failed_files = 0
        self.total_size = 0


class SyncProcessor:
    """
    同步处理器
    处理文件同步操作
    """
    
    def __init__(self, source_path: str, target_paths: List[str],
                 sync_mode: SyncMode = SyncMode.ONE_WAY,
                 conflict_strategy: ConflictStrategy = ConflictStrategy.NEWEST_WINS,
                 include_patterns: List[str] = None,
                 exclude_patterns: List[str] = None,
                 max_workers: int = 4,
                 task_id: str = "",
                 compare_method: str = "mtime"):
        """
        初始化同步处理器
        
        Args:
            source_path: 源文件夹路径
            target_paths: 目标文件夹路径列表
            sync_mode: 同步模式
            conflict_strategy: 冲突处理策略
            include_patterns: 包含文件模式
            exclude_patterns: 排除文件模式
            max_workers: 最大并发工作线程数
            task_id: 任务ID (用于状态管理)
            compare_method: 比较方式 (mtime, hash)
        """
        self.source_path = os.path.abspath(source_path)
        self.target_paths = [os.path.abspath(p) for p in target_paths]
        self.sync_mode = sync_mode
        self.conflict_handler = ConflictHandler(conflict_strategy)
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.max_workers = max_workers
        self.task_id = task_id
        self.compare_method = compare_method
        self.state_manager = state_manager
        
        self._stats = SyncStats()
        self._stats_lock = Lock()
        self._progress_callback: Optional[Callable[[int, int, str], None]] = None
        self._is_running = False
        self._should_stop = False
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]):
        """设置进度回调 (current, total, message)"""
        self._progress_callback = callback
    
    def _update_progress(self, current: int, total: int, message: str):
        """更新进度"""
        if self._progress_callback:
            try:
                self._progress_callback(current, total, message)
            except Exception:
                pass
    
    def _should_process_file(self, filepath: str) -> bool:
        """检查是否应该处理该文件"""
        return match_file_patterns(filepath, self.include_patterns, self.exclude_patterns)
    
    def _update_state(self, rel_path, file_hash, file_path):
        """更新文件状态"""
        try:
            state = FileState(
                hash=file_hash,
                mtime=os.path.getmtime(file_path),
                size=os.path.getsize(file_path),
                last_sync_time=datetime.now().isoformat()
            )
            self.state_manager.update_file_state(self.task_id, rel_path, state)
        except Exception as e:
            logger.warning(f"更新状态失败: {e}", task_id=self.task_id)

    def _sync_file_with_hash(self, source_file: str, target_path: str) -> SyncResult:
        """基于哈希的同步逻辑"""
        try:
            rel_path = get_relative_path(source_file, self.source_path)
            target_file = os.path.join(target_path, rel_path)
            
            # 过滤
            if not self._should_process_file(source_file):
                return SyncResult(True, "skip", source_file, target_file, "文件被过滤规则排除")

            # 计算哈希
            src_hash = get_file_hash(source_file)
            
            # 获取上次状态
            last_state = self.state_manager.get_file_state(self.task_id, rel_path)
            last_hash = last_state.hash if last_state else None
            
            # 目标状态
            target_exists = os.path.exists(target_file)
            tgt_hash = get_file_hash(target_file) if target_exists else None
            
            # 变更检测
            src_changed = (src_hash != last_hash)
            tgt_changed = (not target_exists) or (tgt_hash != last_hash)
            
            # 1. 双方未变
            if not src_changed and not tgt_changed:
                return SyncResult(True, "skip", source_file, target_file, "文件已是最新")
            
            # 2. 源变更，目标未变 (或目标不存在) -> 更新目标
            if src_changed and not tgt_changed:
                success, error = safe_copy_file(source_file, target_file)
                if success:
                    self._update_state(rel_path, src_hash, source_file)
                    return SyncResult(True, "copy", source_file, target_file, "源文件变更，更新目标", get_file_size(source_file))
                return SyncResult(False, "error", source_file, target_file, f"复制失败: {error}")
            
            # 3. 源未变，目标变更
            if not src_changed and tgt_changed:
                if self.sync_mode == SyncMode.TWO_WAY:
                    # 双向模式：跳过，留给反向同步处理 (目标 -> 源)
                    return SyncResult(True, "skip", source_file, target_file, "目标变更，等待反向同步")
                else:
                    # 单向模式：强制还原目标 (Source Wins)
                    success, error = safe_copy_file(source_file, target_file)
                    if success:
                        self._update_state(rel_path, src_hash, source_file)
                        return SyncResult(True, "copy", source_file, target_file, "纠正目标变更，还原为源版本", get_file_size(source_file))
                    return SyncResult(False, "error", source_file, target_file, f"还原失败: {error}")
            
            # 4. 双方变更 -> 冲突
            if src_changed and tgt_changed:
                if src_hash == tgt_hash:
                    # 内容一致
                    self._update_state(rel_path, src_hash, source_file)
                    return SyncResult(True, "skip", source_file, target_file, "双方变更但内容一致")
                
                # 真正的冲突：保留双方
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                base, ext = os.path.splitext(target_file)
                conflict_file = f"{base}.conflict.{timestamp}{ext}"
                
                try:
                    # 尝试移动目标文件作为冲突备份
                    # 注意：safe_move_file 如果跨盘可能耗时
                    shutil.move(target_file, conflict_file)
                except Exception as e:
                    return SyncResult(False, "error", source_file, target_file, f"备份冲突文件失败: {e}")
                
                # 复制源文件到目标
                success, error = safe_copy_file(source_file, target_file)
                if success:
                    self._update_state(rel_path, src_hash, source_file)
                    return SyncResult(True, "copy", source_file, target_file, f"双方冲突，已备份旧版至 {os.path.basename(conflict_file)}", get_file_size(source_file))
                else:
                    return SyncResult(False, "error", source_file, target_file, f"解决冲突失败: {error}")
                    
        except Exception as e:
            return SyncResult(False, "error", source_file, target_path, f"Hash同步异常: {e}")

    def _sync_file(self, source_file: str, target_path: str) -> SyncResult:
        """
        同步单个文件
        
        Args:
            source_file: 源文件路径
            target_path: 目标文件夹路径
        
        Returns:
            同步结果
        """
        # 使用哈希同步
        if self.compare_method == "hash" and self.task_id:
            return self._sync_file_with_hash(source_file, target_path)

        try:
            rel_path = get_relative_path(source_file, self.source_path)
            target_file = os.path.join(target_path, rel_path)
            
            # 检查过滤规则
            if not self._should_process_file(source_file):
                return SyncResult(
                    success=True,
                    action="skip",
                    source_path=source_file,
                    target_path=target_file,
                    message="文件被过滤规则排除"
                )
            
            # 目标文件不存在,直接复制
            if not os.path.exists(target_file):
                success, error = safe_copy_file(source_file, target_file)
                if success:
                    file_size = get_file_size(source_file)
                    return SyncResult(
                        success=True,
                        action="copy",
                        source_path=source_file,
                        target_path=target_file,
                        message="文件已复制",
                        file_size=file_size
                    )
                else:
                    return SyncResult(
                        success=False,
                        action="error",
                        source_path=source_file,
                        target_path=target_file,
                        message=f"复制失败: {error}"
                    )
            
            # 检查冲突
            if self.conflict_handler.check_conflict(source_file, target_file):
                action, resolved_path, reason = self.conflict_handler.resolve(source_file, target_file)
                
                if action == "copy":
                    success, error = safe_copy_file(source_file, resolved_path or target_file)
                    if success:
                        file_size = get_file_size(source_file)
                        return SyncResult(
                            success=True,
                            action="copy",
                            source_path=source_file,
                            target_path=resolved_path or target_file,
                            message=reason,
                            file_size=file_size
                        )
                    else:
                        return SyncResult(
                            success=False,
                            action="error",
                            source_path=source_file,
                            target_path=target_file,
                            message=f"复制失败: {error}"
                        )
                
                elif action == "keep_both":
                    success, error = safe_copy_file(source_file, resolved_path)
                    if success:
                        file_size = get_file_size(source_file)
                        return SyncResult(
                            success=True,
                            action="copy",
                            source_path=source_file,
                            target_path=resolved_path,
                            message=reason,
                            file_size=file_size
                        )
                    else:
                        return SyncResult(
                            success=False,
                            action="error",
                            source_path=source_file,
                            target_path=resolved_path,
                            message=f"保留双方失败: {error}"
                        )
                
                else:  # skip
                    return SyncResult(
                        success=True,
                        action="skip",
                        source_path=source_file,
                        target_path=target_file,
                        message=reason
                    )
            
            # 无冲突,文件相同,跳过
            return SyncResult(
                success=True,
                action="skip",
                source_path=source_file,
                target_path=target_file,
                message="文件已是最新"
            )
            
        except Exception as e:
            return SyncResult(
                success=False,
                action="error",
                source_path=source_file,
                target_path=target_path,
                message=f"同步异常: {str(e)}"
            )
    
    def _sync_deletion(self, deleted_path: str, target_path: str) -> SyncResult:
        """同步删除操作"""
        try:
            rel_path = get_relative_path(deleted_path, self.source_path)
            target_file = os.path.join(target_path, rel_path)
            
            if os.path.exists(target_file):
                success, error = safe_delete_file(target_file)
                if success:
                    return SyncResult(
                        success=True,
                        action="delete",
                        source_path=deleted_path,
                        target_path=target_file,
                        message="文件已删除"
                    )
                else:
                    return SyncResult(
                        success=False,
                        action="error",
                        source_path=deleted_path,
                        target_path=target_file,
                        message=f"删除失败: {error}"
                    )
            
            return SyncResult(
                success=True,
                action="skip",
                source_path=deleted_path,
                target_path=target_file,
                message="目标文件不存在"
            )
            
        except Exception as e:
            return SyncResult(
                success=False,
                action="error",
                source_path=deleted_path,
                target_path=target_path,
                message=f"删除异常: {str(e)}"
            )
    
    def _sync_directory_move(self, src_path: str, dst_path: str, target_base: str) -> SyncResult:
        """同步文件夹移动/重命名 (原子操作)"""
        try:
            rel_src = get_relative_path(src_path, self.source_path)
            rel_dst = get_relative_path(dst_path, self.source_path)
            target_src = os.path.join(target_base, rel_src)
            target_dst = os.path.join(target_base, rel_dst)
            
            # 如果源目录不存在（可能已经被删除或移动），跳过
            if not os.path.exists(target_src):
                return SyncResult(
                    success=True,
                    action="skip",
                    source_path=src_path,
                    target_path=target_dst,
                    message="目标源目录不存在"
                )
            
            # 如果目标已存在，尝试先删除目标（或者这应该是一个冲突？）
            # 为了保证重命名成功，如果目标存在且非空，可能需要手动干预
            # 但为了效率，我们假设覆盖
            if os.path.exists(target_dst):
                safe_delete_file(target_dst)
            
            success, error = safe_move_file(target_src, target_dst)
            if success:
                return SyncResult(
                    success=True,
                    action="move",
                    source_path=src_path,
                    target_path=target_dst,
                    message="文件夹重命名成功"
                )
            else:
                return SyncResult(
                    success=False,
                    action="error",
                    source_path=src_path,
                    target_path=target_dst,
                    message=f"文件夹移动失败: {error}"
                )
        except Exception as e:
            return SyncResult(
                success=False,
                action="error",
                source_path=src_path,
                target_path=target_base,
                message=f"文件夹移动异常: {str(e)}"
            )

    def _sync_directory_move_reverse(self, src_path: str, dst_path: str, target_base: str) -> SyncResult:
        """反向同步文件夹移动 (原子操作)"""
        try:
            rel_src = get_relative_path(src_path, target_base)
            rel_dst = get_relative_path(dst_path, target_base)
            source_src = os.path.join(self.source_path, rel_src)
            source_dst = os.path.join(self.source_path, rel_dst)
            
            if not os.path.exists(source_src):
                return SyncResult(
                    success=True,
                    action="skip",
                    source_path=src_path,
                    target_path=source_dst,
                    message="源目录不存在"
                )
            
            if os.path.exists(source_dst):
                safe_delete_file(source_dst)
            
            success, error = safe_move_file(source_src, source_dst)
            if success:
                return SyncResult(
                    success=True,
                    action="move",
                    source_path=src_path,
                    target_path=source_dst,
                    message="反向文件夹重命名成功"
                )
            else:
                return SyncResult(
                    success=False,
                    action="error",
                    source_path=src_path,
                    target_path=source_dst,
                    message=f"反向文件夹移动失败: {error}"
                )
        except Exception as e:
            return SyncResult(
                success=False,
                action="error",
                source_path=src_path,
                target_path=self.source_path,
                message=f"反向文件夹移动异常: {str(e)}"
            )

    def process_event(self, event: FileEvent) -> List[SyncResult]:
        """
        处理文件事件
        
        Args:
            event: 文件事件
        
        Returns:
            同步结果列表
        """
        results = []
        
        for target_path in self.target_paths:
            if event.event_type == FileEventType.CREATED:
                if not event.is_directory:
                    result = self._sync_file(event.src_path, target_path)
                    results.append(result)
                else:
                    # 目录创建,确保目标也存在
                    rel_path = get_relative_path(event.src_path, self.source_path)
                    target_dir = os.path.join(target_path, rel_path)
                    os.makedirs(target_dir, exist_ok=True)
            
            elif event.event_type == FileEventType.MODIFIED:
                if not event.is_directory:
                    result = self._sync_file(event.src_path, target_path)
                    results.append(result)
            
            elif event.event_type == FileEventType.DELETED:
                result = self._sync_deletion(event.src_path, target_path)
                results.append(result)
            
            elif event.event_type == FileEventType.MOVED:
                # 处理移动
                if event.dst_path:
                    # 文件夹智能移动：直接使用 move，不删除重建
                    if event.is_directory:
                        result = self._sync_directory_move(event.src_path, event.dst_path, target_path)
                        results.append(result)
                    else:
                        # 文件移动：删除旧位置 + 复制到新位置 (暂保持旧逻辑以确保安全，或者可以优化为move)
                        # 为了性能，这里也可以改为 safe_move_file
                        result1 = self._sync_deletion(event.src_path, target_path)
                        results.append(result1)
                        result2 = self._sync_file(event.dst_path, target_path)
                        results.append(result2)
        
        # 更新统计
        with self._stats_lock:
            for result in results:
                self._stats.total_files += 1
                if result.action == "copy" or result.action == "move":
                    self._stats.copied_files += 1
                    self._stats.total_size += result.file_size
                elif result.action == "delete":
                    self._stats.deleted_files += 1
                elif result.action == "skip":
                    self._stats.skipped_files += 1
                elif result.action == "error":
                    self._stats.failed_files += 1
        
        return results
    
        return results
    
    def _sync_file_reverse_with_hash(self, target_file: str, target_base: str) -> SyncResult:
        """反向哈希同步"""
        try:
            rel_path = get_relative_path(target_file, target_base)
            source_file = os.path.join(self.source_path, rel_path)
            
            if not self._should_process_file(target_file):
                return SyncResult(True, "skip", target_file, source_file, "文件被过滤规则排除")

            tgt_hash = get_file_hash(target_file)
            last_state = self.state_manager.get_file_state(self.task_id, rel_path)
            last_hash = last_state.hash if last_state else None
            
            source_exists = os.path.exists(source_file)
            src_hash = get_file_hash(source_file) if source_exists else None
            
            tgt_changed = (tgt_hash != last_hash)
            src_changed = (not source_exists) or (src_hash != last_hash)
            
            # 如果源不存在，或者源没有变更，但目标变更了 -> 同步回去
            if tgt_changed and not src_changed:
                 success, error = safe_copy_file(target_file, source_file)
                 if success:
                     self._update_state(rel_path, tgt_hash, target_file)
                     return SyncResult(True, "copy", target_file, source_file, "反向同步：目标变更，更新源", get_file_size(target_file))
                 return SyncResult(False, "error", target_file, source_file, f"反向同步失败: {error}")
            
            # 其他情况（双方未变，源也变更，双方冲突等）在正向同步中已处理或无需处理
            return SyncResult(True, "skip", target_file, source_file, "跳过（已在正向同步处理或无变更）")
            
        except Exception as e:
            return SyncResult(False, "error", target_file, self.source_path, f"反向Hash同步异常: {e}")

    def _sync_file_reverse(self, target_file: str, target_base: str) -> SyncResult:
        """
        反向同步单个文件（目标 -> 源）
        
        Args:
            target_file: 目标文件路径
            target_base: 目标文件夹基础路径
        
        Returns:
            同步结果
        """
        if self.compare_method == "hash" and self.task_id:
            return self._sync_file_reverse_with_hash(target_file, target_base)

        try:
            rel_path = get_relative_path(target_file, target_base)
            source_file = os.path.join(self.source_path, rel_path)
            
            # 检查过滤规则
            if not self._should_process_file(target_file):
                return SyncResult(
                    success=True,
                    action="skip",
                    source_path=target_file,
                    target_path=source_file,
                    message="文件被过滤规则排除"
                )
            
            # 源文件不存在,直接复制
            if not os.path.exists(source_file):
                success, error = safe_copy_file(target_file, source_file)
                if success:
                    file_size = get_file_size(target_file)
                    return SyncResult(
                        success=True,
                        action="copy",
                        source_path=target_file,
                        target_path=source_file,
                        message="反向同步：文件已复制到源",
                        file_size=file_size
                    )
                else:
                    return SyncResult(
                        success=False,
                        action="error",
                        source_path=target_file,
                        target_path=source_file,
                        message=f"反向复制失败: {error}"
                    )
            
            # 检查冲突
            if self.conflict_handler.check_conflict(target_file, source_file):
                action, resolved_path, reason = self.conflict_handler.resolve(target_file, source_file)
                
                if action == "copy":
                    success, error = safe_copy_file(target_file, resolved_path or source_file)
                    if success:
                        file_size = get_file_size(target_file)
                        return SyncResult(
                            success=True,
                            action="copy",
                            source_path=target_file,
                            target_path=resolved_path or source_file,
                            message=f"反向同步：{reason}",
                            file_size=file_size
                        )
                    else:
                        return SyncResult(
                            success=False,
                            action="error",
                            source_path=target_file,
                            target_path=source_file,
                            message=f"反向复制失败: {error}"
                        )
                else:  # skip
                    return SyncResult(
                        success=True,
                        action="skip",
                        source_path=target_file,
                        target_path=source_file,
                        message=f"反向同步：{reason}"
                    )
            
            # 无冲突,文件相同,跳过
            return SyncResult(
                success=True,
                action="skip",
                source_path=target_file,
                target_path=source_file,
                message="文件已是最新"
            )
            
        except Exception as e:
            return SyncResult(
                success=False,
                action="error",
                source_path=target_file,
                target_path=self.source_path,
                message=f"反向同步异常: {str(e)}"
            )
    
    def _sync_deletion_reverse(self, deleted_path: str, target_base: str) -> SyncResult:
        """反向同步删除操作（目标删除 -> 源删除）"""
        try:
            rel_path = get_relative_path(deleted_path, target_base)
            source_file = os.path.join(self.source_path, rel_path)
            
            if os.path.exists(source_file):
                success, error = safe_delete_file(source_file)
                if success:
                    return SyncResult(
                        success=True,
                        action="delete",
                        source_path=deleted_path,
                        target_path=source_file,
                        message="反向同步：源文件已删除"
                    )
                else:
                    return SyncResult(
                        success=False,
                        action="error",
                        source_path=deleted_path,
                        target_path=source_file,
                        message=f"反向删除失败: {error}"
                    )
            
            return SyncResult(
                success=True,
                action="skip",
                source_path=deleted_path,
                target_path=source_file,
                message="源文件不存在"
            )
            
        except Exception as e:
            return SyncResult(
                success=False,
                action="error",
                source_path=deleted_path,
                target_path=self.source_path,
                message=f"反向删除异常: {str(e)}"
            )

    def process_reverse_event(self, event: FileEvent, target_base: str) -> List[SyncResult]:
        """
        处理反向文件事件（双向同步：目标 -> 源）
        
        Args:
            event: 文件事件
            target_base: 目标文件夹基础路径
        
        Returns:
            同步结果列表
        """
        # 只在双向同步模式下处理
        if self.sync_mode != SyncMode.TWO_WAY:
            return []
        
        results = []
        
        if event.event_type == FileEventType.CREATED:
            if not event.is_directory:
                result = self._sync_file_reverse(event.src_path, target_base)
                results.append(result)
            else:
                # 目录创建,确保源也存在
                rel_path = get_relative_path(event.src_path, target_base)
                source_dir = os.path.join(self.source_path, rel_path)
                os.makedirs(source_dir, exist_ok=True)
        
        elif event.event_type == FileEventType.MODIFIED:
            if not event.is_directory:
                result = self._sync_file_reverse(event.src_path, target_base)
                results.append(result)
        
        elif event.event_type == FileEventType.DELETED:
            result = self._sync_deletion_reverse(event.src_path, target_base)
            results.append(result)
        
        elif event.event_type == FileEventType.MOVED:
            # 处理移动
            if event.dst_path:
                if event.is_directory:
                    result = self._sync_directory_move_reverse(event.src_path, event.dst_path, target_base)
                    results.append(result)
                else:
                    result1 = self._sync_deletion_reverse(event.src_path, target_base)
                    results.append(result1)
                    if not event.is_directory:
                        result2 = self._sync_file_reverse(event.dst_path, target_base)
                        results.append(result2)
        
        # 更新统计
        with self._stats_lock:
            for result in results:
                self._stats.total_files += 1
                if result.action == "copy" or result.action == "move":
                    self._stats.copied_files += 1
                    self._stats.total_size += result.file_size
                elif result.action == "delete":
                    self._stats.deleted_files += 1
                elif result.action == "skip":
                    self._stats.skipped_files += 1
                elif result.action == "error":
                    self._stats.failed_files += 1
        
        return results

    def full_sync(self, delete_orphans: bool = False) -> List[SyncResult]:
        """
        执行全量同步
        
        Args:
            delete_orphans: 是否删除目标中多余的文件
        
        Returns:
            同步结果列表
        """
        self._is_running = True
        self._should_stop = False
        self._stats.reset()
        results = []
        
        try:
            # 扫描源文件夹
            source_files = scan_directory(self.source_path)
            total = len(source_files) * len(self.target_paths)
            current = 0
            
            logger.info(f"开始全量同步: {len(source_files)} 个文件 → {len(self.target_paths)} 个目标",
                       category="sync")
            
            for target_path in self.target_paths:
                if self._should_stop:
                    break
                
                # 使用线程池并行处理
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {}
                    for source_file in source_files:
                        if self._should_stop:
                            break
                        future = executor.submit(self._sync_file, source_file, target_path)
                        futures[future] = source_file
                    
                    for future in as_completed(futures):
                        if self._should_stop:
                            break
                        result = future.result()
                        results.append(result)
                        current += 1
                        self._update_progress(current, total, f"同步: {os.path.basename(result.source_path)}")
                        
                        # 记录日志
                        if result.action == "error":
                            logger.error(f"同步失败: {result.source_path} - {result.message}",
                                        category="sync")
                
                # 删除目标中多余的文件 (仅单向同步且配置了删除)
                if delete_orphans and self.sync_mode == SyncMode.ONE_WAY and not self._should_stop:
                    target_files = scan_directory(target_path)
                    source_rel_paths = set(get_relative_path(f, self.source_path) for f in source_files)
                    
                    for target_file in target_files:
                        rel_path = get_relative_path(target_file, target_path)
                        if rel_path not in source_rel_paths:
                            result = SyncResult(
                                success=True,
                                action="delete",
                                source_path="",
                                target_path=target_file,
                                message="删除多余文件"
                            )
                            success, error = safe_delete_file(target_file)
                            if not success:
                                result.success = False
                                result.action = "error"
                                result.message = f"删除失败: {error}"
                            results.append(result)
                            
                # 双向同步：反向同步 (目标 -> 源)
                if self.sync_mode == SyncMode.TWO_WAY and not self._should_stop:
                    logger.info(f"双向同步：开始反向扫描 {target_path}", category="sync")
                    target_files = scan_directory(target_path)
                    total_reverse = len(target_files)
                    current_reverse = 0
                    
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        futures = {}
                        for target_file in target_files:
                            if self._should_stop:
                                break
                            future = executor.submit(self._sync_file_reverse, target_file, target_path)
                            futures[future] = target_file
                        
                        for future in as_completed(futures):
                            if self._should_stop:
                                break
                            result = future.result()
                            if result.action != "skip": # 仅记录实际操作
                                results.append(result)
                            current_reverse += 1
                            self._update_progress(current_reverse, total_reverse, f"反向同步: {os.path.basename(result.source_path)}")
                            
                            if result.action == "error":
                                logger.error(f"反向同步失败: {result.source_path} - {result.message}", category="sync")

            # 更新统计
            with self._stats_lock:
                for result in results:
                    if result.action == "copy":
                        self._stats.copied_files += 1
                        self._stats.total_size += result.file_size
                    elif result.action == "delete":
                        self._stats.deleted_files += 1
                    elif result.action == "skip":
                        self._stats.skipped_files += 1
                    elif result.action == "error":
                        self._stats.failed_files += 1
                self._stats.total_files = len(results)
            
            logger.info(f"全量同步完成: 复制 {self._stats.copied_files}, "
                       f"删除 {self._stats.deleted_files}, "
                       f"跳过 {self._stats.skipped_files}, "
                       f"失败 {self._stats.failed_files}",
                       category="sync")
            
            # 如果是Hash模式，同步结束后保存状态
            if self.compare_method == "hash" and self.state_manager:
                self.state_manager.save_state()
            
        except Exception as e:
            logger.error(f"全量同步异常: {e}", category="sync")
        finally:
            self._is_running = False
        
        return results
    
    def stop(self):
        """停止同步"""
        self._should_stop = True
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def stats(self) -> SyncStats:
        return self._stats
    
    def get_stats_dict(self) -> dict:
        """获取统计信息字典"""
        with self._stats_lock:
            return {
                "total_files": self._stats.total_files,
                "copied_files": self._stats.copied_files,
                "deleted_files": self._stats.deleted_files,
                "skipped_files": self._stats.skipped_files,
                "failed_files": self._stats.failed_files,
                "total_size": format_file_size(self._stats.total_size)
            }
