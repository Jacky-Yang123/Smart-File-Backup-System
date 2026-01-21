"""
提醒面板模块 - 用于显示和处理安全警告
"""
from datetime import datetime
from typing import Callable, Dict
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QScrollArea, QSizePolicy,
    QListWidget, QListWidgetItem, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from .styles import COLORS

class AlertCard(QFrame):
    """提醒卡片"""
    
    handled = pyqtSignal(str, bool, list)  # alert_id, is_approved, selected_data
    
    def __init__(self, alert_id: str, title: str, task_name: str, message: str, 
                 timestamp: datetime, batch_data: list = None, parent=None):
        super().__init__(parent)
        self.alert_id = alert_id
        self.setObjectName("alert_card")
        self.setStyleSheet(f"""
            QFrame#alert_card {{
                background-color: {COLORS['bg_light']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
            QFrame#alert_card:hover {{
                border: 1px solid {COLORS['warning']};
            }}
        """)
        
        self.batch_data = batch_data or []
        self._init_ui(title, task_name, message, timestamp)
        
    def _init_ui(self, title: str, task_name: str, message: str, timestamp: datetime):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 头部：标题和时间
        header = QHBoxLayout()
        title_label = QLabel(f"⚠️ {title}")
        title_label.setStyleSheet(f"color: {COLORS['warning']}; font-weight: bold; font-size: 13px;")
        header.addWidget(title_label)
        
        header.addStretch()
        
        time_str = timestamp.strftime("%H:%M:%S")
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        header.addWidget(time_label)
        
        layout.addLayout(header)
        
        # 任务名
        task_label = QLabel(f"任务: {task_name}")
        task_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: 600;")
        layout.addWidget(task_label)
        
        # 消息内容
        self.msg_label = QLabel(message)
        self.msg_label.setWordWrap(True)
        self.msg_label.setStyleSheet(f"color: {COLORS['text_secondary']}; margin: 4px 0;")
        layout.addWidget(self.msg_label)
        
        # 详细列表区域 (默认隐藏)
        if self.batch_data:
            self.details_container = QWidget()
            details_layout = QVBoxLayout(self.details_container)
            details_layout.setContentsMargins(0, 0, 0, 0)
            
            # 操作栏
            action_bar = QHBoxLayout()
            self.select_all_btn = QPushButton("全选")
            self.select_all_btn.setFixedSize(60, 24)
            self.select_all_btn.clicked.connect(self._select_all)
            
            self.deselect_all_btn = QPushButton("全不选")
            self.deselect_all_btn.setFixedSize(60, 24)
            self.deselect_all_btn.clicked.connect(self._deselect_all)
            
            action_bar.addWidget(self.select_all_btn)
            action_bar.addWidget(self.deselect_all_btn)
            action_bar.addStretch()
            details_layout.addLayout(action_bar)
            
            # 列表
            self.list_widget = QListWidget()
            self.list_widget.setSelectionMode(QListWidget.NoSelection) # 通过 checkbox 选择
            self.list_widget.setFixedHeight(200)
            self._populate_list()
            details_layout.addWidget(self.list_widget)
            
            self.details_container.setVisible(False)
            layout.addWidget(self.details_container)
            
            # 展开/收起按钮
            self.toggle_details_btn = QPushButton("查看详情/选择操作 (0)")
            self.toggle_details_btn.setStyleSheet(f"color: {COLORS['accent']}; text-align: left; border: none; background: transparent;")
            self.toggle_details_btn.setCursor(Qt.PointingHandCursor)
            self.toggle_details_btn.clicked.connect(self._toggle_details)
            layout.addWidget(self.toggle_details_btn)
            self._update_toggle_text()
        
        
        # 按钮栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setProperty("class", "secondary")
        cancel_btn.setFixedSize(80, 28)
        cancel_btn.clicked.connect(lambda: self.handled.emit(self.alert_id, False, []))
        btn_layout.addWidget(cancel_btn)
        
        continue_btn = QPushButton("执行选中操作")
        continue_btn.setProperty("class", "warning")
        continue_btn.setFixedSize(100, 28)
        continue_btn.clicked.connect(self._on_continue)
        btn_layout.addWidget(continue_btn)
        
        layout.addLayout(btn_layout)

    def _populate_list(self):
        import os
        self.list_widget.clear()
        for idx, item in enumerate(self.batch_data):
            event = item[0]
            action_name = event.event_type.value
            filename = os.path.basename(event.src_path)
            
            # 创建 item
            list_item = QListWidgetItem(self.list_widget)
            # 自定义 widget
            item_widget = QCheckBox(f"[{action_name}] {filename}")
            item_widget.setChecked(True)
            
            self.list_widget.setItemWidget(list_item, item_widget)
            
            # 存储原始数据索引
            list_item.setData(Qt.UserRole, idx)

    def _toggle_details(self):
        is_visible = self.details_container.isVisible()
        self.details_container.setVisible(not is_visible)
        
    def _update_toggle_text(self):
        count = len(self.batch_data)
        self.toggle_details_btn.setText(f"查看详情/选择操作 ({count})")

    def _select_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                widget.setChecked(True)

    def _deselect_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                widget.setChecked(False)

    def _on_continue(self):
        selected_data = []
        if self.batch_data:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                widget = self.list_widget.itemWidget(item)
                if widget and widget.isChecked():
                    original_idx = item.data(Qt.UserRole)
                    if 0 <= original_idx < len(self.batch_data):
                        selected_data.append(self.batch_data[original_idx])
        else:
            # 如果没有 batch_data (旧逻辑兼容)，则认为是全选（但这里实际上 batch_data 为空所以也没东西）
            # 或者应该处理为 True
            selected_data = [] 
            
        self.handled.emit(self.alert_id, True, selected_data)
        
    def update_data(self, message: str, new_batch_data: list):
        """更新数据"""
        self.msg_label.setText(message)
        
        # 将新数据追加到列表
        current_count = len(self.batch_data)
        self.batch_data.extend(new_batch_data)
        
        import os
        for idx, item in enumerate(new_batch_data):
            event = item[0]
            action_name = event.event_type.value
            filename = os.path.basename(event.src_path)
            
            list_item = QListWidgetItem(self.list_widget)
            item_widget = QCheckBox(f"[{action_name}] {filename}")
            item_widget.setChecked(True) # 新增的默认选中
            self.list_widget.setItemWidget(list_item, item_widget)
            # 这里的 index 是全局 index
            list_item.setData(Qt.UserRole, current_count + idx)
            
        self._update_toggle_text()


