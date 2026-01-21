"""
设置对话框模块 - 极简版
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QCheckBox,
    QSpinBox, QGroupBox, QTabWidget, QWidget, QMessageBox,
    QFileDialog, QLineEdit
)
from PyQt5.QtCore import Qt

from utils.config_manager import config_manager
from utils.constants import SyncMode, ConflictStrategy, LogLevel, DATA_DIR
from utils.logger import logger
from .styles import COLORS


class SettingsDialog(QDialog):
    """设置对话框 - 极简版"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(500, 520)
        self.setModal(True)
        self.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标题
        title = QLabel("设置")
        title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_primary']};")
        layout.addWidget(title)
        
        # 标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget, 1)
        
        tab_widget.addTab(self._create_general_tab(), "常规")
        tab_widget.addTab(self._create_backup_tab(), "备份")
        tab_widget.addTab(self._create_notify_tab(), "通知")
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.setFixedHeight(24)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.setFixedHeight(24)
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 启动选项
        group = QGroupBox("启动选项")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)
        
        self.auto_start_check = QCheckBox("开机自动启动")
        group_layout.addWidget(self.auto_start_check)
        
        self.minimize_to_tray_check = QCheckBox("关闭时最小化到托盘")
        self.minimize_to_tray_check.setChecked(True)
        group_layout.addWidget(self.minimize_to_tray_check)
        
        self.auto_backup_check = QCheckBox("启动时自动开始任务")
        group_layout.addWidget(self.auto_backup_check)
        
        layout.addWidget(group)
        
        # UI设置
        ui_group = QGroupBox("界面设置")
        ui_layout = QFormLayout(ui_group)
        ui_layout.setSpacing(6)
        
        self.log_refresh_spin = QSpinBox()
        self.log_refresh_spin.setRange(1, 30)
        self.log_refresh_spin.setValue(3)
        self.log_refresh_spin.setSuffix(" 秒")
        self.log_refresh_spin.setToolTip("日志界面自动刷新的时间间隔")
        ui_layout.addRow("日志刷新间隔:", self.log_refresh_spin)
        
        layout.addWidget(ui_group)
        
        # 存储设置
        storage_group = QGroupBox("存储设置")
        storage_layout = QVBoxLayout(storage_group)
        
        path_layout = QHBoxLayout()
        self.storage_path_edit = QLineEdit()
        self.storage_path_edit.setReadOnly(True)
        path_layout.addWidget(self.storage_path_edit)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(60)
        browse_btn.clicked.connect(self._browse_storage_path)
        path_layout.addWidget(browse_btn)
        storage_layout.addLayout(path_layout)
        
        hint = QLabel("提示: 修改存储路径将更换日志和历史数据库的位置。")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
        storage_layout.addWidget(hint)
        
        layout.addWidget(storage_group)
        layout.addStretch()
        return widget
    
    def _browse_storage_path(self):
        directory = QFileDialog.getExistingDirectory(self, "选择存储目录")
        if directory:
            self.storage_path_edit.setText(directory)
    
    def _create_backup_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 默认设置
        group = QGroupBox("默认设置")
        group_layout = QFormLayout(group)
        group_layout.setSpacing(6)
        
        self.default_mode_combo = QComboBox()
        self.default_mode_combo.addItem("单向同步", SyncMode.ONE_WAY.value)
        self.default_mode_combo.addItem("双向同步", SyncMode.TWO_WAY.value)
        group_layout.addRow("同步模式:", self.default_mode_combo)
        
        self.default_conflict_combo = QComboBox()
        self.default_conflict_combo.addItem("最新优先", ConflictStrategy.NEWEST_WINS.value)
        self.default_conflict_combo.addItem("源优先", ConflictStrategy.SOURCE_WINS.value)
        self.default_conflict_combo.addItem("目标优先", ConflictStrategy.TARGET_WINS.value)
        self.default_conflict_combo.addItem("保留双方", ConflictStrategy.KEEP_BOTH.value)
        self.default_conflict_combo.addItem("跳过", ConflictStrategy.SKIP.value)
        group_layout.addRow("冲突策略:", self.default_conflict_combo)
        
        layout.addWidget(group)
        
        # 监控设置
        monitor_group = QGroupBox("文件监控")
        monitor_layout = QFormLayout(monitor_group)
        monitor_layout.setSpacing(6)
        
        self.debounce_spin = QSpinBox()
        self.debounce_spin.setRange(100, 5000)
        self.debounce_spin.setValue(1000)
        self.debounce_spin.setSuffix(" ms")
        monitor_layout.addRow("防抖时间:", self.debounce_spin)
        
        self.ignore_hidden_check = QCheckBox()
        self.ignore_hidden_check.setChecked(True)
        monitor_layout.addRow("忽略隐藏文件:", self.ignore_hidden_check)
        
        layout.addWidget(monitor_group)
        
        layout.addStretch()
        return widget
    
    def _create_notify_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        group = QGroupBox("通知设置")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)
        
        self.notify_check = QCheckBox("启用系统通知")
        self.notify_check.setChecked(True)
        group_layout.addWidget(self.notify_check)
        
        sep = QLabel("通知类型:")
        sep.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 9px; margin-top: 4px;")
        group_layout.addWidget(sep)
        
        self.notify_delete_check = QCheckBox("文件删除时通知")
        self.notify_delete_check.setChecked(True)
        group_layout.addWidget(self.notify_delete_check)
        
        self.notify_conflict_check = QCheckBox("文件冲突时通知")
        self.notify_conflict_check.setChecked(True)
        group_layout.addWidget(self.notify_conflict_check)
        
        self.notify_error_check = QCheckBox("发生错误时通知")
        self.notify_error_check.setChecked(True)
        group_layout.addWidget(self.notify_error_check)
        
        layout.addWidget(group)
        layout.addStretch()
        return widget
    
    def _load_settings(self):
        self.auto_start_check.setChecked(config_manager.get("general.auto_start", False))
        self.minimize_to_tray_check.setChecked(config_manager.get("general.minimize_to_tray", True))
        
        # UI设置
        self.log_refresh_spin.setValue(config_manager.get("ui.log_refresh_interval", 3))
        
        # 存储路径
        self.storage_path_edit.setText(config_manager.get("general.storage_path", DATA_DIR))
        
        # 备份
        mode = config_manager.get("backup.default_sync_mode", SyncMode.ONE_WAY.value)
        idx = self.default_mode_combo.findData(mode)
        if idx >= 0:
            self.default_mode_combo.setCurrentIndex(idx)
        
        strategy = config_manager.get("backup.default_conflict_strategy", ConflictStrategy.NEWEST_WINS.value)
        idx = self.default_conflict_combo.findData(strategy)
        if idx >= 0:
            self.default_conflict_combo.setCurrentIndex(idx)
        
        debounce = config_manager.get("monitor.debounce_seconds", 1.0)
        self.debounce_spin.setValue(int(debounce * 1000))
        self.ignore_hidden_check.setChecked(config_manager.get("monitor.ignore_hidden", True))
        
        # 通知
        self.notify_check.setChecked(config_manager.get("general.show_notifications", True))
        self.notify_delete_check.setChecked(config_manager.get("notifications.on_delete", True))
        self.notify_conflict_check.setChecked(config_manager.get("notifications.on_conflict", True))
        self.notify_error_check.setChecked(config_manager.get("notifications.on_error", True))
    
    def _save_settings(self):
        # 常规
        config_manager.set("general.auto_start", self.auto_start_check.isChecked())
        config_manager.set("general.minimize_to_tray", self.minimize_to_tray_check.isChecked())
        config_manager.set("general.show_notifications", self.notify_check.isChecked())
        
        # UI
        config_manager.set("ui.log_refresh_interval", self.log_refresh_spin.value())
        
        # 通知
        config_manager.set("notifications.on_delete", self.notify_delete_check.isChecked())
        config_manager.set("notifications.on_conflict", self.notify_conflict_check.isChecked())
        config_manager.set("notifications.on_error", self.notify_error_check.isChecked())
        
        # 备份
        config_manager.set("backup.default_sync_mode", self.default_mode_combo.currentData())
        config_manager.set("backup.default_conflict_strategy", self.default_conflict_combo.currentData())
        
        # 监控
        config_manager.set("monitor.debounce_seconds", self.debounce_spin.value() / 1000.0)
        config_manager.set("monitor.ignore_hidden", self.ignore_hidden_check.isChecked())
        
        # 存储
        old_path = config_manager.get("general.storage_path", DATA_DIR)
        new_path = self.storage_path_edit.text()
        if old_path != new_path:
            config_manager.set("general.storage_path", new_path)
            # 通知日志管理器更换路径
            logger.update_storage_path(new_path)
        
        config_manager.save_config()
        self.accept()
