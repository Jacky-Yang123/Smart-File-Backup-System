# 智能文件备份系统 | Smart File Backup System

[中文](#中文) | [English](#english)

---

## 中文

### 简介
这是一个基于 Python 和 PyQt5 开发的高性能智能文件备份系统。它支持实时监控文件变更、单/双向同步以及灵活的冲突处理策略，旨在为用户提供简单而强大的数据保护方案。

### 核心功能
*   **实时监控**: 基于 `watchdog` 的秒级文件变更检测，即刻同步。
*   **灵活同步模式**:
    *   **单向同步**: 源文件夹到目标文件夹的增量备份。
    *   **双向同步**: 自动同步两个文件夹之间的差异，确保两端数据一致。
*   **智能冲突处理**:
    *   支持最新优先、源优先、目标优先、保留双方等多种策略。
*   **高级过滤系统**:
    *   内置常用开发文件夹过滤（.git, node_modules, __pycache__, venv 等）。
    *   支持自定义通配符包含/排除规则。
*   **安全保护**:
    *   **禁止删除模式**: 开启后，程序仅执行新增和修改同步，永不删除任何文件。
    *   **反向删除防护**: 单向备份中可选是否同步删除操作。
*   **任务管理**:
    *   支持多任务并发运行。
    *   支持程序启动时自动开始备份任务。
*   **现代交互**:
    *   深淡色调和谐的 UI 设计。
    *   系统托盘运行，不占用任务栏。
    *   实时状态栏显示，精确到秒的“上次备份时间”。

### 安装与运行
1.  确保已安装 Python 3.8+。
2.  安装依赖库：
    ```bash
    pip install -r requirements.txt
    ```
3.  启动程序：
    ```bash
    python main.py
    ```

---

## English

### Introduction
A high-performance intelligent file backup system built with Python and PyQt5. It features real-time file monitoring, one/two-way synchronization, and flexible conflict resolution strategies, providing a powerful yet simple data protection solution.

### Core Features
*   **Real-time Monitoring**: Second-level file change detection based on `watchdog`, enabling instant synchronization.
*   **Flexible Sync Modes**:
    *   **One-way Sync**: Incremental backup from source to target.
    *   **Two-way Sync**: Automatically syncs differences between two folders to keep both ends consistent.
*   **Intelligent Conflict Resolution**:
    *   Supports multiple strategies: Newest Wins, Source Wins, Target Wins, Keep Both (Versioning), and more.
*   **Advanced Filtering**:
    *   Built-in filters for common development folders (.git, node_modules, __pycache__, venv, etc.).
    *   Supports custom wildcard include/exclude patterns.
*   **Safety & Protection**:
    *   **Disable Delete Mode**: When enabled, the program only syncs additions/modifications and never deletes any files.
    *   **Reverse Delete Control**: Optional deletion synchronization in one-way backups.
*   **Task Management**:
    *   Supports multiple concurrent tasks.
    *   Auto-start tasks on application launch.
*   **Modern Interaction**:
    *   Sleek UI design with harmonious color palettes.
    *   System tray integration (runs in the background).
    *   Real-time status bar showing "Last backup time" accurate to the second.

### Installation & Usage
1.  Ensure Python 3.8+ is installed.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    python main.py
    ```
