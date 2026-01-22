"""
UI样式定义模块 - 黑白渐变版 (优化字体大小)
"""

# 黑白灰主题色
COLORS = {
    "primary": "#ffffff",       # 主色调 - 白色
    "primary_hover": "#e5e5e5",
    "accent": "#888888",        # 强调色 - 灰色
    "success": "#4ade80",
    "warning": "#fbbf24",
    "error": "#f87171",
    "info": "#60a5fa",
    
    "bg_dark": "#0a0a0a",       # 最深背景
    "bg_medium": "#141414",     # 中等背景
    "bg_light": "#1f1f1f",      # 浅色背景
    "bg_card": "#181818",       # 卡片背景
    "bg_hover": "#2a2a2a",      # 悬停背景
    "bg_input": "#1a1a1a",      # 输入框背景
    
    "text_primary": "#ffffff",  # 主要文字
    "text_secondary": "#a0a0a0", # 次要文字
    "text_muted": "#666666",    # 暗淡文字
    
    "border": "#2a2a2a",        # 边框
    "border_light": "#3a3a3a",
}


# 全局样式表 - 优化字体大小
GLOBAL_STYLE = f"""
/* 全局样式 */
QWidget {{
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 12px;
    color: {COLORS["text_primary"]};
    background-color: transparent;
}}

QMainWindow {{
    background-color: {COLORS["bg_dark"]};
}}

/* 按钮样式 */
QPushButton {{
    background-color: {COLORS["bg_light"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 12px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: {COLORS["bg_hover"]};
    border-color: {COLORS["border_light"]};
}}

QPushButton:pressed {{
    background-color: {COLORS["bg_medium"]};
}}

QPushButton:disabled {{
    background-color: {COLORS["bg_medium"]};
    color: {COLORS["text_muted"]};
    border-color: {COLORS["border"]};
}}

QPushButton[class="primary"] {{
    background-color: {COLORS["text_primary"]};
    color: {COLORS["bg_dark"]};
    border: none;
}}

QPushButton[class="primary"]:hover {{
    background-color: {COLORS["primary_hover"]};
}}

QPushButton[class="success"] {{
    background-color: transparent;
    color: {COLORS["success"]};
    border-color: {COLORS["success"]};
}}

QPushButton[class="success"]:hover {{
    background-color: rgba(74, 222, 128, 0.15);
}}

QPushButton[class="secondary"] {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
    border-color: {COLORS["border"]};
}}

QPushButton[class="secondary"]:hover {{
    background-color: {COLORS["bg_hover"]};
    color: {COLORS["text_primary"]};
}}

QPushButton[class="icon"] {{
    background-color: transparent;
    border: none;
    padding: 4px;
    min-height: 24px;
    min-width: 24px;
    font-size: 14px;
    color: {COLORS["text_muted"]};
}}

QPushButton[class="icon"]:hover {{
    color: {COLORS["text_primary"]};
    background-color: {COLORS["bg_hover"]};
    border-radius: 4px;
}}

/* 输入框样式 */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {COLORS["bg_input"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
    color: {COLORS["text_primary"]};
    selection-background-color: {COLORS["accent"]};
}}

QLineEdit:focus, QTextEdit:focus {{
    border-color: {COLORS["text_muted"]};
}}

/* 下拉框样式 */
QComboBox {{
    background-color: {COLORS["bg_input"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    min-height: 24px;
}}

QComboBox::drop-down {{
    border: none;
    width: 18px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS["text_muted"]};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["bg_medium"]};
    border: 1px solid {COLORS["border"]};
    selection-background-color: {COLORS["bg_hover"]};
    font-size: 12px;
}}

/* 列表样式 */
QListWidget {{
    background-color: {COLORS["bg_input"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 2px;
    font-size: 12px;
}}

QListWidget::item {{
    padding: 4px 8px;
    border-radius: 3px;
}}

QListWidget::item:hover {{
    background-color: {COLORS["bg_hover"]};
}}

QListWidget::item:selected {{
    background-color: {COLORS["bg_light"]};
}}

/* 表格样式 */
QTableWidget {{
    background-color: {COLORS["bg_medium"]};
    border: 1px solid {COLORS["border"]};
    gridline-color: {COLORS["border"]};
    font-size: 11px;
}}

QTableWidget::item {{
    padding: 4px;
}}

QTableWidget::item:selected {{
    background-color: {COLORS["bg_hover"]};
}}

QHeaderView::section {{
    background-color: {COLORS["bg_dark"]};
    color: {COLORS["text_muted"]};
    padding: 5px;
    border: none;
    border-bottom: 1px solid {COLORS["border"]};
    font-size: 11px;
}}

/* 滚动条样式 */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["border"]};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS["text_muted"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS["border"]};
    min-width: 24px;
    border-radius: 4px;
}}

/* 标签页样式 */
QTabWidget::pane {{
    border: 1px solid {COLORS["border"]};
    background-color: {COLORS["bg_medium"]};
    border-radius: 4px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {COLORS["text_muted"]};
    padding: 6px 14px;
    font-size: 12px;
    border-bottom: 2px solid transparent;
}}

QTabBar::tab:hover {{
    color: {COLORS["text_secondary"]};
}}

QTabBar::tab:selected {{
    color: {COLORS["text_primary"]};
    border-bottom-color: {COLORS["text_primary"]};
}}

/* 复选框样式 */
QCheckBox {{
    color: {COLORS["text_primary"]};
    spacing: 8px;
    font-size: 12px;
    min-height: 22px;
    padding: 2px 0;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid {COLORS["border_light"]};
    background-color: transparent;
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS["text_primary"]};
    border-color: {COLORS["text_primary"]};
}}

/* 进度条样式 */
QProgressBar {{
    background-color: {COLORS["bg_light"]};
    border: none;
    border-radius: 3px;
    height: 6px;
}}

QProgressBar::chunk {{
    background-color: {COLORS["text_primary"]};
    border-radius: 3px;
}}

/* 分组框样式 */
QGroupBox {{
    background-color: transparent;
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    margin-top: 12px;
    padding: 10px;
    font-size: 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: {COLORS["text_muted"]};
}}

/* 工具提示样式 */
QToolTip {{
    background-color: {COLORS["bg_light"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    padding: 4px 8px;
    font-size: 11px;
}}

/* 菜单样式 */
QMenu {{
    background-color: {COLORS["bg_medium"]};
    border: 1px solid {COLORS["border"]};
    padding: 4px;
    font-size: 12px;
}}

QMenu::item {{
    padding: 5px 20px;
}}

QMenu::item:selected {{
    background-color: {COLORS["bg_hover"]};
}}

/* 对话框样式 */
QDialog {{
    background-color: {COLORS["bg_dark"]};
}}

/* 标签样式 */
QLabel {{
    color: {COLORS["text_primary"]};
    font-size: 12px;
    min-height: 18px;
}}

/* SpinBox样式 */
QSpinBox {{
    background-color: {COLORS["bg_input"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    min-height: 24px;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    width: 16px;
    border: none;
    background-color: transparent;
}}
"""


