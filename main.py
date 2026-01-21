"""
智能文件自动备份系统
主程序入口
"""
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

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
