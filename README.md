# 智能文件备份系统 (Smart File Backup System)

[English](#english) | [中文](#chinese)

<a name="english"></a>
## English

### 📝 Description
**Smart File Backup System** is a powerful, real-time file synchronization and backup tool built with Python and PyQt5. It supports one-way and two-way synchronization, intelligent conflict resolution, and hash-based integrity checks to ensures your data is safe and consistent across multiple locations.

### ✨ Key Features
- **Real-time Monitoring**: Automatically detects file changes (creation, modification, deletion, renaming) and syncs them instantly.
- **Multiple Sync Modes**:
    - **One-way Sync**: Source directory to multiple target directories.
    - **Two-way Sync**: Keeps both source and target directories in parity.
- **Intelligent Conflict Resolution**:
    - **Newest Wins**: Uses file modification time.
    - **Source/Target Wins**: Forced priority.
    - **Keep Both**: Renames conflicting files to preserve both versions.
    - **Hash Comparison**: (Optional) Uses MD5/SHA hashes for precise change detection, supporting 3-way conflict detection.
- **Advanced Filtering**: Include or exclude files based on patterns and common file groups (Documents, Images, Code, etc.).
- **User-Friendly UI**:
    - Dashboard with real-time stats (synced files, errors).
    - Detailed activity logs and file modification history.
    - System tray support for background operation.
    - Dark mode aesthetics with a premium look.
- **Task Scheduling**: Set automated backup intervals.

### 🛠 Tech Stack
- **Language**: Python 3.x
- **GUI Framework**: PyQt5
- **File System Monitoring**: Watchdog
- **Task Scheduling**: Schedule
- **Data Storage**: JSON / SQLite

### 🚀 Quick Start
1. **Installation**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Run**:
   ```bash
   python main.py
   ```

---

<a name="chinese"></a>
## 中文

### 📝 项目简介
**智能文件备份系统** 是一款基于 Python 和 PyQt5 开发的高性能实时文件同步与备份工具。它支持单向和双向同步、智能冲突解析以及基于哈希的文件校验，确保您的数据在不同位置之间保持安全和一致。

### ✨ 核心功能
- **实时监控**：自动检测文件变化（创建、修改、删除、重命名）并立即同步。
- **多种同步模式**：
    - **单向同步**：源目录同步至一个或多个目标目录。
    - **双向同步**：保持源目录与目标目录内容完全一致。
- **智能冲突处理**：
    - **最新优先**：基于文件修改时间判断。
    - **源/目标优先**：强制指定某一侧为准。
    - **保留双方**：自动重命名冲突文件，同时保留两个版本。
    - **哈希校验**：（可选）使用 MD5/SHA 哈希进行精准变更检测，支持三方冲突检测。
- **高级过滤规则**：支持通过通配符包含或排除特定文件，内置常用文件组（文档、图片、代码等）快速配置。
- **优雅的 UI 界面**：
    - 仪表盘实时显示统计数据（同步总数、错误数）。
    - 详尽的活动日志与文件修改历史记录。
    - 支持系统托盘，可后台静默运行。
    - 现代感十足的深色系高级审美设计。
- **任务调度**：支持设置定时备份计划。

### 🛠 技术栈
- **编程语言**：Python 3.x
- **GUI 框架**：PyQt5
- **文件监控**：Watchdog
- **任务调度**：Schedule
- **数据存储**：JSON / SQLite

### 🚀 快速开始
1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```
2. **运行程序**：
   ```bash
   python main.py
   ```