# 侧边栏样式
SIDEBAR_STYLE = f"""
QWidget#sidebar {{
    background-color: {COLORS["bg_medium"]};
}}

QPushButton#nav_button {{
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 8px 10px;
    text-align: left;
    font-size: 12px;
    color: {COLORS["text_muted"]};
}}

QPushButton#nav_button:hover {{
    background-color: {COLORS["bg_hover"]};
    color: {COLORS["text_secondary"]};
}}

QPushButton#nav_button:checked {{
    background-color: {COLORS["bg_light"]};
    color: {COLORS["text_primary"]};
}}
"""


# 任务卡片样式
TASK_CARD_STYLE = f"""
QFrame#task_card {{
    background-color: {COLORS["bg_card"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
}}

QFrame#task_card:hover {{
    border-color: {COLORS["border_light"]};
}}
"""


# 日志条目样式
LOG_STYLE = f"""
QTextEdit#log_viewer {{
    background-color: {COLORS["bg_dark"]};
    border: 1px solid {COLORS["border"]};
    font-family: "Consolas", monospace;
    font-size: 11px;
}}
"""


# 状态栏样式
STATUSBAR_STYLE = f"""
QStatusBar {{
    background-color: {COLORS["bg_medium"]};
    border-top: 1px solid {COLORS["border"]};
}}

QStatusBar QLabel {{
    color: {COLORS["text_muted"]};
    font-size: 11px;
}}
"""


def get_status_color(status: str) -> str:
    """获取状态对应的颜色"""
    status_colors = {
        "running": COLORS["success"],
        "paused": COLORS["warning"],
        "stopped": COLORS["text_muted"],
        "error": COLORS["error"],
    }
    return status_colors.get(status, COLORS["text_muted"])


def get_log_color(level: str) -> str:
    """获取日志级别对应的颜色"""
    level_colors = {
        "DEBUG": COLORS["text_muted"],
        "INFO": COLORS["info"],
        "WARNING": COLORS["warning"],
        "ERROR": COLORS["error"],
    }
    return level_colors.get(level.upper(), COLORS["text_primary"])
