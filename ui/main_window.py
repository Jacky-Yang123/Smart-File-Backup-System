"""
主窗口模块 - 优化版
"""
import os
from typing import Optional
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame,
    QScrollArea, QMessageBox, QStatusBar, QSizePolicy,
    QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from datetime import datetime


from utils.constants import APP_NAME, APP_VERSION, TaskStatus
from utils.config_manager import config_manager
from utils.logger import logger
from core.task_manager import task_manager, BackupTask
from core.backup_engine import backup_engine
from core.file_monitor import FileEvent

from .styles import GLOBAL_STYLE, SIDEBAR_STYLE, TASK_CARD_STYLE, STATUSBAR_STYLE, COLORS
from .task_dialog import TaskDialog
from .monitor_panel import MonitorPanel
from .log_viewer import LogViewer
from .settings_panel import SettingsPanel
from .system_tray import SystemTray
from .file_change_viewer import FileChangeViewer
from .crash_log_viewer import CrashLogViewer
from .alert_panel import AlertPanel
from .queue_status_panel import QueueStatusPanel


class TaskCard(QFrame):
    """任务卡片 - 优化版"""
    
    edit_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    start_clicked = pyqtSignal(str)
    stop_clicked = pyqtSignal(str)
    sync_clicked = pyqtSignal(str)
    
    def __init__(self, task: BackupTask, parent=None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("task_card")
        self.setStyleSheet(TASK_CARD_STYLE)
        self.setFixedHeight(70)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self._init_ui()
        self._update_status()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 10, 12, 10)
        
        # 左侧：任务信息
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # 任务名称行
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        
        self.name_label = QLabel(self.task.name)
        self.name_label.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLORS['text_primary']};")
        name_row.addWidget(self.name_label)
        
        # 同步模式标签
        mode_text = "单向" if self.task.sync_mode == "one_way" else "双向"
        mode_label = QLabel(f"[{mode_text}]")
        mode_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        name_row.addWidget(mode_label)
        
        name_row.addStretch()
        info_layout.addLayout(name_row)
        
        # 路径行
        source_name = os.path.basename(self.task.source_path) or self.task.source_path
        if len(source_name) > 35:
            source_name = source_name[:32] + "..."
        target_count = len(self.task.target_paths)
        path_text = f"{source_name} → {target_count} 个目标"
        
        self.path_label = QLabel(path_text)
        self.path_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        self.path_label.setToolTip(f"源: {self.task.source_path}\n目标:\n" + "\n".join(self.task.target_paths))
        info_layout.addWidget(self.path_label)
        
        layout.addLayout(info_layout, 1)
        
        # 状态标签
        self.status_label = QLabel("停止")
        self.status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        self.status_label.setFixedWidth(55)
        layout.addWidget(self.status_label)
        
        # 操作按钮
        self.start_btn = QPushButton("▶")
        self.start_btn.setProperty("class", "icon")
        self.start_btn.setToolTip("启动")
        self.start_btn.setFixedSize(28, 28)
        self.start_btn.clicked.connect(lambda: self.start_clicked.emit(self.task.id))
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("■")
        self.stop_btn.setProperty("class", "icon")
        self.stop_btn.setToolTip("停止")
        self.stop_btn.setFixedSize(28, 28)
        self.stop_btn.clicked.connect(lambda: self.stop_clicked.emit(self.task.id))
        self.stop_btn.hide()
        layout.addWidget(self.stop_btn)
        
        sync_btn = QPushButton("↻")
        sync_btn.setProperty("class", "icon")
        sync_btn.setToolTip("全量同步")
        sync_btn.setFixedSize(28, 28)
        sync_btn.clicked.connect(lambda: self.sync_clicked.emit(self.task.id))
        layout.addWidget(sync_btn)
        
        edit_btn = QPushButton("✎")
        edit_btn.setProperty("class", "icon")
        edit_btn.setToolTip("编辑")
        edit_btn.setFixedSize(28, 28)
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.task.id))
        layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("×")
        delete_btn.setProperty("class", "icon")
        delete_btn.setToolTip("删除")
        delete_btn.setFixedSize(28, 28)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.task.id))
        layout.addWidget(delete_btn)
    
    def _update_status(self):
        """更新状态显示"""
        status = task_manager.get_task_status(self.task.id)
        
        status_config = {
            TaskStatus.RUNNING: ("● 运行中", COLORS["success"], True),
            TaskStatus.PAUSED: ("● 暂停", COLORS["warning"], True),
            TaskStatus.STOPPED: ("○ 停止", COLORS["text_muted"], False),
            TaskStatus.ERROR: ("● 错误", COLORS["error"], False),
        }
        
        text, color, is_running = status_config.get(status, ("○ 停止", COLORS["text_muted"], False))
        
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        
        self.start_btn.setVisible(not is_running)
        self.stop_btn.setVisible(is_running)
    
    def update_task(self, task: BackupTask):
        self.task = task
        self.name_label.setText(task.name)
        self._update_status()
    
    def refresh_status(self):
        self._update_status()


