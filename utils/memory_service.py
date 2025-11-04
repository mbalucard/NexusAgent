
import uuid

from fastapi import HTTPException
from utils.logger_manager import LoggerManager


# 设置日志
logger = LoggerManager.get_logger(name=__name__)


class MemoryService:
    """
    定义记忆服务类
    """

    def __init__(self, store):
        self.store = store

    async def read_long_term_info(self, user_id: str):
        """
        读取指定用户长期记忆中的内容
        Args:
            user_id: 用户的唯一标识
        Returns:
            Dict[str, Any]: 包含记忆内容和状态的响应
        """
        try:
            # 指定命名空间
            namespace = ("memories", user_id)
            # 搜索记忆内容
            memories = await self.store.asearch(namespace, query="")
            # 处理查询结果
            if memories is None:
                raise HTTPException(
                    status_code=500, detail="查询返回无效结果，可能是存储系统错误。")
            # 提取并拼接记忆内容
            long_term_info = " ".join(
                [d.value["data"] for d in memories if isinstance(
                    d.value, dict) and "data" in d.value]
            ) if memories else ""
            # 记录查询成功的日志
            logger.info(
                f"成功获取用户ID: {user_id} 的长期记忆，内容长度: {len(long_term_info)} 字符")
            # 返回结构化响应
            return {
                "success": True,
                "user_id": user_id,
                "long_term_info": long_term_info,
                "message": "长期记忆获取成功" if long_term_info else "未找到长期记忆内容"
            }
        except Exception as e:
            # 处理其他未预期的错误
            logger.error(f"获取用户ID: {user_id} 的长期记忆时发生意外错误: {str(e)}")
            raise HTTPException(status_code=500, detail=f"获取长期记忆失败: {str(e)}")

    async def write_long_term_info(self, user_id: str, memory_info: str):
        """
        写入指定用户长期记忆内容
        Args:
            user_id: 用户的唯一标识
            memory_info: 要保存的记忆内容
        Returns:
            Dict[str, Any]: 包含成功状态和存储记忆ID的响应
        """
        try:
            # 生成命名空间和唯一记忆ID
            namespace = ("memories", user_id)
            memory_id = str(uuid.uuid4())
            # 存储数据到指定命名空间
            result = await self.store.aput(
                namespace=namespace,
                key=memory_id,
                value={"data": memory_info}
            )
            # 记录存储成功的日志
            logger.info(f"成功为用户ID: {user_id} 存储记忆，记忆ID: {memory_id}")
            # 返回结构化响应
            return {
                "success": True,
                "memory_id": memory_id,
                "message": "记忆存储成功"
            }
        except Exception as e:
            # 处理其他未预期的错误
            logger.error(f"存储用户ID: {user_id} 的记忆时发生意外错误: {str(e)}")
            raise HTTPException(status_code=500, detail=f"存储记忆失败: {str(e)}")


def get_memory_service(state):
    """
    获取记忆服务实例
    Args:
        state: 应用状态实例
    Returns:
        MemoryService: 记忆服务实例
    """
    try:
        return MemoryService(state.store)
    except Exception as e:
        logger.error(f"获取记忆服务实例时发生错误: {str(e)}")
        raise RuntimeError(f"获取记忆服务实例时发生错误: {str(e)}")


if __name__ == "__main__":
    pass
