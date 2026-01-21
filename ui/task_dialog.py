"""
任务配置对话框模块 - 优化版
"""
import os
from typing import Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QListWidget, QTabWidget, QWidget, QFileDialog, QMessageBox, QSpinBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt

from utils.constants import SyncMode, ConflictStrategy, FILE_TYPE_GROUPS
from core.task_manager import BackupTask
from .styles import COLORS


class TaskDialog(QDialog):
    """任务配置对话框 - 优化版"""
    
    def __init__(self, parent=None, task: Optional[BackupTask] = None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("编辑任务" if task else "新建任务")
        self.setFixedSize(500, 450)
        self.setModal(True)
        self.setStyleSheet(f"background-color: {COLORS['bg_dark']};")
        
        self._init_ui()
        if task:
            self._load_task(task)
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget, 1)
        
        tab_widget.addTab(self._create_basic_tab(), "基本")
        tab_widget.addTab(self._create_sync_tab(), "同步")
        tab_widget.addTab(self._create_filter_tab(), "过滤")
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.setFixedHeight(28)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.setFixedHeight(28)
        save_btn.clicked.connect(self._save_task)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_basic_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)
        
        form = QFormLayout()
        form.setSpacing(8)
        
        # 任务名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入任务名称")
        form.addRow("名称:", self.name_edit)
        
        # 源文件夹
        source_layout = QHBoxLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("选择源文件夹")
        source_layout.addWidget(self.source_edit)
        
        source_btn = QPushButton("...")
        source_btn.setFixedWidth(36)
        source_btn.clicked.connect(self._select_source)
        source_layout.addWidget(source_btn)
        form.addRow("源文件夹:", source_layout)
        
        layout.addLayout(form)
        
        # 目标文件夹
        target_label = QLabel("目标文件夹:")
        target_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(target_label)
        
        self.target_list = QListWidget()
        self.target_list.setMaximumHeight(90)
        layout.addWidget(self.target_list)
        
        target_btn_layout = QHBoxLayout()
        add_target_btn = QPushButton("+ 添加目标")
        add_target_btn.setFixedHeight(26)
        add_target_btn.clicked.connect(self._add_target)
        target_btn_layout.addWidget(add_target_btn)
        
        remove_target_btn = QPushButton("- 移除")
        remove_target_btn.setProperty("class", "secondary")
        remove_target_btn.setFixedHeight(26)
        remove_target_btn.clicked.connect(self._remove_target)
        target_btn_layout.addWidget(remove_target_btn)
        
        target_btn_layout.addStretch()
        layout.addLayout(target_btn_layout)
        
        # 选项
        self.enabled_check = QCheckBox("启用任务")
        self.enabled_check.setChecked(True)
        layout.addWidget(self.enabled_check)
        
        self.auto_start_check = QCheckBox("程序启动时自动开始")
        layout.addWidget(self.auto_start_check)
        
        layout.addStretch()
        return widget
    
    def _create_sync_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)
        
        form = QFormLayout()
        form.setSpacing(8)
        
        # 同步模式
        self.sync_mode_combo = QComboBox()
        self.sync_mode_combo.addItem("单向同步 (源 → 目标)", SyncMode.ONE_WAY.value)
        self.sync_mode_combo.addItem("双向同步", SyncMode.TWO_WAY.value)
        self.sync_mode_combo.currentIndexChanged.connect(self._on_sync_mode_changed)
        form.addRow("同步模式:", self.sync_mode_combo)
        
        # 冲突策略
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("最新优先", ConflictStrategy.NEWEST_WINS.value)
        self.conflict_combo.addItem("源优先", ConflictStrategy.SOURCE_WINS.value)
        self.conflict_combo.addItem("目标优先", ConflictStrategy.TARGET_WINS.value)
        self.conflict_combo.addItem("保留双方", ConflictStrategy.KEEP_BOTH.value)
        self.conflict_combo.addItem("跳过", ConflictStrategy.SKIP.value)
        form.addRow("冲突处理:", self.conflict_combo)
        
        # 监控模式
        self.monitor_mode_combo = QComboBox()
        self.monitor_mode_combo.addItem("实时监控 (watchdog)", "realtime")
        self.monitor_mode_combo.addItem("轮询模式 (定时检测)", "polling")
        self.monitor_mode_combo.currentIndexChanged.connect(self._on_monitor_mode_changed)
        form.addRow("监控模式:", self.monitor_mode_combo)
        
        # 轮询间隔
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 60)
        self.poll_interval_spin.setValue(5)
        self.poll_interval_spin.setSuffix(" 秒")
        self.poll_interval_spin.setEnabled(False)
        form.addRow("轮询间隔:", self.poll_interval_spin)
        
        layout.addLayout(form)
        
        # 删除选项组
        delete_group = QLabel("删除文件处理:")
        delete_group.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; margin-top: 8px;")
        layout.addWidget(delete_group)
        
        self.delete_orphans_check = QCheckBox("全量同步时删除目标中多余的文件")
        self.delete_orphans_check.setToolTip("执行全量同步时，删除目标目录中存在但源目录中不存在的文件")
        layout.addWidget(self.delete_orphans_check)
        
        self.reverse_delete_check = QCheckBox("目标文件删除时，同步删除源文件 (仅单向同步)")
        self.reverse_delete_check.setToolTip("当目标目录中的文件被删除时，源目录中对应的文件也会被删除")
        self.reverse_delete_check.setStyleSheet(f"color: {COLORS['warning']};")
        layout.addWidget(self.reverse_delete_check)
        
        # 警告说明
        warning_label = QLabel("⚠️ 启用反向删除可能导致源文件丢失，请谨慎使用！")
        warning_label.setStyleSheet(f"color: {COLORS['warning']}; font-size: 10px; margin-top: 4px;")
        warning_label.setVisible(False)
        self.warning_label = warning_label
        layout.addWidget(warning_label)
        
        self.reverse_delete_check.stateChanged.connect(
            lambda s: warning_label.setVisible(s == Qt.Checked)
        )
        
        # 禁止删除选项
        self.disable_delete_check = QCheckBox("禁止删除操作 (安全模式)")
        self.disable_delete_check.setToolTip("启用后，程序不会删除任何文件，即使源文件已被删除，目标文件也会保留")
        self.disable_delete_check.setStyleSheet(f"color: {COLORS['success']};")
        layout.addWidget(self.disable_delete_check)
        
        # 文件数量差异阈值（双向同步）
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("双向同步文件数量差异警告阈值:")
        threshold_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(1, 1000)
        self.threshold_spinbox.setValue(20)
        self.threshold_spinbox.setToolTip("当源文件夹与目标文件夹的文件数量差异超过此阈值时，会显示警告")
        self.threshold_spinbox.setFixedWidth(80)
        threshold_layout.addWidget(self.threshold_spinbox)
        threshold_layout.addStretch()
        layout.addLayout(threshold_layout)
        
        safety_layout = QHBoxLayout()
        safety_label = QLabel("单次同步最大变更安全阈值:")
        safety_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        safety_layout.addWidget(safety_label)
        
        self.safety_spinbox = QSpinBox()
        self.safety_spinbox.setRange(1, 10000)
        self.safety_spinbox.setValue(50)
        self.safety_spinbox.setToolTip("当单次同步涉及的文件变更(含删除)超过此阈值时，会显示警告")
        self.safety_spinbox.setFixedWidth(80)
        safety_layout.addWidget(self.safety_spinbox)
        safety_layout.addStretch()
        layout.addLayout(safety_layout)
        
        # 批量防抖延迟
        delay_layout = QHBoxLayout()
        delay_label = QLabel("批量操作防抖延迟 (秒):")
        delay_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        delay_layout.addWidget(delay_label)
        
        self.batch_delay_spin = QDoubleSpinBox()
        self.batch_delay_spin.setRange(0.1, 60.0)
        self.batch_delay_spin.setValue(1.0)
        self.batch_delay_spin.setSingleStep(0.5)
        self.batch_delay_spin.setToolTip("检测到文件变更后等待的时间，用于聚合多次短时间内的操作")
        self.batch_delay_spin.setFixedWidth(80)
        delay_layout.addWidget(self.batch_delay_spin)
        delay_layout.addStretch()
        layout.addLayout(delay_layout)
        
        layout.addStretch()
        return widget
    
    def _on_sync_mode_changed(self, index):
        """同步模式改变时更新UI"""
        is_one_way = self.sync_mode_combo.currentData() == SyncMode.ONE_WAY.value
        self.reverse_delete_check.setEnabled(is_one_way)
        if not is_one_way:
            self.reverse_delete_check.setChecked(False)
    
    def _on_monitor_mode_changed(self, index):
        """监控模式改变时更新UI"""
        is_polling = self.monitor_mode_combo.currentData() == "polling"
        self.poll_interval_spin.setEnabled(is_polling)
    
    def _create_filter_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # 包含
        include_label = QLabel("包含文件类型 (留空=全部):")
        include_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(include_label)
        
        self.include_edit = QLineEdit()
        self.include_edit.setPlaceholderText("例如: *.txt, *.doc, *.py")
        layout.addWidget(self.include_edit)
        
        # 排除
        exclude_label = QLabel("排除文件/文件夹:")
        exclude_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(exclude_label)
        
        self.exclude_edit = QLineEdit()
        self.exclude_edit.setPlaceholderText("例如: *.tmp, node_modules, __pycache__")
        layout.addWidget(self.exclude_edit)
        
        # 常用排除
        self.exclude_hidden_check = QCheckBox("排除隐藏文件 (以.开头)")
        self.exclude_hidden_check.setChecked(True)
        layout.addWidget(self.exclude_hidden_check)
        
        self.exclude_temp_check = QCheckBox("排除临时文件 (*.tmp, *.bak, *.swp)")
        self.exclude_temp_check.setChecked(True)
        layout.addWidget(self.exclude_temp_check)
        
        # 常用开发文件夹排除
        dev_folder_label = QLabel("常用开发文件夹排除:")
        dev_folder_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; margin-top: 6px;")
        layout.addWidget(dev_folder_label)
        
        self.exclude_git_check = QCheckBox(".git (版本控制)")
        self.exclude_git_check.setChecked(True)
        layout.addWidget(self.exclude_git_check)
        
        self.exclude_node_modules_check = QCheckBox("node_modules (Node.js依赖)")
        self.exclude_node_modules_check.setChecked(True)
        layout.addWidget(self.exclude_node_modules_check)
        
        self.exclude_pycache_check = QCheckBox("__pycache__ (Python缓存)")
        self.exclude_pycache_check.setChecked(True)
        layout.addWidget(self.exclude_pycache_check)
        
        self.exclude_venv_check = QCheckBox("venv / .venv (Python虚拟环境)")
        self.exclude_venv_check.setChecked(True)
        layout.addWidget(self.exclude_venv_check)
        
        self.exclude_idea_check = QCheckBox(".idea / .vscode (IDE配置)")
        self.exclude_idea_check.setChecked(False)
        layout.addWidget(self.exclude_idea_check)
        
        self.exclude_build_check = QCheckBox("build / dist / target (构建产物)")
        self.exclude_build_check.setChecked(False)
        layout.addWidget(self.exclude_build_check)
        
        layout.addStretch()
        return widget
    
    def _select_source(self):
        folder = QFileDialog.getExistingDirectory(self, "选择源文件夹")
        if folder:
            self.source_edit.setText(folder)
    
    def _add_target(self):
        folder = QFileDialog.getExistingDirectory(self, "选择目标文件夹")
        if folder:
            # 检查重复
            for i in range(self.target_list.count()):
                if self.target_list.item(i).text() == folder:
                    return
            self.target_list.addItem(folder)
    
    def _remove_target(self):
        current = self.target_list.currentRow()
        if current >= 0:
            self.target_list.takeItem(current)
    
    def _load_task(self, task: BackupTask):
        self.name_edit.setText(task.name)
        self.source_edit.setText(task.source_path)
        
        for target in task.target_paths:
            self.target_list.addItem(target)
        
        self.enabled_check.setChecked(task.enabled)
        self.auto_start_check.setChecked(task.auto_start)
        
        idx = self.sync_mode_combo.findData(task.sync_mode)
        if idx >= 0:
            self.sync_mode_combo.setCurrentIndex(idx)
        
        idx = self.conflict_combo.findData(task.conflict_strategy)
        if idx >= 0:
            self.conflict_combo.setCurrentIndex(idx)
        
        self.delete_orphans_check.setChecked(task.delete_orphans)
        self.reverse_delete_check.setChecked(getattr(task, 'reverse_delete', False))
        self.disable_delete_check.setChecked(getattr(task, 'disable_delete', False))
        self.disable_delete_check.setChecked(getattr(task, 'disable_delete', False))
        self.threshold_spinbox.setValue(getattr(task, 'file_count_diff_threshold', 20))
        self.safety_spinbox.setValue(getattr(task, 'safety_threshold', 50))
        self.batch_delay_spin.setValue(getattr(task, 'batch_delay', 1.0))
        
        # 监控模式
        monitor_mode = getattr(task, 'monitor_mode', 'realtime')
        idx = self.monitor_mode_combo.findData(monitor_mode)
        if idx >= 0:
            self.monitor_mode_combo.setCurrentIndex(idx)
        self.poll_interval_spin.setValue(getattr(task, 'poll_interval', 5))
        self._on_monitor_mode_changed(self.monitor_mode_combo.currentIndex())
        
        # 更新UI状态
        self._on_sync_mode_changed(self.sync_mode_combo.currentIndex())
        
        if task.include_patterns:
            self.include_edit.setText(", ".join(task.include_patterns))
        if task.exclude_patterns:
            # 过滤掉自动添加的排除模式
            custom_excludes = [p for p in task.exclude_patterns if p not in [".*", "*/.*", "*.tmp", "*.bak", "*.swp", "~*"]]
            if custom_excludes:
                self.exclude_edit.setText(", ".join(custom_excludes))
    
    def _save_task(self):
        name = self.name_edit.text().strip()
        source = self.source_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "提示", "请输入任务名称")
            return
        
        if not source or not os.path.isdir(source):
            QMessageBox.warning(self, "提示", "请选择有效的源文件夹")
            return
        
        targets = [self.target_list.item(i).text() for i in range(self.target_list.count())]
        if not targets:
            QMessageBox.warning(self, "提示", "请添加至少一个目标文件夹")
            return
        
        self.accept()
    
    def get_task(self) -> Optional[BackupTask]:
        name = self.name_edit.text().strip()
        source = self.source_edit.text().strip()
        targets = [self.target_list.item(i).text() for i in range(self.target_list.count())]
        
        excludes = []
        if self.exclude_edit.text().strip():
            excludes = [p.strip() for p in self.exclude_edit.text().split(",") if p.strip()]
        if self.exclude_hidden_check.isChecked():
            excludes.extend([".*", "*/.*"])
        if self.exclude_temp_check.isChecked():
            excludes.extend(["*.tmp", "*.bak", "*.swp", "~*"])
        if self.exclude_git_check.isChecked():
            excludes.extend([".git", "*/.git"])
        if self.exclude_node_modules_check.isChecked():
            excludes.extend(["node_modules", "*/node_modules"])
        if self.exclude_pycache_check.isChecked():
            excludes.extend(["__pycache__", "*/__pycache__"])
        if self.exclude_venv_check.isChecked():
            excludes.extend(["venv", ".venv", "*/venv", "*/.venv"])
        if self.exclude_idea_check.isChecked():
            excludes.extend([".idea", ".vscode", "*/.idea", "*/.vscode"])
        if self.exclude_build_check.isChecked():
            excludes.extend(["build", "dist", "target", "*/build", "*/dist", "*/target"])
        
        includes = []
        if self.include_edit.text().strip():
            includes = [p.strip() for p in self.include_edit.text().split(",") if p.strip()]
        
        return BackupTask(
            id=self.task.id if self.task else "",
            name=name,
            source_path=source,
            target_paths=targets,
            sync_mode=self.sync_mode_combo.currentData(),
            conflict_strategy=self.conflict_combo.currentData(),
            include_patterns=includes,
            exclude_patterns=excludes,
            enabled=self.enabled_check.isChecked(),
            auto_start=self.auto_start_check.isChecked(),
            delete_orphans=self.delete_orphans_check.isChecked(),
            reverse_delete=self.reverse_delete_check.isChecked(),
            disable_delete=self.disable_delete_check.isChecked(),
            file_count_diff_threshold=self.threshold_spinbox.value(),
            monitor_mode=self.monitor_mode_combo.currentData(),
            poll_interval=self.poll_interval_spin.value(),
            safety_threshold=self.safety_spinbox.value(),
            batch_delay=self.batch_delay_spin.value()
        )
