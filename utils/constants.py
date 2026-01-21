"""
常量定义模块
"""
import os
from enum import Enum

# 应用信息
APP_NAME = "智能文件备份系统"
APP_VERSION = "1.0.0"
APP_AUTHOR = "SmartBackup"

# 目录路径
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(APP_DIR, "data")
RESOURCES_DIR = os.path.join(APP_DIR, "resources")

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 配置文件路径
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
DATABASE_FILE = os.path.join(DATA_DIR, "backup.db")
LOG_FILE = os.path.join(DATA_DIR, "backup.log")


class SyncMode(Enum):
    """同步模式"""
    ONE_WAY = "one_way"  # 单向同步 (源 → 目标)
    TWO_WAY = "two_way"  # 双向同步


class ConflictStrategy(Enum):
    """冲突处理策略"""
    NEWEST_WINS = "newest_wins"  # 最新时间优先
    SOURCE_WINS = "source_wins"  # 源文件优先
    TARGET_WINS = "target_wins"  # 目标文件优先
    KEEP_BOTH = "keep_both"      # 保留双方
    ASK_USER = "ask_user"        # 询问用户
    SKIP = "skip"                # 跳过


class TaskStatus(Enum):
    """任务状态"""
    STOPPED = "stopped"    # 已停止
    RUNNING = "running"    # 运行中
    PAUSED = "paused"      # 已暂停
    ERROR = "error"        # 错误


class FileEventType(Enum):
    """文件事件类型"""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# 默认配置
DEFAULT_CONFIG = {
    "general": {
        "auto_start": False,          # 开机自启动
        "minimize_to_tray": True,     # 最小化到托盘
        "show_notifications": True,   # 显示通知
        "language": "zh_CN",          # 语言
        "storage_path": DATA_DIR       # 日志和配置存储根路径
    },
    "backup": {
        "default_sync_mode": SyncMode.ONE_WAY.value,
        "default_conflict_strategy": ConflictStrategy.NEWEST_WINS.value,
        "max_concurrent_tasks": 3,    # 最大并发任务数
        "compare_method": "mtime",    # 比较方式: mtime, hash
        "buffer_size": 1024 * 1024    # 文件复制缓冲区大小 (1MB)
    },
    "log": {
        "level": LogLevel.INFO.value,
        "max_days": 30,               # 日志保留天数
        "max_size_mb": 100            # 日志最大大小
    },
    "monitor": {
        "debounce_seconds": 1.0,      # 事件防抖时间
        "ignore_hidden": True         # 忽略隐藏文件
    }
}

# 常用文件类型
FILE_TYPE_GROUPS = {
    "文档": [".doc", ".docx", ".pdf", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".rtf"],
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff"],
    "视频": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
    "音频": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"],
    "代码": [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".cs", ".go", ".rs", ".php"],
    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
}
