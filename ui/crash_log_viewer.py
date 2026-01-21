"""
崩溃日志查看器模块 - 专业日志
"""
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFileDialog, QMessageBox,
    QFrame, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QTextCharFormat, QFont

from utils.logger import logger
from .styles import COLORS


class CrashLogViewer(QWidget):
    """崩溃日志查看器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_refresh = True
        self._init_ui()
        self._start_refresh_timer()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # 标题
        header = QHBoxLayout()
        title = QLabel("🔧 专业日志 / 崩溃报告")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {COLORS['text_primary']};")
        header.addWidget(title)
        header.addStretch()
        
        # 状态指示
        self.status_label = QLabel("● 正常运行")
        self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
        header.addWidget(self.status_label)
        
        layout.addLayout(header)
        
        # 说明
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_card']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 8, 12, 8)
        
        info_text = QLabel(
            "📋 此页面显示程序运行时的错误和崩溃日志。\n"
            "如遇程序卡死或异常，可在此查看详细报错信息。"
        )
        info_text.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        
        layout.addWidget(info_frame)
        
        # 筛选和工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        
        toolbar.addWidget(QLabel("类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("全部日志", "all")
        self.type_combo.addItem("🔴 崩溃/错误", "crash")
        self.type_combo.addItem("🟡 警告", "warning")
        self.type_combo.addItem("🔵 信息", "info")
        self.type_combo.setFixedWidth(120)
        self.type_combo.currentIndexChanged.connect(self._refresh_logs)
        toolbar.addWidget(self.type_combo)
        
        toolbar.addStretch()
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setProperty("class", "secondary")
        refresh_btn.setFixedHeight(26)
        refresh_btn.clicked.connect(self._refresh_logs)
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
        
        # 日志文本区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        layout.addWidget(self.log_text, 1)
        
        # 统计信息
        self.stats_label = QLabel("共 0 条日志记录")
        self.stats_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(self.stats_label)
        
        # 初始加载
        self._refresh_logs()
    
    def _start_refresh_timer(self):
        """启动自动刷新定时器"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_logs)
        self.refresh_timer.start(5000)  # 5秒刷新一次
    
    def _refresh_logs(self):
        """刷新日志显示"""
        filter_type = self.type_combo.currentData()
        
        # 获取日志
        if filter_type == "crash":
            logs = logger.get_logs(level="ERROR", limit=500)
        elif filter_type == "warning":
            logs = logger.get_logs(level="WARNING", limit=500)
        elif filter_type == "info":
            logs = logger.get_logs(level="INFO", limit=500)
        else:
            logs = logger.get_logs(limit=500)
        
        # 根据category筛选崩溃日志
        if filter_type == "crash":
            logs = [l for l in logs if l.get("category") == "crash" or l.get("level") == "ERROR"]
        
        # 构建显示文本
        self.log_text.clear()
        
        error_count = 0
        warning_count = 0
        
        for log in reversed(logs):  # 最新的在最上面
            level = log.get("level", "INFO")
            timestamp = log.get("timestamp", "")
            if hasattr(timestamp, "strftime"):
                timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            category = log.get("category", "")
            message = log.get("message", "")
            
            # 统计
            if level == "ERROR":
                error_count += 1
            elif level == "WARNING":
                warning_count += 1
            
            # 颜色标记
            level_colors = {
                "ERROR": "#f44336",
                "WARNING": "#ff9800",
                "INFO": "#4caf50",
                "DEBUG": "#9e9e9e"
            }
            color = level_colors.get(level, "#d4d4d4")
            
            # 添加带颜色的行
            line = f"[{timestamp}] [{level}]"
            if category:
                line += f" [{category}]"
            line += f" {message}\n"
            
            # 使用HTML格式显示
            html_line = f'<span style="color: {color};">{line}</span>'
            self.log_text.insertHtml(html_line)
        
        # 更新统计
        total = len(logs)
        self.stats_label.setText(f"共 {total} 条日志记录 | 错误: {error_count} | 警告: {warning_count}")
        
        # 更新状态
        if error_count > 0:
            self.status_label.setText(f"⚠️ 发现 {error_count} 个错误")
            self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")
        else:
            self.status_label.setText("● 正常运行")
            self.status_label.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
    
    def _export_logs(self):
        """导出日志"""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出专业日志",
            f"crash_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "文本文件 (*.txt)"
        )
        if not filepath:
            return
        
        try:
            logs = logger.get_logs(limit=10000)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"=== 智能备份系统 - 专业日志导出 ===\n")
                f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                
                for log in logs:
                    timestamp = log.get("timestamp", "")
                    if hasattr(timestamp, "strftime"):
                        timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    
                    level = log.get("level", "INFO")
                    category = log.get("category", "")
                    message = log.get("message", "")
                    
                    line = f"[{timestamp}] [{level}]"
                    if category:
                        line += f" [{category}]"
                    line += f" {message}\n"
                    f.write(line)
            
            QMessageBox.information(self, "导出成功", f"已导出到:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败: {str(e)}")
    
    def _clear_logs(self):
        """清空日志"""
        reply = QMessageBox.question(
            self, "确认清空",
            "确定要清空所有日志记录吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            logger.clear_old_logs(days=0)
            self._refresh_logs()