class MainWindow(QMainWindow):
    """主窗口 - 优化版"""
    
    # 线程安全的文件事件信号
    file_event_signal = pyqtSignal(str, object, dict)
    log_entry_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        # 跟踪活跃的任务提醒 task_id -> alert_id
        self._active_task_alerts = {}
        
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(850, 500)
        self.resize(900, 550)
        
        self.setStyleSheet(GLOBAL_STYLE)
        self._task_cards = {}
        
        self._init_ui()
        self._init_tray()
        self._setup_callbacks()
        self._start_update_timer()
        
        # 连接信号到处理槽 (确保主线程执行)
        self.file_event_signal.connect(self._process_file_event)
        self.log_entry_signal.connect(self._process_log_entry)
        
        backup_engine.start()
        logger.info("程序启动完成", category="system")
    
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 2. 侧边栏
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # 分隔线
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setStyleSheet(f"background-color: {COLORS['border']};")
        main_layout.addWidget(separator)
        
        # 3. 内容堆栈 (QStackedWidget)
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)
        
        # --- 按顺序初始化并记录组件 ---
        # 0: 任务主页
        self.task_page = self._create_task_page()
        self.content_stack.addWidget(self.task_page)
        
        # 1: 监控面板
        self.monitor_panel = MonitorPanel()
        self.content_stack.addWidget(self.monitor_panel)
        
        # 2: 日志查看器
        self.log_viewer = LogViewer()
        self.content_stack.addWidget(self.log_viewer)
        
        # 3: 文件变更查看
        self.file_change_viewer = FileChangeViewer()
        self.content_stack.addWidget(self.file_change_viewer)
        
        # 4: 警告面板
        self.alert_panel = AlertPanel()
        self.content_stack.addWidget(self.alert_panel)
        
        # 5: 队列状态
        self.queue_status_panel = QueueStatusPanel()
        self.content_stack.addWidget(self.queue_status_panel)
        
        # 6: 设置面板
        self.settings_panel = SettingsPanel()
        self.content_stack.addWidget(self.settings_panel)
        
        self._create_status_bar()
    
    def _create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(140)
        sidebar.setStyleSheet(f"background-color: {COLORS['bg_medium']};")
        
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(2)
        layout.setContentsMargins(8, 12, 8, 12)
        
        # 标题
        title = QLabel("智能备份")
        title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px; font-weight: bold; padding: 6px 8px;")
        layout.addWidget(title)
        
        layout.addSpacing(10)
        
        # 导航按钮
        self.nav_buttons = []
        nav_items = [
            ("📋 任务", 0), 
            ("📊 监控", 1), 
            ("📝 日志", 2), 
            ("📁 变更", 3), 
            ("⚠️ 提醒", 4), 
            ("⚡ 队列", 5), 
            ("⚙️ 设置", 6)
        ]
        
        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("nav_button")
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton#nav_button {{
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 10px;
                    text-align: left;
                    font-size: 12px;
                    color: {COLORS['text_muted']};
                }}
                QPushButton#nav_button:hover {{
                    background-color: {COLORS['bg_hover']};
                    color: {COLORS['text_secondary']};
                }}
                QPushButton#nav_button:checked {{
                    background-color: {COLORS['bg_light']};
                    color: {COLORS['text_primary']};
                }}
            """)
            btn.clicked.connect(lambda checked, i=index: self._switch_page(i))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        self.nav_buttons[0].setChecked(True)
        
        layout.addStretch()
        
        # 最小化按钮
        min_btn = QPushButton("📥 收到托盘")
        min_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 11px;
                color: {COLORS['text_muted']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
                color: {COLORS['text_secondary']};
            }}
        """)
        min_btn.clicked.connect(self._minimize_to_tray)
        layout.addWidget(min_btn)
        
        return sidebar
    
    def _create_task_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # 头部
        header = QHBoxLayout()
        header.setSpacing(8)
        
        title = QLabel("备份任务")
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['text_primary']};")
        header.addWidget(title)
        
        header.addStretch()
        
        new_btn = QPushButton("+ 新建任务")
        new_btn.setFixedHeight(28)
        new_btn.clicked.connect(self._on_new_task)
        header.addWidget(new_btn)
        
        start_all_btn = QPushButton("▶ 全部启动")
        start_all_btn.setProperty("class", "success")
        start_all_btn.setFixedHeight(28)
        start_all_btn.clicked.connect(self._on_start_all)
        header.addWidget(start_all_btn)
        
        stop_all_btn = QPushButton("■ 全部停止")
        stop_all_btn.setProperty("class", "secondary")
        stop_all_btn.setFixedHeight(28)
        stop_all_btn.clicked.connect(self._on_stop_all)
        header.addWidget(stop_all_btn)
        
        layout.addLayout(header)
        
        # 任务列表
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setSpacing(6)
        self.task_layout.setContentsMargins(0, 0, 6, 0)
        self.task_layout.addStretch()
        
        scroll.setWidget(self.task_container)
        layout.addWidget(scroll, 1)
        
        self._load_tasks()
        return page
    
    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(STATUSBAR_STYLE)
        self.status_bar.setFixedHeight(24)
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(QLabel("|"))
        
        self.task_count_label = QLabel("任务: 0")
        self.status_bar.addPermanentWidget(self.task_count_label)
        self.status_bar.addPermanentWidget(QLabel("|"))
        
        self.running_count_label = QLabel("运行: 0")
        self.status_bar.addPermanentWidget(self.running_count_label)
    
    def _init_tray(self):
        self.tray = SystemTray(self)
        self.tray.show_requested.connect(self._show_from_tray)
        self.tray.quit_requested.connect(self._quit_app)
        self.tray.show()
    
    def _setup_callbacks(self):
        logger.add_callback(self._on_log_entry)
        task_manager.set_status_callback(self._on_task_status_changed)
        task_manager.set_event_callback(self._on_file_event)
    
    def _start_update_timer(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_status)
        self.update_timer.start(2000)
    
    def _show_settings(self):
        """切换到设置页面"""
        self.content_stack.setCurrentWidget(self.settings_panel)
        self.status_label.setText("系统设置")
        
    def _switch_page(self, index: int):
        """主导航切换逻辑"""
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
            
        if index == 6:
            self._show_settings()
        elif 0 <= index < self.content_stack.count():
            self.content_stack.setCurrentIndex(index)
    
    def _minimize_to_tray(self):
        self.hide()
        self.tray.show_notification(APP_NAME, "已最小化到托盘", "info")
    
    def _load_tasks(self):
        for card in self._task_cards.values():
            card.deleteLater()
        self._task_cards.clear()
        
        for task in task_manager.get_all_tasks():
            self._add_task_card(task)
    
    def _add_task_card(self, task: BackupTask):
        card = TaskCard(task)
        card.edit_clicked.connect(self._on_edit_task)
        card.delete_clicked.connect(self._on_delete_task)
        card.start_clicked.connect(self._on_start_task)
        card.stop_clicked.connect(self._on_stop_task)
        card.sync_clicked.connect(self._on_sync_task)
        
        self.task_layout.insertWidget(self.task_layout.count() - 1, card)
        self._task_cards[task.id] = card
    
    def _on_new_task(self):
        dialog = TaskDialog(self)
        if dialog.exec_() == TaskDialog.Accepted:
            task = dialog.get_task()
            if task:
                created_task = task_manager.create_task(
                    name=task.name,
                    source_path=task.source_path,
                    target_paths=task.target_paths,
                    include_patterns=task.include_patterns,
                    exclude_patterns=task.exclude_patterns,
                    enabled=task.enabled,
                    auto_start=task.auto_start,
                    delete_orphans=task.delete_orphans
                )
                if created_task:
                    self._add_task_card(created_task)
                    self._update_status()
                    logger.info(f"创建任务: {task.name}", category="task")
    
    def _on_edit_task(self, task_id: str):
        task = task_manager.get_task(task_id)
        if not task:
            return
        dialog = TaskDialog(self, task)
        if dialog.exec_() == TaskDialog.Accepted:
            updated_task = dialog.get_task()
            if updated_task:
                task_manager.update_task(task_id, **updated_task.to_dict())
                if task_id in self._task_cards:
                    self._task_cards[task_id].update_task(updated_task)
    
    def _on_delete_task(self, task_id: str):
        task = task_manager.get_task(task_id)
        if not task:
            return
        reply = QMessageBox.question(self, "确认", f"删除任务 \"{task.name}\"？",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            task_manager.delete_task(task_id)
            if task_id in self._task_cards:
                self._task_cards[task_id].deleteLater()
                del self._task_cards[task_id]
            self._update_status()
            logger.info(f"删除任务: {task.name}", category="task")
    
    def _on_start_task(self, task_id: str):
        task_manager.start_task(task_id)
        if task_id in self._task_cards:
            self._task_cards[task_id].refresh_status()
        self._update_status()
        task = task_manager.get_task(task_id)
        if task:
            logger.info(f"启动任务: {task.name}", category="task")
    
    def _on_stop_task(self, task_id: str):
        task_manager.stop_task(task_id)
        if task_id in self._task_cards:
            self._task_cards[task_id].refresh_status()
        self._update_status()
    
    def _on_sync_task(self, task_id: str):
        task = task_manager.get_task(task_id)
        if not task:
            return
        
        # 先进行安全检查
        runner = task_manager._runners.get(task_id)
        if runner:
            safety = runner.check_sync_safety()
            if not safety["safe"]:
                # 使用新的提醒面板
                def run_sync_callback():
                    import threading
                    def run_sync():
                        task_manager.run_full_sync(task_id, skip_safety_check=True)
                        self.tray.show_notification("同步完成", f"{task.name}", "info")
                    threading.Thread(target=run_sync, daemon=True).start()
                    self.tray.show_notification("开始同步", f"{task.name}...", "info")
                
                self._add_safety_alert(task, safety, run_sync_callback)
                return
        
        reply = QMessageBox.question(self, "确认", f"对任务 \"{task.name}\" 执行全量同步？",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            import threading
            def run_sync():
                task_manager.run_full_sync(task_id)
                self.tray.show_notification("同步完成", f"{task.name}", "info")
            threading.Thread(target=run_sync, daemon=True).start()
            self.tray.show_notification("开始同步", f"{task.name}...", "info")

    
    def _add_safety_alert(self, task: BackupTask, safety_info: dict, callback: callable):
        """添加或更新安全提醒"""
        task_id = task.id
        message = safety_info["message"]
        batch_data = safety_info.get("batch_data")
        
        # 检查是否已有活跃提醒
        if task_id in self._active_task_alerts:
            alert_id = self._active_task_alerts[task_id]
            self.alert_panel.update_alert(alert_id, message, batch_data)
            # 可选：更新通知
            # self.tray.show_notification("安全警告更新", f"任务 {task.name} 累积更多变更", "warning")
        else:
            alert_id = self.alert_panel.add_alert(
                title="安全警告",
                task_name=task.name,
                message=message,
                callback=callback,
                batch_data=batch_data
            )
            self._active_task_alerts[task_id] = alert_id
            
            # 切换到提醒页
            self._switch_page(4)
            
            # 显示通知
            self.tray.show_notification("安全警告", f"任务 {task.name} 需要确认", "warning")
    
    def _on_start_all(self):
        task_manager.start_all(force=True)
        for card in self._task_cards.values():
            card.refresh_status()
        self._update_status()
        logger.info("启动所有任务", category="task")
    
    def _on_stop_all(self):
        task_manager.stop_all()
        for card in self._task_cards.values():
            card.refresh_status()
        self._update_status()
        logger.info("停止所有任务", category="task")
    
    def _show_log_entry(self, entry: dict):
        # 这是一个占位，防止冲突
        pass
    
    def _on_log_entry(self, entry: dict):
        """日志回调 - 可能从后台线程调用"""
        self.log_entry_signal.emit(entry)
        
    def _process_log_entry(self, entry: dict):
        """在主线程处理日志"""
        self.log_viewer.add_log(entry)
        if entry.get("level") == "ERROR":
            self.tray.notify_error(entry.get("message", ""), entry.get("task_id"))
    
    def _on_task_status_changed(self, task_id: str, status: TaskStatus):
        if task_id in self._task_cards:
            self._task_cards[task_id].refresh_status()
        self._update_status()
    
    def _on_file_event(self, task_id: str, event: FileEvent, result: dict):
        """文件事件回调 - 每次文件变更都会调用（可能从后台线程调用）"""
        # 使用信号确保在主线程执行UI更新
        self.file_event_signal.emit(task_id, event, result)
    
    def _process_file_event(self, task_id: str, event: FileEvent, result: dict):
        """处理文件事件（在主线程执行）- 不做任何阻塞操作"""
        try:
            task = task_manager.get_task(task_id)
            if not task:
                return
            task_name = task.name
            
            # 处理安全警报
            if result.get("action") == "safety_alert":
                accumulated = result.get("accumulated_count", 0)
                batch_data = result.get("batch_data", [])
                is_initial_sync = result.get("is_initial_sync", False)
                
                # 构造符合 _add_safety_alert 期望的 safety_info
                # 注意: is_initial_sync 必须存储在 safety_info 中，以便回调时正确获取
                safety_info = {
                    "message": result.get("message", "检测到大量变更"),
                    "warning_type": result.get("alert_type", "massive_change"),
                    "task_id": task_id,
                    "batch_data": batch_data,
                    "is_initial_sync": is_initial_sync  # 存入 safety_info 供回调使用
                }
                
                # 使用工厂函数创建回调，正确捕获当前值
                def make_callback(tid, tname, tsk, is_init):
                    def confirm_batch_callback(filtered_data=None):
                        logger.info(f"执行回调: task_id={tid}, is_initial_sync={is_init}", category="sync")
                        if is_init:
                            # 初始同步：执行全量同步而不是批量操作
                            delete_rule = getattr(tsk, 'initial_sync_delete', False)
                            logger.info(f"执行初始全量同步 (删除策略={delete_rule})", task_id=tid, category="sync")
                            
                            # 在新线程执行以避免阻塞UI
                            import threading
                            def do_sync():
                                task_manager.run_full_sync(tid, delete_orphans_override=delete_rule)
                            threading.Thread(target=do_sync, daemon=True).start()
                            
                            msg = f"{tname}: 初始全量同步已确认执行"
                        elif filtered_data is not None and len(filtered_data) > 0:
                            # 执行选中的操作
                            task_manager.execute_batch(tid, filtered_data)
                            task_manager.reset_safety_pause(tid)
                            count = len(filtered_data)
                            msg = f"{tname}: 执行了 {count} 个选中的操作"
                        elif filtered_data is not None and len(filtered_data) == 0:
                            # 用户没有选择任何项目
                            task_manager.reset_safety_pause(tid)
                            msg = f"{tname}: 未选择任何操作"
                        else:
                            # 旧逻辑兼容
                            task_manager.confirm_safety_alert(tid)
                            msg = f"{tname}: 安全处理确认"
                            
                        # 清除活跃提醒记录
                        if tid in self._active_task_alerts:
                            del self._active_task_alerts[tid]
                        self.tray.show_notification("执行批量更改", msg, "info")
                    return confirm_batch_callback
                
                callback = make_callback(task_id, task_name, task, is_initial_sync)
                self._add_safety_alert(task, safety_info, callback)
                return
            
            # 处理进度更新事件
            if result.get("action") == "progress":
                current = result.get("progress_current", 0)
                total = result.get("progress_total", 0)
                remaining = result.get("progress_remaining", 0)
                self.monitor_panel.update_progress(current, total, remaining)
                return
            
            task_name = task.name if task else "未知"
            
            # 检查是否是目录操作或批量文件夹操作
            is_directory = event.is_directory
            is_folder_batch = result.get("is_folder_batch", False)
            
            # 直接使用result中传递的file_count，不在主线程计算
            file_count = result.get("file_count", 0)
            
            # 事件类型中文名
            event_names = {
                "created": "创建",
                "modified": "修改", 
                "deleted": "删除",
                "moved": "移动"
            }
            event_name = event_names.get(event.event_type.value, event.event_type.value)
            filename = os.path.basename(event.src_path)
            
            # 添加到监控面板 - 包含任务名
            self.monitor_panel.add_activity(
                event.event_type.value,
                event.src_path,
                "success" if result.get("success") else "failed",
                target_path=result.get("target_path"),
                task_name=task_name,
                is_directory=is_directory,
                file_count=file_count
            )
            
            # 添加到文件变更查看器
            self.file_change_viewer.add_change(
                event_type=event.event_type.value,
                source_path=event.src_path,
                target_path=result.get("target_path", ""),
                task_name=task_name,
                is_directory=is_directory,
                file_count=file_count,
                success=result.get("success", True),
                message=result.get("message", "")
            )
            
            # 记录日志（只记录一次）
            if is_directory:
                log_msg = f"[{task_name}] 文件夹{event_name}: {filename}"
                if file_count > 0:
                    log_msg += f" (包含 {file_count} 个文件)"
            else:
                log_msg = f"[{task_name}] 文件{event_name}: {filename}"
                
            if result.get("success"):
                logger.info(log_msg, category="sync", task_id=task_id)
            else:
                logger.warning(f"{log_msg} (失败: {result.get('message', '')})", category="sync", task_id=task_id)
            
            # 大量文件操作完成时显示右下角通知（阈值：10个文件）
            LARGE_OPERATION_THRESHOLD = 10
            if is_directory and file_count >= LARGE_OPERATION_THRESHOLD:
                status_text = "完成" if result.get("success") else "部分失败"
                self.tray.show_notification(
                    f"文件夹{event_name}{status_text}",
                    f"[{task_name}] {filename}\n包含 {file_count} 个文件",
                    "info" if result.get("success") else "warning"
                )
            
            # 删除事件通知（仅非批量操作）
            if event.event_type.value == "deleted" and not is_folder_batch:
                if not is_directory:  # 只有单个文件删除才通知
                    self.tray.notify_file_deleted(filename, task_name)
            
            # 冲突事件通知
            if "冲突" in result.get("message", "") or "conflict" in result.get("message", "").lower():
                self.tray.notify_conflict(filename, task_name, result.get("message", ""))
                
        except Exception as e:
            # 记录崩溃日志
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"处理文件事件时崩溃: {e}\n{error_detail}", category="crash")
    
    def _update_status(self):
        stats = task_manager.get_overall_stats()
        self.task_count_label.setText(f"任务: {stats['total_tasks']}")
        self.running_count_label.setText(f"运行: {stats['running']}")
        
        # 优先显示同步状态
        if stats.get('is_syncing', False):
            self.status_label.setText("● 正在备份中...")
            self.status_label.setStyleSheet(f"color: #f59e0b; font-weight: bold;")  # 橙色
            self.tray.set_icon_status("syncing")
        elif stats['running'] > 0:
            # 计算上次备份时间
            last_run_str = stats.get('last_run_time', "")
            status_text = "● 监控中"
            
            if last_run_str:
                try:
                    last_run = datetime.fromisoformat(last_run_str)
                    delta = datetime.now() - last_run
                    seconds = int(delta.total_seconds())
                    
                    if seconds < 60:
                        time_str = f"{seconds}秒前"
                    elif seconds < 3600:
                        time_str = f"{seconds // 60}分钟前"
                    elif seconds < 86400:
                        time_str = f"{seconds // 3600}小时前"
                    else:
                        time_str = f"{seconds // 86400}天前"
                        
                    status_text = f"✓ 备份完成，上次 {time_str}"
                except Exception:
                    pass
            
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet(f"color: #22c55e;")  # 绿色
            self.tray.set_icon_status("running")
        else:
            self.status_label.setText("○ 就绪")
            self.status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
            self.tray.set_icon_status("idle")
            
        self.tray.update_status(stats['running'])
    
    def _show_from_tray(self):
        self.show()
        self.activateWindow()
        self.raise_()
    
    def _quit_app(self):
        backup_engine.stop()
        self.tray.hide()
        logger.info("程序退出", category="system")
        QApplication.quit()
    
    def closeEvent(self, event):
        if config_manager.get("general.minimize_to_tray", True):
            event.ignore()
            self.hide()
            self.tray.show_notification(APP_NAME, "已最小化到托盘，双击图标可恢复", "info")
        else:
            reply = QMessageBox.question(self, "确认", "退出程序？",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._quit_app()
            else:
                event.ignore()
