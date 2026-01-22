"""
智能文件自动备份系统
主程序入口
"""
import sys
import os
import traceback
from datetime import datetime

# 添加项目根目录到Python路径
if getattr(sys, 'frozen', False):
    project_root = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
else:
    project_root = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = project_root
sys.path.insert(0, project_root)

# Issue 2 Fix: 全局异常处理和崩溃日志
CRASH_LOG_DIR = os.path.join(APP_DIR, "crash_log")

def save_crash_log(exc_type, exc_value, exc_traceback):
    """保存崩溃日志到文件"""
    try:
        os.makedirs(CRASH_LOG_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_file = os.path.join(CRASH_LOG_DIR, f"crash_{timestamp}.txt")
        
        with open(crash_file, 'w', encoding='utf-8') as f:
            f.write(f"=== 程序崩溃日志 ===\n")
            f.write(f"时间: {datetime.now().isoformat()}\n")
            f.write(f"异常类型: {exc_type.__name__}\n")
            f.write(f"异常信息: {exc_value}\n\n")
            f.write("=== 完整堆栈 ===\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
        
        print(f"崩溃日志已保存到: {crash_file}")
    except Exception as e:
        print(f"保存崩溃日志失败: {e}")

def global_exception_handler(exc_type, exc_value, exc_traceback):
    """全局异常处理器"""
    # 忽略 KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # 保存崩溃日志
    save_crash_log(exc_type, exc_value, exc_traceback)
    
    # 调用默认处理器
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# 设置全局异常钩子
sys.excepthook = global_exception_handler

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from utils.constants import APP_NAME
from utils.logger import logger


def main():
    """主函数"""
    # 启用高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    
    # 设置默认字体
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)
    
    # 记录启动日志
    logger.info("程序启动", category="system")
    
    # 创建主窗口
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    
    # 运行应用
    exit_code = app.exec_()
    
    # 记录退出日志
    logger.info("程序退出", category="system")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

