# 用来存储所有配置的类

import os
import dotenv

dotenv.load_dotenv()


class DatabaseConfig:
    """数据库配置"""
    DB_URI = f"postgresql://{os.getenv('SQL_USER')}:{os.getenv('SQL_PASSWORD')}@{os.getenv('SQL_HOST')}:{os.getenv('SQL_PORT')}/{os.getenv('SQL_DATABASE')}"
    MIN_SIZE = 5
    MAX_SIZE = 10


class ConfigLogFile:
    """配置日志文件"""
    LOG_FILE_PATH = "logfile/app.log"
    if not os.path.exists(os.path.dirname(LOG_FILE_PATH)):
        os.makedirs(os.path.dirname(LOG_FILE_PATH))
    MAX_BYTES = 5*1024*1024
    BACKUP_COUNT = 3


class ConfigRedis:
    """配置Redis"""
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = os.getenv("REDIS_PORT", 6379)
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
    REDIS_DB = os.getenv("REDIS_DB", 0)
    SESSION_TIMEOUT = os.getenv("SESSION_TIMEOUT", 300)  # 会话过期时间
    TTL = os.getenv("REDIS_TTL", 3600)  # 会话超时时间


class ConfigAPI:
    """配置API"""
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = os.getenv("PORT", 8001)

class FilePath:
    """配置文件路径"""
    SYSTEM_MESSAGE_PATH = "markdown/system_massage.md"