class AlertPanel(QWidget):
    """提醒面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._alerts: Dict[str, Callable] = {}  # id -> success_callback
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet(f"background-color: {COLORS['bg_medium']}; border-bottom: 1px solid {COLORS['border']};")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 15, 20, 15)
        
        title = QLabel("安全提醒")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']};")
        title_layout.addWidget(title)
        
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet(f"""
            background-color: {COLORS['warning']}; 
            color: #fff; 
            border-radius: 10px; 
            padding: 2px 8px; 
            font-weight: bold;
            font-size: 12px;
        """)
        self.count_label.setVisible(False)
        title_layout.addWidget(self.count_label)
        
        title_layout.addStretch()
        
        layout.addWidget(title_bar)
        
        # 内容区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(12)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.addStretch()
        
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)
        
        # 空状态提示
        self.empty_label = QLabel("暂无待处理的安全提醒")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px;")
        
        # 初始显示空状态（通过调整布局或可见性）
        layout.addWidget(self.empty_label)
        self.empty_label.setVisible(True)
        scroll.setVisible(False)
        
        self.scroll = scroll  # 保存引用以便切换显示
        
    def add_alert(self, title: str, task_name: str, message: str, callback: Callable, batch_data: list = None):
        """添加提醒"""
        import uuid
        alert_id = str(uuid.uuid4())
        
        self._alerts[alert_id] = callback
        
        card = AlertCard(alert_id, title, task_name, message, datetime.now(), batch_data)
        card.handled.connect(self._on_alert_handled)
        
        # 插入到最新的位置（顶部）
        self.content_layout.insertWidget(0, card)
        
        self._update_ui_state()
        return alert_id
        
    def update_alert(self, alert_id: str, new_message: str, new_batch_data: list = None):
        """更新提醒消息和数据"""
        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if isinstance(widget, AlertCard) and widget.alert_id == alert_id:
                widget.update_data(new_message, new_batch_data or [])
                break
        
    def _on_alert_handled(self, alert_id: str, is_approved: bool, selected_data: list):
        """处理提醒结果"""
        # 找到对应的卡片并移除
        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if isinstance(widget, AlertCard) and widget.alert_id == alert_id:
                widget.deleteLater()
                break
        
        # 如果批准，执行回调
        if is_approved and alert_id in self._alerts:
            try:
                # 回调现在接收 selected_data
                self._alerts[alert_id](selected_data)
            except Exception as e:
                print(f"Error executing alert callback: {e}")
        
        # 清理回调
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            
        self._update_ui_state()
        
    def _update_ui_state(self):
        """更新UI状态（空/非空）"""
        count = len(self._alerts)
        
        self.count_label.setText(str(count))
        self.count_label.setVisible(count > 0)
        
        self.empty_label.setVisible(count == 0)
        self.scroll.setVisible(count > 0)
