"""
日志查看器模块 - 优化版
"""
from datetime import datetime
from typing import List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from utils.logger import logger
from utils.constants import LogLevel
from .styles import COLORS, get_log_color


class LogViewer(QWidget):
    """日志查看器 - 优化版"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_scroll = True
        
        self._init_ui()
        self._load_logs()
        self._start_update_timer()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # 标题
        header = QHBoxLayout()
        title = QLabel("📝 日志记录")
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['text_primary']};")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        
        # 过滤器
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        filter_layout.addWidget(QLabel("级别:"))
        self.level_combo = QComboBox()
        self.level_combo.addItem("全部", "")
        self.level_combo.addItem("信息", LogLevel.INFO.value)
        self.level_combo.addItem("警告", LogLevel.WARNING.value)
        self.level_combo.addItem("错误", LogLevel.ERROR.value)
        self.level_combo.setFixedWidth(80)
        self.level_combo.currentIndexChanged.connect(self._load_logs)
        filter_layout.addWidget(self.level_combo)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索日志...")
        self.search_edit.setFixedWidth(180)
        self.search_edit.textChanged.connect(self._load_logs)
        filter_layout.addWidget(self.search_edit)
        
        filter_layout.addStretch()
        
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(
            lambda s: setattr(self, '_auto_scroll', s == Qt.Checked)
        )
        filter_layout.addWidget(self.auto_scroll_check)
        
        # 显示 DEBUG 日志
        self.show_debug_check = QCheckBox("显示 DEBUG")
        self.show_debug_check.setChecked(False)  # 默认不显示
        self.show_debug_check.stateChanged.connect(self._load_logs)
        filter_layout.addWidget(self.show_debug_check)
        
        export_btn = QPushButton("📥 导出")
        export_btn.setProperty("class", "secondary")
        export_btn.setFixedHeight(26)
        export_btn.clicked.connect(self._export_logs)
        filter_layout.addWidget(export_btn)
        
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setProperty("class", "secondary")
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self._clear_logs)
        filter_layout.addWidget(clear_btn)
        
        layout.addLayout(filter_layout)
        
        # 日志表格
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(4)
        self.log_table.setHorizontalHeaderLabels(["时间", "级别", "分类", "消息"])
        self.log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setStyleSheet(f"alternate-background-color: {COLORS['bg_light']};")
        
        layout.addWidget(self.log_table, 1)
    
    def _start_update_timer(self):
        from utils.config_manager import config_manager
        interval_seconds = config_manager.get("ui.log_refresh_interval", 3)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._check_new_logs)
        self.update_timer.start(interval_seconds * 1000)
    
    def _load_logs(self):
        level = self.level_combo.currentData()
        logs = logger.get_logs(level=level if level else None, limit=500)
        self._display_logs(logs)
    
    def _display_logs(self, logs: List[dict]):
        search_text = self.search_edit.text().lower()
        
        # 优化：如果是追加模式且没有搜索关键词，可以使用增量更新
        # 但为了简单起见，这里先保持全量刷新，但处理好时间格式
        
        self.log_table.setRowCount(0)
        self.log_table.setSortingEnabled(False) # 暂停排序以提高性能
        
        for log in reversed(logs):
            # 搜索过滤
            if search_text and search_text not in log.get("message", "").lower():
                continue
            
            # DEBUG 过滤：除非勾选了"显示 DEBUG"，否则隐藏 DEBUG 日志
            log_level = log.get("level", "INFO")
            if log_level == "DEBUG" and not self.show_debug_check.isChecked():
                continue
            
            row = self.log_table.rowCount()
            self.log_table.insertRow(row)
            
            # 时间
            timestamp = log.get("timestamp")
            if isinstance(timestamp, str):
                # 尝试解析 ISO 格式
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%H:%M:%S")
                except ValueError:
                    time_str = timestamp
            elif hasattr(timestamp, "strftime"):
                time_str = timestamp.strftime("%H:%M:%S")
            else:
                time_str = str(timestamp)
            
            time_item = QTableWidgetItem(time_str)
            time_item.setForeground(QColor(COLORS["text_muted"]))
            self.log_table.setItem(row, 0, time_item)
            
            # 级别
            level = log.get("level", "INFO")
            level_icons = {"DEBUG": "⚪", "INFO": "🔵", "WARNING": "🟡", "ERROR": "🔴"}
            level_item = QTableWidgetItem(f"{level_icons.get(level, '⚪')} {level}")
            level_item.setForeground(QColor(get_log_color(level)))
            self.log_table.setItem(row, 1, level_item)
            
            # 分类
            category_item = QTableWidgetItem(log.get("category", ""))
            category_item.setForeground(QColor(COLORS["text_muted"]))
            self.log_table.setItem(row, 2, category_item)
            
            # 消息
            self.log_table.setItem(row, 3, QTableWidgetItem(log.get("message", "")))
        
        self.log_table.setSortingEnabled(True)
        
        if self._auto_scroll:
            self.log_table.scrollToBottom()
    
    def _check_new_logs(self):
        if self._auto_scroll:
            self._load_logs()
    
    def _export_logs(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出日志", f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "文本文件 (*.txt)"
        )
        if not filepath:
            return
        try:
            logs = logger.get_logs(limit=10000)
            with open(filepath, 'w', encoding='utf-8') as f:
                for log in logs:
                    ts = log.get("timestamp", "")
                    if hasattr(ts, "strftime"):
                        ts = ts.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f'[{ts}] [{log.get("level", "")}] [{log.get("category", "")}] {log.get("message", "")}\n')
            QMessageBox.information(self, "成功", f"已导出到:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "失败", f"导出失败: {str(e)}")
    
    def _clear_logs(self):
        reply = QMessageBox.question(self, "确认", "清空所有日志？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            logger.clear_old_logs(days=0)
            self._load_logs()
    
    def add_log(self, log_entry: dict):
        """添加新日志条目"""
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)
        
        timestamp = log_entry.get("timestamp")
        time_str = timestamp.strftime("%H:%M:%S") if hasattr(timestamp, "strftime") else datetime.now().strftime("%H:%M:%S")
        
        time_item = QTableWidgetItem(time_str)
        time_item.setForeground(QColor(COLORS["text_muted"]))
        self.log_table.setItem(row, 0, time_item)
        
        level = log_entry.get("level", "INFO")
        level_icons = {"DEBUG": "⚪", "INFO": "🔵", "WARNING": "🟡", "ERROR": "🔴"}
        level_item = QTableWidgetItem(f"{level_icons.get(level, '⚪')} {level}")
        level_item.setForeground(QColor(get_log_color(level)))
        self.log_table.setItem(row, 1, level_item)
        
        category_item = QTableWidgetItem(log_entry.get("category", ""))
        category_item.setForeground(QColor(COLORS["text_muted"]))
        self.log_table.setItem(row, 2, category_item)
        
        self.log_table.setItem(row, 3, QTableWidgetItem(log_entry.get("message", "")))
        
        if self._auto_scroll:
            self.log_table.scrollToBottom()
