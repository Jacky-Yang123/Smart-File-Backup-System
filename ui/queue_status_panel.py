"""
队列状态面板 - 显示操作队列进度和状态
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QListWidget,
    QListWidgetItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from .styles import COLORS


class QueueStatusPanel(QWidget):
    """队列状态面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._start_update_timer()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # 标题
        title_layout = QHBoxLayout()
        title = QLabel("⚡ 操作队列")
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {COLORS['text_primary']};")
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        # 状态标签
        self.status_label = QLabel("空闲")
        self.status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        title_layout.addWidget(self.status_label)
        
        layout.addLayout(title_layout)
        
        # 当前操作
        current_frame = QFrame()
        current_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        current_layout = QVBoxLayout(current_frame)
        current_layout.setSpacing(6)
        current_layout.setContentsMargins(10, 10, 10, 10)
        
        self.current_file_label = QLabel("等待操作...")
        self.current_file_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 12px;")
        self.current_file_label.setWordWrap(True)
        current_layout.addWidget(self.current_file_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['bg_light']};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['success']};
                border-radius: 4px;
            }}
        """)
        current_layout.addWidget(self.progress_bar)
        
        layout.addWidget(current_frame)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self.pending_label = QLabel("待处理: 0")
        self.pending_label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
        stats_layout.addWidget(self.pending_label)
        
        self.completed_label = QLabel("已完成: 0")
        self.completed_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
        stats_layout.addWidget(self.completed_label)
        
        self.failed_label = QLabel("失败: 0")
        self.failed_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")
        stats_layout.addWidget(self.failed_label)
        
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        # 下一步操作预览
        preview_label = QLabel("接下来:")
        preview_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(preview_label)
        
        self.preview_list = QListWidget()
        self.preview_list.setFixedHeight(80)
        self.preview_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                font-size: 11px;
            }}
            QListWidget::item {{
                padding: 3px 6px;
                color: {COLORS['text_secondary']};
            }}
        """)
        layout.addWidget(self.preview_list)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.pause_btn = QPushButton("⏸ 暂停")
        self.pause_btn.setFixedHeight(28)
        self.pause_btn.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(self.pause_btn)
        
        self.clear_btn = QPushButton("🗑 清空")
        self.clear_btn.setProperty("class", "secondary")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.clicked.connect(self._clear_queue)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
    
    def _start_update_timer(self):
        """启动更新定时器"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._refresh_status)
        self.update_timer.start(500)
    
    def _refresh_status(self):
        """刷新状态"""
        try:
            from core.operation_queue import operation_queue
            
            status = operation_queue.get_status()
            pending = status.get("pending", 0)
            completed = status.get("completed", 0)
            failed = status.get("failed", 0)
            is_paused = status.get("is_paused", False)
            current_file = status.get("current_file", "")
            
            # 更新标签
            self.pending_label.setText(f"待处理: {pending}")
            self.completed_label.setText(f"已完成: {completed}")
            self.failed_label.setText(f"失败: {failed}")
            
            # 更新当前文件
            total = pending + completed + failed
            
            if current_file:
                self.current_file_label.setText(f"正在处理: {current_file} ({completed + 1}/{total})")
                self.status_label.setText("处理中")
                self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
            elif pending > 0:
                self.current_file_label.setText(f"准备处理... ({completed}/{total})")
                self.status_label.setText("队列中")
                self.status_label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
            else:
                self.current_file_label.setText("等待操作...")
                self.status_label.setText("空闲")
                self.status_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
            
            # 更新暂停按钮
            if is_paused:
                self.pause_btn.setText("▶ 继续")
            else:
                self.pause_btn.setText("⏸ 暂停")
            
            # 更新进度条
            total = pending + completed
            if total > 0:
                progress = int(completed / total * 100)
                self.progress_bar.setValue(progress)
            else:
                self.progress_bar.setValue(0)
            
            # 更新预览列表
            next_ops = operation_queue.get_next_operations(5)
            self.preview_list.clear()
            for op in next_ops:
                item = QListWidgetItem(f"[{op['type']}] {op['file']}")
                self.preview_list.addItem(item)
            
            if not next_ops:
                item = QListWidgetItem("(无待处理操作)")
                item.setForeground(Qt.gray)
                self.preview_list.addItem(item)
                
        except Exception as e:
            print(f"Queue status refresh error: {e}")
    
    def _toggle_pause(self):
        """切换暂停状态"""
        try:
            from core.operation_queue import operation_queue
            status = operation_queue.get_status()
            if status.get("is_paused", False):
                operation_queue.resume()
            else:
                operation_queue.pause()
        except Exception as e:
            print(f"Toggle pause error: {e}")
    
    def _clear_queue(self):
        """清空队列"""
        try:
            from core.operation_queue import operation_queue
            operation_queue.clear()
        except Exception as e:
            print(f"Clear queue error: {e}")
    
    def update_from_signal(self, status: dict):
        """从信号更新状态"""
        # 此方法可用于直接从信号更新，但当前使用定时器轮询
        pass
