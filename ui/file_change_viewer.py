"""
文件变更查看器模块 - 专门记录文件/文件夹变更操作
"""
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, 
    QCheckBox, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from core.task_manager import task_manager
from .styles import COLORS


@dataclass
class FileChangeEntry:
    """文件变更条目"""
    timestamp: datetime
    task_name: str
    event_type: str  # created, modified, deleted, moved
    filename: str
    source_path: str
    target_path: str = ""
    is_directory: bool = False
    file_count: int = 0
    success: bool = True
    message: str = ""


class FileChangeViewer(QWidget):
    """文件变更查看器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: List[FileChangeEntry] = []
        self._max_entries = 2000
        self._auto_scroll = True
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # 标题和统计
        header = QHBoxLayout()
        title = QLabel("📁 文件变更记录")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLORS['text_primary']};")
        header.addWidget(title)
        header.addStretch()
        
        # 统计卡片
        self.stats_label = QLabel("总计: 0 | 成功: 0 | 失败: 0")
        self.stats_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        header.addWidget(self.stats_label)
        
        layout.addLayout(header)
        
        # 筛选区域
        filter_frame = QFrame()
        filter_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(10)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        
        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 搜索文件名或路径...")
        self.search_edit.setFixedWidth(200)
        self.search_edit.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_edit)
        
        # 操作类型筛选
        filter_layout.addWidget(QLabel("操作:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("全部", "")
        self.type_combo.addItem("📄 创建", "created")
        self.type_combo.addItem("✏️ 修改", "modified")
        self.type_combo.addItem("🗑️ 删除", "deleted")
        self.type_combo.addItem("📦 移动/重命名", "moved")
        self.type_combo.setFixedWidth(120)
        self.type_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.type_combo)
        
        # 任务筛选
        filter_layout.addWidget(QLabel("任务:"))
        self.task_combo = QComboBox()
        self.task_combo.addItem("全部任务", "")
        self.task_combo.setFixedWidth(120)
        self.task_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.task_combo)
        
        # 时间范围
        filter_layout.addWidget(QLabel("时间:"))
        self.time_combo = QComboBox()
        self.time_combo.addItem("今天", "today")
        self.time_combo.addItem("最近7天", "week")
        self.time_combo.addItem("全部", "all")
        self.time_combo.setFixedWidth(90)
        self.time_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.time_combo)
        
        filter_layout.addStretch()
        
        # 仅显示文件夹
        self.folder_only_check = QCheckBox("仅文件夹")
        self.folder_only_check.stateChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.folder_only_check)
        
        # 仅显示失败
        self.failed_only_check = QCheckBox("仅失败")
        self.failed_only_check.stateChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.failed_only_check)
        
        layout.addWidget(filter_frame)
        
        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(
            lambda s: setattr(self, '_auto_scroll', s == Qt.Checked)
        )
        toolbar.addWidget(self.auto_scroll_check)
        
        toolbar.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.setFixedHeight(26)
        refresh_btn.clicked.connect(self._refresh_task_list)
        toolbar.addWidget(refresh_btn)
        
        export_btn = QPushButton("📥 导出")
        export_btn.setProperty("class", "secondary")
        export_btn.setFixedHeight(26)
        export_btn.clicked.connect(self._export_logs)
        toolbar.addWidget(export_btn)
        
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setProperty("class", "secondary")
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self._clear_logs)
        toolbar.addWidget(clear_btn)
        
        layout.addLayout(toolbar)
        
        # 变更记录表格
        self.change_table = QTableWidget()
        self.change_table.setColumnCount(7)
        self.change_table.setHorizontalHeaderLabels([
            "时间", "任务", "类型", "名称", "源路径", "目标路径", "状态"
        ])
        
        # 设置列宽
        header = self.change_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 时间
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 任务
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 类型
        header.setSectionResizeMode(3, QHeaderView.Interactive)       # 名称
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # 源路径
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # 目标路径
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # 状态
        
        self.change_table.setColumnWidth(3, 150)  # 名称列默认宽度
        
        self.change_table.verticalHeader().setVisible(False)
        self.change_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.change_table.setAlternatingRowColors(True)
        self.change_table.setStyleSheet(f"""
            QTableWidget {{
                alternate-background-color: {COLORS['bg_light']};
                gridline-color: {COLORS['border']};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
        """)
        
        layout.addWidget(self.change_table, 1)
        
        # 底部信息
        self.info_label = QLabel("显示 0 条记录")
        self.info_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(self.info_label)
        
        # 初始化任务列表
        self._refresh_task_list()
    
    def _refresh_task_list(self):
        """刷新任务列表"""
        current_task = self.task_combo.currentData()
        self.task_combo.clear()
        self.task_combo.addItem("全部任务", "")
        
        for task in task_manager.get_all_tasks():
            self.task_combo.addItem(task.name, task.id)
        
        # 恢复之前的选择
        if current_task:
            index = self.task_combo.findData(current_task)
            if index >= 0:
                self.task_combo.setCurrentIndex(index)
    
    def add_change(self, event_type: str, source_path: str, target_path: str = "",
                   task_name: str = "", is_directory: bool = False, 
                   file_count: int = 0, success: bool = True, message: str = ""):
        """添加变更记录"""
        entry = FileChangeEntry(
            timestamp=datetime.now(),
            task_name=task_name,
            event_type=event_type,
            filename=os.path.basename(source_path),
            source_path=source_path,
            target_path=target_path,
            is_directory=is_directory,
            file_count=file_count,
            success=success,
            message=message
        )
        
        self._entries.insert(0, entry)
        
        # 限制条目数量
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[:self._max_entries]
        
        # 更新显示
        self._apply_filter()
    
    def _apply_filter(self):
        """应用筛选条件"""
        search_text = self.search_edit.text().lower()
        type_filter = self.type_combo.currentData()
        task_filter = self.task_combo.currentData()
        time_filter = self.time_combo.currentData()
        folder_only = self.folder_only_check.isChecked()
        failed_only = self.failed_only_check.isChecked()
        
        # 时间范围
        now = datetime.now()
        if time_filter == "today":
            time_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_filter == "week":
            time_start = now - timedelta(days=7)
        else:
            time_start = None
        
        filtered_entries = []
        for entry in self._entries:
            # 时间筛选
            if time_start and entry.timestamp < time_start:
                continue
            
            # 搜索筛选
            if search_text:
                if (search_text not in entry.filename.lower() and 
                    search_text not in entry.source_path.lower() and
                    search_text not in entry.target_path.lower()):
                    continue
            
            # 类型筛选
            if type_filter and entry.event_type != type_filter:
                continue
            
            # 任务筛选
            if task_filter and entry.task_name != task_filter:
                # 尝试通过任务ID匹配任务名
                task = task_manager.get_task(task_filter)
                if not task or entry.task_name != task.name:
                    continue
            
            # 仅文件夹
            if folder_only and not entry.is_directory:
                continue
            
            # 仅失败
            if failed_only and entry.success:
                continue
            
            filtered_entries.append(entry)
        
        self._display_entries(filtered_entries)
    
    def _display_entries(self, entries: List[FileChangeEntry]):
        """显示条目"""
        self.change_table.setRowCount(0)
        
        # 统计
        total = len(self._entries)
        success_count = sum(1 for e in self._entries if e.success)
        failed_count = total - success_count
        self.stats_label.setText(f"总计: {total} | 成功: {success_count} | 失败: {failed_count}")
        
        for entry in entries:
            row = self.change_table.rowCount()
            self.change_table.insertRow(row)
            
            # 时间
            time_item = QTableWidgetItem(entry.timestamp.strftime("%H:%M:%S"))
            time_item.setForeground(QColor(COLORS["text_muted"]))
            self.change_table.setItem(row, 0, time_item)
            
            # 任务名
            task_item = QTableWidgetItem(entry.task_name)
            task_item.setForeground(QColor(COLORS["info"]))
            self.change_table.setItem(row, 1, task_item)
            
            # 类型
            type_icons = {
                "created": "📄 创建",
                "modified": "✏️ 修改",
                "deleted": "🗑️ 删除",
                "moved": "📦 移动"
            }
            if entry.is_directory:
                type_icons = {
                    "created": "📁 创建文件夹",
                    "modified": "📁 修改文件夹",
                    "deleted": "📁 删除文件夹",
                    "moved": "📁 重命名文件夹"
                }
            type_text = type_icons.get(entry.event_type, entry.event_type)
            if entry.is_directory and entry.file_count > 0:
                type_text += f" ({entry.file_count}个文件)"
            type_item = QTableWidgetItem(type_text)
            self.change_table.setItem(row, 2, type_item)
            
            # 文件名
            name_item = QTableWidgetItem(entry.filename)
            name_item.setToolTip(entry.source_path)
            self.change_table.setItem(row, 3, name_item)
            
            # 源路径
            source_item = QTableWidgetItem(entry.source_path)
            source_item.setForeground(QColor(COLORS["text_muted"]))
            source_item.setToolTip(entry.source_path)
            self.change_table.setItem(row, 4, source_item)
            
            # 目标路径
            target_item = QTableWidgetItem(entry.target_path if entry.target_path else "-")
            target_item.setForeground(QColor(COLORS["text_muted"]))
            if entry.target_path:
                target_item.setToolTip(entry.target_path)
            self.change_table.setItem(row, 5, target_item)
            
            # 状态
            if entry.success:
                status_item = QTableWidgetItem("✓ 成功")
                status_item.setForeground(QColor(COLORS["success"]))
            else:
                status_item = QTableWidgetItem("✗ 失败")
                status_item.setForeground(QColor(COLORS["error"]))
                if entry.message:
                    status_item.setToolTip(entry.message)
            self.change_table.setItem(row, 6, status_item)
        
        # 更新信息
        self.info_label.setText(f"显示 {len(entries)} / {len(self._entries)} 条记录")
        
        # 自动滚动
        if self._auto_scroll and entries:
            self.change_table.scrollToTop()
    
    def _export_logs(self):
        """导出日志"""
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self, "导出变更日志", 
            f"file_changes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", 
            "文本文件 (*.txt);;CSV文件 (*.csv)"
        )
        if not filepath:
            return
        
        try:
            is_csv = filepath.endswith('.csv')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                if is_csv:
                    f.write("时间,任务,类型,文件名,源路径,目标路径,状态\n")
                
                for entry in self._entries:
                    ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    type_text = entry.event_type
                    if entry.is_directory:
                        type_text = f"folder_{entry.event_type}"
                    status = "成功" if entry.success else f"失败: {entry.message}"
                    
                    if is_csv:
                        # CSV格式，处理特殊字符
                        row = [ts, entry.task_name, type_text, entry.filename, 
                               entry.source_path, entry.target_path, status]
                        row = [f'"{v}"' if ',' in v or '"' in v else v for v in row]
                        f.write(','.join(row) + '\n')
                    else:
                        # 文本格式
                        f.write(f'[{ts}] [{entry.task_name}] {type_text}: {entry.filename}\n')
                        f.write(f'  源: {entry.source_path}\n')
                        if entry.target_path:
                            f.write(f'  目标: {entry.target_path}\n')
                        f.write(f'  状态: {status}\n')
                        f.write('\n')
            
            QMessageBox.information(self, "导出成功", f"已导出 {len(self._entries)} 条记录到:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")
    
    def _clear_logs(self):
        """清空日志"""
        if not self._entries:
            return
        
        reply = QMessageBox.question(
            self, "确认清空", 
            f"确定要清空全部 {len(self._entries)} 条变更记录吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._entries.clear()
            self._apply_filter()
