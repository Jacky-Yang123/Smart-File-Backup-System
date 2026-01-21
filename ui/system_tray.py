"""
系统托盘模块 - 优化版
"""
from PyQt5.QtWidgets import (
    QSystemTrayIcon, QMenu, QAction, QApplication
)
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QBrush
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRectF

from utils.constants import APP_NAME
from utils.config_manager import config_manager
from core.task_manager import task_manager


def create_app_icon(status: str = "idle") -> QIcon:
    """
    创建应用图标
    
    Args:
        status: 状态 (idle, running, paused, error)
    """
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # 根据状态选择颜色
    colors = {
        "running": "#22c55e",  # 绿色
        "syncing": "#f59e0b",  # 橙色 - 同步中
        "paused": "#f59e0b",   # 黄色
        "error": "#ef4444",    # 红色
        "idle": "#6366f1",     # 蓝色
    }
    main_color = QColor(colors.get(status, "#6366f1"))
    
    # 绘制外圈
    painter.setPen(QPen(main_color, 3))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(6, 6, 52, 52)
    
    # 绘制内部双箭头同步图标
    painter.setPen(QPen(main_color, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    
    # 上半圆箭头
    painter.drawArc(18, 20, 28, 24, 30 * 16, 120 * 16)
    # 箭头头部
    painter.drawLine(44, 26, 44, 20)
    painter.drawLine(44, 26, 38, 24)
    
    # 下半圆箭头
    painter.drawArc(18, 20, 28, 24, 210 * 16, 120 * 16)
    # 箭头头部
    painter.drawLine(20, 38, 20, 44)
    painter.drawLine(20, 38, 26, 40)
    
    painter.end()
    
    return QIcon(pixmap)


class SystemTray(QObject):
    """系统托盘"""
    
    show_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray_icon = None
        self._notification_enabled = True
        self._notify_on_delete = True
        self._notify_on_conflict = True
        self._notify_on_error = True
        self._init_tray()
        self._load_notification_settings()
    
    def _load_notification_settings(self):
        """加载通知设置"""
        self._notification_enabled = config_manager.get("general.show_notifications", True)
        self._notify_on_delete = config_manager.get("notifications.on_delete", True)
        self._notify_on_conflict = config_manager.get("notifications.on_conflict", True)
        self._notify_on_error = config_manager.get("notifications.on_error", True)
    
    def _init_tray(self):
        """初始化托盘"""
        self._tray_icon = QSystemTrayIcon(self.parent())
        self._tray_icon.setIcon(create_app_icon("idle"))
        self._tray_icon.setToolTip(APP_NAME)
        
        # 创建菜单
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
                font-size: 12px;
                color: #f8fafc;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #475569;
            }
            QMenu::separator {
                height: 1px;
                background-color: #334155;
                margin: 4px 8px;
            }
        """)
        
        # 显示主窗口
        show_action = QAction("📺 显示主窗口", menu)
        show_action.triggered.connect(self._on_show)
        menu.addAction(show_action)
        
        menu.addSeparator()
        
        # 开始所有任务
        start_all_action = QAction("▶ 开始所有任务", menu)
        start_all_action.triggered.connect(self._on_start_all)
        menu.addAction(start_all_action)
        
        # 停止所有任务
        stop_all_action = QAction("⏹ 停止所有任务", menu)
        stop_all_action.triggered.connect(self._on_stop_all)
        menu.addAction(stop_all_action)
        
        menu.addSeparator()
        
        # 状态信息
        self._status_action = QAction("● 状态: 就绪", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        
        menu.addSeparator()
        
        # 退出
        quit_action = QAction("✕ 退出程序", menu)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)
        
        self._tray_icon.setContextMenu(menu)
        
        # 双击显示窗口
        self._tray_icon.activated.connect(self._on_activated)
    
    def _on_show(self):
        """显示主窗口"""
        self.show_requested.emit()
    
    def _on_start_all(self):
        """开始所有任务"""
        task_manager.start_all()
        self.show_notification("备份任务", "已启动所有备份任务", "info")
    
    def _on_stop_all(self):
        """停止所有任务"""
        task_manager.stop_all()
        self.show_notification("备份任务", "已停止所有备份任务", "info")
    
    def _on_quit(self):
        """退出程序"""
        self.quit_requested.emit()
    
    def _on_activated(self, reason):
        """托盘图标被激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_requested.emit()
    
    def show(self):
        """显示托盘图标"""
        self._tray_icon.show()
    
    def hide(self):
        """隐藏托盘图标"""
        self._tray_icon.hide()
    
    def show_notification(self, title: str, message: str, 
                         notification_type: str = "info",
                         force: bool = False):
        """
        显示通知
        
        Args:
            title: 标题
            message: 消息内容
            notification_type: 类型 (info, warning, error, delete, conflict)
            force: 强制显示（忽略用户设置）
        """
        if not force and not self._notification_enabled:
            return
        
        # 根据类型检查是否应该显示
        if notification_type == "delete" and not self._notify_on_delete:
            return
        if notification_type == "conflict" and not self._notify_on_conflict:
            return
        if notification_type == "error" and not self._notify_on_error:
            return
        
        # 选择图标
        icon_map = {
            "info": QSystemTrayIcon.Information,
            "warning": QSystemTrayIcon.Warning,
            "error": QSystemTrayIcon.Critical,
            "delete": QSystemTrayIcon.Warning,
            "conflict": QSystemTrayIcon.Warning,
        }
        icon = icon_map.get(notification_type, QSystemTrayIcon.Information)
        
        self._tray_icon.showMessage(title, message, icon, 3000)
    
    def notify_file_deleted(self, filename: str, task_name: str):
        """通知文件删除"""
        self.show_notification(
            "文件删除",
            f"任务 [{task_name}]\n{filename}",
            "delete"
        )
    
    def notify_conflict(self, filename: str, task_name: str, resolution: str):
        """通知文件冲突"""
        self.show_notification(
            "文件冲突",
            f"任务 [{task_name}]\n{filename}\n处理: {resolution}",
            "conflict"
        )
    
    def notify_error(self, message: str, task_name: str = None):
        """通知错误"""
        title = f"错误 - {task_name}" if task_name else "备份错误"
        self.show_notification(title, message, "error")
    
    def update_status(self, running_count: int):
        """更新状态"""
        if running_count > 0:
            status = f"● {running_count} 个任务运行中"
            self.set_icon_status("running")
        else:
            status = "○ 就绪"
            self.set_icon_status("idle")
        
        self._status_action.setText(status)
        self._tray_icon.setToolTip(f"{APP_NAME}\n{status}")
    
    def set_icon_status(self, status: str):
        """设置图标状态"""
        self._tray_icon.setIcon(create_app_icon(status))
    
    def update_notification_settings(self):
        """更新通知设置"""
        self._load_notification_settings()
    
    def set_notification_enabled(self, enabled: bool):
        """设置是否启用通知"""
        self._notification_enabled = enabled
    
    def set_notify_on_delete(self, enabled: bool):
        """设置删除时是否通知"""
        self._notify_on_delete = enabled
        config_manager.set("notifications.on_delete", enabled)
        config_manager.save_config()
    
    def set_notify_on_conflict(self, enabled: bool):
        """设置冲突时是否通知"""
        self._notify_on_conflict = enabled
        config_manager.set("notifications.on_conflict", enabled)
        config_manager.save_config()
    
    def set_notify_on_error(self, enabled: bool):
        """设置错误时是否通知"""
        self._notify_on_error = enabled
        config_manager.set("notifications.on_error", enabled)
        config_manager.save_config()
