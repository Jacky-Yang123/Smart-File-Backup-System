"""
定时调度器模块
"""
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
import schedule

from utils.logger import logger


@dataclass
class ScheduledJob:
    """计划任务"""
    job_id: str
    task_id: str
    schedule_type: str  # interval, daily, weekly, once
    schedule_value: str  # 具体时间或间隔
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True


class Scheduler:
    """
    定时调度器
    管理定时备份任务
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._jobs: Dict[str, ScheduledJob] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def add_job(self, task_id: str, schedule_type: str, schedule_value: str,
                callback: Callable, job_id: str = None) -> str:
        """
        添加计划任务
        
        Args:
            task_id: 关联的备份任务ID
            schedule_type: 调度类型 (interval, daily, weekly, once)
            schedule_value: 调度值 (如 "30m", "09:00", "monday 09:00")
            callback: 执行回调
            job_id: 任务ID (可选)
        
        Returns:
            任务ID
        """
        with self._lock:
            if job_id is None:
                job_id = f"job_{task_id}_{len(self._jobs)}"
            
            job = ScheduledJob(
                job_id=job_id,
                task_id=task_id,
                schedule_type=schedule_type,
                schedule_value=schedule_value
            )
            
            self._jobs[job_id] = job
            self._callbacks[job_id] = callback
            
            # 配置schedule
            self._configure_job(job)
            
            logger.info(f"添加计划任务: {job_id} ({schedule_type}: {schedule_value})",
                       category="scheduler")
            return job_id
    
    def _configure_job(self, job: ScheduledJob):
        """配置schedule任务"""
        def job_wrapper():
            job.last_run = datetime.now()
            if job_id in self._callbacks:
                try:
                    self._callbacks[job.job_id]()
                except Exception as e:
                    logger.error(f"执行计划任务失败: {e}", category="scheduler")
        
        job_id = job.job_id
        
        if job.schedule_type == "interval":
            # 解析间隔 (如 "30m", "2h", "1d")
            value = job.schedule_value.lower()
            if value.endswith('m'):
                minutes = int(value[:-1])
                schedule.every(minutes).minutes.do(job_wrapper).tag(job_id)
            elif value.endswith('h'):
                hours = int(value[:-1])
                schedule.every(hours).hours.do(job_wrapper).tag(job_id)
            elif value.endswith('d'):
                days = int(value[:-1])
                schedule.every(days).days.do(job_wrapper).tag(job_id)
        
        elif job.schedule_type == "daily":
            # 每天固定时间 (如 "09:00")
            schedule.every().day.at(job.schedule_value).do(job_wrapper).tag(job_id)
        
        elif job.schedule_type == "weekly":
            # 每周固定时间 (如 "monday 09:00")
            parts = job.schedule_value.lower().split()
            day = parts[0]
            time_str = parts[1] if len(parts) > 1 else "00:00"
            
            day_map = {
                "monday": schedule.every().monday,
                "tuesday": schedule.every().tuesday,
                "wednesday": schedule.every().wednesday,
                "thursday": schedule.every().thursday,
                "friday": schedule.every().friday,
                "saturday": schedule.every().saturday,
                "sunday": schedule.every().sunday
            }
            
            if day in day_map:
                day_map[day].at(time_str).do(job_wrapper).tag(job_id)
    
    def remove_job(self, job_id: str):
        """移除计划任务"""
        with self._lock:
            if job_id in self._jobs:
                schedule.clear(job_id)
                del self._jobs[job_id]
                if job_id in self._callbacks:
                    del self._callbacks[job_id]
                logger.info(f"移除计划任务: {job_id}", category="scheduler")
    
    def remove_task_jobs(self, task_id: str):
        """移除某个备份任务的所有计划"""
        with self._lock:
            job_ids = [j.job_id for j in self._jobs.values() if j.task_id == task_id]
            for job_id in job_ids:
                self.remove_job(job_id)
    
    def enable_job(self, job_id: str):
        """启用计划任务"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].enabled = True
    
    def disable_job(self, job_id: str):
        """禁用计划任务"""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].enabled = False
    
    def get_jobs(self, task_id: str = None) -> List[ScheduledJob]:
        """获取计划任务列表"""
        if task_id:
            return [j for j in self._jobs.values() if j.task_id == task_id]
        return list(self._jobs.values())
    
    def _run_scheduler(self):
        """调度器主循环"""
        while self._running:
            schedule.run_pending()
            time.sleep(1)
    
    def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._thread.start()
        logger.info("调度器已启动", category="scheduler")
    
    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("调度器已停止", category="scheduler")
    
    @property
    def is_running(self) -> bool:
        return self._running


# 全局调度器实例
scheduler = Scheduler()
