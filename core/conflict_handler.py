"""
冲突处理模块
"""
import os
from typing import Tuple, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from utils.constants import ConflictStrategy
from utils.file_utils import (
    get_file_mtime, get_file_hash, get_file_size,
    generate_versioned_filename, format_file_size
)
from utils.logger import logger


@dataclass
class ConflictInfo:
    """冲突信息"""
    source_path: str
    target_path: str
    source_mtime: str
    target_mtime: str
    source_size: str
    target_size: str
    source_hash: str = None
    target_hash: str = None


class ConflictHandler:
    """
    冲突处理器
    处理文件同步时的冲突
    """
    
    def __init__(self, strategy: ConflictStrategy = ConflictStrategy.NEWEST_WINS,
                 user_callback: Callable[[ConflictInfo], ConflictStrategy] = None):
        """
        初始化冲突处理器
        
        Args:
            strategy: 默认冲突处理策略
            user_callback: 用户决策回调 (用于ASK_USER策略)
        """
        self.strategy = strategy
        self.user_callback = user_callback
    
    def get_conflict_info(self, source_path: str, target_path: str) -> ConflictInfo:
        """获取冲突详细信息"""
        source_mtime = get_file_mtime(source_path)
        target_mtime = get_file_mtime(target_path)
        
        return ConflictInfo(
            source_path=source_path,
            target_path=target_path,
            source_mtime=source_mtime.strftime("%Y-%m-%d %H:%M:%S") if source_mtime else "未知",
            target_mtime=target_mtime.strftime("%Y-%m-%d %H:%M:%S") if target_mtime else "未知",
            source_size=format_file_size(get_file_size(source_path)),
            target_size=format_file_size(get_file_size(target_path))
        )
    
    def check_conflict(self, source_path: str, target_path: str) -> bool:
        """
        检查是否存在冲突
        
        Args:
            source_path: 源文件路径
            target_path: 目标文件路径
        
        Returns:
            True表示存在冲突
        """
        if not os.path.exists(target_path):
            return False
        
        if not os.path.exists(source_path):
            return False
        
        # 检查文件是否相同
        source_mtime = get_file_mtime(source_path)
        target_mtime = get_file_mtime(target_path)
        source_size = get_file_size(source_path)
        target_size = get_file_size(target_path)
        
        # 时间和大小都相同,认为无冲突
        if source_mtime == target_mtime and source_size == target_size:
            return False
        
        return True
    
    def resolve(self, source_path: str, target_path: str,
                strategy: ConflictStrategy = None) -> Tuple[str, Optional[str], str]:
        """
        解决冲突
        
        Args:
            source_path: 源文件路径
            target_path: 目标文件路径
            strategy: 使用的策略 (None则使用默认策略)
        
        Returns:
            (动作, 目标路径, 说明)
            动作: "copy", "skip", "keep_both", "ask"
        """
        if strategy is None:
            strategy = self.strategy
        
        # 询问用户
        if strategy == ConflictStrategy.ASK_USER:
            if self.user_callback:
                conflict_info = self.get_conflict_info(source_path, target_path)
                user_strategy = self.user_callback(conflict_info)
                return self.resolve(source_path, target_path, user_strategy)
            else:
                # 没有回调则跳过
                return "skip", None, "需要用户决策但未设置回调"
        
        # 跳过
        if strategy == ConflictStrategy.SKIP:
            return "skip", None, "根据策略跳过冲突文件"
        
        # 源文件优先
        if strategy == ConflictStrategy.SOURCE_WINS:
            return "copy", target_path, "源文件覆盖目标文件"
        
        # 目标文件优先
        if strategy == ConflictStrategy.TARGET_WINS:
            return "skip", None, "保留目标文件"
        
        # 最新时间优先
        if strategy == ConflictStrategy.NEWEST_WINS:
            source_mtime = get_file_mtime(source_path)
            target_mtime = get_file_mtime(target_path)
            
            if source_mtime is None or target_mtime is None:
                return "skip", None, "无法获取文件时间"
            
            if source_mtime > target_mtime:
                return "copy", target_path, f"源文件较新 ({source_mtime} > {target_mtime})"
            else:
                return "skip", None, f"目标文件较新或相同"
        
        # 保留双方
        if strategy == ConflictStrategy.KEEP_BOTH:
            # 生成带版本号的文件名
            versioned_path = generate_versioned_filename(target_path)
            return "keep_both", versioned_path, f"保留双方,源文件保存为 {os.path.basename(versioned_path)}"
        
        return "skip", None, "未知策略"
    
    def set_strategy(self, strategy: ConflictStrategy):
        """设置默认策略"""
        self.strategy = strategy
        logger.info(f"冲突处理策略已更改为: {strategy.value}", category="conflict")
    
    def set_user_callback(self, callback: Callable[[ConflictInfo], ConflictStrategy]):
        """设置用户决策回调"""
        self.user_callback = callback
