"""
文件工具函数模块
"""
import os
import hashlib
import shutil
from datetime import datetime
from typing import Optional, List, Tuple


def get_file_hash(filepath: str, algorithm: str = "md5", chunk_size: int = 8192) -> str:
    """
    计算文件哈希值
    
    Args:
        filepath: 文件路径
        algorithm: 哈希算法 (md5, sha1, sha256)
        chunk_size: 读取块大小
    
    Returns:
        文件哈希值
    """
    hash_func = hashlib.new(algorithm)
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except Exception:
        return ""


def get_file_mtime(filepath: str) -> Optional[datetime]:
    """获取文件修改时间"""
    try:
        timestamp = os.path.getmtime(filepath)
        return datetime.fromtimestamp(timestamp)
    except Exception:
        return None


def get_file_size(filepath: str) -> int:
    """获取文件大小 (字节)"""
    try:
        return os.path.getsize(filepath)
    except Exception:
        return 0


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 字节数
    
    Returns:
        格式化的大小字符串 (如 "1.5 GB")
    """
    if size_bytes < 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def safe_copy_file(src: str, dst: str, buffer_size: int = 1024 * 1024) -> Tuple[bool, str]:
    """
    安全复制文件
    
    Args:
        src: 源文件路径
        dst: 目标文件路径
        buffer_size: 缓冲区大小
    
    Returns:
        (成功标志, 错误信息)
    """
    try:
        # 确保目标目录存在
        dst_dir = os.path.dirname(dst)
        if dst_dir and not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        
        # 复制文件
        shutil.copy2(src, dst)
        return True, ""
    except Exception as e:
        return False, str(e)


def safe_delete_file(filepath: str) -> Tuple[bool, str]:
    """
    安全删除文件
    
    Args:
        filepath: 文件路径
    
    Returns:
        (成功标志, 错误信息)
    """
    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
        elif os.path.isdir(filepath):
            shutil.rmtree(filepath)
        return True, ""
    except Exception as e:
        return False, str(e)


def safe_move_file(src: str, dst: str) -> Tuple[bool, str]:
    """
    安全移动文件
    
    Args:
        src: 源路径
        dst: 目标路径
    
    Returns:
        (成功标志, 错误信息)
    """
    try:
        dst_dir = os.path.dirname(dst)
        if dst_dir and not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
        shutil.move(src, dst)
        return True, ""
    except Exception as e:
        return False, str(e)


def compare_files(file1: str, file2: str, method: str = "mtime") -> int:
    """
    比较两个文件
    
    Args:
        file1: 文件1路径
        file2: 文件2路径
        method: 比较方法 (mtime, hash, size)
    
    Returns:
        -1: file1更旧/更小
         0: 相同
         1: file1更新/更大
    """
    if method == "hash":
        hash1 = get_file_hash(file1)
        hash2 = get_file_hash(file2)
        if hash1 == hash2:
            return 0
        # 哈希不同时按修改时间判断
        method = "mtime"
    
    if method == "mtime":
        mtime1 = get_file_mtime(file1)
        mtime2 = get_file_mtime(file2)
        if mtime1 is None or mtime2 is None:
            return 0
        if mtime1 < mtime2:
            return -1
        elif mtime1 > mtime2:
            return 1
        return 0
    
    if method == "size":
        size1 = get_file_size(file1)
        size2 = get_file_size(file2)
        if size1 < size2:
            return -1
        elif size1 > size2:
            return 1
        return 0
    
    return 0


def get_relative_path(filepath: str, base_path: str) -> str:
    """获取相对路径"""
    try:
        return os.path.relpath(filepath, base_path)
    except ValueError:
        return filepath


def is_hidden_file(filepath: str) -> bool:
    """检查是否是隐藏文件"""
    name = os.path.basename(filepath)
    if name.startswith('.'):
        return True
    # Windows隐藏属性
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(filepath)
        return attrs != -1 and attrs & 2
    except Exception:
        return False


def match_file_patterns(filepath: str, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
    """
    检查文件是否匹配过滤模式
    
    Args:
        filepath: 文件路径
        include_patterns: 包含模式列表 (如 ["*.txt", "*.doc"])
        exclude_patterns: 排除模式列表
    
    Returns:
        True表示应该处理该文件
    """
    import fnmatch
    
    filename = os.path.basename(filepath)
    
    # 检查排除模式
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filepath, pattern):
            return False
    
    # 如果没有包含模式,默认包含所有
    if not include_patterns:
        return True
    
    # 检查包含模式
    for pattern in include_patterns:
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(filepath, pattern):
            return True
    
    return False


def generate_versioned_filename(filepath: str, version: int = None) -> str:
    """
    生成带版本号的文件名
    
    Args:
        filepath: 原文件路径
        version: 版本号 (None则自动查找)
    
    Returns:
        带版本号的文件路径
    """
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    
    if version is None:
        # 自动查找下一个可用版本号
        version = 1
        while True:
            new_path = os.path.join(directory, f"{name}_v{version}{ext}")
            if not os.path.exists(new_path):
                break
            version += 1
    
    return os.path.join(directory, f"{name}_v{version}{ext}")


def scan_directory(directory: str, recursive: bool = True) -> List[str]:
    """
    扫描目录获取所有文件
    
    Args:
        directory: 目录路径
        recursive: 是否递归扫描
    
    Returns:
        文件路径列表
    """
    files = []
    try:
        if recursive:
            for root, dirs, filenames in os.walk(directory):
                for filename in filenames:
                    files.append(os.path.join(root, filename))
        else:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    files.append(item_path)
    except Exception:
        pass
    return files
