"""
文件监控模块 - 基于watchdog
"""
import os
import time
import threading
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass
from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent
)

from utils.constants import FileEventType
from utils.logger import logger


@dataclass
class FileEvent:
    """文件事件数据类"""
    event_type: FileEventType
    src_path: str
    dst_path: Optional[str] = None
    is_directory: bool = False
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class DebouncedEventHandler(FileSystemEventHandler):
    """
    防抖文件事件处理器
    避免短时间内同一文件多次触发
    """
    
    def __init__(self, callback: Callable[[FileEvent], None], 
                 debounce_seconds: float = 1.0,
                 ignore_hidden: bool = True,
                 include_patterns: List[str] = None,
                 exclude_patterns: List[str] = None):
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.ignore_hidden = ignore_hidden
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        
        self._pending_events: Dict[str, FileEvent] = {}
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._processed_paths: Set[str] = set()
    
    def _should_ignore(self, path: str) -> bool:
        """检查是否应该忽略该路径"""
        from utils.file_utils import is_hidden_file, match_file_patterns
        
        # 忽略隐藏文件
        if self.ignore_hidden and is_hidden_file(path):
            return True
        
        # 检查文件过滤
        if not match_file_patterns(path, self.include_patterns, self.exclude_patterns):
            return True
        
        return False
    
    def _schedule_callback(self):
        """调度防抖回调"""
        if self._timer is not None:
            self._timer.cancel()
        
        self._timer = threading.Timer(self.debounce_seconds, self._process_events)
        self._timer.start()
    
    def _process_events(self):
        """处理待处理的事件"""
        with self._lock:
            events = list(self._pending_events.values())
            self._pending_events.clear()
        
        for event in events:
            try:
                self.callback(event)
            except Exception as e:
                logger.error(f"处理文件事件失败: {e}", category="monitor")
    
    def _add_event(self, event: FileEvent):
        """添加事件到待处理队列"""
        if self._should_ignore(event.src_path):
            return
        
        with self._lock:
            # 使用源路径作为键,后续事件会覆盖之前的
            key = event.src_path
            self._pending_events[key] = event
        
        self._schedule_callback()
    
    def on_created(self, event):
        if not event.is_directory:
            self._add_event(FileEvent(
                event_type=FileEventType.CREATED,
                src_path=event.src_path,
                is_directory=False
            ))
        else:
            self._add_event(FileEvent(
                event_type=FileEventType.CREATED,
                src_path=event.src_path,
                is_directory=True
            ))
    
    def on_modified(self, event):
        if not event.is_directory:
            self._add_event(FileEvent(
                event_type=FileEventType.MODIFIED,
                src_path=event.src_path,
                is_directory=False
            ))
    
    def on_deleted(self, event):
        self._add_event(FileEvent(
            event_type=FileEventType.DELETED,
            src_path=event.src_path,
            is_directory=event.is_directory
        ))
    
    def on_moved(self, event):
        self._add_event(FileEvent(
            event_type=FileEventType.MOVED,
            src_path=event.src_path,
            dst_path=event.dest_path,
            is_directory=event.is_directory
        ))
    
    def stop(self):
        """停止处理器"""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


class FileMonitor:
    """
    文件监控器
    监控文件夹变化并触发回调
    """
    
    def __init__(self, path: str, callback: Callable[[FileEvent], None],
                 recursive: bool = True,
                 debounce_seconds: float = 1.0,
                 ignore_hidden: bool = True,
                 include_patterns: List[str] = None,
                 exclude_patterns: List[str] = None):
        """
        初始化文件监控器
        
        Args:
            path: 监控路径
            callback: 事件回调函数
            recursive: 是否递归监控子目录
            debounce_seconds: 防抖时间(秒)
            ignore_hidden: 是否忽略隐藏文件
            include_patterns: 包含文件模式
            exclude_patterns: 排除文件模式
        """
        self.path = os.path.abspath(path)
        self.callback = callback
        self.recursive = recursive
        
        self._observer: Optional[Observer] = None
        self._event_handler = DebouncedEventHandler(
            callback=callback,
            debounce_seconds=debounce_seconds,
            ignore_hidden=ignore_hidden,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns
        )
        self._running = False
    
    def start(self) -> bool:
        """启动监控"""
        if self._running:
            return True
        
        if not os.path.exists(self.path):
            logger.error(f"监控路径不存在: {self.path}", category="monitor")
            return False
        
        try:
            self._observer = Observer()
            self._observer.schedule(
                self._event_handler,
                self.path,
                recursive=self.recursive
            )
            self._observer.start()
            self._running = True
            logger.info(f"开始监控: {self.path}", category="monitor")
            return True
        except Exception as e:
            logger.error(f"启动监控失败: {e}", category="monitor")
            return False
    
    def stop(self):
        """停止监控"""
        if not self._running:
            return
        
        try:
            self._event_handler.stop()
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None
            self._running = False
            logger.info(f"停止监控: {self.path}", category="monitor")
        except Exception as e:
            logger.error(f"停止监控失败: {e}", category="monitor")
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
    
    def update_filters(self, include_patterns: List[str] = None,
                       exclude_patterns: List[str] = None):
        """更新过滤规则"""
        if include_patterns is not None:
            self._event_handler.include_patterns = include_patterns
        if exclude_patterns is not None:
            self._event_handler.exclude_patterns = exclude_patterns


