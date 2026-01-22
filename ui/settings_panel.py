"""
设置面板模块 - 嵌入式 (完全重做版)
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QSpinBox, QGroupBox, QTabWidget, QMessageBox,
    QFileDialog, QLineEdit, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt
import os

from utils.config_manager import config_manager
from utils.constants import SyncMode, ConflictStrategy, LogLevel, DATA_DIR
from utils.logger import logger
from .styles import COLORS

class SettingsPanel(QWidget):
    """设置面板 - 嵌入式主页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settings_panel")
        # 确保背景明显
        self.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        
        try:
            self._init_ui()
            self._load_settings()
        except Exception as e:
            logger.error(f"SettingsPanel Error: {e}")
    
    def _init_ui(self):
        # 顶级布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(12)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题栏
        header = QHBoxLayout()
        title = QLabel("⚙️ 系统设置")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']};")
        header.addWidget(title)
        
        header.addStretch()
        
        # 显眼的保存按钮
        self.save_btn = QPushButton("💾 保存所有设置")
        self.save_btn.setProperty("class", "primary")
        self.save_btn.setFixedSize(120, 32)
        self.save_btn.clicked.connect(self._save_settings)
        header.addWidget(self.save_btn)
        
        self.main_layout.addLayout(header)
        
        # 分隔线
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {COLORS['border']};")
        self.main_layout.addWidget(line)
        
        # 标签页组件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                background: {COLORS['bg_card']};
                border-radius: 4px;
            }}
            QTabBar::tab {{
                padding: 10px 20px;
                color: {COLORS['text_muted']};
                background: {COLORS['bg_medium']};
            }}
            QTabBar::tab:selected {{
                color: {COLORS['text_primary']};
                background: {COLORS['bg_card']};
            }}
        """)
        
        # 常规选项卡
        self.tab_widget.addTab(self._setup_general_tab(), "常规选项")
        # 备份选项卡
        self.tab_widget.addTab(self._setup_backup_tab(), "备份策略")
        # 通知选项卡
        self.tab_widget.addTab(self._setup_notify_tab(), "通知提醒")
        
        self.main_layout.addWidget(self.tab_widget, 1)

    def _setup_general_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 启动组
        group = QGroupBox("启动与窗口")
        group.setStyleSheet(self._group_style())
        g_layout = QVBoxLayout(group)
        
        self.auto_start_check = QCheckBox("系统开机时自动启动")
        self.minimize_to_tray_check = QCheckBox("主窗口关闭时继续运行 (最小化到托盘)")
        self.auto_backup_check = QCheckBox("程序启动后自动激活所有备份任务")
        
        g_layout.addWidget(self.auto_start_check)
        g_layout.addWidget(self.minimize_to_tray_check)
        g_layout.addWidget(self.auto_backup_check)
        layout.addWidget(group)
        
        # 存储组
        s_group = QGroupBox("数据存储路径")
        s_group.setStyleSheet(self._group_style())
        s_layout = QVBoxLayout(s_group)
        
        path_box = QHBoxLayout()
        self.storage_path_edit = QLineEdit()
        self.storage_path_edit.setReadOnly(True)
        path_box.addWidget(self.storage_path_edit)
        
        browse_btn = QPushButton("更改目录")
        browse_btn.clicked.connect(self._select_path)
        path_box.addWidget(browse_btn)
        s_layout.addLayout(path_box)
        layout.addWidget(s_group)
        
        layout.addStretch()
        return widget

    def _setup_backup_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        form_group = QGroupBox("默认行为控制")
        form_group.setStyleSheet(self._group_style())
        form = QFormLayout(form_group)
        form.setSpacing(15)
        
        self.default_mode_combo = QComboBox()
        self.default_mode_combo.addItem("单向备份 (Source -> Target)", SyncMode.ONE_WAY.value)
        self.default_mode_combo.addItem("双向同步 (Source <-> Target)", SyncMode.TWO_WAY.value)
        
        self.default_conflict_combo = QComboBox()
        self.default_conflict_combo.addItem("覆盖旧文件 (Newest Wins)", ConflictStrategy.NEWEST_WINS.value)
        self.default_conflict_combo.addItem("保留两个版本 (Keep Both)", ConflictStrategy.KEEP_BOTH.value)
        
        self.ignore_hidden_check = QCheckBox("自动跳过隐藏文件和系统文件")
        
        form.addRow("新任务默认模式:", self.default_mode_combo)
        form.addRow("冲突处理方式:", self.default_conflict_combo)
        form.addRow("过滤选项:", self.ignore_hidden_check)
        
        layout.addWidget(form_group)
        layout.addStretch()
        return widget

    def _setup_notify_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        n_group = QGroupBox("通知事件订阅")
        n_group.setStyleSheet(self._group_style())
        n_layout = QVBoxLayout(n_group)
        
        self.notify_check = QCheckBox("启用全局通知系统")
        self.notify_err_check = QCheckBox("当任务发生严重错误时提醒")
        self.notify_del_check = QCheckBox("当大量文件被删除时进行安全确认")
        
        n_layout.addWidget(self.notify_check)
        n_layout.addWidget(self.notify_err_check)
        n_layout.addWidget(self.notify_del_check)
        
        layout.addWidget(n_group)
        layout.addStretch()
        return widget

    def _group_style(self):
        return f"""
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                margin-top: 10px;
                font-weight: bold;
                color: {COLORS['text_primary']};
                padding: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }}
        """

    def _load_settings(self):
        # 映射 config 到 UI
        self.auto_start_check.setChecked(config_manager.get("general.auto_start", False))
        self.minimize_to_tray_check.setChecked(config_manager.get("general.minimize_to_tray", True))
        self.auto_backup_check.setChecked(config_manager.get("general.auto_backup_on_start", False))
        self.storage_path_edit.setText(config_manager.get("general.storage_path", DATA_DIR))
        
        self.ignore_hidden_check.setChecked(config_manager.get("monitor.ignore_hidden", True))
        self.notify_check.setChecked(config_manager.get("general.show_notifications", True))
        self.notify_err_check.setChecked(config_manager.get("notifications.on_error", True))
        self.notify_del_check.setChecked(config_manager.get("notifications.on_delete", True))

    def _select_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择数据存储目录")
        if path:
            self.storage_path_edit.setText(path)

    def _save_settings(self):
        try:
            config_manager.set("general.auto_start", self.auto_start_check.isChecked())
            config_manager.set("general.minimize_to_tray", self.minimize_to_tray_check.isChecked())
            config_manager.set("general.auto_backup_on_start", self.auto_backup_check.isChecked())
            config_manager.set("general.storage_path", self.storage_path_edit.text())
            
            config_manager.set("monitor.ignore_hidden", self.ignore_hidden_check.isChecked())
            config_manager.set("general.show_notifications", self.notify_check.isChecked())
            config_manager.set("notifications.on_error", self.notify_err_check.isChecked())
            config_manager.set("notifications.on_delete", self.notify_del_check.isChecked())
            
            config_manager.save_config()
            QMessageBox.information(self, "成功", "设置已保存生效")
        except Exception as e:
            QMessageBox.warning(self, "失败", f"保存出错: {e}")
