"""
文件扫描器模块
提供可追踪、可配置的文件扫描功能
"""
import os
import fnmatch
from typing import List, Optional
from utils.logger import logger

class Scanner:
    def __init__(self, root_path: str, include_patterns: List[str] = None, exclude_patterns: List[str] = None):
        """
        初始化扫描器
        
        Args:
            root_path: 扫描根目录
            include_patterns: 包含模式列表
            exclude_patterns: 排除模式列表
        """
        self.root_path = os.path.abspath(root_path)
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        
    def scan(self) -> List[str]:
        """
        执行扫描
        
        Returns:
            只有符合条件的文件绝对路径列表
        """
        files = []
        if not os.path.exists(self.root_path):
            logger.warning(f"[Scanner]Root path does not exist: {self.root_path}", category="scan")
            return files
            
        logger.debug(f"[Scanner] Start scanning: {self.root_path}", category="scan")
        logger.debug(f"[Scanner] Includes: {self.include_patterns}", category="scan")
        logger.debug(f"[Scanner] Excludes: {self.exclude_patterns}", category="scan")
        
        try:
            for root, dirs, filenames in os.walk(self.root_path):
                # 1. 目录过滤 (修剪遍历树)
                i = 0
                while i < len(dirs):
                    d = dirs[i]
                    d_path = os.path.join(root, d)
                    
                    if self._should_exclude(d, d_path, is_dir=True):
                        # logger.debug(f"[Scanner] Pruning directory: {d_path}", category="scan")
                        del dirs[i]
                    else:
                        i += 1
                
                # 2. 文件过滤
                for filename in filenames:
                    f_path = os.path.join(root, filename)
                    if self._should_include(filename, f_path):
                        files.append(f_path)
                    # else:
                        # logger.debug(f"[Scanner] Skipping file: {f_path}", category="scan")
                        
        except Exception as e:
            logger.error(f"[Scanner] Scan failed: {e}", category="scan")
            
        logger.debug(f"[Scanner] Scan finished. Found {len(files)} files.", category="scan")
        return files

    def _should_exclude(self, name: str, path: str, is_dir: bool = False) -> bool:
        """检查是否应该排除"""
        for pattern in self.exclude_patterns:
            # 1. 匹配名称 (例如 "*.git")
            if fnmatch.fnmatch(name, pattern):
                return True
                
            # 2. 匹配路径 (例如 "C:\Backup\Target")
            # 注意: fnmatch 对路径分隔符敏感，需标准化
            # 如果 pattern 包含分隔符，或者是绝对路径，则尝试匹配完整路径
            if os.sep in pattern or (os.name == 'nt' and ':' in pattern):
                # 归一化路径分隔符
                norm_pattern = os.path.normpath(pattern)
                norm_path = os.path.normpath(path)
                
                # 如果是目录，我们要确保不仅仅是前缀匹配，而是完全匹配或者是子目录
                if is_dir:
                    # 检查 path 是否是 pattern 的子目录或者就是 pattern
                    # 例如 pattern="C:/Backup", path="C:/Backup/Sub" -> 应该排除
                    # 但os.walk是从上到下的，所以当我们遇到 "C:/Backup" 时排除即可
                    if norm_path == norm_pattern:
                        return True
                    # 如果 pattern 是 "C:/Backup"，而我们正在扫描 "C:/" 下的 "Backup" 目录
                    if norm_path.startswith(norm_pattern + os.sep):
                         return True
                
                if fnmatch.fnmatch(norm_path, norm_pattern):
                    return True
                    
        return False

    def _should_include(self, name: str, path: str) -> bool:
        """检查是否应该包含"""
        # 首先检查显式的排除
        if self._should_exclude(name, path, is_dir=False):
            return False
            
        # 如果没有包含模式，默认包含所有
        if not self.include_patterns:
            return True
            
        # 检查包含模式
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(path, pattern):
                return True
                
        return False