class MultiPathMonitor:
    """
    多路径监控器
    同时监控多个路径
    """
    
    def __init__(self):
        self._monitors: Dict[str, FileMonitor] = {}
    
    def add_path(self, path: str, callback: Callable[[FileEvent], None],
                 **kwargs) -> bool:
        """添加监控路径"""
        path = os.path.abspath(path)
        if path in self._monitors:
            return True
        
        monitor = FileMonitor(path, callback, **kwargs)
        if monitor.start():
            self._monitors[path] = monitor
            return True
        return False
    
    def remove_path(self, path: str):
        """移除监控路径"""
        path = os.path.abspath(path)
        if path in self._monitors:
            self._monitors[path].stop()
            del self._monitors[path]
    
    def stop_all(self):
        """停止所有监控"""
        for monitor in self._monitors.values():
            monitor.stop()
        self._monitors.clear()
    
    def get_active_paths(self) -> List[str]:
        """获取所有活动监控路径"""
        return list(self._monitors.keys())


class PollingMonitor:
    """
    轮询监控器
    定期扫描文件夹变化（替代实时监控）
    """
    
    def __init__(self, path: str, callback: Callable[[FileEvent], None],
                 interval: int = 5,
                 recursive: bool = True,
                 include_patterns: List[str] = None,
                 exclude_patterns: List[str] = None):
        """
        初始化轮询监控器
        
        Args:
            path: 监控路径
            callback: 事件回调函数
            interval: 轮询间隔（秒）
            recursive: 是否递归监控子目录
            include_patterns: 包含文件模式
            exclude_patterns: 排除文件模式
        """
        self.path = os.path.abspath(path)
        self.callback = callback
        self.interval = interval
        self.recursive = recursive
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._file_states: Dict[str, float] = {}  # path -> mtime
    
    def _scan_files(self) -> Dict[str, float]:
        """扫描目录获取文件状态"""
        from utils.file_utils import scan_directory, match_file_patterns
        
        file_states = {}
        try:
            files = scan_directory(self.path)
            for file_path in files:
                if match_file_patterns(file_path, self.include_patterns, self.exclude_patterns):
                    try:
                        file_states[file_path] = os.path.getmtime(file_path)
                    except OSError:
                        pass
        except Exception as e:
            logger.error(f"轮询扫描失败: {e}", category="monitor")
        return file_states
    
    def _poll_loop(self):
        """轮询循环"""
        while self._running:
            try:
                current_states = self._scan_files()
                
                # 检测新增和修改的文件
                for path, mtime in current_states.items():
                    if path not in self._file_states:
                        # 新文件
                        self.callback(FileEvent(
                            event_type=FileEventType.CREATED,
                            src_path=path,
                            is_directory=False
                        ))
                    elif self._file_states[path] != mtime:
                        # 修改的文件
                        self.callback(FileEvent(
                            event_type=FileEventType.MODIFIED,
                            src_path=path,
                            is_directory=False
                        ))
                
                # 检测删除的文件
                for path in self._file_states:
                    if path not in current_states:
                        self.callback(FileEvent(
                            event_type=FileEventType.DELETED,
                            src_path=path,
                            is_directory=False
                        ))
                
                self._file_states = current_states
                
            except Exception as e:
                logger.error(f"轮询处理失败: {e}", category="monitor")
            
            # 等待下一次轮询
            time.sleep(self.interval)
    
    def start(self) -> bool:
        """启动轮询"""
        if self._running:
            return True
        
        if not os.path.exists(self.path):
            logger.error(f"轮询路径不存在: {self.path}", category="monitor")
            return False
        
        # 初始化文件状态
        self._file_states = self._scan_files()
        
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"开始轮询监控: {self.path} (间隔 {self.interval}s)", category="monitor")
        return True
    
    def stop(self):
        """停止轮询"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None
        logger.info(f"停止轮询监控: {self.path}", category="monitor")
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
