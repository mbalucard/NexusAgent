import logging
import uuid
import asyncio

from concurrent_log_handler import ConcurrentRotatingFileHandler
from typing import List, Any, Optional, Dict
from fastapi import HTTPException

from langchain_core.messages.utils import trim_messages, RemoveMessage
from langchain.agents.middleware import before_model
from langchain.agents import AgentState
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from configs.configuration import ConfigLogFile


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

@before_model
def trimmed_messages_hook(state: AgentState, runtime: Runtime):
    """
    修剪聊天历史以满足 token 数量或消息数量的限制
    Args:
        state: 历史消息列表
    Returns:
        state: 修剪后的历史消息列表
    """
    trimmed_messages = trim_messages(
        messages=state["messages"],
        max_tokens=20,
        strategy="last",
        token_counter=len,
        start_on="human",
        # include_system=True,  # 包含系统消息
        allow_partial=False
    )
    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *trimmed_messages
        ]
    }


def parse_messages(messages: List[Any]) -> None:
    """
    解析消息列表，打印 HumanMessage、AIMessage 和 ToolMessage 的详细信息

    Args:
        messages: 包含消息的列表，每个消息是一个对象
    """
    print("=== 消息解析结果 ===")
    for idx, msg in enumerate(messages, 1):
        print(f"\n消息 {idx}:")
        # 获取消息类型
        msg_type = msg.__class__.__name__
        print(f"类型: {msg_type}")
        # 提取消息内容
        content = getattr(msg, 'content', '')
        print(f"内容: {content if content else '<空>'}")
        # 处理附加信息
        additional_kwargs = getattr(msg, 'additional_kwargs', {})
        if additional_kwargs:
            print("附加信息:")
            for key, value in additional_kwargs.items():
                if key == 'tool_calls' and value:
                    print("  工具调用:")
                    for tool_call in value:
                        print(f"    - ID: {tool_call['id']}")
                        print(f"      函数: {tool_call['function']['name']}")
                        print(
                            f"      参数: {tool_call['function']['arguments']}")
                else:
                    print(f"  {key}: {value}")
        # 处理 ToolMessage 特有字段
        if msg_type == 'ToolMessage':
            tool_name = getattr(msg, 'name', '')
            tool_call_id = getattr(msg, 'tool_call_id', '')
            print(f"工具名称: {tool_name}")
            print(f"工具调用 ID: {tool_call_id}")
        # 处理 AIMessage 的工具调用和元数据
        if msg_type == 'AIMessage':
            tool_calls = getattr(msg, 'tool_calls', [])
            if tool_calls:
                print("工具调用:")
                for tool_call in tool_calls:
                    print(f"  - 名称: {tool_call['name']}")
                    print(f"    参数: {tool_call['args']}")
                    print(f"    ID: {tool_call['id']}")
            # 提取元数据
            metadata = getattr(msg, 'response_metadata', {})
            if metadata:
                print("元数据:")
                token_usage = metadata.get('token_usage', {})
                print(f"  令牌使用: {token_usage}")
                print(f"  模型名称: {metadata.get('model_name', '未知')}")
                print(f"  完成原因: {metadata.get('finish_reason', '未知')}")
        # 打印消息 ID
        msg_id = getattr(msg, 'id', '未知')
        print(f"消息 ID: {msg_id}")
        print("-" * 50)


async def async_parse_messages(messages: List[Any]) -> None:
    """
    异步解析消息列表，打印 HumanMessage、AIMessage 和 ToolMessage 的详细信息
    Args:
        messages: 包含消息的列表，每个消息是一个对象
    """
    await asyncio.to_thread(parse_messages, messages)


def save_graph_visualization(graph, filename: str = "graph.png") -> None:
    """
    保存状态图的可视化表示

    Args:
        graph: 状态图实例
        filename: 保存文件路径
    """
    try:
        with open(filename, "wb") as f:
            f.write(graph.get_graph().draw_mermaid_png())
        print(f"Graph visualization saved as {filename}")
    except IOError as e:
        print(f"Failed to save graph visualization: {e}")