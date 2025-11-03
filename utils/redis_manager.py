import logging
import uuid
import json

from concurrent_log_handler import ConcurrentRotatingFileHandler
import redis.asyncio as redis
from typing import Dict, Any, Optional, List
from datetime import timedelta
from pydantic import BaseModel

from configs.configuration import ConfigLogFile, ConfigRedis
from utils.data_models import AgentResponse


# 设置日志
logger = logging.getLogger(__name__)
# 日志级别设置，DEBUG，INFO，WARNING，ERROR，CRITICAL
logger.setLevel(logging.DEBUG)
logger.handlers = []  # 清空默认处理器
handler = ConcurrentRotatingFileHandler(
    ConfigLogFile.LOG_FILE_PATH,  # 日志文件路径
    maxBytes=ConfigLogFile.MAX_BYTES,  # 日志文件最大大小
    backupCount=ConfigLogFile.BACKUP_COUNT  # 日志文件备份数量
)
# 设置处理级别为DEBUG
handler.setLevel(logging.DEBUG)
# 设置日志格式
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
# 添加处理器到日志
logger.addHandler(handler)


class RedisSessionManager:
    """
    定义Redis会话管理器
    """

    def __init__(self, redis_host: str, redis_port: int, redis_db: int, redis_password: str, session_timeout: int):
        """
        初始化Redis会话管理器
        Args:
            redis_host: Redis主机地址
            redis_port: Redis端口
            redis_db: Redis数据库索引
            session_timeout: 会话超时时间
        """
        # 创建Redis客户端连接
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True
        )
        # 设置默认会话过期时间（秒）
        self.session_timeout = session_timeout

    async def close(self):
        """
        关闭Redis连接
        """
        await self.redis_client.close()

    async def create_session(
            self,
            user_id: str,
            session_id: Optional[str] = None,
            status: str = "active",
            last_query: Optional[str] = None,
            last_response: Optional['AgentResponse'] = None,
            last_updated: Optional[float] = None,
            ttl: Optional[int] = None
    ) -> str:
        """
        创建会话,匹配指定数据结构，保存每个用户的智能体实例和状态。
        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识
            status: 会话状态
            last_query: 最后一次查询
            last_updated: 最后一次更新时间
            last_response: 最后一次响应
            ttl: 会话超时时间
        Returns:
            session_id: 会话唯一标识
        """
        # 如果未提供 session_id，生成新的 UUID
        if session_id is None:
            session_id = str(uuid.uuid4())
        # 如果未提供最后更新时间，设置为 0 秒
        if last_updated is None:
            last_updated = str(timedelta(seconds=0))
        # 使用提供的 TTL 或默认的 session_timeout
        effective_ttl = ttl if ttl is not None else self.session_timeout

        # 构造会话数据结构
        session_data = {
            "session_id": session_id,
            "status": status,
            "last_response": last_response.model_dump() if isinstance(last_response, BaseModel) else last_response,
            "last_query": last_query,
            "last_updated": last_updated
        }

        # 将会话数据存储到 Redis，使用 JSON 序列化，并设置过期时间
        await self.redis_client.set(
            f"session:{user_id}:{session_id}",
            json.dumps(session_data, default=lambda o: o.__dict__ if not hasattr(
                o, 'model_dump') else o.model_dump()),
            ex=effective_ttl
        )
        # 将 session_id 添加到用户的会话列表中
        await self.redis_client.sadd(f"user_sessions:{user_id}", session_id)
        # 返回新创建的 session_id
        return session_id

    async def update_session(
            self,
            user_id: str,
            session_id: str,
            status: Optional[str] = None,
            last_query: Optional[str] = None,
            last_response: Optional['AgentResponse'] = None,
            last_updated: Optional[float] = None,
            ttl: Optional[int] = None) -> bool:
        """
        更新会话
        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识
            status: 会话状态
            last_query: 最后一次查询
            last_updated: 最后一次更新时间
            last_response: 最后一次响应
            ttl: 会话超时时间
        Returns:
            bool: 是否更新成功
        """
        # 检查会话是否存在
        if await self.redis_client.exists(f"session:{user_id}:{session_id}"):
            # 获取当前会话数据
            current_data = await self.get_session(user_id, session_id)
            if not current_data:
                return False
            # 更新提供的字段
            if status is not None:
                current_data["status"] = status
            if last_response is not None:
                if isinstance(last_response, BaseModel):
                    current_data["last_response"] = last_response.model_dump()
                else:
                    current_data["last_response"] = last_response
            if last_query is not None:
                current_data["last_query"] = last_query
            if last_updated is not None:
                current_data["last_updated"] = last_updated
            # 使用提供的 TTL 或默认的 session_timeout
            effective_ttl = ttl if ttl is not None else self.session_timeout
            # 将更新后的数据重新存储到 Redis，并设置新的过期时间
            await self.redis_client.set(
                f"session:{user_id}:{session_id}",
                json.dumps(current_data, default=lambda o: o.__dict__ if not hasattr(
                    o, 'model_dump') else o.model_dump()),
                ex=effective_ttl
            )
            # 更新成功返回 True
            return True
        # 会话不存在返回 False
        return False

    async def get_session(self, user_id: str, session_id: str) -> Optional[dict]:
        """
        获取指定用户当前会话ID的状态数据
        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识
        Returns:
            Optional[dict]: 会话数据
        """
        # 从 Redis 获取会话数据
        session_data = await self.redis_client.get(f"session:{user_id}:{session_id}")
        # 如果会话不存在，返回 None
        if not session_data:
            return None
        # 解析 JSON 数据
        session = json.loads(session_data)
        # 处理 last_response 字段，尝试转换为 AgentResponse 对象
        if session and "last_response" in session:
            if session["last_response"] is not None:
                try:
                    session["last_response"] = AgentResponse(
                        **session["last_response"])
                except Exception as e:
                    # 记录转换失败的错误日志
                    logger.error(f"转换 last_response 失败: {e}")
                    session["last_response"] = None
        # 返回会话数据
        return session

    async def get_user_active_session_id(self, user_id: str) -> str | None:
        """
        获取指定用户当前激活的会话ID
        Args:
            user_id: 用户唯一标识
        Returns:
            str | None: 当前激活的会话ID
        """
        # 在查询前清理指定用户的无效会话
        await self.cleanup_user_sessions(user_id)
        # 获取用户的所有 session_id
        session_ids = await self.redis_client.smembers(f"user_sessions:{user_id}")
        # 初始化最新会话信息
        latest_session_id = None
        latest_timestamp = -1  # 使用负值确保任何有效时间戳都更大
        # 遍历每个 session_id，获取会话数据
        for session_id in session_ids:
            session = await self.get_session(user_id, session_id)
            if session:
                last_updated = session.get('last_updated')
                # 过滤掉 last_updated 为 "0:00:00" 的记录
                if isinstance(last_updated, str) and last_updated == "0:00:00":
                    continue
                # 确保 last_updated 是数字（时间戳）
                if isinstance(last_updated, (int, float)) and last_updated > latest_timestamp:
                    latest_timestamp = last_updated
                    latest_session_id = session_id
        # 返回最新会话ID，如果没有有效会话则返回 None
        return latest_session_id

    async def get_all_session_ids(self, user_id: str) -> List[str]:
        """
        获取指定用户下的所有 session_id
        Args:
            user_id: 用户唯一标识
        Returns:
            List[str]: 所有 session_id
        """
        # 在查询前清理指定用户的无效会话，确保返回的 session_id 都是有效的
        await self.cleanup_user_sessions(user_id)
        # 从 Redis 获取用户的所有 session_id
        session_ids = await self.redis_client.smembers(f"user_sessions:{user_id}")
        # 将集合转换为列表并返回
        return list(session_ids)

    async def get_all_users_session_ids(self) -> Dict[str, List[str]]:
        """
        获取系统内所有用户下的所有 session_id
        Returns:
            Dict[str, List[str]]: 所有用户及其 session_id
        """
        # 清理所有用户的无效会话
        await self.cleanup_all_sessions()
        # 初始化结果字典
        result = {}
        # 遍历所有 user_sessions:* 键
        async for key in self.redis_client.scan_iter("user_sessions:*"):
            # 提取用户 ID
            user_id = key.split(":", 1)[1]
            # 获取该用户的所有 session_id
            session_ids = await self.redis_client.smembers(f"user_sessions:{user_id}")
            # 如果集合非空，将用户 ID 和 session_id 列表存入结果字典
            if session_ids:
                result[user_id] = list(session_ids)
        # 返回所有用户及其 session_id
        return result

    async def get_all_user_sessions(self, user_id: str) -> List[dict]:
        """
        获取指定用户ID的所有会话状态详情数据
        Args:
            user_id: 用户唯一标识
        Returns:
            List[dict]: 所有会话状态详情数据
        """
        # 初始化会话列表
        sessions = []
        # 获取用户的所有 session_id
        session_ids = await self.redis_client.smembers(f"user_sessions:{user_id}")
        # 遍历每个 session_id，获取会话数据
        for session_id in session_ids:
            session = await self.get_session(user_id, session_id)
            if session:
                sessions.append(session)
        # 返回所有会话数据
        return sessions

    async def user_id_exists(self, user_id: str) -> bool:
        """
        检查指定用户ID是否在 Redis 中
        Args:
            user_id: 用户唯一标识
        Returns:
            bool: 用户ID是否在 Redis 中
        """
        # 在查询前清理指定用户的无效会话
        await self.cleanup_user_sessions(user_id)
        # 检查是否存在 user_sessions:{user_id} 键
        return (await self.redis_client.exists(f"user_sessions:{user_id}")) > 0

    async def session_id_exists(self, user_id: str, session_id: str) -> bool:
        """
        检查指定用户ID的特定 session_id 是否存在
        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识
        Returns:
            bool: 会话ID是否在 Redis 中
        """
        # 在查询前清理指定用户的无效会话
        await self.cleanup_user_sessions(user_id)
        # 检查指定用户的特定会话是否存在
        return (await self.redis_client.exists(f"session:{user_id}:{session_id}")) > 0

    async def get_session_count(self) -> int:
        """
        获取会话数量
        Returns:
            int: 会话数量
        """
        # 清理所有用户的无效会话
        await self.cleanup_all_sessions()
        # 初始化计数器
        count = 0
        # 遍历所有 session:* 键
        async for _ in self.redis_client.scan_iter("session:*"):
            count += 1
        # 返回会话总数
        return count

    async def cleanup_user_sessions(self, user_id: str) -> None:
        """
        清理指定用户的无效会话
        Args:
            user_id: 用户唯一标识
        """
        # 获取用户会话集合中的所有 session_id
        session_ids = await self.redis_client.smembers(f"user_sessions:{user_id}")
        # 遍历每个 session_id，检查对应的会话键是否存在
        for session_id in session_ids:
            if not await self.redis_client.exists(f"session:{user_id}:{session_id}"):
                # 如果会话键已过期或不存在，从集合中移除 session_id
                await self.redis_client.srem(f"user_sessions:{user_id}", session_id)
                logger.info(
                    f"已移除过期 session_id {session_id} for user {user_id}")
        # 如果集合为空，删除集合
        if not await self.redis_client.scard(f"user_sessions:{user_id}"):
            await self.redis_client.delete(f"user_sessions:{user_id}")
            logger.info(f"已删除空 user_sessions 集合 for user {user_id}")

    async def cleanup_all_sessions(self) -> None:
        """
        清理所有用户的无效会话
        """
        # 遍历所有 user_sessions:* 键
        async for key in self.redis_client.scan_iter("user_sessions:*"):
            # 提取用户 ID
            user_id = key.split(":", 1)[1]
            # 清理用户无效会话
            await self.cleanup_user_sessions(user_id)

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """
        删除指定用户的特定会话
        Args:
            user_id: 用户唯一标识
            session_id: 会话唯一标识
        Returns:
            bool: 是否删除成功
        """
        # 从用户会话列表中移除 session_id
        await self.redis_client.srem(f"user_sessions:{user_id}", session_id)
        # 删除会话数据并返回是否成功
        return (await self.redis_client.delete(f"session:{user_id}:{session_id}")) > 0


def get_session_manager() -> RedisSessionManager:
    """
    获取 Redis 会话管理器
    Returns:
        RedisSessionManager: Redis 会话管理器
    """
    session_manager = RedisSessionManager(
        redis_host=ConfigRedis.REDIS_HOST,
        redis_port=ConfigRedis.REDIS_PORT,
        redis_password=ConfigRedis.REDIS_PASSWORD,
        redis_db=ConfigRedis.REDIS_DB,
        session_timeout=ConfigRedis.SESSION_TIMEOUT
    )
    return session_manager


if __name__ == "__main__":
    session_manager = get_session_manager()
    print(session_manager)