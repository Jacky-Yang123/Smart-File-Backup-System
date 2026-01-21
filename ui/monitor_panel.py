"""
实时监控面板模块 - 优化版
"""
import os
from datetime import datetime
from typing import Dict, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QTextEdit, QSplitter
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from utils.constants import TaskStatus
from core.task_manager import task_manager
from .styles import COLORS


class StatCard(QFrame):
    """统计卡片"""
    
    def __init__(self, title: str, value: str = "0", color: str = None, parent=None):
        super().__init__(parent)
        self._color = color or COLORS["text_primary"]
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["bg_card"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(14, 12, 14, 12)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(title_label)
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {self._color}; font-size: 22px; font-weight: bold;")
        layout.addWidget(self.value_label)
    
    def set_value(self, value: str, color: str = None):
        self.value_label.setText(value)
        if color:
            self.value_label.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: bold;")


class MonitorPanel(QWidget):
    """监控面板 - 优化版"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._activities = []
        self._file_log_entries = []
        self._max_activities = 100
        self._max_file_log_entries = 500
        
        self._init_ui()
        self._start_update_timer()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 14, 16, 14)
        
        # 标题
        header = QHBoxLayout()
        title = QLabel("📊 实时监控")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLORS['text_primary']};")
        header.addWidget(title)
        header.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.setFixedHeight(28)
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn)
        
        clear_btn = QPushButton("🗑️ 清空活动")
        clear_btn.setProperty("class", "secondary")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self.clear_activities)
        header.addWidget(clear_btn)
        
        layout.addLayout(header)
        
        # 统计卡片
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(12)
        
        self.running_card = StatCard("运行中任务", "0", COLORS["success"])
        stats_layout.addWidget(self.running_card)
        
        self.synced_card = StatCard("已同步文件", "0", COLORS["info"])
        stats_layout.addWidget(self.synced_card)
        
        self.error_card = StatCard("错误数量", "0", COLORS["error"])
        stats_layout.addWidget(self.error_card)
        
        layout.addLayout(stats_layout)
        
        # 任务状态表
        status_label = QLabel("任务状态")
        status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; margin-top: 6px;")
        layout.addWidget(status_label)
        
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(4)
        self.status_table.setHorizontalHeaderLabels(["任务名称", "状态", "已同步", "失败"])
        self.status_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.status_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.status_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.status_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.status_table.setMaximumHeight(140)
        self.status_table.verticalHeader().setVisible(False)
        self.status_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.status_table)
        
        # 使用 Splitter 分割两个日志区域
        splitter = QSplitter(Qt.Vertical)
        
        # ===== 文件修改日志区域（专用文本框）=====
        file_log_widget = QWidget()
        file_log_layout = QVBoxLayout(file_log_widget)
        file_log_layout.setContentsMargins(0, 0, 0, 0)
        file_log_layout.setSpacing(4)
        
        file_log_header = QHBoxLayout()
        file_log_label = QLabel("📂 文件修改日志")
        file_log_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; margin-top: 6px;")
        file_log_header.addWidget(file_log_label)
        
        self.file_log_count_label = QLabel("(0)")
        self.file_log_count_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        file_log_header.addWidget(self.file_log_count_label)
        file_log_header.addStretch()
        
        clear_file_log_btn = QPushButton("🗑️ 清空")
        clear_file_log_btn.setProperty("class", "secondary")
        clear_file_log_btn.setFixedHeight(24)
        clear_file_log_btn.clicked.connect(self.clear_file_log)
        file_log_header.addWidget(clear_file_log_btn)
        
        file_log_layout.addLayout(file_log_header)
        
        self.file_log_text = QTextEdit()
        self.file_log_text.setReadOnly(True)
        self.file_log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                color: {COLORS['text_primary']};
                font-size: 11px;
                font-family: 'Consolas', 'Courier New', monospace;
                padding: 6px;
            }}
        """)
        self.file_log_text.setPlaceholderText("文件修改日志将在此显示...")
        file_log_layout.addWidget(self.file_log_text)
        
        splitter.addWidget(file_log_widget)
        
        # ===== 活动日志区域 =====
        activity_widget = QWidget()
        activity_layout_inner = QVBoxLayout(activity_widget)
        activity_layout_inner.setContentsMargins(0, 0, 0, 0)
        activity_layout_inner.setSpacing(4)
        
        activity_header = QHBoxLayout()
        activity_label = QLabel("📝 最近活动")
        activity_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; margin-top: 6px;")
        activity_header.addWidget(activity_label)
        
        self.activity_count_label = QLabel("(0)")
        self.activity_count_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        activity_header.addWidget(self.activity_count_label)
        activity_header.addStretch()
        
        activity_layout_inner.addLayout(activity_header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.activity_container = QWidget()
        self.activity_layout = QVBoxLayout(self.activity_container)
        self.activity_layout.setSpacing(4)
        self.activity_layout.setContentsMargins(0, 0, 0, 0)
        self.activity_layout.addStretch()
        
        scroll.setWidget(self.activity_container)
        activity_layout_inner.addWidget(scroll, 1)
        
        splitter.addWidget(activity_widget)
        
        # 设置默认分割比例
        splitter.setSizes([200, 200])
        layout.addWidget(splitter, 1)
    
    def _start_update_timer(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._refresh)
        self.update_timer.start(2000)
    
    def _refresh(self):
        self._update_stats()
        self._update_task_table()
    
    def _update_stats(self):
        stats = task_manager.get_overall_stats()
        running = stats.get("running", 0)
        self.running_card.set_value(str(running), COLORS["success"] if running > 0 else COLORS["text_muted"])
        
        total_synced = 0
        total_errors = 0
        for task in task_manager.get_all_tasks():
            task_stats = task_manager.get_task_stats(task.id)
            total_synced += task_stats.get("copied_files", 0)
            total_errors += task_stats.get("failed_files", 0)
        
        self.synced_card.set_value(str(total_synced))
        self.error_card.set_value(str(total_errors), COLORS["error"] if total_errors > 0 else COLORS["text_muted"])
    
    def _update_task_table(self):
        tasks = task_manager.get_all_tasks()
        self.status_table.setRowCount(len(tasks))
        
        for row, task in enumerate(tasks):
            name_item = QTableWidgetItem(task.name)
            self.status_table.setItem(row, 0, name_item)
            
            status = task_manager.get_task_status(task.id)
            status_map = {
                TaskStatus.RUNNING: ("● 运行中", COLORS["success"]),
                TaskStatus.PAUSED: ("● 暂停", COLORS["warning"]),
                TaskStatus.STOPPED: ("○ 停止", COLORS["text_muted"]),
                TaskStatus.ERROR: ("● 错误", COLORS["error"]),
            }
            status_text, status_color = status_map.get(status, ("○ 未知", COLORS["text_muted"]))
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(status_color))
            self.status_table.setItem(row, 1, status_item)
            
            stats = task_manager.get_task_stats(task.id)
            synced_item = QTableWidgetItem(str(stats.get("copied_files", 0)))
            synced_item.setTextAlignment(Qt.AlignCenter)
            self.status_table.setItem(row, 2, synced_item)
            
            failed_item = QTableWidgetItem(str(stats.get("failed_files", 0)))
            failed_item.setTextAlignment(Qt.AlignCenter)
            if stats.get("failed_files", 0) > 0:
                failed_item.setForeground(QColor(COLORS["error"]))
            self.status_table.setItem(row, 3, failed_item)
    
    def add_activity(self, event_type: str, path: str, status: str = "success", 
                     target_path: str = None, task_name: str = None,
                     is_directory: bool = False, file_count: int = 0):
        """添加活动记录 - 每次文件变更都会显示
        
        Args:
            event_type: 事件类型 (created, modified, deleted, moved)
            path: 源文件路径
            status: 状态 (success, failed)
            target_path: 目标文件路径 (可选)
            task_name: 任务名称 (可选)
            is_directory: 是否是目录操作
            file_count: 目录包含的文件数量
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 事件类型图标和中文
        if is_directory:
            type_info = {
                "created": ("📁", "创建文件夹"),
                "modified": ("📁", "修改文件夹"),
                "deleted": ("📁", "删除文件夹"),
                "moved": ("📁", "重命名文件夹"),
                "copied": ("📁", "复制文件夹")
            }
        else:
            type_info = {
                "created": ("📄", "创建"),
                "modified": ("✏️", "修改"),
                "deleted": ("🗑️", "删除"),
                "moved": ("📦", "移动"),
                "copied": ("📋", "复制")
            }
        icon, type_cn = type_info.get(event_type, ("📁", event_type))
        
        # 文件名
        filename = os.path.basename(path)
        dirname = os.path.dirname(path)
        short_dir = os.path.basename(dirname) if dirname else ""
        
        # 构建显示文本
        if is_directory:
            # 文件夹操作特殊格式
            file_count_str = f"，包含 {file_count} 个文件" if file_count > 0 else ""
            if event_type == "moved" and target_path:
                new_name = os.path.basename(target_path)
                display_text = f"{timestamp}  {icon} {type_cn} {filename} → {new_name}{file_count_str}"
            else:
                display_text = f"{timestamp}  {icon} {type_cn} {filename}{file_count_str}"
        else:
            # 普通文件操作
            if target_path:
                target_name = os.path.basename(target_path)
                if event_type == "deleted":
                    display_text = f"{timestamp}  {icon} {type_cn}  {filename}"
                else:
                    display_text = f"{timestamp}  {icon} {type_cn}  {filename} → {os.path.basename(os.path.dirname(target_path))}"
            else:
                display_text = f"{timestamp}  {icon} {type_cn}  {filename}"
        
        if task_name:
            if is_directory:
                file_count_str = f"，包含 {file_count} 个文件" if file_count > 0 else ""
                if event_type == "moved" and target_path:
                    new_name = os.path.basename(target_path)
                    display_text = f"{timestamp}  [{task_name}] {icon} {type_cn} {filename} → {new_name}{file_count_str}"
                else:
                    display_text = f"{timestamp}  [{task_name}] {icon} {type_cn} {filename}{file_count_str}"
            else:
                display_text = f"{timestamp}  [{task_name}] {icon} {type_cn}  {filename}"
        
        # 状态颜色
        if status == 'success':
            color = COLORS['success']
            status_icon = "✓"
        else:
            color = COLORS['error']
            status_icon = "✗"
        
        # 完整行
        full_text = f"{display_text}  {status_icon}"
        
        # 创建活动行
        activity = QLabel(full_text)
        activity.setStyleSheet(f"""
            color: {color};
            font-size: 11px;
            padding: 5px 10px;
            background-color: {COLORS['bg_card']};
            border-radius: 4px;
            border-left: 3px solid {color};
        """)
        activity.setToolTip(f"源: {path}" + (f"\n目标: {target_path}" if target_path else ""))
        activity.setWordWrap(True)
        
        self.activity_layout.insertWidget(0, activity)
        self._activities.append(full_text)
        
        # 同时添加到文件修改日志文本框
        self._add_to_file_log(timestamp, event_type, type_cn, filename, path, target_path, status, task_name, is_directory, file_count)
        
        # 更新计数
        count = self.activity_layout.count() - 1  # -1 for stretch
        self.activity_count_label.setText(f"({count})")
        
        # 限制数量
        while self.activity_layout.count() > self._max_activities + 1:
            item = self.activity_layout.takeAt(self.activity_layout.count() - 2)
            if item and item.widget():
                item.widget().deleteLater()
            if self._activities:
                self._activities.pop(0)
    
    def clear_activities(self):
        """清空活动记录"""
        while self.activity_layout.count() > 1:
            item = self.activity_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._activities.clear()
        self.activity_count_label.setText("(0)")
    
    def _add_to_file_log(self, timestamp: str, event_type: str, type_cn: str, 
                          filename: str, path: str, target_path: str = None, 
                          status: str = "success", task_name: str = None,
                          is_directory: bool = False, file_count: int = 0):
        """添加条目到文件修改日志文本框"""
        # 状态标记
        status_mark = "✓" if status == "success" else "✗"
        
        # 构建详细日志行
        if task_name:
            log_line = f"[{timestamp}] [{task_name}] {type_cn} {status_mark}"
        else:
            log_line = f"[{timestamp}] {type_cn} {status_mark}"
        
        # 文件夹显示文件数量
        if is_directory and file_count > 0:
            log_line += f" (包含 {file_count} 个文件)"
        
        log_line += f"\n  源: {path}"
        if target_path:
            log_line += f"\n  目标: {target_path}"
        log_line += "\n"
        
        # 添加到文本框顶部
        current_text = self.file_log_text.toPlainText()
        new_text = log_line + current_text
        
        # 限制条目数量
        self._file_log_entries.insert(0, log_line)
        if len(self._file_log_entries) > self._max_file_log_entries:
            self._file_log_entries = self._file_log_entries[:self._max_file_log_entries]
            # 重建文本
            new_text = "".join(self._file_log_entries)
        
        self.file_log_text.setPlainText(new_text)
        
        # 更新计数
        self.file_log_count_label.setText(f"({len(self._file_log_entries)})")
    
    def clear_file_log(self):
        """清空文件修改日志"""
        self.file_log_text.clear()
        self._file_log_entries.clear()
        self.file_log_count_label.setText("(0)")
