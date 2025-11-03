# utils/logger_manager.py
import logging
from concurrent_log_handler import ConcurrentRotatingFileHandler
from configs.configuration import ConfigLogFile


class LoggerManager:
    """统一的日志管理器"""
    
    _loggers = {}  # 存储已创建的logger实例
    _handler = None  # 共享的handler实例
    
    @classmethod
    def _get_handler(cls):
        """获取共享的日志处理器"""
        if cls._handler is None:
            cls._handler = ConcurrentRotatingFileHandler(
                ConfigLogFile.LOG_FILE_PATH,  # 日志文件路径
                maxBytes=ConfigLogFile.MAX_BYTES,  # 日志文件最大大小
                backupCount=ConfigLogFile.BACKUP_COUNT  # 日志文件备份数量
            )
            # 日志级别设置，DEBUG，INFO，WARNING，ERROR，CRITICAL
            cls._handler.setLevel(logging.DEBUG)
            # 设置日志格式
            cls._handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ))
        return cls._handler
    
    @classmethod
    def get_logger(cls, name: str = None, level: int = logging.DEBUG):
        """
        获取配置好的logger实例
        
        Args:
            name: logger名称，默认使用调用模块的__name__
            level: 日志级别，默认DEBUG,可选参数：INFO,WARNING,ERROR,CRITICAL
            
        Returns:
            配置好的logger实例
        """
        if name is None:
            # 自动获取调用模块的名称
            import inspect
            frame = inspect.currentframe().f_back
            name = frame.f_globals.get('__name__', 'unknown')
        
        # 如果logger已存在，直接返回
        if name in cls._loggers:
            return cls._loggers[name]
        
        # 创建新的logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers = []  # 清空默认处理器
        logger.addHandler(cls._get_handler())
        
        # 缓存logger实例
        cls._loggers[name] = logger
        
        return logger
    
    @classmethod
    def set_level(cls, level: int):
        """设置所有logger的日志级别"""
        for logger in cls._loggers.values():
            logger.setLevel(level)
        if cls._handler:
            cls._handler.setLevel(level)